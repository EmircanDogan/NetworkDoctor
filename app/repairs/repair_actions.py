import ctypes
import time
from dataclasses import dataclass
from typing import Optional

from app.services.command_runner import CommandRunner


@dataclass
class RepairResult:
    action_id: str
    title: str
    success: bool
    message: str
    output: str = ""
    requires_restart: bool = False


class RepairService:
    """
    Windows üzerinde gerçek ağ onarım işlemlerini çalıştırır.

    Hiçbir işlem otomatik uygulanmaz.
    UI tarafından kullanıcı seçimi sonrası çağrılması amaçlanmıştır.
    """

    @staticmethod
    def is_admin() -> bool:
        try:
            return bool(
                ctypes.windll.shell32.IsUserAnAdmin()
            )
        except Exception:
            return False

    @staticmethod
    def renew_dhcp(
        adapter_name: Optional[str] = None
    ) -> RepairResult:

        # ipconfig /renew adaptör adıyla da kullanılabilir.
        if adapter_name:
            command = (
                f'ipconfig /renew "{adapter_name}"'
            )
        else:
            command = "ipconfig /renew"

        output = CommandRunner.run(
            command,
            timeout=45
        )

        success = RepairService._dhcp_renew_success(
            output
        )

        return RepairResult(
            action_id="renew_dhcp",
            title="DHCP Adresini Yenile",
            success=success,
            message=(
                "DHCP adresi yenilendi."
                if success
                else (
                    "DHCP adresi yenilenemedi. "
                    "DHCP sunucusu, fiziksel hat veya "
                    "VLAN bağlantısı kontrol edilmeli."
                )
            ),
            output=output,
        )

    @staticmethod
    def flush_dns() -> RepairResult:
        output = CommandRunner.run(
            "ipconfig /flushdns",
            timeout=15
        )

        output_lower = output.lower()

        success = (
            "success" in output_lower
            or "başarı" in output_lower
            or "successfully" in output_lower
            or "dns resolver cache" in output_lower
        )

        return RepairResult(
            action_id="flush_dns",
            title="DNS Önbelleğini Temizle",
            success=success,
            message=(
                "DNS önbelleği temizlendi."
                if success
                else "DNS önbelleği temizlenemedi."
            ),
            output=output,
        )

    @staticmethod
    def clear_arp() -> RepairResult:
        if not RepairService.is_admin():
            return RepairService._admin_required(
                action_id="clear_arp",
                title="ARP Tablosunu Temizle",
            )

        output = CommandRunner.run(
            "arp -d *",
            timeout=15
        )

        # arp -d * başarılı olduğunda bazen çıktı üretmez.
        success = not RepairService._looks_like_error(
            output
        )

        return RepairResult(
            action_id="clear_arp",
            title="ARP Tablosunu Temizle",
            success=success,
            message=(
                "ARP tablosu temizlendi."
                if success
                else "ARP tablosu temizlenemedi."
            ),
            output=output,
        )

    @staticmethod
    def restart_adapter(
        adapter_name: str
    ) -> RepairResult:

        if not RepairService.is_admin():
            return RepairService._admin_required(
                action_id="restart_adapter",
                title="Ağ Adaptörünü Yeniden Başlat",
            )

        safe_name = (
            adapter_name.replace("'", "''")
        )

        disable_command = (
            "powershell -NoProfile -Command "
            f"\"Disable-NetAdapter "
            f"-Name '{safe_name}' "
            "-Confirm:$false "
            "-ErrorAction Stop\""
        )

        disable_output = CommandRunner.run(
            disable_command,
            timeout=20
        )

        if RepairService._looks_like_error(
            disable_output
        ):
            return RepairResult(
                action_id="restart_adapter",
                title="Ağ Adaptörünü Yeniden Başlat",
                success=False,
                message=(
                    "Ağ adaptörü devre dışı bırakılamadı."
                ),
                output=disable_output,
            )

        # Windows'un adaptörü gerçekten kapatmasına
        # kısa süre izin ver.
        time.sleep(2)

        enable_command = (
            "powershell -NoProfile -Command "
            f"\"Enable-NetAdapter "
            f"-Name '{safe_name}' "
            "-Confirm:$false "
            "-ErrorAction Stop\""
        )

        enable_output = CommandRunner.run(
            enable_command,
            timeout=20
        )

        success = not RepairService._looks_like_error(
            enable_output
        )

        full_output = (
            f"DISABLE:\n{disable_output}\n\n"
            f"ENABLE:\n{enable_output}"
        )

        return RepairResult(
            action_id="restart_adapter",
            title="Ağ Adaptörünü Yeniden Başlat",
            success=success,
            message=(
                "Ağ adaptörü yeniden başlatıldı."
                if success
                else (
                    "Ağ adaptörü tekrar "
                    "etkinleştirilemedi."
                )
            ),
            output=full_output,
        )

    @staticmethod
    def reset_winsock() -> RepairResult:
        if not RepairService.is_admin():
            return RepairService._admin_required(
                action_id="reset_winsock",
                title="Winsock Sıfırla",
                requires_restart=True,
            )

        output = CommandRunner.run(
            "netsh winsock reset",
            timeout=20
        )

        success = not RepairService._looks_like_error(
            output
        )

        return RepairResult(
            action_id="reset_winsock",
            title="Winsock Sıfırla",
            success=success,
            message=(
                "Winsock sıfırlandı. "
                "Bilgisayarın yeniden başlatılması "
                "gerekebilir."
                if success
                else "Winsock sıfırlanamadı."
            ),
            output=output,
            requires_restart=success,
        )

    @staticmethod
    def reset_tcp_ip() -> RepairResult:
        if not RepairService.is_admin():
            return RepairService._admin_required(
                action_id="reset_tcp_ip",
                title="TCP/IP Stack Sıfırla",
                requires_restart=True,
            )

        output = CommandRunner.run(
            "netsh int ip reset",
            timeout=30
        )

        success = not RepairService._looks_like_error(
            output
        )

        return RepairResult(
            action_id="reset_tcp_ip",
            title="TCP/IP Stack Sıfırla",
            success=success,
            message=(
                "TCP/IP stack sıfırlandı. "
                "Bilgisayarın yeniden başlatılması "
                "gerekebilir."
                if success
                else "TCP/IP stack sıfırlanamadı."
            ),
            output=output,
            requires_restart=success,
        )

    @staticmethod
    def execute(
        action_id: str,
        adapter_name: Optional[str] = None,
    ) -> RepairResult:

        if action_id == "renew_dhcp":
            return RepairService.renew_dhcp(
                adapter_name
            )

        if action_id == "flush_dns":
            return RepairService.flush_dns()

        if action_id == "clear_arp":
            return RepairService.clear_arp()

        if action_id == "restart_adapter":
            if not adapter_name:
                return RepairResult(
                    action_id=action_id,
                    title="Ağ Adaptörünü Yeniden Başlat",
                    success=False,
                    message=(
                        "Adaptör adı belirtilmedi."
                    ),
                )

            return RepairService.restart_adapter(
                adapter_name
            )

        if action_id == "reset_winsock":
            return RepairService.reset_winsock()

        if action_id == "reset_tcp_ip":
            return RepairService.reset_tcp_ip()

        return RepairResult(
            action_id=action_id,
            title="Bilinmeyen İşlem",
            success=False,
            message=(
                f"Bilinmeyen onarım işlemi: "
                f"{action_id}"
            ),
        )

    @staticmethod
    def _admin_required(
        action_id: str,
        title: str,
        requires_restart: bool = False,
    ) -> RepairResult:

        return RepairResult(
            action_id=action_id,
            title=title,
            success=False,
            message=(
                "Bu işlem yönetici yetkisi gerektiriyor. "
                "Network Doctor'u Yönetici olarak "
                "çalıştırın."
            ),
            requires_restart=requires_restart,
        )

    @staticmethod
    def _dhcp_renew_success(
        output: str
    ) -> bool:

        lower = output.lower()

        error_terms = (
            "unable to contact",
            "dhcp server",
            "timed out",
            "media disconnected",
            "general failure",
            "erişilemiyor",
            "bağlantısı kesildi",
            "hata",
        )

        if any(
            term in lower
            for term in error_terms
        ):
            return False

        # Yenileme sonucunda IPv4 görünmesi
        # çoğu durumda yeterli göstergedir.
        return (
            "ipv4" in lower
            or "ip address" in lower
            or bool(output.strip())
        )

    @staticmethod
    def _looks_like_error(
        output: str
    ) -> bool:

        lower = output.lower()

        error_terms = (
            "access is denied",
            "erişim engellendi",
            "error",
            "failed",
            "failure",
            "hata",
            "cannot",
            "could not",
            "not recognized",
        )

        return any(
            term in lower
            for term in error_terms
        )