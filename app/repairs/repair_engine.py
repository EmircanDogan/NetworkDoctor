from dataclasses import dataclass
from typing import List

from app.network.models import NetworkAdapterInfo
from app.network.diagnostics import DiagnosticResult


@dataclass
class RepairRecommendation:
    action_id: str
    title: str
    description: str

    recommended: bool = False

    requires_admin: bool = False
    requires_restart: bool = False

    level: str = "safe"


class RepairEngine:

    @staticmethod
    def get_recommendations(
        adapter: NetworkAdapterInfo,
        result: DiagnosticResult,
    ) -> List[RepairRecommendation]:

        recommendations: List[
            RepairRecommendation
        ] = []

        # ---------------------------------------------
        # DHCP RENEW
        # ---------------------------------------------
        if adapter.dhcp_enabled:
            recommendations.append(
                RepairRecommendation(
                    action_id="renew_dhcp",
                    title="DHCP Adresini Yenile",
                    description=(
                        "DHCP sunucusundan yeni IPv4, "
                        "gateway ve DNS bilgileri ister."
                    ),
                    recommended=(
                        result.apipa
                        or not result.valid_ip
                        or (
                            result.valid_ip
                            and not result.gateway_ok
                        )
                    ),
                    requires_admin=False,
                    requires_restart=False,
                    level="safe",
                )
            )

        # ---------------------------------------------
        # DNS FLUSH
        # ---------------------------------------------
        recommendations.append(
            RepairRecommendation(
                action_id="flush_dns",
                title="DNS Önbelleğini Temizle",
                description=(
                    "Windows DNS önbelleğini temizler. "
                    "Eski veya hatalı DNS kayıtlarında "
                    "yararlı olabilir."
                ),
                recommended=(
                    result.internet_ok
                    and not result.dns_ok
                ),
                requires_admin=False,
                requires_restart=False,
                level="safe",
            )
        )

        # ---------------------------------------------
        # ARP CLEAR
        # ---------------------------------------------
        recommendations.append(
            RepairRecommendation(
                action_id="clear_arp",
                title="ARP Tablosunu Temizle",
                description=(
                    "Yerel IP-MAC eşleştirmelerini "
                    "yeniden öğrenmek için ARP "
                    "önbelleğini temizler."
                ),
                recommended=(
                    result.valid_ip
                    and not result.gateway_ok
                ),
                requires_admin=True,
                requires_restart=False,
                level="medium",
            )
        )

        # ---------------------------------------------
        # ADAPTER RESTART
        # ---------------------------------------------
        recommendations.append(
            RepairRecommendation(
                action_id="restart_adapter",
                title="Ağ Adaptörünü Yeniden Başlat",
                description=(
                    "Seçili ağ adaptörünü devre dışı "
                    "bırakıp tekrar etkinleştirir."
                ),
                recommended=(
                    result.physical_link_ok
                    and (
                        result.apipa
                        or not result.valid_ip
                        or not result.gateway_ok
                    )
                ),
                requires_admin=True,
                requires_restart=False,
                level="medium",
            )
        )

        # ---------------------------------------------
        # WINSOCK RESET
        # ---------------------------------------------
        recommendations.append(
            RepairRecommendation(
                action_id="reset_winsock",
                title="Winsock Sıfırla",
                description=(
                    "Windows Socket kataloğunu "
                    "varsayılan duruma getirir. "
                    "Daha ileri seviye bir onarımdır."
                ),
                recommended=False,
                requires_admin=True,
                requires_restart=True,
                level="advanced",
            )
        )

        # ---------------------------------------------
        # TCP/IP RESET
        # ---------------------------------------------
        recommendations.append(
            RepairRecommendation(
                action_id="reset_tcp_ip",
                title="TCP/IP Stack Sıfırla",
                description=(
                    "Windows TCP/IP yapılandırmasını "
                    "sıfırlar. Diğer yazılımsal "
                    "onarımlar başarısızsa kullanılmalı."
                ),
                recommended=False,
                requires_admin=True,
                requires_restart=True,
                level="advanced",
            )
        )

        return recommendations