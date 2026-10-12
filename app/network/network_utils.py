import ipaddress
from typing import List, Optional, Set

from app.network.models import NetworkAdapterInfo


class NetworkUtils:
    @staticmethod
    def get_network(
        adapter: NetworkAdapterInfo
    ) -> Optional[ipaddress.IPv4Network]:
        """
        Adaptörün IPv4 + subnet mask bilgisinden
        IPv4Network nesnesi üretir.
        """

        if not adapter.ipv4:
            return None

        if not adapter.subnet_mask:
            return None

        try:
            interface = ipaddress.IPv4Interface(
                f"{adapter.ipv4}/{adapter.subnet_mask}"
            )

            return interface.network

        except ValueError:
            return None

    @staticmethod
    def get_network_address(
        adapter: NetworkAdapterInfo
    ) -> Optional[str]:
        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return None

        return str(network.network_address)

    @staticmethod
    def get_broadcast_address(
        adapter: NetworkAdapterInfo
    ) -> Optional[str]:
        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return None

        return str(network.broadcast_address)

    @staticmethod
    def get_cidr(
        adapter: NetworkAdapterInfo
    ) -> Optional[str]:
        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return None

        return str(network)

    @staticmethod
    def get_prefix_length(
        adapter: NetworkAdapterInfo
    ) -> Optional[int]:
        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return None

        return network.prefixlen

    @staticmethod
    def get_host_count(
        adapter: NetworkAdapterInfo
    ) -> int:
        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return 0

        # Network + broadcast çıkarılır.
        # /31 ve /32 için negatif olmaması önemli.
        return max(
            0,
            network.num_addresses - 2
        )

    @staticmethod
    def get_all_host_ips(
        adapter: NetworkAdapterInfo,
        max_hosts: int = 1024,
    ) -> List[str]:
        """
        Ağdaki kullanılabilir host IP'lerini döndürür.

        Güvenlik/performance amacıyla varsayılan
        maksimum 1024 adres ile sınırlandırılmıştır.
        """

        network = NetworkUtils.get_network(
            adapter
        )

        if not network:
            return []

        hosts = []

        for index, host in enumerate(
            network.hosts()
        ):
            if index >= max_hosts:
                break

            hosts.append(
                str(host)
            )

        return hosts

    @staticmethod
    def get_reserved_ips(
        adapter: NetworkAdapterInfo
    ) -> Set[str]:
        """
        Tarama veya boş-IP hesaplamasında
        otomatik olarak hariç tutulması gereken
        adresleri döndürür.
        """

        reserved = set()

        network = NetworkUtils.get_network(
            adapter
        )

        if network:
            reserved.add(
                str(network.network_address)
            )

            reserved.add(
                str(network.broadcast_address)
            )

        if adapter.ipv4:
            reserved.add(
                adapter.ipv4
            )

        if adapter.gateway:
            reserved.add(
                adapter.gateway
            )

        if adapter.dhcp_server:
            reserved.add(
                adapter.dhcp_server
            )

        for dns_server in adapter.dns_servers:
            try:
                ipaddress.IPv4Address(
                    dns_server
                )

                reserved.add(
                    dns_server
                )

            except ValueError:
                pass

        return reserved

    @staticmethod
    def get_candidate_free_ips(
        adapter: NetworkAdapterInfo,
        active_ips: Set[str],
        max_results: int = 50,
    ) -> List[str]:
        """
        Aktif olduğu bilinen adresleri ve
        kritik/reserved adresleri çıkararak
        'boş görünen' IP adaylarını üretir.

        ÖNEMLİ:
        Bunlar kesin boş IP değildir.
        Ping'e cevap vermeyen cihazlar olabilir.
        """

        all_hosts = (
            NetworkUtils.get_all_host_ips(
                adapter
            )
        )

        reserved = (
            NetworkUtils.get_reserved_ips(
                adapter
            )
        )

        unavailable = (
            set(active_ips)
            | reserved
        )

        candidates = []

        for ip in all_hosts:
            if ip in unavailable:
                continue

            candidates.append(ip)

            if len(candidates) >= max_results:
                break

        return candidates