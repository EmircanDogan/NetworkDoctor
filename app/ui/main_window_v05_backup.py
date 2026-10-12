from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QProgressBar,
    QFrame,
    QTextEdit,
    QCheckBox,
    QMessageBox,
    QScrollArea,
)

from app.network.adapters import AdapterService
from app.network.diagnostics import DiagnosticService
from app.repairs.repair_actions import RepairService
from app.repairs.repair_engine import RepairEngine


# =========================================================
# DIAGNOSTIC WORKER
# =========================================================
class DiagnosticWorker(QThread):
    progress = Signal(int, str, str, bool)
    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter

    def run(self):
        try:
            # 1 - PHYSICAL
            self.progress.emit(
                8,
                "Ağ adaptörü kontrol ediliyor...",
                "physical",
                False,
            )

            physical_ok = DiagnosticService.test_physical_link(
                self.adapter
            )

            self.progress.emit(
                18,
                "Fiziksel bağlantı kontrol edildi.",
                "physical",
                physical_ok,
            )

            if not physical_ok:
                result = DiagnosticService.analyze(
                    adapter=self.adapter,
                    physical_link_ok=False,
                    valid_ip=False,
                    dhcp_ok=False,
                    apipa=False,
                    gateway_ok=False,
                    internet_ok=False,
                    dns_ok=False,
                )

                self.progress.emit(
                    100,
                    "Tarama tamamlandı.",
                    "done",
                    False,
                )

                self.finished_result.emit(result)
                return

            # 2 - IPv4
            self.progress.emit(
                25,
                "IPv4 yapılandırması kontrol ediliyor...",
                "ip",
                False,
            )

            valid_ip, apipa = DiagnosticService.test_ip(
                self.adapter
            )

            self.progress.emit(
                35,
                "IPv4 kontrolü tamamlandı.",
                "ip",
                valid_ip,
            )

            if not valid_ip:
                result = DiagnosticService.analyze(
                    adapter=self.adapter,
                    physical_link_ok=True,
                    valid_ip=False,
                    dhcp_ok=False,
                    apipa=apipa,
                    gateway_ok=False,
                    internet_ok=False,
                    dns_ok=False,
                )

                self.progress.emit(
                    100,
                    "Tarama tamamlandı.",
                    "done",
                    False,
                )

                self.finished_result.emit(result)
                return

            # 3 - DHCP
            self.progress.emit(
                40,
                "DHCP yapılandırması inceleniyor...",
                "dhcp",
                False,
            )

            dhcp_ok = DiagnosticService.test_dhcp(
                self.adapter
            )

            self.progress.emit(
                48,
                "DHCP kontrolü tamamlandı.",
                "dhcp",
                dhcp_ok,
            )

            # 4 - GATEWAY
            self.progress.emit(
                52,
                "Default Gateway test ediliyor...",
                "gateway",
                False,
            )

            gateway_ok, gateway_latency = (
                DiagnosticService.test_gateway(
                    self.adapter
                )
            )

            self.progress.emit(
                63,
                "Gateway testi tamamlandı.",
                "gateway",
                gateway_ok,
            )

            if not gateway_ok:
                result = DiagnosticService.analyze(
                    adapter=self.adapter,
                    physical_link_ok=True,
                    valid_ip=True,
                    dhcp_ok=dhcp_ok,
                    apipa=False,
                    gateway_ok=False,
                    internet_ok=False,
                    dns_ok=False,
                    gateway_latency=gateway_latency,
                )

                self.progress.emit(
                    100,
                    "Tarama tamamlandı.",
                    "done",
                    False,
                )

                self.finished_result.emit(result)
                return

            # 5 - INTERNET
            self.progress.emit(
                68,
                "Internet çıkışı test ediliyor...",
                "internet",
                False,
            )

            internet_ok, internet_latency = (
                DiagnosticService.test_internet()
            )

            self.progress.emit(
                80,
                "Internet testi tamamlandı.",
                "internet",
                internet_ok,
            )

            if not internet_ok:
                result = DiagnosticService.analyze(
                    adapter=self.adapter,
                    physical_link_ok=True,
                    valid_ip=True,
                    dhcp_ok=dhcp_ok,
                    apipa=False,
                    gateway_ok=True,
                    internet_ok=False,
                    dns_ok=False,
                    gateway_latency=gateway_latency,
                    internet_latency=internet_latency,
                )

                self.progress.emit(
                    100,
                    "Tarama tamamlandı.",
                    "done",
                    False,
                )

                self.finished_result.emit(result)
                return

            # 6 - DNS
            self.progress.emit(
                84,
                "DNS çözümleme test ediliyor...",
                "dns",
                False,
            )

            dns_ok, resolved_ip = (
                DiagnosticService.test_dns()
            )

            self.progress.emit(
                94,
                "DNS testi tamamlandı.",
                "dns",
                dns_ok,
            )

            # 7 - ANALYSIS
            self.progress.emit(
                97,
                "Teşhis motoru sonuçları analiz ediyor...",
                "analysis",
                True,
            )

            result = DiagnosticService.analyze(
                adapter=self.adapter,
                physical_link_ok=True,
                valid_ip=True,
                dhcp_ok=dhcp_ok,
                apipa=False,
                gateway_ok=True,
                internet_ok=True,
                dns_ok=dns_ok,
                gateway_latency=gateway_latency,
                internet_latency=internet_latency,
                resolved_ip=resolved_ip,
            )

            self.progress.emit(
                100,
                "Tarama tamamlandı.",
                "done",
                True,
            )

            self.finished_result.emit(result)

        except Exception as exc:
            self.failed.emit(str(exc))


# =========================================================
# REPAIR WORKER
# =========================================================
class RepairWorker(QThread):
    action_finished = Signal(object)
    all_finished = Signal()
    failed = Signal(str)

    def __init__(self, actions, adapter_name):
        super().__init__()
        self.actions = actions
        self.adapter_name = adapter_name

    def run(self):
        try:
            for action_id in self.actions:
                result = RepairService.execute(
                    action_id,
                    self.adapter_name,
                )

                self.action_finished.emit(result)

            self.all_finished.emit()

        except Exception as exc:
            self.failed.emit(str(exc))


# =========================================================
# MAIN WINDOW
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.adapters = []
        self.worker = None
        self.repair_worker = None
        self.last_result = None
        self.repair_checkboxes = {}

        self.setWindowTitle("Network Doctor")
        self.resize(1050, 850)
        self.setMinimumSize(850, 650)

        self.build_ui()
        self.load_adapters()

    # =====================================================
    # BUILD UI
    # =====================================================
    def build_ui(self):
        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.setCentralWidget(scroll_area)

        root = QWidget()
        scroll_area.setWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )
        main_layout.setSpacing(16)

        # -------------------------------------------------
        # TITLE
        # -------------------------------------------------
        title = QLabel("NETWORK DOCTOR")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            """
            font-size: 30px;
            font-weight: 700;
            """
        )

        subtitle = QLabel(
            "Windows Network Diagnostic & Repair Utility"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            """
            font-size: 13px;
            color: #777;
            """
        )

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # -------------------------------------------------
        # ADAPTER CARD
        # -------------------------------------------------
        adapter_card = QFrame()
        adapter_card.setFrameShape(QFrame.StyledPanel)

        adapter_layout = QVBoxLayout(adapter_card)

        adapter_title = QLabel("Ağ Adaptörü")
        adapter_title.setStyleSheet(
            """
            font-size: 15px;
            font-weight: 600;
            """
        )

        self.adapter_combo = QComboBox()
        self.adapter_combo.setMinimumHeight(38)

        self.adapter_combo.currentIndexChanged.connect(
            self.update_adapter_info
        )

        adapter_layout.addWidget(adapter_title)
        adapter_layout.addWidget(self.adapter_combo)

        self.adapter_info = QLabel()
        self.adapter_info.setWordWrap(True)
        self.adapter_info.setStyleSheet(
            """
            padding: 10px;
            font-family: Consolas;
            font-size: 13px;
            """
        )

        adapter_layout.addWidget(self.adapter_info)
        main_layout.addWidget(adapter_card)

        # -------------------------------------------------
        # TEST BUTTON
        # -------------------------------------------------
        self.test_button = QPushButton(
            "AĞI TEST ET"
        )

        self.test_button.setMinimumHeight(58)

        self.test_button.clicked.connect(
            self.start_diagnostic
        )

        self.test_button.setStyleSheet(
            """
            QPushButton {
                font-size: 19px;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px;
            }
            """
        )

        main_layout.addWidget(self.test_button)

        # -------------------------------------------------
        # PROGRESS
        # -------------------------------------------------
        progress_card = QFrame()
        progress_card.setFrameShape(QFrame.StyledPanel)

        progress_layout = QVBoxLayout(progress_card)

        self.progress_status = QLabel("Hazır")
        self.progress_status.setAlignment(Qt.AlignCenter)
        self.progress_status.setStyleSheet(
            """
            font-size: 14px;
            font-weight: 600;
            """
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(30)

        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #777;
                border-radius: 8px;
                text-align: center;
                height: 26px;
                font-weight: 600;
            }

            QProgressBar::chunk {
                border-radius: 7px;
            }
            """
        )

        progress_layout.addWidget(
            self.progress_status
        )

        progress_layout.addWidget(
            self.progress_bar
        )

        main_layout.addWidget(
            progress_card
        )

        # -------------------------------------------------
        # TEST RESULTS
        # -------------------------------------------------
        status_card = QFrame()
        status_card.setFrameShape(QFrame.StyledPanel)

        status_layout = QVBoxLayout(status_card)

        status_title = QLabel("Test Sonuçları")
        status_title.setStyleSheet(
            """
            font-size: 15px;
            font-weight: 600;
            """
        )

        status_layout.addWidget(status_title)

        self.physical_label = QLabel(
            "Fiziksel Link     ○"
        )

        self.ip_label = QLabel(
            "IPv4              ○"
        )

        self.dhcp_label = QLabel(
            "DHCP              ○"
        )

        self.gateway_label = QLabel(
            "Gateway           ○"
        )

        self.internet_label = QLabel(
            "Internet          ○"
        )

        self.dns_label = QLabel(
            "DNS               ○"
        )

        for label in (
            self.physical_label,
            self.ip_label,
            self.dhcp_label,
            self.gateway_label,
            self.internet_label,
            self.dns_label,
        ):
            label.setStyleSheet(
                """
                font-family: Consolas;
                font-size: 14px;
                padding: 3px;
                """
            )

            status_layout.addWidget(label)

        main_layout.addWidget(status_card)

        # -------------------------------------------------
        # DIAGNOSIS
        # -------------------------------------------------
        diagnosis_card = QFrame()
        diagnosis_card.setFrameShape(QFrame.StyledPanel)

        diagnosis_layout = QVBoxLayout(
            diagnosis_card
        )

        diagnosis_title = QLabel("Teşhis")
        diagnosis_title.setStyleSheet(
            """
            font-size: 15px;
            font-weight: 600;
            """
        )

        self.diagnosis_output = QTextEdit()
        self.diagnosis_output.setReadOnly(True)
        self.diagnosis_output.setMinimumHeight(130)

        diagnosis_layout.addWidget(
            diagnosis_title
        )

        diagnosis_layout.addWidget(
            self.diagnosis_output
        )

        main_layout.addWidget(
            diagnosis_card
        )

        # -------------------------------------------------
        # REPAIR CARD
        # -------------------------------------------------
        self.repair_card = QFrame()
        self.repair_card.setFrameShape(
            QFrame.StyledPanel
        )

        self.repair_layout = QVBoxLayout(
            self.repair_card
        )

        repair_title = QLabel(
            "Ağ Onarım Araçları"
        )

        repair_title.setStyleSheet(
            """
            font-size: 15px;
            font-weight: 600;
            """
        )

        self.repair_layout.addWidget(
            repair_title
        )

        self.admin_label = QLabel()
        self.repair_layout.addWidget(
            self.admin_label
        )

        self.repair_info_label = QLabel(
            "Önce ağ testi çalıştırın."
        )
        self.repair_info_label.setWordWrap(True)

        self.repair_layout.addWidget(
            self.repair_info_label
        )

        self.repair_button = QPushButton(
            "SEÇİLEN ONARIMLARI UYGULA"
        )

        self.repair_button.setMinimumHeight(50)

        self.repair_button.setStyleSheet(
            """
            QPushButton {
                font-size: 15px;
                font-weight: 700;
                padding: 10px;
                border-radius: 7px;
            }

            QPushButton:disabled {
                color: #888;
            }
            """
        )

        self.repair_button.setEnabled(False)

        self.repair_button.clicked.connect(
            self.apply_selected_repairs
        )

        self.repair_layout.addWidget(
            self.repair_button
        )

        self.repair_output = QTextEdit()
        self.repair_output.setReadOnly(True)
        self.repair_output.setMinimumHeight(110)

        self.repair_layout.addWidget(
            self.repair_output
        )

        main_layout.addWidget(
            self.repair_card
        )

        main_layout.addStretch()

        self.statusBar().showMessage(
            "Network Doctor hazır."
        )

        self.update_admin_status()

    # =====================================================
    # ADMIN STATUS
    # =====================================================
    def update_admin_status(self):
        if RepairService.is_admin():
            self.admin_label.setText(
                "Yönetici Yetkisi: ✓ Aktif"
            )
        else:
            self.admin_label.setText(
                "Yönetici Yetkisi: ✗ Aktif değil"
            )

    # =====================================================
    # ADAPTERS
    # =====================================================
    def load_adapters(self):
        self.adapters = (
            AdapterService.get_adapters()
        )

        self.adapter_combo.blockSignals(True)
        self.adapter_combo.clear()

        for adapter in self.adapters:
            label = (
                f"{adapter.name} — "
                f"{adapter.description}"
            )

            self.adapter_combo.addItem(label)

        self.adapter_combo.blockSignals(False)

        if not self.adapters:
            self.adapter_info.setText(
                "Ağ adaptörü bulunamadı."
            )

            self.test_button.setEnabled(False)

            return

        connected_index = 0

        for index, adapter in enumerate(
            self.adapters
        ):
            if adapter.is_connected:
                connected_index = index
                break

        self.adapter_combo.setCurrentIndex(
            connected_index
        )

        self.update_adapter_info()

    def get_selected_adapter(self):
        index = (
            self.adapter_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(self.adapters)
        ):
            return None

        return self.adapters[index]

    def update_adapter_info(self):
        adapter = (
            self.get_selected_adapter()
        )

        if not adapter:
            self.adapter_info.setText(
                "Adaptör bulunamadı."
            )
            return

        status = (
            "Bağlı"
            if adapter.is_connected
            else "Bağlı değil"
        )

        ipv4 = adapter.ipv4 or "-"
        subnet = adapter.subnet_mask or "-"
        gateway = adapter.gateway or "-"

        dns = (
            ", ".join(
                adapter.dns_servers
            )
            if adapter.dns_servers
            else "-"
        )

        dhcp_state = (
            "Açık"
            if adapter.dhcp_enabled
            else "Kapalı / Statik"
        )

        dhcp_server = (
            adapter.dhcp_server
            if adapter.dhcp_server
            else "-"
        )

        mac_address = (
            adapter.mac_address
            if adapter.mac_address
            else "-"
        )

        self.adapter_info.setText(
            f"Durum        : {status}\n"
            f"Link Speed   : "
            f"{adapter.link_speed_mbps} Mbps\n"
            f"IPv4         : {ipv4}\n"
            f"Subnet       : {subnet}\n"
            f"Gateway      : {gateway}\n"
            f"DHCP         : {dhcp_state}\n"
            f"DHCP Server  : {dhcp_server}\n"
            f"DNS          : {dns}\n"
            f"MAC          : {mac_address}"
        )

        self.reset_results()

    # =====================================================
    # RESET
    # =====================================================
    def reset_results(self):
        self.progress_bar.setValue(0)
        self.progress_status.setText("Hazır")

        self.physical_label.setText(
            "Fiziksel Link     ○"
        )

        self.ip_label.setText(
            "IPv4              ○"
        )

        self.dhcp_label.setText(
            "DHCP              ○"
        )

        self.gateway_label.setText(
            "Gateway           ○"
        )

        self.internet_label.setText(
            "Internet          ○"
        )

        self.dns_label.setText(
            "DNS               ○"
        )

        self.diagnosis_output.clear()
        self.repair_output.clear()

        self.clear_repair_options()

        self.repair_info_label.setText(
            "Önce ağ testi çalıştırın."
        )

        self.last_result = None

    def clear_repair_options(self):
        for checkbox in (
            self.repair_checkboxes.values()
        ):
            self.repair_layout.removeWidget(
                checkbox
            )

            checkbox.deleteLater()

        self.repair_checkboxes.clear()

        self.repair_button.setEnabled(False)

    # =====================================================
    # DIAGNOSTIC START
    # =====================================================
    def start_diagnostic(self):
        adapter = (
            self.get_selected_adapter()
        )

        if not adapter:
            return

        refreshed = (
            AdapterService.get_adapter_by_name(
                adapter.name
            )
        )

        if refreshed:
            adapter = refreshed

            index = (
                self.adapter_combo.currentIndex()
            )

            if (
                index >= 0
                and index < len(self.adapters)
            ):
                self.adapters[index] = refreshed

        self.reset_results()

        self.test_button.setEnabled(False)
        self.adapter_combo.setEnabled(False)

        self.progress_status.setText(
            "Ağ taraması başlatılıyor..."
        )

        self.worker = DiagnosticWorker(
            adapter
        )

        self.worker.progress.connect(
            self.update_progress
        )

        self.worker.finished_result.connect(
            self.show_result
        )

        self.worker.failed.connect(
            self.show_error
        )

        self.worker.start()

    # =====================================================
    # PROGRESS
    # =====================================================
    def update_progress(
        self,
        value,
        message,
        stage,
        success,
    ):
        self.progress_bar.setValue(value)
        self.progress_status.setText(message)

        pending = "◉ TEST EDİLİYOR"
        passed = "✓ BAŞARILI"
        failed = "✗ BAŞARISIZ"

        text = (
            passed
            if success
            else failed
        )

        if stage == "physical":
            if value < 18:
                text = pending

            self.physical_label.setText(
                f"Fiziksel Link     {text}"
            )

        elif stage == "ip":
            if value < 35:
                text = pending

            self.ip_label.setText(
                f"IPv4              {text}"
            )

        elif stage == "dhcp":
            if value < 48:
                text = pending

            self.dhcp_label.setText(
                f"DHCP              {text}"
            )

        elif stage == "gateway":
            if value < 63:
                text = pending

            self.gateway_label.setText(
                f"Gateway           {text}"
            )

        elif stage == "internet":
            if value < 80:
                text = pending

            self.internet_label.setText(
                f"Internet          {text}"
            )

        elif stage == "dns":
            if value < 94:
                text = pending

            self.dns_label.setText(
                f"DNS               {text}"
            )

        elif stage == "analysis":
            self.progress_status.setText(
                "Teşhis motoru analiz yapıyor..."
            )

        elif stage == "done":
            self.progress_status.setText(
                "Tarama tamamlandı"
            )

    # =====================================================
    # RESULT
    # =====================================================
    def show_result(self, result):
        self.test_button.setEnabled(True)
        self.adapter_combo.setEnabled(True)

        self.last_result = result

        self.progress_bar.setValue(100)
        self.progress_status.setText(
            "Tarama tamamlandı"
        )

        self.physical_label.setText(
            "Fiziksel Link     "
            + (
                "✓ BAŞARILI"
                if result.physical_link_ok
                else "✗ BAŞARISIZ"
            )
        )

        self.ip_label.setText(
            "IPv4              "
            + (
                "✓ BAŞARILI"
                if result.valid_ip
                else "✗ BAŞARISIZ"
            )
        )

        self.dhcp_label.setText(
            "DHCP              "
            + (
                "✓ BAŞARILI"
                if result.dhcp_ok
                else "✗ BAŞARISIZ"
            )
        )

        gateway_text = (
            "✓ BAŞARILI"
            if result.gateway_ok
            else "✗ BAŞARISIZ"
        )

        if (
            result.gateway_latency_ms
            is not None
        ):
            gateway_text += (
                f" "
                f"({result.gateway_latency_ms} ms)"
            )

        self.gateway_label.setText(
            f"Gateway           "
            f"{gateway_text}"
        )

        internet_text = (
            "✓ BAŞARILI"
            if result.internet_ok
            else "✗ BAŞARISIZ"
        )

        if (
            result.internet_latency_ms
            is not None
        ):
            internet_text += (
                f" "
                f"({result.internet_latency_ms} ms)"
            )

        self.internet_label.setText(
            f"Internet          "
            f"{internet_text}"
        )

        dns_text = (
            "✓ BAŞARILI"
            if result.dns_ok
            else "✗ BAŞARISIZ"
        )

        if result.dns_resolved_ip:
            dns_text += (
                f" "
                f"({result.dns_resolved_ip})"
            )

        self.dns_label.setText(
            f"DNS               "
            f"{dns_text}"
        )

        severity_title = {
            "success": "BAĞLANTI SAĞLIKLI",
            "warning": "UYARI",
            "critical": (
                "ARIZA TESPİT EDİLDİ"
            ),
            "info": "BİLGİ",
        }.get(
            result.severity,
            "SONUÇ",
        )

        self.diagnosis_output.setPlainText(
            f"{severity_title}\n\n"
            f"{result.diagnosis}"
        )

        self.populate_repair_options(
            result
        )

        self.statusBar().showMessage(
            "Ağ testi tamamlandı."
        )

    # =====================================================
    # REPAIR OPTIONS
    # =====================================================
    def populate_repair_options(
        self,
        result,
    ):
        self.clear_repair_options()

        adapter = (
            self.get_selected_adapter()
        )

        if not adapter:
            return

        recommendations = (
            RepairEngine.get_recommendations(
                adapter,
                result,
            )
        )

        any_recommended = any(
            recommendation.recommended
            for recommendation in recommendations
        )

        if any_recommended:
            self.repair_info_label.setText(
                "⚠ Tespit edilen sorun için "
                "önerilen işlemler otomatik seçildi."
            )
        else:
            self.repair_info_label.setText(
                "✓ Şu anda otomatik önerilen "
                "bir onarım bulunmuyor."
            )

        for recommendation in recommendations:
            suffix_parts = []

            if recommendation.recommended:
                suffix_parts.append(
                    "ÖNERİLEN"
                )

            if recommendation.requires_admin:
                suffix_parts.append(
                    "ADMIN"
                )

            if recommendation.requires_restart:
                suffix_parts.append(
                    "RESTART"
                )

            suffix = ""

            if suffix_parts:
                suffix = (
                    "  ["
                    + " | ".join(
                        suffix_parts
                    )
                    + "]"
                )

            checkbox = QCheckBox(
                recommendation.title + suffix
            )

            admin_blocked = (
                recommendation.requires_admin
                and not RepairService.is_admin()
            )

            if admin_blocked:
                checkbox.setEnabled(False)
                checkbox.setChecked(False)

                checkbox.setToolTip(
                    recommendation.description
                    + "\n\nBu işlem yönetici "
                    "yetkisi gerektiriyor."
                )

            else:
                checkbox.setChecked(
                    recommendation.recommended
                )

                checkbox.setToolTip(
                    recommendation.description
                )

            checkbox.stateChanged.connect(
                self.update_repair_button_state
            )

            self.repair_checkboxes[
                recommendation.action_id
            ] = checkbox

            # Butondan önce checkbox ekle
            insert_index = (
                self.repair_layout.indexOf(
                    self.repair_button
                )
            )

            self.repair_layout.insertWidget(
                insert_index,
                checkbox,
            )

        self.update_repair_button_state()

    def update_repair_button_state(self):
        any_checked = any(
            checkbox.isChecked()
            and checkbox.isEnabled()
            for checkbox
            in self.repair_checkboxes.values()
        )

        self.repair_button.setEnabled(
            any_checked
        )

    # =====================================================
    # APPLY REPAIRS
    # =====================================================
    def apply_selected_repairs(self):
        adapter = (
            self.get_selected_adapter()
        )

        if not adapter:
            return

        selected_actions = [
            action_id
            for action_id, checkbox
            in self.repair_checkboxes.items()
            if (
                checkbox.isChecked()
                and checkbox.isEnabled()
            )
        ]

        if not selected_actions:
            return

        dangerous = {
            "reset_winsock",
            "reset_tcp_ip",
        }

        if any(
            action in dangerous
            for action in selected_actions
        ):
            answer = QMessageBox.warning(
                self,
                "Gelişmiş Ağ Onarımı",
                (
                    "Winsock veya TCP/IP "
                    "sıfırlama seçildi.\n\n"
                    "Bu işlemler mevcut ağ "
                    "yapılandırmasını etkileyebilir "
                    "ve yeniden başlatma "
                    "gerektirebilir.\n\n"
                    "Devam etmek istiyor musunuz?"
                ),
                QMessageBox.Yes
                | QMessageBox.No,
                QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                return

        admin_required_actions = {
            "clear_arp",
            "restart_adapter",
            "reset_winsock",
            "reset_tcp_ip",
        }

        if (
            any(
                action in admin_required_actions
                for action in selected_actions
            )
            and not RepairService.is_admin()
        ):
            QMessageBox.information(
                self,
                "Yönetici Yetkisi Gerekli",
                (
                    "Seçilen işlemlerden en az biri "
                    "yönetici yetkisi gerektiriyor.\n\n"
                    "Network Doctor'u Yönetici "
                    "olarak çalıştırıp tekrar deneyin."
                ),
            )

            return

        self.repair_output.clear()

        self.repair_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.adapter_combo.setEnabled(False)

        self.repair_output.append(
            "Onarım işlemleri başlatılıyor...\n"
        )

        self.repair_worker = RepairWorker(
            selected_actions,
            adapter.name,
        )

        self.repair_worker.action_finished.connect(
            self.on_repair_action_finished
        )

        self.repair_worker.all_finished.connect(
            self.on_repairs_finished
        )

        self.repair_worker.failed.connect(
            self.on_repair_error
        )

        self.repair_worker.start()

    # =====================================================
    # REPAIR RESULT
    # =====================================================
    def on_repair_action_finished(
        self,
        result,
    ):
        status = (
            "✓"
            if result.success
            else "✗"
        )

        self.repair_output.append(
            f"{status} {result.title}\n"
            f"   {result.message}\n"
        )

        if result.requires_restart:
            self.repair_output.append(
                "   ⚠ Yeniden başlatma "
                "gerekebilir.\n"
            )

    def on_repairs_finished(self):
        self.repair_output.append(
            "\nOnarım işlemleri tamamlandı."
        )

        self.test_button.setEnabled(True)
        self.adapter_combo.setEnabled(True)

        self.update_repair_button_state()

        self.statusBar().showMessage(
            "Onarım işlemleri tamamlandı."
        )

        QMessageBox.information(
            self,
            "Onarım Tamamlandı",
            (
                "Seçilen ağ onarımları "
                "tamamlandı.\n\n"
                "Sonucu doğrulamak için tekrar "
                "\"AĞI TEST ET\" "
                "çalıştırabilirsiniz."
            ),
        )

    def on_repair_error(
        self,
        message,
    ):
        self.test_button.setEnabled(True)
        self.adapter_combo.setEnabled(True)

        self.update_repair_button_state()

        self.repair_output.append(
            "\nBeklenmeyen hata:\n"
            f"{message}"
        )

    # =====================================================
    # GENERAL ERROR
    # =====================================================
    def show_error(
        self,
        message,
    ):
        self.test_button.setEnabled(True)
        self.adapter_combo.setEnabled(True)

        self.progress_status.setText(
            "Test sırasında hata oluştu."
        )

        self.diagnosis_output.setPlainText(
            "Beklenmeyen hata:\n\n"
            f"{message}"
        )

        self.statusBar().showMessage(
            "Test sırasında hata oluştu."
        )