import re
from dataclasses import dataclass
from typing import Optional

from app.network.models import NetworkAdapterInfo
from app.services.command_runner import CommandRunner


@dataclass
class DiagnosticResult:
    adapter_name: str

    physical_link_ok: bool
    valid_ip: bool
    dhcp_ok: bool
    apipa: bool

    gateway_ok: bool
    internet_ok: bool
    dns_ok: bool

    gateway_latency_ms: Optional[int] = None
    internet_latency_ms: Optional[int] = None
    dns_resolved_ip: Optional[str] = None

    diagnosis: str = ""
    severity: str = "info"


class DiagnosticService:

    # =====================================================
    # PHYSICAL LINK
    # =====================================================

    @staticmethod
    def test_physical_link(
        adapter: NetworkAdapterInfo
    ) -> bool:
        return adapter.is_connected

    # =====================================================
    # IPv4
    # =====================================================

    @staticmethod
    def test_ip(
        adapter: NetworkAdapterInfo
    ):
        return (
            adapter.has_valid_ipv4,
            adapter.is_apipa,
        )

    # =====================================================
    # DHCP
    # =====================================================

    @staticmethod
    def test_dhcp(
        adapter: NetworkAdapterInfo
    ) -> bool:
        """
        DHCP açıksa:
            - geçerli IPv4
            - DHCP server

        kontrol edilir.

        Statik IP kullanılıyorsa DHCP arızası
        sayılmaz.
        """

        if not adapter.dhcp_enabled:
            return adapter.has_valid_ipv4

        return bool(
            adapter.has_valid_ipv4
            and adapter.dhcp_server
        )

    # =====================================================
    # GATEWAY
    # =====================================================

    @staticmethod
    def test_gateway(
        adapter: NetworkAdapterInfo
    ):
        """
        Gateway ping'i seçili adaptörün IPv4
        adresinden gönderilir.

        Böylece Wi-Fi / Ethernet karışması
        engellenir.
        """

        if not adapter.is_connected:
            return False, None

        if not adapter.has_valid_ipv4:
            return False, None

        if not adapter.gateway:
            return False, None

        return DiagnosticService._ping(
            host=adapter.gateway,
            source_ip=adapter.ipv4,
        )

    # =====================================================
    # INTERNET
    # =====================================================

    @staticmethod
    def test_internet(
        adapter: NetworkAdapterInfo
    ):
        """
        Internet testi seçili adaptörün IPv4
        adresine bind edilir.

        Örnek:

        Ethernet:
            192.168.2.50

        Wi-Fi:
            192.168.10.181

        Ethernet seçiliyse:

            ping -S 192.168.2.50 1.1.1.1

        çalışır.

        Böylece ping'in Wi-Fi üzerinden
        çıkması önlenir.
        """

        if not adapter.is_connected:
            return False, None

        if not adapter.has_valid_ipv4:
            return False, None

        return DiagnosticService._ping(
            host="1.1.1.1",
            source_ip=adapter.ipv4,
        )

    # =====================================================
    # DNS
    # =====================================================

    @staticmethod
    def test_dns(
        adapter: NetworkAdapterInfo
    ):
        """
        Sistem genelindeki DNS yerine seçili
        adaptörün DNS sunucusuna doğrudan sorgu
        gönderir.

        Böylece Ethernet seçildiğinde Wi-Fi'ın
        DNS ayarları test sonucuna karışmaz.
        """

        if not adapter.is_connected:
            return False, None

        if not adapter.has_valid_ipv4:
            return False, None

        dns_server = (
            DiagnosticService._get_ipv4_dns_server(
                adapter
            )
        )

        if not dns_server:
            return False, None

        return DiagnosticService._resolve_dns(
            dns_server=dns_server,
        )

    # =====================================================
    # ANALYSIS
    # =====================================================

    @staticmethod
    def analyze(
        adapter,
        physical_link_ok,
        valid_ip,
        dhcp_ok,
        apipa,
        gateway_ok,
        internet_ok,
        dns_ok,
        gateway_latency=None,
        internet_latency=None,
        resolved_ip=None,
    ) -> DiagnosticResult:

        severity = "success"

        diagnosis = (
            "Ağ bağlantısı normal görünüyor."
        )

        # -------------------------------------------------
        # PHYSICAL
        # -------------------------------------------------

        if not physical_link_ok:
            severity = "critical"

            diagnosis = (
                "Fiziksel ağ bağlantısı bulunamadı.\n\n"
                "Olası nedenler:\n"
                "• CAT5e/CAT6 kablosu takılı değil veya hasarlı\n"
                "• RJ45 sonlandırma problemi\n"
                "• Switch portunda link yok\n"
                "• Ağ adaptörü devre dışı\n"
                "• Switch portu kapalı"
            )

        # -------------------------------------------------
        # APIPA / INVALID IP
        # -------------------------------------------------

        elif apipa or not valid_ip:
            severity = "critical"

            diagnosis = (
                "Fiziksel bağlantı mevcut ancak geçerli "
                "IPv4 adresi alınamıyor.\n\n"
                "Windows APIPA (169.254.x.x) kullanıyor "
                "olabilir.\n\n"
                "Olası nedenler:\n"
                "• DHCP sunucusuna ulaşılamıyor\n"
                "• VLAN yapılandırması hatalı\n"
                "• Switch uplink problemi\n"
                "• CAT6 damar/sonlandırma problemi\n"
                "• Yanlış yapılandırılmış router veya access point"
            )

        # -------------------------------------------------
        # DHCP
        # -------------------------------------------------

        elif (
            not dhcp_ok
            and adapter.dhcp_enabled
        ):
            severity = "warning"

            diagnosis = (
                "DHCP etkin ancak DHCP yapılandırması "
                "sağlıklı görünmüyor.\n\n"
                "DHCP sunucusu veya ağ yapılandırması "
                "kontrol edilmeli."
            )

        # -------------------------------------------------
        # NO GATEWAY
        # -------------------------------------------------

        elif not adapter.gateway:
            severity = "critical"

            diagnosis = (
                "IPv4 adresi mevcut ancak Default "
                "Gateway bulunamadı.\n\n"
                "DHCP veya statik IP yapılandırması "
                "kontrol edilmeli."
            )

        # -------------------------------------------------
        # GATEWAY FAILURE
        # -------------------------------------------------

        elif not gateway_ok:
            severity = "critical"

            diagnosis = (
                "Geçerli IPv4 adresi mevcut ancak "
                "seçili ağ adaptörü üzerinden gateway'e "
                "erişilemiyor.\n\n"
                "Olası nedenler:\n"
                "• Yanlış gateway\n"
                "• VLAN problemi\n"
                "• Switch/router problemi\n"
                "• Yerel ağ bağlantısı problemi\n"
                "• IP çakışması\n"
                "• Hatalı subnet yapılandırması"
            )

        # -------------------------------------------------
        # INTERNET FAILURE
        # -------------------------------------------------

        elif not internet_ok:
            severity = "warning"

            diagnosis = (
                "Yerel ağ ve gateway erişilebilir ancak "
                "seçili ağ adaptörü üzerinden internet "
                "çıkışı bulunamıyor.\n\n"
                "Olası nedenler:\n"
                "• Router/WAN bağlantısı\n"
                "• Routing problemi\n"
                "• Firewall kuralı\n"
                "• Yanlış gateway\n"
                "• Üst ağ/uplink problemi"
            )

        # -------------------------------------------------
        # DNS FAILURE
        # -------------------------------------------------

        elif not dns_ok:
            severity = "warning"

            diagnosis = (
                "Internet erişimi mevcut ancak seçili "
                "adaptörün DNS sunucusu isim çözümleme "
                "yapamıyor.\n\n"
                "DNS sunucuları veya DNS yapılandırması "
                "kontrol edilmeli."
            )

        # -------------------------------------------------
        # ETHERNET SPEED WARNING
        # -------------------------------------------------

        if (
            adapter.name.lower().startswith(
                "ethernet"
            )
            and physical_link_ok
            and 0
            < adapter.link_speed_mbps
            <= 100
        ):
            if severity == "success":
                severity = "warning"

            diagnosis += (
                "\n\n⚠ EK BULGU:\n"
                f"Ethernet link hızı "
                f"{adapter.link_speed_mbps} Mbps.\n\n"
                "Gigabit destekli bir hatta aşağıdaki "
                "noktalar kontrol edilmeli:\n"
                "• CAT5e/CAT6 damarları\n"
                "• RJ45 sonlandırması\n"
                "• Patch panel\n"
                "• Switch port hızı\n"
                "• Speed/Duplex ayarı"
            )

        return DiagnosticResult(
            adapter_name=adapter.name,
            physical_link_ok=physical_link_ok,
            valid_ip=valid_ip,
            dhcp_ok=dhcp_ok,
            apipa=apipa,
            gateway_ok=gateway_ok,
            internet_ok=internet_ok,
            dns_ok=dns_ok,
            gateway_latency_ms=gateway_latency,
            internet_latency_ms=internet_latency,
            dns_resolved_ip=resolved_ip,
            diagnosis=diagnosis,
            severity=severity,
        )

    # =====================================================
    # PING
    # =====================================================

    @staticmethod
    def _ping(
        host: str,
        source_ip: Optional[str] = None,
    ):
        """
        Windows ping.

        source_ip verilirse -S ile kaynak IPv4
        açıkça belirtilir.
        """

        if source_ip:
            command = (
                f'ping -4 '
                f'-S "{source_ip}" '
                f'-n 2 '
                f'-w 1500 '
                f'"{host}"'
            )

        else:
            command = (
                f'ping -4 '
                f'-n 2 '
                f'-w 1500 '
                f'"{host}"'
            )

        output = CommandRunner.run(
            command,
            timeout=8,
        )

        success = (
            "TTL=" in output.upper()
        )

        latency = (
            DiagnosticService._extract_latency(
                output
            )
        )

        return (
            success,
            latency,
        )

    # =====================================================
    # LATENCY PARSER
    # =====================================================

    @staticmethod
    def _extract_latency(
        output: str
    ) -> Optional[int]:

        patterns = [
            r"time[=<]\s*(\d+)\s*ms",
            r"süre[=<]\s*(\d+)\s*ms",
            r"zaman[=<]\s*(\d+)\s*ms",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                output,
                re.IGNORECASE,
            )

            if match:
                try:
                    return int(
                        match.group(1)
                    )

                except ValueError:
                    pass

        lower = output.lower()

        if (
            "time<1ms" in lower
            or "süre<1ms" in lower
            or "zaman<1ms" in lower
        ):
            return 1

        return None

    # =====================================================
    # DNS SERVER
    # =====================================================

    @staticmethod
    def _get_ipv4_dns_server(
        adapter: NetworkAdapterInfo
    ) -> Optional[str]:

        for server in adapter.dns_servers:
            if (
                server
                and "." in server
                and ":" not in server
            ):
                return server

        return None

    # =====================================================
    # DNS RESOLUTION
    # =====================================================

    @staticmethod
    def _resolve_dns(
        dns_server: str
    ):
        """
        Belirtilen DNS sunucusuna doğrudan
        Resolve-DnsName sorgusu gönderir.
        """

        safe_dns = (
            dns_server.replace(
                "'",
                "''",
            )
        )

        command = (
            'powershell -NoProfile -Command '
            '"try { '
            "$result = Resolve-DnsName "
            "-Name 'google.com' "
            f"-Server '{safe_dns}' "
            "-Type A "
            "-DnsOnly "
            "-ErrorAction Stop | "
            "Where-Object { $_.IPAddress } | "
            "Select-Object -First 1 "
            "-ExpandProperty IPAddress; "
            "if ($result) { "
            "$result "
            "} "
            "else { "
            "exit 1 "
            "} "
            "} "
            "catch { "
            "Write-Output 'DNS_TEST_FAILED'; "
            "exit 1 "
            '}"'
        )

        output = CommandRunner.run(
            command,
            timeout=12,
        ).strip()

        if not output:
            return False, None

        if (
            "DNS_TEST_FAILED"
            in output
        ):
            return False, None

        if output.startswith(
            "ERROR:"
        ):
            return False, None

        ip_match = re.search(
            r"\b"
            r"(?:\d{1,3}\.){3}"
            r"\d{1,3}"
            r"\b",
            output,
        )

        if not ip_match:
            return False, None

        resolved_ip = (
            ip_match.group(0)
        )

        return (
            True,
            resolved_ip,
        )