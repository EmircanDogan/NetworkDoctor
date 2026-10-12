import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set

from app.network.models import NetworkAdapterInfo
from app.services.command_runner import CommandRunner


@dataclass
class IpConflictEvidence:
    source: str
    description: str
    severity: str = "info"


@dataclass
class IpConflictResult:
    ip: Optional[str]
    conflict_suspected: bool
    confidence: str

    local_mac: Optional[str]
    observed_mac: Optional[str]

    observed_macs: List[str] = field(
        default_factory=list
    )

    evidence: List[IpConflictEvidence] = field(
        default_factory=list
    )

    message: str = ""


class IpConflictDetector:

    # =====================================================
    # PUBLIC CHECK
    # =====================================================

    @staticmethod
    def check(
        adapter: NetworkAdapterInfo,
        sample_count: int = 3,
        sample_delay: float = 0.6,
    ) -> IpConflictResult:

        evidence: List[
            IpConflictEvidence
        ] = []

        if not adapter.is_connected:
            return IpConflictResult(
                ip=adapter.ipv4,
                conflict_suspected=False,
                confidence="none",
                local_mac=adapter.mac_address,
                observed_mac=None,
                observed_macs=[],
                evidence=[],
                message=(
                    "Adaptör bağlı değil. "
                    "IP çakışması testi uygulanamadı."
                ),
            )

        if not adapter.ipv4:
            return IpConflictResult(
                ip=None,
                conflict_suspected=False,
                confidence="none",
                local_mac=adapter.mac_address,
                observed_mac=None,
                observed_macs=[],
                evidence=[],
                message=(
                    "Adaptörde IPv4 adresi bulunmuyor."
                ),
            )

        if adapter.is_apipa:
            return IpConflictResult(
                ip=adapter.ipv4,
                conflict_suspected=False,
                confidence="none",
                local_mac=adapter.mac_address,
                observed_mac=None,
                observed_macs=[],
                evidence=[
                    IpConflictEvidence(
                        source="APIPA",
                        description=(
                            "Adaptör 169.254.x.x APIPA "
                            "adresi kullanıyor."
                        ),
                        severity="warning",
                    )
                ],
                message=(
                    "Adaptör APIPA adresi kullanıyor. "
                    "Öncelikli problem DHCP veya ağ "
                    "erişimi olabilir."
                ),
            )

        local_ip = adapter.ipv4

        local_mac = (
            IpConflictDetector._normalize_mac(
                adapter.mac_address
            )
        )

        observed_macs: Set[str] = set()

        # =================================================
        # 1 - WINDOWS EVENT LOG
        # =================================================

        event_result = (
            IpConflictDetector._check_windows_events(
                local_ip
            )
        )

        if event_result:
            evidence.append(
                IpConflictEvidence(
                    source="Windows Event Log",
                    description=(
                        "Windows System log içinde "
                        "duplicate/conflict IP belirtisi "
                        "bulundu."
                    ),
                    severity="critical",
                )
            )

        # =================================================
        # 2 - MULTIPLE NEIGHBOR SAMPLES
        # =================================================

        for _ in range(
            max(
                1,
                sample_count,
            )
        ):
            IpConflictDetector._stimulate_neighbor(
                adapter
            )

            neighbor_macs = (
                IpConflictDetector._collect_neighbor_macs(
                    local_ip,
                    adapter.interface_index,
                )
            )

            for mac in neighbor_macs:
                normalized = (
                    IpConflictDetector._normalize_mac(
                        mac
                    )
                )

                if normalized:
                    observed_macs.add(
                        normalized
                    )

            if sample_delay > 0:
                time.sleep(
                    sample_delay
                )

        # =================================================
        # 3 - ARP TABLE
        # =================================================

        arp_macs = (
            IpConflictDetector._collect_arp_macs(
                local_ip
            )
        )

        for mac in arp_macs:
            normalized = (
                IpConflictDetector._normalize_mac(
                    mac
                )
            )

            if normalized:
                observed_macs.add(
                    normalized
                )

        # =================================================
        # 4 - FILTER INVALID / LOCAL
        # =================================================

        filtered_observed = {
            mac
            for mac in observed_macs
            if (
                mac
                and not IpConflictDetector._is_invalid_mac(
                    mac
                )
            )
        }

        foreign_macs = {
            mac
            for mac in filtered_observed
            if (
                not local_mac
                or mac != local_mac
            )
        }

        # =================================================
        # 5 - EVIDENCE ANALYSIS
        # =================================================

        if len(filtered_observed) > 1:
            evidence.append(
                IpConflictEvidence(
                    source="Neighbor/ARP",
                    description=(
                        "Aynı IPv4 adresi için birden "
                        "fazla farklı MAC adresi gözlendi: "
                        + ", ".join(
                            sorted(
                                filtered_observed
                            )
                        )
                    ),
                    severity="critical",
                )
            )

        elif foreign_macs:
            evidence.append(
                IpConflictEvidence(
                    source="Neighbor/ARP",
                    description=(
                        "Yerel adaptörün IPv4 adresi için "
                        "farklı bir MAC adresi gözlendi: "
                        + ", ".join(
                            sorted(
                                foreign_macs
                            )
                        )
                    ),
                    severity="critical",
                )
            )

        # =================================================
        # 6 - CONFIDENCE
        # =================================================

        critical_evidence_count = sum(
            1
            for item in evidence
            if item.severity == "critical"
        )

        warning_evidence_count = sum(
            1
            for item in evidence
            if item.severity == "warning"
        )

        if (
            event_result
            and foreign_macs
        ):
            confidence = "high"
            conflict_suspected = True

        elif len(filtered_observed) > 1:
            confidence = "high"
            conflict_suspected = True

        elif foreign_macs:
            confidence = "high"
            conflict_suspected = True

        elif critical_evidence_count >= 1:
            confidence = "medium"
            conflict_suspected = True

        elif warning_evidence_count >= 1:
            confidence = "low"
            conflict_suspected = False

        else:
            confidence = "low"
            conflict_suspected = False

        # =================================================
        # 7 - PRIMARY OBSERVED MAC
        # =================================================

        observed_mac = None

        if foreign_macs:
            observed_mac = sorted(
                foreign_macs
            )[0]

        elif filtered_observed:
            observed_mac = sorted(
                filtered_observed
            )[0]

        # =================================================
        # 8 - MESSAGE
        # =================================================

        if conflict_suspected:
            if confidence == "high":
                message = (
                    "IP çakışması olasılığı yüksek. "
                    "Aynı IPv4 adresi için farklı bir "
                    "MAC veya birden fazla MAC gözlendi."
                )

            else:
                message = (
                    "IP çakışmasına işaret eden sistem "
                    "belirtileri bulundu."
                )

        else:
            if filtered_observed:
                message = (
                    "IP çakışmasına ilişkin doğrudan "
                    "bir belirti bulunamadı."
                )

            else:
                message = (
                    "IP çakışmasına ilişkin doğrudan "
                    "bir belirti bulunamadı. Windows "
                    "kendi IP adresi için ARP/Neighbor "
                    "kaydı üretmemiş olabilir."
                )

        return IpConflictResult(
            ip=local_ip,
            conflict_suspected=conflict_suspected,
            confidence=confidence,
            local_mac=local_mac,
            observed_mac=observed_mac,
            observed_macs=sorted(
                filtered_observed
            ),
            evidence=evidence,
            message=message,
        )

    # =====================================================
    # STIMULATE NEIGHBOR CACHE
    # =====================================================

    @staticmethod
    def _stimulate_neighbor(
        adapter: NetworkAdapterInfo
    ):
        """
        Seçili adaptör üzerinden ağ trafiği oluşturarak
        Neighbor/ARP cache'in güncellenmesine yardımcı olur.
        """

        if not adapter.ipv4:
            return

        targets = []

        if adapter.gateway:
            targets.append(
                adapter.gateway
            )

        targets.append(
            adapter.ipv4
        )

        for target in targets:
            command = (
                f'ping -4 '
                f'-S "{adapter.ipv4}" '
                f'-n 1 '
                f'-w 350 '
                f'"{target}"'
            )

            CommandRunner.run(
                command,
                timeout=2,
            )

    # =====================================================
    # GET-NETNEIGHBOR
    # =====================================================

    @staticmethod
    def _collect_neighbor_macs(
        ip: str,
        interface_index: Optional[int],
    ) -> List[str]:

        if interface_index is not None:
            command = (
                'powershell -NoProfile -Command '
                '"Get-NetNeighbor '
                f"-IPAddress '{ip}' "
                f"-InterfaceIndex {interface_index} "
                "-ErrorAction SilentlyContinue | "
                "Where-Object { "
                "$_.LinkLayerAddress "
                "} | "
                "Select-Object -ExpandProperty "
                'LinkLayerAddress"'
            )

        else:
            command = (
                'powershell -NoProfile -Command '
                '"Get-NetNeighbor '
                f"-IPAddress '{ip}' "
                "-ErrorAction SilentlyContinue | "
                "Where-Object { "
                "$_.LinkLayerAddress "
                "} | "
                "Select-Object -ExpandProperty "
                'LinkLayerAddress"'
            )

        output = CommandRunner.run(
            command,
            timeout=10,
        )

        if not output:
            return []

        if output.startswith(
            "ERROR:"
        ):
            return []

        macs = []

        for line in output.splitlines():
            line = line.strip()

            if not line:
                continue

            if IpConflictDetector._looks_like_mac(
                line
            ):
                macs.append(
                    line
                )

        return macs

    # =====================================================
    # ARP TABLE
    # =====================================================

    @staticmethod
    def _collect_arp_macs(
        ip: str
    ) -> List[str]:

        output = CommandRunner.run(
            "arp -a",
            timeout=10,
        )

        if not output:
            return []

        pattern = re.compile(
            r"^\s*"
            + re.escape(ip)
            + r"\s+"
            + r"([0-9A-Fa-f]{2}"
            r"(?:-[0-9A-Fa-f]{2}){5})"
            r"\s+",
            re.MULTILINE,
        )

        return [
            match.group(1)
            for match in pattern.finditer(
                output
            )
        ]

    # =====================================================
    # WINDOWS EVENT LOG
    # =====================================================

    @staticmethod
    def _check_windows_events(
        ip: str
    ) -> bool:
        """
        Son 24 saatte System log içindeki TCP/IP
        duplicate/conflict belirtilerini kontrol eder.
        """

        safe_ip = (
            ip.replace(
                "'",
                "''",
            )
        )

        command = (
            'powershell -NoProfile -Command '
            '"$events = Get-WinEvent '
            "-FilterHashtable @{"
            "LogName='System'; "
            "StartTime=(Get-Date).AddHours(-24)"
            "} "
            "-ErrorAction SilentlyContinue | "
            "Where-Object { "
            "$_.ProviderName -match "
            "'Tcpip|TcpIp|Dhcp' "
            "-and "
            "$_.Message -match "
            "'duplicate|conflict|çakış|same IP|"
            "address.*already.*use' "
            "}; "
            "$matches = $events | "
            "Where-Object { "
            f"$_.Message -match '{safe_ip}' "
            "} | "
            "Select-Object -First 5 "
            "-ExpandProperty Message; "
            "if ($matches) { "
            "$matches "
            "}"
        )

        output = CommandRunner.run(
            command,
            timeout=20,
        )

        if not output:
            return False

        if output.startswith(
            "ERROR:"
        ):
            return False

        lower = output.lower()

        keywords = (
            "duplicate",
            "conflict",
            "çakış",
            "same ip",
            "already in use",
        )

        return any(
            keyword in lower
            for keyword in keywords
        )

    # =====================================================
    # MAC HELPERS
    # =====================================================

    @staticmethod
    def _normalize_mac(
        mac: Optional[str]
    ) -> Optional[str]:

        if not mac:
            return None

        clean = re.sub(
            r"[^0-9A-Fa-f]",
            "",
            mac,
        )

        if len(clean) != 12:
            return mac.upper()

        return "-".join(
            clean[index:index + 2]
            for index in range(
                0,
                12,
                2,
            )
        ).upper()

    @staticmethod
    def _looks_like_mac(
        value: str
    ) -> bool:

        return bool(
            re.fullmatch(
                r"[0-9A-Fa-f]{2}"
                r"(?:[-:][0-9A-Fa-f]{2}){5}",
                value.strip(),
            )
        )

    @staticmethod
    def _is_invalid_mac(
        mac: str
    ) -> bool:

        normalized = (
            IpConflictDetector._normalize_mac(
                mac
            )
        )

        if not normalized:
            return True

        invalid_values = {
            "00-00-00-00-00-00",
            "FF-FF-FF-FF-FF-FF",
        }

        return normalized in invalid_values