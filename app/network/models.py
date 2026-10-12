from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class NetworkAdapterInfo:
    name: str
    description: str
    status: str
    link_speed_mbps: int

    mac_address: Optional[str] = None
    ipv4: Optional[str] = None
    subnet_mask: Optional[str] = None
    gateway: Optional[str] = None

    dns_servers: List[str] = field(default_factory=list)

    dhcp_enabled: bool = False
    dhcp_server: Optional[str] = None

    interface_index: Optional[int] = None

    @property
    def is_connected(self) -> bool:
        return self.status.lower() == "up"

    @property
    def is_apipa(self) -> bool:
        return bool(
            self.ipv4
            and self.ipv4.startswith("169.254.")
        )

    @property
    def has_valid_ipv4(self) -> bool:
        return bool(
            self.ipv4
            and not self.is_apipa
        )