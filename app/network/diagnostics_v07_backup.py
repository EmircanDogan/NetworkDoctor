import socket
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

    @staticmethod
    def test_physical_link(adapter: NetworkAdapterInfo) -> bool:
        return adapter.is_connected

    @staticmethod
    def test_ip(adapter: NetworkAdapterInfo):
        return adapter.has_valid_ipv4, adapter.is_apipa

    @staticmethod
    def test_dhcp(adapter: NetworkAdapterInfo) -> bool:
        if not adapter.dhcp_enabled:
            # Statik IP kullanılıyor olabilir.
            return adapter.has_valid_ipv4

        return bool(
            adapter.has_valid_ipv4
            and adapter.dhcp_server
        )

    @staticmethod
    def test_gateway(adapter: NetworkAdapterInfo):
        if not adapter.gateway:
            return False, None

        return DiagnosticService._ping(
            adapter.gateway
        )

    @staticmethod
    def test_internet():
        return DiagnosticService._ping(
            "1.1.1.1"
        )

    @staticmethod
    def test_dns():
        return DiagnosticService._dns_test()

    @staticmethod
    def analyze(
        adapter: NetworkAdapterInfo,
        physical_link_ok: bool,
        valid_ip: bool,
        dhcp_ok: bool,
        apipa: bool,
        gateway_ok: bool,
        internet_ok: bool,
        dns_ok: bool,
        gateway_latency=None,
        internet_latency=None,
        resolved_ip=None,
    ) -> DiagnosticResult:

        severity = "success"
        diagnosis = "Ağ bağlantısı normal görünüyor."

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

        elif apipa or not valid_ip:
            severity = "critical"
            diagnosis = (
                "Fiziksel bağlantı mevcut ancak geçerli IPv4 "
                "adresi alınamıyor.\n\n"
                "Windows APIPA (169.254.x.x) kullanıyor olabilir.\n\n"
                "Olası nedenler:\n"
                "• DHCP sunucusuna ulaşılamıyor\n"
                "• VLAN yapılandırması hatalı\n"
                "• Switch uplink problemi\n"
                "• CAT6 damar/sonlandırma problemi\n"
                "• Yanlış yapılandırılmış router veya access point"
            )

        elif not dhcp_ok and adapter.dhcp_enabled:
            severity = "warning"
            diagnosis = (
                "DHCP etkin ancak DHCP yapılandırması sağlıklı "
                "görünmüyor.\n\n"
                "DHCP sunucusu veya ağ yapılandırması kontrol edilmeli."
            )

        elif not adapter.gateway:
            severity = "critical"
            diagnosis = (
                "IPv4 adresi mevcut ancak Default Gateway yok.\n\n"
                "DHCP veya statik IP yapılandırması kontrol edilmeli."
            )

        elif not gateway_ok:
            severity = "critical"
            diagnosis = (
                "Geçerli IP adresi mevcut ancak gateway'e "
                "erişilemiyor.\n\n"
                "Olası nedenler:\n"
                "• Yanlış gateway\n"
                "• VLAN problemi\n"
                "• Switch/router problemi\n"
                "• Yerel ağ bağlantısı problemi"
            )

        elif not internet_ok:
            severity = "warning"
            diagnosis = (
                "Yerel ağ ve gateway erişilebilir ancak internet "
                "çıkışı bulunamıyor.\n\n"
                "Olası nedenler:\n"
                "• Router/WAN bağlantısı\n"
                "• Routing problemi\n"
                "• Firewall kuralı\n"
                "• Yanlış gateway\n"
                "• Üst ağ/uplink problemi"
            )

        elif not dns_ok:
            severity = "warning"
            diagnosis = (
                "Internet erişimi var ancak DNS isim çözümleme "
                "çalışmıyor.\n\n"
                "DNS sunucuları veya DNS önbelleği kontrol edilmeli."
            )

        # Gigabit destekli Ethernet için ekstra uyarı
        if (
            adapter.name.lower().startswith("ethernet")
            and physical_link_ok
            and 0 < adapter.link_speed_mbps <= 100
        ):
            if severity == "success":
                severity = "warning"

            diagnosis += (
                "\n\n⚠ EK BULGU:\n"
                f"Ethernet link hızı {adapter.link_speed_mbps} Mbps.\n"
                "Gigabit destekli bir hatta CAT5e/CAT6 damarları, "
                "RJ45 sonlandırması, Speed/Duplex veya switch port "
                "hızı kontrol edilmeli."
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

    @staticmethod
    def _ping(host: str):
        output = CommandRunner.run(
            f'ping -n 2 -w 1500 "{host}"',
            timeout=8
        )

        success = "TTL=" in output.upper()

        latency = None

        patterns = [
            r"time[=<]\s*(\d+)\s*ms",
            r"süre[=<]\s*(\d+)\s*ms",
            r"zaman[=<]\s*(\d+)\s*ms",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                output,
                re.IGNORECASE
            )

            if match:
                latency = int(match.group(1))
                break

        return success, latency

    @staticmethod
    def _dns_test():
        try:
            ip = socket.gethostbyname(
                "google.com"
            )
            return True, ip

        except socket.gaierror:
            return False, None