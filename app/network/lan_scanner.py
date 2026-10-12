import concurrent.futures
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from app.network.models import NetworkAdapterInfo
from app.network.network_utils import NetworkUtils
from app.services.command_runner import CommandRunner


@dataclass
class LanDevice:
    ip: str
    is_online: bool
    latency_ms: Optional[int] = None
    mac_address: Optional[str] = None
    hostname: Optional[str] = None


class LanScanner:
    @staticmethod
    def scan(
        adapter: NetworkAdapterInfo,
        max_workers: int = 64,
        max_hosts: int = 512,
    ) -> List[LanDevice]:
        """
        Seçili adaptörün subnet'indeki hostları paralel tarar.

        Not:
        Ping'e cevap vermeyen bazı cihazlar yine de ağda olabilir.
        Bu yüzden sonuçlar 'görülen cihazlar' olarak yorumlanmalıdır.
        """

        if not adapter.is_connected:
            return []

        if not adapter.ipv4:
            return []

        host_ips = NetworkUtils.get_all_host_ips(
            adapter,
            max_hosts=max_hosts,
        )

        if not host_ips:
            return []

        devices = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:

            future_map = {
                executor.submit(
                    LanScanner._probe_host,
                    ip,
                    adapter.ipv4,
                ): ip
                for ip in host_ips
            }

            for future in concurrent.futures.as_completed(
                future_map
            ):
                try:
                    device = future.result()

                    if device.is_online:
                        devices.append(device)

                except Exception:
                    pass

        LanScanner._populate_mac_addresses(
            devices
        )

        LanScanner._populate_hostnames(
            devices
        )

        for device in devices:
            if device.ip == adapter.ipv4:
                device.mac_address = adapter.mac_address
        devices.sort(
            key=lambda device: LanScanner._ip_sort_key(
                device.ip
            )
        )

        return devices

    @staticmethod
    def _probe_host(
        ip: str,
        source_ip: Optional[str] = None,
    ) -> LanDevice:

        command = (
            f'ping -4 -n 1 -w 500 "{ip}"'
        )

        if source_ip:
            command = (
                f'ping -4 -S "{source_ip}" '
                f'-n 1 -w 500 "{ip}"'
            )

        output = CommandRunner.run(
            command,
            timeout=3,
        )

        success = (
            "TTL=" in output.upper()
        )

        latency = (
            LanScanner._extract_latency(
                output
            )
        )

        return LanDevice(
            ip=ip,
            is_online=success,
            latency_ms=latency,
        )

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

        # Windows bazen <1ms döndürür.
        lower_output = output.lower()

        if (
            "time<1ms" in lower_output
            or "süre<1ms" in lower_output
            or "zaman<1ms" in lower_output
        ):
            return 1

        return None

    @staticmethod
    def _populate_mac_addresses(
        devices: List[LanDevice]
    ):
        """
        Ping sonrasında Windows ARP cache'inden
        IP -> MAC eşleşmelerini toplar.
        """

        output = CommandRunner.run(
            "arp -a",
            timeout=10,
        )

        if not output:
            return

        arp_table = {}

        pattern = re.compile(
            r"(\d{1,3}(?:\.\d{1,3}){3})"
            r"\s+"
            r"([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})"
        )

        for match in pattern.finditer(
            output
        ):
            ip = match.group(1)
            mac = match.group(2).upper()

            arp_table[ip] = mac

        for device in devices:
            device.mac_address = (
                arp_table.get(
                    device.ip
                )
            )

    @staticmethod
    def _populate_hostnames(
        devices: List[LanDevice]
    ):
        """
        Reverse DNS ile hostname çözmeye çalışır.
        Başarısız olması normaldir.
        """

        for device in devices:
            try:
                hostname, _, _ = (
                    socket.gethostbyaddr(
                        device.ip
                    )
                )

                device.hostname = hostname

            except (
                socket.herror,
                socket.gaierror,
                OSError,
            ):
                device.hostname = None

    @staticmethod
    def _ip_sort_key(
        ip: str
    ):
        try:
            return tuple(
                int(part)
                for part in ip.split(".")
            )

        except ValueError:
            return (
                999,
                999,
                999,
                999,
            )