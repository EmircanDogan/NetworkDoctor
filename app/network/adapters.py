import json
from typing import List, Optional

from app.network.models import NetworkAdapterInfo
from app.services.command_runner import CommandRunner


class AdapterService:
    @staticmethod
    def get_adapters() -> List[NetworkAdapterInfo]:
        adapters_raw = AdapterService._get_net_adapters()
        configs_raw = AdapterService._get_ip_configurations()
        dhcp_raw = AdapterService._get_dhcp_configurations()

        adapters: List[NetworkAdapterInfo] = []

        for item in adapters_raw:
            name = item.get("Name")
            if_index = item.get("ifIndex")
            description = item.get("InterfaceDescription", "")

            if "Bluetooth" in description:
                continue

            config = AdapterService._find_config(
                configs_raw,
                if_index
            )

            dhcp_config = AdapterService._find_dhcp_config(
                dhcp_raw,
                if_index
            )

            ipv4 = None
            subnet_mask = None
            gateway = None
            dns_servers = []

            dhcp_enabled = False
            dhcp_server = None

            if config:
                ipv4 = config.get("IPv4")
                gateway = config.get("Gateway")
                dns_servers = config.get("DnsServers") or []

                prefix = config.get("PrefixLength")
                subnet_mask = AdapterService._prefix_to_mask(prefix)

            if dhcp_config:
                dhcp_enabled = bool(
                    dhcp_config.get("DHCPEnabled", False)
                )

                dhcp_server = dhcp_config.get(
                    "DHCPServer"
                )

            adapters.append(
                NetworkAdapterInfo(
                    name=name or "Unknown",
                    description=description,
                    status=str(
                        item.get("Status", "Down")
                    ),
                    link_speed_mbps=AdapterService._parse_speed(
                        item.get("LinkSpeed")
                    ),
                    mac_address=item.get("MacAddress"),
                    ipv4=ipv4,
                    subnet_mask=subnet_mask,
                    gateway=gateway,
                    dns_servers=dns_servers,
                    dhcp_enabled=dhcp_enabled,
                    dhcp_server=dhcp_server,
                    interface_index=if_index,
                )
            )

        return adapters

    @staticmethod
    def _get_net_adapters() -> List[dict]:
        command = (
            'powershell -NoProfile -Command '
            '"Get-NetAdapter | '
            'Select-Object '
            'Name,InterfaceDescription,ifIndex,Status,LinkSpeed,MacAddress | '
            'ConvertTo-Json -Depth 4 -Compress"'
        )

        output = CommandRunner.run(
            command,
            timeout=15
        )

        return AdapterService._parse_json(output)

    @staticmethod
    def _get_ip_configurations() -> List[dict]:
        command = (
            'powershell -NoProfile -Command '
            '"$result = Get-NetIPConfiguration | ForEach-Object { '
            '[PSCustomObject]@{ '
            'InterfaceAlias = $_.InterfaceAlias; '
            'InterfaceIndex = $_.InterfaceIndex; '
            'IPv4 = if ($_.IPv4Address) '
            '{ $_.IPv4Address[0].IPAddress } '
            'else { $null }; '
            'PrefixLength = if ($_.IPv4Address) '
            '{ $_.IPv4Address[0].PrefixLength } '
            'else { $null }; '
            'Gateway = if ($_.IPv4DefaultGateway) '
            '{ $_.IPv4DefaultGateway.NextHop } '
            'else { $null }; '
            'DnsServers = @($_.DNSServer.ServerAddresses) '
            '} '
            '}; '
            '$result | ConvertTo-Json -Depth 4 -Compress"'
        )

        output = CommandRunner.run(
            command,
            timeout=15
        )

        return AdapterService._parse_json(output)

    @staticmethod
    def _get_dhcp_configurations() -> List[dict]:
        command = (
            'powershell -NoProfile -Command '
            '"Get-CimInstance '
            'Win32_NetworkAdapterConfiguration | '
            'Where-Object { $_.IPEnabled -eq $true } | '
            'Select-Object '
            'InterfaceIndex,DHCPEnabled,DHCPServer | '
            'ConvertTo-Json -Depth 3 -Compress"'
        )

        output = CommandRunner.run(
            command,
            timeout=15
        )

        return AdapterService._parse_json(output)

    @staticmethod
    def _parse_json(output: str) -> List[dict]:
        if not output:
            return []

        if output.startswith("ERROR:"):
            print("PowerShell komut hatası:")
            print(output)
            return []

        try:
            data = json.loads(output)

        except json.JSONDecodeError as exc:
            print("JSON parse edilemedi:")
            print(output)
            print(f"Hata: {exc}")
            return []

        if isinstance(data, dict):
            return [data]

        if isinstance(data, list):
            return data

        return []

    @staticmethod
    def _find_config(
        configs: List[dict],
        if_index
    ) -> Optional[dict]:

        for config in configs:
            if config.get("InterfaceIndex") == if_index:
                return config

        return None

    @staticmethod
    def _find_dhcp_config(
        configs: List[dict],
        if_index
    ) -> Optional[dict]:

        for config in configs:
            if config.get("InterfaceIndex") == if_index:
                return config

        return None

    @staticmethod
    def _parse_speed(value) -> int:
        if not value:
            return 0

        text = str(value).strip().lower()

        try:
            if "gbps" in text:
                return int(
                    float(
                        text
                        .replace("gbps", "")
                        .replace(",", ".")
                        .strip()
                    ) * 1000
                )

            if "mbps" in text:
                return int(
                    float(
                        text
                        .replace("mbps", "")
                        .replace(",", ".")
                        .strip()
                    )
                )

            if "kbps" in text:
                return int(
                    float(
                        text
                        .replace("kbps", "")
                        .replace(",", ".")
                        .strip()
                    ) / 1000
                )

        except ValueError:
            return 0

        return 0

    @staticmethod
    def _prefix_to_mask(prefix) -> Optional[str]:
        if prefix is None:
            return None

        try:
            prefix = int(prefix)

        except (ValueError, TypeError):
            return None

        if prefix < 0 or prefix > 32:
            return None

        if prefix == 0:
            return "0.0.0.0"

        mask = (
            (0xFFFFFFFF << (32 - prefix))
            & 0xFFFFFFFF
        )

        return ".".join(
            str(
                (mask >> shift) & 0xFF
            )
            for shift in (24, 16, 8, 0)
        )

    @staticmethod
    def get_adapter_by_name(
        name: str
    ) -> Optional[NetworkAdapterInfo]:

        for adapter in AdapterService.get_adapters():
            if adapter.name == name:
                return adapter

        return None