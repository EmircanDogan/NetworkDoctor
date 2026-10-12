import sys
import socket
import subprocess
import re
import psutil

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PySide6.QtCore import Qt


class NetworkDoctor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Network Doctor")
        self.resize(900, 700)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        title = QLabel("NETWORK DOCTOR")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            margin: 15px;
        """)

        self.status_label = QLabel("Hazır")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.test_button = QPushButton("AĞI TEST ET")
        self.test_button.setMinimumHeight(60)
        self.test_button.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
        """)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.test_button)
        layout.addWidget(self.output)

        self.test_button.clicked.connect(self.run_tests)

    # -------------------------------------------------------
    # WINDOWS KOMUT ÇALIŞTIRMA
    # Encoding hatasına dayanıklı
    # -------------------------------------------------------
    def run_command(self, command, timeout=15):
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                timeout=timeout
            )

            # Önce Windows Türkçe OEM codepage
            try:
                stdout = result.stdout.decode("cp857")
            except UnicodeDecodeError:
                stdout = result.stdout.decode("utf-8", errors="replace")

            try:
                stderr = result.stderr.decode("cp857")
            except UnicodeDecodeError:
                stderr = result.stderr.decode("utf-8", errors="replace")

            output = stdout.strip()

            if stderr.strip():
                output += "\n" + stderr.strip()

            return output

        except subprocess.TimeoutExpired:
            return "Komut zaman aşımına uğradı."

        except Exception as e:
            return f"Hata: {e}"

    # -------------------------------------------------------
    # AKTİF ETHERNET ADAPTÖRÜ
    # -------------------------------------------------------
    def get_active_ethernet(self):
        stats = psutil.net_if_stats()
        addresses = psutil.net_if_addrs()

        candidates = []

        for adapter, adapter_stats in stats.items():

            name_lower = adapter.lower()

            # Wi-Fi / Bluetooth / sanal adaptörleri atla
            if (
                "wi-fi" in name_lower
                or "wifi" in name_lower
                or "bluetooth" in name_lower
                or "loopback" in name_lower
                or "virtual" in name_lower
            ):
                continue

            ipv4 = None
            subnet = None

            if adapter in addresses:
                for addr in addresses[adapter]:
                    if addr.family == socket.AF_INET:
                        ipv4 = addr.address
                        subnet = addr.netmask

            if ipv4:
                candidates.append({
                    "name": adapter,
                    "up": adapter_stats.isup,
                    "speed": adapter_stats.speed,
                    "ipv4": ipv4,
                    "subnet": subnet
                })

        # Önce UP olanı tercih et
        for adapter in candidates:
            if adapter["up"]:
                return adapter

        if candidates:
            return candidates[0]

        return None

    # -------------------------------------------------------
    # GATEWAY OTOMATİK BULMA
    # -------------------------------------------------------
    def get_default_gateway(self):
        output = self.run_command("route print -4")

        # 0.0.0.0   0.0.0.0   gateway şeklindeki satırı bul
        pattern = r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)"

        for line in output.splitlines():
            match = re.search(pattern, line)

            if match:
                return match.group(1)

        return None

    # -------------------------------------------------------
    # PING
    # -------------------------------------------------------
    def ping_test(self, host):
        if not host:
            return False, None

        output = self.run_command(
            f'ping -n 2 -w 1500 "{host}"',
            timeout=8
        )

        success = "TTL=" in output.upper()

        latency = None

        # time=19ms veya time<1ms
        match = re.search(
            r"(?:time|süre)[=<]\s*(\d+)\s*ms",
            output,
            re.IGNORECASE
        )

        if match:
            latency = int(match.group(1))

        return success, latency

    # -------------------------------------------------------
    # DNS TESTİ
    # -------------------------------------------------------
    def dns_test(self):
        try:
            ip = socket.gethostbyname("google.com")
            return True, ip

        except socket.gaierror:
            return False, None

    # -------------------------------------------------------
    # ANA TEST
    # -------------------------------------------------------
    def run_tests(self):
        self.test_button.setEnabled(False)
        self.output.clear()
        self.status_label.setText("Testler çalışıyor...")

        QApplication.processEvents()

        results = []

        adapter = self.get_active_ethernet()

        results.append("========== NETWORK DOCTOR ==========\n")

        # ADAPTÖR YOK
        if not adapter:
            results.append("❌ Ethernet adaptörü bulunamadı.")
            results.append("")
            results.append("OLASI NEDENLER:")
            results.append("• Ethernet kablosu takılı değil")
            results.append("• Ağ adaptörü devre dışı")
            results.append("• Sürücü problemi")
            results.append("• USB Ethernet adaptörü algılanmadı")

            self.finish(results)
            return

        # ---------------------------------------------------
        # ADAPTÖR BİLGİLERİ
        # ---------------------------------------------------
        results.append("=== ETHERNET ===")
        results.append(f"Adaptör       : {adapter['name']}")
        results.append(
            f"Durum         : {'BAĞLI' if adapter['up'] else 'BAĞLI DEĞİL'}"
        )
        results.append(f"Link Speed    : {adapter['speed']} Mbps")
        results.append(f"IPv4          : {adapter['ipv4']}")
        results.append(f"Subnet Mask   : {adapter['subnet']}")

        gateway = self.get_default_gateway()

        results.append(
            f"Default Gateway: {gateway if gateway else 'YOK'}"
        )

        ip = adapter["ipv4"]

        apipa = ip.startswith("169.254.")

        # ---------------------------------------------------
        # TESTLER
        # ---------------------------------------------------
        results.append("\n=== TESTLER ===")

        if adapter["up"]:
            results.append("Fiziksel Link : ✅ BAŞARILI")
        else:
            results.append("Fiziksel Link : ❌ BAŞARISIZ")

        if apipa:
            results.append("DHCP / IP     : ❌ APIPA (169.254.x.x)")
        else:
            results.append("DHCP / IP     : ✅ IP ALINDI")

        gateway_ok = False

        if gateway:
            gateway_ok, gateway_latency = self.ping_test(gateway)

            if gateway_ok:
                latency_text = (
                    f" ({gateway_latency} ms)"
                    if gateway_latency is not None
                    else ""
                )

                results.append(
                    f"Gateway       : ✅ BAŞARILI{latency_text}"
                )

            else:
                results.append("Gateway       : ❌ BAŞARISIZ")

        else:
            results.append("Gateway       : ❌ YOK")

        internet_ok, internet_latency = self.ping_test("1.1.1.1")

        if internet_ok:
            latency_text = (
                f" ({internet_latency} ms)"
                if internet_latency is not None
                else ""
            )

            results.append(
                f"Internet      : ✅ BAŞARILI{latency_text}"
            )
        else:
            results.append("Internet      : ❌ BAŞARISIZ")

        dns_ok, resolved_ip = self.dns_test()

        if dns_ok:
            results.append(
                f"DNS           : ✅ BAŞARILI ({resolved_ip})"
            )
        else:
            results.append("DNS           : ❌ BAŞARISIZ")

        # ---------------------------------------------------
        # ANALİZ MOTORU
        # ---------------------------------------------------
        results.append("\n=== TEŞHİS ===")

        diagnosis = []

        # Kablo tamamen yok
        if not adapter["up"]:

            diagnosis.append(
                "🔴 Fiziksel Ethernet bağlantısı bulunamadı."
            )

            diagnosis.append(
                "CAT kablosu, RJ45 uçları ve switch portunu kontrol edin."
            )

        # APIPA
        elif apipa:

            diagnosis.append(
                "🔴 Fiziksel bağlantı var fakat DHCP'den IP alınamıyor."
            )

            diagnosis.append("")
            diagnosis.append("Olası nedenler:")

            diagnosis.append(
                "• CAT5e/CAT6 kablosunda damar veya sonlandırma problemi"
            )

            diagnosis.append(
                "• Switch portu / VLAN problemi"
            )

            diagnosis.append(
                "• DHCP sunucusuna erişilemiyor"
            )

            diagnosis.append(
                "• Switch uplink problemi"
            )

            diagnosis.append(
                "• Yanlış yapılandırılmış router / access point"
            )

        # Gateway yok
        elif not gateway:

            diagnosis.append(
                "🔴 IP alınmış ancak Default Gateway bulunamadı."
            )

            diagnosis.append(
                "DHCP yapılandırması veya statik IP ayarlarını kontrol edin."
            )

        # Gateway erişilemiyor
        elif not gateway_ok:

            diagnosis.append(
                "🔴 Gateway'e erişilemiyor."
            )

            diagnosis.append(
                "Yerel ağ, VLAN veya gateway tarafında problem olabilir."
            )

        # Gateway var internet yok
        elif gateway_ok and not internet_ok:

            diagnosis.append(
                "🟠 Yerel ağ ve gateway çalışıyor fakat internet çıkışı yok."
            )

            diagnosis.append("")
            diagnosis.append("Olası nedenler:")

            diagnosis.append(
                "• Gateway/router WAN bağlantısı"
            )

            diagnosis.append(
                "• Routing problemi"
            )

            diagnosis.append(
                "• Firewall kuralı"
            )

            diagnosis.append(
                "• Yanlış gateway"
            )

        # İnternet var DNS yok
        elif internet_ok and not dns_ok:

            diagnosis.append(
                "🟠 Internet erişimi var fakat DNS çözümleme çalışmıyor."
            )

            diagnosis.append(
                "DNS sunucusu veya istemci DNS ayarlarını kontrol edin."
            )

        else:

            diagnosis.append(
                "🟢 Ağ bağlantısı normal görünüyor."
            )

        # LINK SPEED ANALİZİ
        if adapter["up"]:

            speed = adapter["speed"]

            if 0 < speed <= 100:

                diagnosis.append("")
                diagnosis.append(
                    f"⚠ Link hızı yalnızca {speed} Mbps."
                )

                diagnosis.append(
                    "Gigabit desteklenen bir hatta CAT5e/CAT6 damarları,"
                )

                diagnosis.append(
                    "RJ45 sonlandırması veya switch port hızı kontrol edilmeli."
                )

        results.extend(diagnosis)

        # ---------------------------------------------------
        # ÖNERİLEN İŞLEMLER
        # ---------------------------------------------------
        results.append("\n=== ÖNERİLEN İŞLEMLER ===")

        if apipa:

            results.append("1. DHCP adresini yenile")
            results.append("2. Ethernet adaptörünü yeniden başlat")
            results.append("3. CAT6/RJ45 uçlarını kontrol et")
            results.append("4. Aynı switch portunu kısa kabloyla test et")

        elif internet_ok and not dns_ok:

            results.append("1. DNS cache temizle")
            results.append("2. DNS sunucularını kontrol et")

        elif gateway_ok and not internet_ok:

            results.append("1. Gateway adresini doğrula")
            results.append("2. Router/uplink bağlantısını kontrol et")
            results.append("3. Traceroute çalıştır")

        else:

            results.append("Ek bir onarım gerekli görünmüyor.")

        self.finish(results)

    def finish(self, results):
        self.output.setPlainText("\n".join(results))

        self.status_label.setText("Test tamamlandı")

        self.test_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = NetworkDoctor()
    window.show()

    sys.exit(app.exec())