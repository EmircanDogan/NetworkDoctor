from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
)

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QProgressBar,
    QFrame,
    QTextEdit,
    QCheckBox,
    QMessageBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from app.network.adapters import AdapterService
from app.network.diagnostics import DiagnosticService
from app.network.lan_scanner import LanScanner
from app.network.ip_conflict import IpConflictDetector
from app.network.network_utils import NetworkUtils

from app.repairs.repair_actions import RepairService
from app.repairs.repair_engine import RepairEngine


# =========================================================
# COLORS
# =========================================================

COLOR_BG = "#0B1120"
COLOR_PANEL = "#111827"
COLOR_PANEL_ALT = "#172033"
COLOR_BORDER = "#263247"

COLOR_TEXT = "#F8FAFC"
COLOR_MUTED = "#94A3B8"

COLOR_BLUE = "#3B82F6"
COLOR_BLUE_HOVER = "#2563EB"

COLOR_GREEN = "#22C55E"
COLOR_GREEN_DARK = "#16351F"

COLOR_YELLOW = "#F59E0B"
COLOR_YELLOW_DARK = "#3B2D0B"

COLOR_RED = "#EF4444"
COLOR_RED_DARK = "#3F171B"


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
            # -------------------------------------------------
            # 1 - PHYSICAL
            # -------------------------------------------------
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

            # -------------------------------------------------
            # 2 - IPv4
            # -------------------------------------------------
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

            # -------------------------------------------------
            # 3 - DHCP
            # -------------------------------------------------
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

            # -------------------------------------------------
            # 4 - GATEWAY
            # -------------------------------------------------
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

            # -------------------------------------------------
            # 5 - INTERNET
            # -------------------------------------------------
            self.progress.emit(
                68,
                "Internet çıkışı test ediliyor...",
                "internet",
                False,
            )

            internet_ok, internet_latency = (
                DiagnosticService.test_internet(
                    self.adapter
                )
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

            # -------------------------------------------------
            # 6 - DNS
            # -------------------------------------------------
            self.progress.emit(
                84,
                "DNS çözümleme test ediliyor...",
                "dns",
                False,
            )

            dns_ok, resolved_ip = DiagnosticService.test_dns(
                self.adapter
            )

            self.progress.emit(
                94,
                "DNS testi tamamlandı.",
                "dns",
                dns_ok,
            )

            # -------------------------------------------------
            # 7 - ANALYSIS
            # -------------------------------------------------
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
# LAN SCAN WORKER
# =========================================================

class LanScanWorker(QThread):
    status = Signal(str)
    finished_result = Signal(object, object, object)
    failed = Signal(str)

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter

    def run(self):
        try:
            self.status.emit(
                "Subnet hesaplanıyor..."
            )

            network = NetworkUtils.get_cidr(
                self.adapter
            )

            if not network:
                raise RuntimeError(
                    "Seçili adaptör için geçerli subnet "
                    "bilgisi bulunamadı."
                )

            self.status.emit(
                f"{network} ağı taranıyor..."
            )

            devices = LanScanner.scan(
                self.adapter
            )

            # Yerel bilgisayarın MAC'i Windows ARP
            # tablosunda görünmeyebilir.
            for device in devices:
                if device.ip == self.adapter.ipv4:
                    device.mac_address = (
                        self.adapter.mac_address
                    )

            self.status.emit(
                "IP çakışması kontrol ediliyor..."
            )

            conflict_result = (
                IpConflictDetector.check(
                    self.adapter
                )
            )

            self.status.emit(
                "Boş görünen IP adayları hesaplanıyor..."
            )

            active_ips = {
                device.ip
                for device in devices
            }

            free_candidates = (
                NetworkUtils.get_candidate_free_ips(
                    self.adapter,
                    active_ips,
                    max_results=50,
                )
            )

            self.finished_result.emit(
                devices,
                conflict_result,
                free_candidates,
            )

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
        self.lan_worker = None

        self.last_result = None
        self.last_conflict_result = None
        self.repair_checkboxes = {}
        self.status_cards = {}

        self.progress_animation = None

        self.setWindowTitle(
            "Network Doctor"
        )

        self.resize(
            1180,
            850,
        )

        self.setMinimumSize(
            900,
            650,
        )

        self.build_ui()
        self.apply_theme()
        self.load_adapters()

    # =====================================================
    # GLOBAL THEME
    # =====================================================

    def apply_theme(self):
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLOR_BG};
            }}

            QWidget {{
                color: {COLOR_TEXT};
                font-family: "Segoe UI";
                font-size: 13px;
            }}

            QScrollArea {{
                background-color: {COLOR_BG};
                border: none;
            }}

            QScrollArea > QWidget > QWidget {{
                background-color: {COLOR_BG};
            }}

            QFrame#Card {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}

            QLabel#SectionTitle {{
                font-size: 15px;
                font-weight: 700;
                color: {COLOR_TEXT};
            }}

            QLabel#Muted {{
                color: {COLOR_MUTED};
            }}

            QComboBox {{
                background-color: {COLOR_PANEL_ALT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {COLOR_TEXT};
                min-height: 26px;
            }}

            QComboBox:hover {{
                border: 1px solid {COLOR_BLUE};
            }}

            QComboBox::drop-down {{
                border: none;
                width: 32px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                selection-background-color: {COLOR_BLUE};
            }}

            QPushButton {{
                background-color: {COLOR_BLUE};
                color: white;
                border: none;
                border-radius: 9px;
                padding: 10px 16px;
                font-weight: 700;
            }}

            QPushButton:hover {{
                background-color: {COLOR_BLUE_HOVER};
            }}

            QPushButton:pressed {{
                background-color: #1D4ED8;
            }}

            QPushButton:disabled {{
                background-color: #273449;
                color: #64748B;
            }}

            QTextEdit {{
                background-color: {COLOR_PANEL_ALT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
                color: {COLOR_TEXT};
                selection-background-color: {COLOR_BLUE};
            }}

            QCheckBox {{
                spacing: 8px;
                padding: 4px;
            }}

            QCheckBox::indicator {{
                width: 17px;
                height: 17px;
            }}

            QProgressBar {{
                background-color: {COLOR_PANEL_ALT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 9px;
                text-align: center;
                color: {COLOR_TEXT};
                font-weight: 700;
                min-height: 26px;
            }}

            QProgressBar::chunk {{
                background-color: {COLOR_BLUE};
                border-radius: 8px;
            }}

            QTableWidget {{
                background-color: {COLOR_PANEL_ALT};
                alternate-background-color: #131D2E;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                gridline-color: {COLOR_BORDER};
                selection-background-color: #1E3A5F;
            }}

            QHeaderView::section {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: none;
                border-bottom: 1px solid {COLOR_BORDER};
                border-right: 1px solid {COLOR_BORDER};
                padding: 8px;
                font-weight: 700;
            }}

            QStatusBar {{
                background-color: {COLOR_PANEL};
                color: {COLOR_MUTED};
            }}

            QScrollBar:vertical {{
                background: {COLOR_BG};
                width: 12px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background: #334155;
                min-height: 30px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #475569;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )

    # =====================================================
    # BUILD UI
    # =====================================================

    def build_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(
            QFrame.NoFrame
        )

        self.setCentralWidget(
            scroll_area
        )

        root = QWidget()
        scroll_area.setWidget(root)

        main_layout = QVBoxLayout(root)

        main_layout.setContentsMargins(
            28,
            24,
            28,
            30,
        )

        main_layout.setSpacing(18)

        # =================================================
        # HEADER
        # =================================================

        header_layout = QHBoxLayout()

        header_left = QVBoxLayout()

        title = QLabel(
            "NETWORK DOCTOR"
        )

        title.setStyleSheet(
            f"""
            font-size: 30px;
            font-weight: 800;
            color: {COLOR_TEXT};
            """
        )

        subtitle = QLabel(
            "Windows Network Diagnostic & Repair Utility"
        )

        subtitle.setObjectName(
            "Muted"
        )

        header_left.addWidget(title)
        header_left.addWidget(subtitle)

        header_layout.addLayout(
            header_left
        )

        header_layout.addStretch()

        version_label = QLabel(
            "v0.7 LAN Tools"
        )

        version_label.setStyleSheet(
            f"""
            color: {COLOR_MUTED};
            font-size: 12px;
            padding: 6px 10px;
            background: {COLOR_PANEL};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            """
        )

        header_layout.addWidget(
            version_label
        )

        main_layout.addLayout(
            header_layout
        )

        # =================================================
        # HEALTH CARD
        # =================================================

        health_card = self.create_card()

        health_layout = QHBoxLayout(
            health_card
        )

        health_layout.setContentsMargins(
            22,
            18,
            22,
            18,
        )

        health_text_layout = QVBoxLayout()

        health_title = QLabel(
            "NETWORK HEALTH"
        )

        health_title.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLOR_MUTED};
            """
        )

        self.health_status_label = QLabel(
            "READY"
        )

        self.health_status_label.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 800;
            color: {COLOR_MUTED};
            """
        )

        self.health_description_label = QLabel(
            "Ağ testi başlatılmayı bekliyor."
        )

        self.health_description_label.setStyleSheet(
            f"""
            color: {COLOR_MUTED};
            """
        )

        health_text_layout.addWidget(
            health_title
        )

        health_text_layout.addWidget(
            self.health_status_label
        )

        health_text_layout.addWidget(
            self.health_description_label
        )

        health_layout.addLayout(
            health_text_layout
        )

        health_layout.addStretch()

        score_layout = QVBoxLayout()
        score_layout.setAlignment(
            Qt.AlignCenter
        )

        self.health_score_label = QLabel(
            "--"
        )

        self.health_score_label.setAlignment(
            Qt.AlignCenter
        )

        self.health_score_label.setStyleSheet(
            f"""
            font-size: 42px;
            font-weight: 900;
            color: {COLOR_MUTED};
            """
        )

        score_caption = QLabel(
            "/ 100"
        )

        score_caption.setAlignment(
            Qt.AlignCenter
        )

        score_caption.setStyleSheet(
            f"""
            color: {COLOR_MUTED};
            font-size: 12px;
            """
        )

        score_layout.addWidget(
            self.health_score_label
        )

        score_layout.addWidget(
            score_caption
        )

        health_layout.addLayout(
            score_layout
        )

        main_layout.addWidget(
            health_card
        )

        # =================================================
        # ADAPTER CARD
        # =================================================

        adapter_card = self.create_card()

        adapter_layout = QVBoxLayout(
            adapter_card
        )

        adapter_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        adapter_layout.setSpacing(
            10
        )

        adapter_title = QLabel(
            "Ağ Adaptörü"
        )

        adapter_title.setObjectName(
            "SectionTitle"
        )

        self.adapter_combo = QComboBox()
        self.adapter_combo.setMinimumHeight(
            40
        )

        self.adapter_combo.currentIndexChanged.connect(
            self.update_adapter_info
        )

        self.adapter_info = QLabel()

        self.adapter_info.setWordWrap(
            True
        )

        self.adapter_info.setStyleSheet(
            f"""
            background-color: {COLOR_PANEL_ALT};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 12px;
            font-family: Consolas;
            font-size: 12px;
            color: #CBD5E1;
            """
        )

        adapter_layout.addWidget(
            adapter_title
        )

        adapter_layout.addWidget(
            self.adapter_combo
        )

        adapter_layout.addWidget(
            self.adapter_info
        )

        main_layout.addWidget(
            adapter_card
        )

        # =================================================
        # STATUS GRID
        # =================================================

        status_container = QWidget()

        status_grid = QGridLayout(
            status_container
        )

        status_grid.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        status_grid.setHorizontalSpacing(
            12
        )

        status_grid.setVerticalSpacing(
            12
        )

        cards = [
            (
                "physical",
                "PHYSICAL",
                "Fiziksel Link",
            ),
            (
                "ip",
                "IPv4",
                "IP Yapılandırması",
            ),
            (
                "dhcp",
                "DHCP",
                "Adres Atama",
            ),
            (
                "gateway",
                "GATEWAY",
                "Yerel Ağ",
            ),
            (
                "internet",
                "INTERNET",
                "WAN Erişimi",
            ),
            (
                "dns",
                "DNS",
                "İsim Çözümleme",
            ),
        ]

        for index, card_data in enumerate(
            cards
        ):
            key, card_title, card_subtitle = (
                card_data
            )

            card = self.create_status_card(
                key,
                card_title,
                card_subtitle,
            )

            row = index // 3
            column = index % 3

            status_grid.addWidget(
                card,
                row,
                column,
            )

        main_layout.addWidget(
            status_container
        )

        # =================================================
        # TEST BUTTON
        # =================================================

        self.test_button = QPushButton(
            "AĞI TEST ET"
        )

        self.test_button.setMinimumHeight(
            58
        )

        self.test_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_BLUE};
                font-size: 17px;
                font-weight: 800;
                border-radius: 10px;
            }}

            QPushButton:hover {{
                background-color: {COLOR_BLUE_HOVER};
            }}

            QPushButton:disabled {{
                background-color: #253247;
                color: #64748B;
            }}
            """
        )

        self.test_button.clicked.connect(
            self.start_diagnostic
        )

        main_layout.addWidget(
            self.test_button
        )

        # =================================================
        # PROGRESS
        # =================================================

        progress_card = self.create_card()

        progress_layout = QVBoxLayout(
            progress_card
        )

        progress_layout.setContentsMargins(
            18,
            15,
            18,
            15,
        )

        self.progress_status = QLabel(
            "Hazır"
        )

        self.progress_status.setAlignment(
            Qt.AlignCenter
        )

        self.progress_status.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLOR_MUTED};
            """
        )

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            "%p%"
        )

        self.progress_bar.setMinimumHeight(
            30
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

        # =================================================
        # DIAGNOSIS
        # =================================================

        diagnosis_card = self.create_card()

        diagnosis_layout = QVBoxLayout(
            diagnosis_card
        )

        diagnosis_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        diagnosis_title = QLabel(
            "Teşhis"
        )

        diagnosis_title.setObjectName(
            "SectionTitle"
        )

        self.diagnosis_output = QTextEdit()

        self.diagnosis_output.setReadOnly(
            True
        )

        self.diagnosis_output.setMinimumHeight(
            130
        )

        diagnosis_layout.addWidget(
            diagnosis_title
        )

        diagnosis_layout.addWidget(
            self.diagnosis_output
        )

        main_layout.addWidget(
            diagnosis_card
        )

        # =================================================
        # LAN TOOLS
        # =================================================

        lan_card = self.create_card()

        lan_layout = QVBoxLayout(
            lan_card
        )

        lan_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        lan_layout.setSpacing(
            12
        )

        lan_header = QHBoxLayout()

        lan_title_layout = QVBoxLayout()

        lan_title = QLabel(
            "LAN Tools"
        )

        lan_title.setObjectName(
            "SectionTitle"
        )

        lan_subtitle = QLabel(
            "Yerel ağdaki cihazları, IP çakışmalarını "
            "ve boş görünen IP adreslerini analiz eder."
        )

        lan_subtitle.setWordWrap(
            True
        )

        lan_subtitle.setStyleSheet(
            f"""
            color: {COLOR_MUTED};
            """
        )

        lan_title_layout.addWidget(
            lan_title
        )

        lan_title_layout.addWidget(
            lan_subtitle
        )

        lan_header.addLayout(
            lan_title_layout
        )

        lan_header.addStretch()

        self.lan_scan_button = QPushButton(
            "LAN AĞINI TARA"
        )

        self.lan_scan_button.setMinimumHeight(
            42
        )

        self.lan_scan_button.clicked.connect(
            self.start_lan_scan
        )

        lan_header.addWidget(
            self.lan_scan_button
        )

        lan_layout.addLayout(
            lan_header
        )

        # -------------------------------------------------
        # NETWORK INFO
        # -------------------------------------------------

        self.lan_network_label = QLabel(
            "Ağ: -"
        )

        self.lan_network_label.setStyleSheet(
            f"""
            color: {COLOR_MUTED};
            font-family: Consolas;
            font-weight: 700;
            """
        )

        lan_layout.addWidget(
            self.lan_network_label
        )

        # -------------------------------------------------
        # LAN STATUS
        # -------------------------------------------------

        self.lan_status_label = QLabel(
            "LAN taraması henüz çalıştırılmadı."
        )

        self.lan_status_label.setWordWrap(
            True
        )

        self.lan_status_label.setStyleSheet(
            f"""
            background-color: {COLOR_PANEL_ALT};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 10px;
            color: {COLOR_MUTED};
            """
        )

        lan_layout.addWidget(
            self.lan_status_label
        )

        # -------------------------------------------------
        # IP CONFLICT
        # -------------------------------------------------

        conflict_title = QLabel(
            "IP Conflict"
        )

        conflict_title.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 800;
            color: {COLOR_TEXT};
            """
        )

        lan_layout.addWidget(
            conflict_title
        )

        self.conflict_label = QLabel(
            "○ Henüz kontrol edilmedi"
        )

        self.conflict_label.setWordWrap(
            True
        )

        self.conflict_label.setStyleSheet(
            f"""
            background-color: {COLOR_PANEL_ALT};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 12px;
            color: {COLOR_MUTED};
            """
        )

        lan_layout.addWidget(
            self.conflict_label
        )

        # -------------------------------------------------
        # DEVICE TABLE
        # -------------------------------------------------

        devices_title = QLabel(
            "Ağdaki Cihazlar"
        )

        devices_title.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 800;
            """
        )

        lan_layout.addWidget(
            devices_title
        )

        self.device_table = QTableWidget()

        self.device_table.setColumnCount(
            5
        )

        self.device_table.setHorizontalHeaderLabels(
            [
                "IP",
                "Durum",
                "MAC",
                "Hostname",
                "Ping",
            ]
        )

        self.device_table.setRowCount(
            0
        )

        self.device_table.setAlternatingRowColors(
            True
        )

        self.device_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.device_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.device_table.verticalHeader().setVisible(
            False
        )

        self.device_table.setMinimumHeight(
            240
        )

        header = (
            self.device_table.horizontalHeader()
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.Stretch,
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeToContents,
        )

        lan_layout.addWidget(
            self.device_table
        )

        # -------------------------------------------------
        # FREE IPS
        # -------------------------------------------------

        free_title = QLabel(
            "Boş Görünen IP Adayları"
        )

        free_title.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 800;
            """
        )

        lan_layout.addWidget(
            free_title
        )

        free_warning = QLabel(
            "⚠ Bu adreslerin kesin olarak boş olduğu garanti "
            "edilemez. Ping'e cevap vermeyen cihazlar veya "
            "DHCP rezervasyonları bulunabilir."
        )

        free_warning.setWordWrap(
            True
        )

        free_warning.setStyleSheet(
            f"""
            color: {COLOR_YELLOW};
            font-size: 11px;
            """
        )

        lan_layout.addWidget(
            free_warning
        )

        self.free_ips_output = QTextEdit()

        self.free_ips_output.setReadOnly(
            True
        )

        self.free_ips_output.setMinimumHeight(
            130
        )

        self.free_ips_output.setPlaceholderText(
            "LAN taramasından sonra IP adayları burada görünecek."
        )

        lan_layout.addWidget(
            self.free_ips_output
        )

        main_layout.addWidget(
            lan_card
        )

        # =================================================
        # REPAIR CARD
        # =================================================

        self.repair_card = self.create_card()

        self.repair_layout = QVBoxLayout(
            self.repair_card
        )

        self.repair_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        self.repair_layout.setSpacing(
            8
        )

        repair_title = QLabel(
            "Ağ Onarım Araçları"
        )

        repair_title.setObjectName(
            "SectionTitle"
        )

        self.admin_label = QLabel()

        self.repair_info_label = QLabel(
            "Önce ağ testi çalıştırın."
        )

        self.repair_info_label.setWordWrap(
            True
        )

        self.repair_layout.addWidget(
            repair_title
        )

        self.repair_layout.addWidget(
            self.admin_label
        )

        self.repair_layout.addWidget(
            self.repair_info_label
        )

        self.repair_button = QPushButton(
            "SEÇİLEN ONARIMLARI UYGULA"
        )

        self.repair_button.setMinimumHeight(
            48
        )

        self.repair_button.setEnabled(
            False
        )

        self.repair_button.clicked.connect(
            self.apply_selected_repairs
        )

        self.repair_output = QTextEdit()

        self.repair_output.setReadOnly(
            True
        )

        self.repair_output.setMinimumHeight(
            110
        )

        self.repair_layout.addWidget(
            self.repair_button
        )

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
    # CARD HELPERS
    # =====================================================

    def create_card(self):
        card = QFrame()

        card.setObjectName(
            "Card"
        )

        return card

    def create_status_card(
        self,
        key,
        title,
        subtitle,
    ):
        card = QFrame()

        card.setMinimumHeight(
            105
        )

        layout = QVBoxLayout(
            card
        )

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        title_label = QLabel(
            title
        )

        title_label.setStyleSheet(
            f"""
            font-size: 12px;
            font-weight: 800;
            color: {COLOR_MUTED};
            """
        )

        value_label = QLabel(
            "○ BEKLENİYOR"
        )

        value_label.setStyleSheet(
            f"""
            font-size: 15px;
            font-weight: 800;
            color: {COLOR_MUTED};
            """
        )

        subtitle_label = QLabel(
            subtitle
        )

        subtitle_label.setStyleSheet(
            f"""
            font-size: 11px;
            color: {COLOR_MUTED};
            """
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            value_label
        )

        layout.addWidget(
            subtitle_label
        )

        card.setStyleSheet(
            self.status_card_style(
                COLOR_PANEL,
                COLOR_BORDER,
            )
        )

        self.status_cards[key] = {
            "frame": card,
            "title": title_label,
            "value": value_label,
            "subtitle": subtitle_label,
        }

        return card

    def status_card_style(
        self,
        background,
        border,
    ):
        return f"""
        QFrame {{
            background-color: {background};
            border: 1px solid {border};
            border-radius: 10px;
        }}

        QLabel {{
            border: none;
            background: transparent;
        }}
        """

    def set_status_card(
        self,
        key,
        state,
        detail=None,
    ):
        if key not in self.status_cards:
            return

        card = self.status_cards[key]

        if state == "pending":
            background = COLOR_PANEL_ALT
            border = COLOR_BLUE
            color = "#60A5FA"
            text = "● TEST EDİLİYOR"

        elif state == "success":
            background = COLOR_GREEN_DARK
            border = COLOR_GREEN
            color = "#4ADE80"
            text = "✓ BAŞARILI"

        elif state == "warning":
            background = COLOR_YELLOW_DARK
            border = COLOR_YELLOW
            color = "#FBBF24"
            text = "⚠ UYARI"

        elif state == "failed":
            background = COLOR_RED_DARK
            border = COLOR_RED
            color = "#F87171"
            text = "✗ BAŞARISIZ"

        else:
            background = COLOR_PANEL
            border = COLOR_BORDER
            color = COLOR_MUTED
            text = "○ BEKLENİYOR"

        if detail:
            text += f"\n{detail}"

        card["frame"].setStyleSheet(
            self.status_card_style(
                background,
                border,
            )
        )

        card["value"].setText(
            text
        )

        card["value"].setStyleSheet(
            f"""
            font-size: 15px;
            font-weight: 800;
            color: {color};
            """
        )

    # =====================================================
    # ADMIN
    # =====================================================

    def update_admin_status(self):
        if RepairService.is_admin():
            self.admin_label.setText(
                "● Yönetici Yetkisi: Aktif"
            )

            self.admin_label.setStyleSheet(
                f"""
                color: {COLOR_GREEN};
                font-weight: 700;
                """
            )

        else:
            self.admin_label.setText(
                "● Yönetici Yetkisi: Aktif değil"
            )

            self.admin_label.setStyleSheet(
                f"""
                color: {COLOR_YELLOW};
                font-weight: 700;
                """
            )

    # =====================================================
    # ADAPTERS
    # =====================================================

    def load_adapters(self):
        self.adapters = (
            AdapterService.get_adapters()
        )

        self.adapter_combo.blockSignals(
            True
        )

        self.adapter_combo.clear()

        for adapter in self.adapters:
            self.adapter_combo.addItem(
                f"{adapter.name} — "
                f"{adapter.description}"
            )

        self.adapter_combo.blockSignals(
            False
        )

        if not self.adapters:
            self.adapter_info.setText(
                "Ağ adaptörü bulunamadı."
            )

            self.test_button.setEnabled(
                False
            )

            self.lan_scan_button.setEnabled(
                False
            )

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
            or "-"
        )

        mac_address = (
            adapter.mac_address
            or "-"
        )

        self.adapter_info.setText(
            f"Durum        : {status}\n"
            f"Link Speed   : {adapter.link_speed_mbps} Mbps\n"
            f"IPv4         : {ipv4}\n"
            f"Subnet       : {subnet}\n"
            f"Gateway      : {gateway}\n"
            f"DHCP         : {dhcp_state}\n"
            f"DHCP Server  : {dhcp_server}\n"
            f"DNS          : {dns}\n"
            f"MAC          : {mac_address}"
        )

        network = NetworkUtils.get_cidr(
            adapter
        )

        self.lan_network_label.setText(
            f"Ağ: {network or '-'}"
        )

        self.reset_results()
        self.reset_lan_results()

    # =====================================================
    # RESET
    # =====================================================

    def reset_results(self):
        self.animate_progress(
            0
        )

        self.progress_status.setText(
            "Hazır"
        )

        for key in self.status_cards:
            self.set_status_card(
                key,
                "idle",
            )

        self.health_score_label.setText(
            "--"
        )

        self.health_score_label.setStyleSheet(
            f"""
            font-size: 42px;
            font-weight: 900;
            color: {COLOR_MUTED};
            """
        )

        self.health_status_label.setText(
            "READY"
        )

        self.health_status_label.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 800;
            color: {COLOR_MUTED};
            """
        )

        self.health_description_label.setText(
            "Ağ testi başlatılmayı bekliyor."
        )

        self.diagnosis_output.clear()
        self.repair_output.clear()

        self.clear_repair_options()

        self.repair_info_label.setText(
            "Önce ağ testi çalıştırın."
        )

        self.last_result = None

    def reset_lan_results(self):
        self.last_conflict_result = None
        self.device_table.setRowCount(
            0
        )

        self.free_ips_output.clear()

        self.conflict_label.setText(
            "○ Henüz kontrol edilmedi"
        )

        self.conflict_label.setStyleSheet(
            f"""
            background-color: {COLOR_PANEL_ALT};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 12px;
            color: {COLOR_MUTED};
            """
        )

        self.lan_status_label.setText(
            "LAN taraması henüz çalıştırılmadı."
        )
        if self.last_result:
            self.update_health_card(
            self.last_result
    )

    # =====================================================
    # PROGRESS
    # =====================================================

    def animate_progress(
        self,
        target_value,
    ):
        current_value = (
            self.progress_bar.value()
        )

        if self.progress_animation:
            self.progress_animation.stop()

        self.progress_animation = (
            QPropertyAnimation(
                self.progress_bar,
                b"value",
                self,
            )
        )

        self.progress_animation.setDuration(
            350
        )

        self.progress_animation.setStartValue(
            current_value
        )

        self.progress_animation.setEndValue(
            target_value
        )

        self.progress_animation.setEasingCurve(
            QEasingCurve.OutCubic
        )

        self.progress_animation.start()

    # =====================================================
    # DIAGNOSTIC
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

            if 0 <= index < len(
                self.adapters
            ):
                self.adapters[index] = refreshed

        self.reset_results()

        self.test_button.setEnabled(
            False
        )

        self.lan_scan_button.setEnabled(
            False
        )

        self.adapter_combo.setEnabled(
            False
        )

        self.progress_status.setText(
            "Ağ taraması başlatılıyor..."
        )

        self.health_status_label.setText(
            "SCANNING"
        )

        self.health_status_label.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 800;
            color: {COLOR_BLUE};
            """
        )

        self.health_description_label.setText(
            "Ağ yapılandırması analiz ediliyor."
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

    def update_progress(
        self,
        value,
        message,
        stage,
        success,
    ):
        self.animate_progress(
            value
        )

        self.progress_status.setText(
            message
        )

        finish_values = {
            "physical": 18,
            "ip": 35,
            "dhcp": 48,
            "gateway": 63,
            "internet": 80,
            "dns": 94,
        }

        if stage in self.status_cards:
            finished_at = (
                finish_values.get(
                    stage,
                    0,
                )
            )

            if value < finished_at:
                self.set_status_card(
                    stage,
                    "pending",
                )

            else:
                self.set_status_card(
                    stage,
                    (
                        "success"
                        if success
                        else "failed"
                    ),
                )

        elif stage == "analysis":
            self.health_description_label.setText(
                "Test sonuçları değerlendiriliyor."
            )

    # =====================================================
    # HEALTH SCORE
    # =====================================================

    def calculate_health_score(
        self,
        result,
    ):
        score = 100

        if not result.physical_link_ok:
            score -= 70

        elif not result.valid_ip:
            score -= 55

        else:
            if not result.dhcp_ok:
                score -= 10

            if not result.gateway_ok:
                score -= 35

            if not result.internet_ok:
                score -= 25

            if not result.dns_ok:
                score -= 15

        if result.gateway_latency_ms is not None:
            if result.gateway_latency_ms > 100:
                score -= 8
            elif result.gateway_latency_ms > 40:
                score -= 4

        if result.internet_latency_ms is not None:
            if result.internet_latency_ms > 250:
                score -= 8
            elif result.internet_latency_ms > 120:
                score -= 4

        if self.last_conflict_result:
            if self.last_conflict_result.conflict_suspected:
                if self.last_conflict_result.confidence == "high":
                    score -= 50

        elif self.last_conflict_result.confidence == "medium":
            score -= 25
        return max(
            0,
            min(
                100,
                score,
            ),
        )

    def update_health_card(
        self,
        result,
    ):
        score = self.calculate_health_score(
            result
        )

        self.health_score_label.setText(
            str(score)
        )

        if score >= 90:
            status = "HEALTHY"
            color = COLOR_GREEN
            description = (
                "Ağ bağlantısı sağlıklı görünüyor."
            )

        elif score >= 70:
            status = "GOOD"
            color = "#84CC16"
            description = (
                "Bağlantı çalışıyor ancak bazı "
                "değerler ideal olmayabilir."
            )

        elif score >= 45:
            status = "WARNING"
            color = COLOR_YELLOW
            description = (
                "Ağ bağlantısında dikkat gerektiren "
                "bir problem tespit edildi."
            )

        else:
            status = "CRITICAL"
            color = COLOR_RED
            description = (
                "Ağ bağlantısında ciddi bir arıza "
                "tespit edildi."
            )

        self.health_status_label.setText(
            status
        )

        self.health_status_label.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 800;
            color: {color};
            """
        )

        self.health_score_label.setStyleSheet(
            f"""
            font-size: 42px;
            font-weight: 900;
            color: {color};
            """
        )

        self.health_description_label.setText(
            description
        )

    # =====================================================
    # SHOW DIAGNOSTIC RESULT
    # =====================================================

    def show_result(
        self,
        result,
    ):
        self.test_button.setEnabled(
            True
        )

        self.lan_scan_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

        self.last_result = result

        self.animate_progress(
            100
        )

        self.progress_status.setText(
            "Tarama tamamlandı"
        )

        self.update_health_card(
            result
        )

        self.set_status_card(
            "physical",
            (
                "success"
                if result.physical_link_ok
                else "failed"
            ),
        )

        self.set_status_card(
            "ip",
            (
                "success"
                if result.valid_ip
                else "failed"
            ),
        )

        self.set_status_card(
            "dhcp",
            (
                "success"
                if result.dhcp_ok
                else "failed"
            ),
        )

        gateway_detail = None

        if result.gateway_latency_ms is not None:
            gateway_detail = (
                f"{result.gateway_latency_ms} ms"
            )

        self.set_status_card(
            "gateway",
            (
                "success"
                if result.gateway_ok
                else "failed"
            ),
            gateway_detail,
        )

        internet_detail = None

        if result.internet_latency_ms is not None:
            internet_detail = (
                f"{result.internet_latency_ms} ms"
            )

        self.set_status_card(
            "internet",
            (
                "success"
                if result.internet_ok
                else "failed"
            ),
            internet_detail,
        )

        dns_detail = (
            result.dns_resolved_ip
            if result.dns_resolved_ip
            else None
        )

        self.set_status_card(
            "dns",
            (
                "success"
                if result.dns_ok
                else "failed"
            ),
            dns_detail,
        )

        severity_title = {
            "success": "BAĞLANTI SAĞLIKLI",
            "warning": "UYARI",
            "critical": "ARIZA TESPİT EDİLDİ",
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
    # LAN SCAN
    # =====================================================

    def start_lan_scan(self):
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

            if 0 <= index < len(
                self.adapters
            ):
                self.adapters[index] = refreshed

        if not adapter.is_connected:
            QMessageBox.warning(
                self,
                "LAN Tarama",
                "Seçili ağ adaptörü bağlı değil.",
            )
            return

        if not adapter.has_valid_ipv4:
            QMessageBox.warning(
                self,
                "LAN Tarama",
                (
                    "Seçili adaptörde geçerli bir IPv4 "
                    "adresi bulunmuyor."
                ),
            )
            return

        network = NetworkUtils.get_cidr(
            adapter
        )

        if not network:
            QMessageBox.warning(
                self,
                "LAN Tarama",
                "Subnet bilgisi hesaplanamadı.",
            )
            return

        self.reset_lan_results()

        self.lan_network_label.setText(
            f"Ağ: {network}"
        )

        self.lan_status_label.setText(
            "LAN taraması başlatılıyor..."
        )

        self.lan_status_label.setStyleSheet(
            f"""
            background-color: {COLOR_PANEL_ALT};
            border: 1px solid {COLOR_BLUE};
            border-radius: 8px;
            padding: 10px;
            color: #60A5FA;
            font-weight: 700;
            """
        )

        self.lan_scan_button.setEnabled(
            False
        )

        self.test_button.setEnabled(
            False
        )

        self.adapter_combo.setEnabled(
            False
        )

        self.lan_worker = LanScanWorker(
            adapter
        )

        self.lan_worker.status.connect(
            self.update_lan_status
        )

        self.lan_worker.finished_result.connect(
            self.show_lan_results
        )

        self.lan_worker.failed.connect(
            self.show_lan_error
        )

        self.lan_worker.start()

    def update_lan_status(
        self,
        message,
    ):
        self.lan_status_label.setText(
            message
        )

        self.statusBar().showMessage(
            message
        )

    def show_lan_results(
        self,
        devices,
        conflict_result,
        free_candidates,
    ):
        self.last_conflict_result = conflict_result
        self.lan_scan_button.setEnabled(
            True
        )

        self.test_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

        self.device_table.setRowCount(
            len(devices)
        )

        for row, device in enumerate(
            devices
        ):
            ip_item = QTableWidgetItem(
                device.ip
            )

            status_item = QTableWidgetItem(
                "ONLINE"
            )

            mac_item = QTableWidgetItem(
                device.mac_address
                or "-"
            )

            hostname_item = QTableWidgetItem(
                device.hostname
                or "-"
            )

            ping_item = QTableWidgetItem(
                (
                    f"{device.latency_ms} ms"
                    if device.latency_ms
                    is not None
                    else "-"
                )
            )

            status_item.setForeground(
                Qt.green
            )

            self.device_table.setItem(
                row,
                0,
                ip_item,
            )

            self.device_table.setItem(
                row,
                1,
                status_item,
            )

            self.device_table.setItem(
                row,
                2,
                mac_item,
            )

            self.device_table.setItem(
                row,
                3,
                hostname_item,
            )

            self.device_table.setItem(
                row,
                4,
                ping_item,
            )

        self.lan_status_label.setText(
            f"✓ Tarama tamamlandı. "
            f"{len(devices)} aktif cihaz bulundu."
        )

        self.lan_status_label.setStyleSheet(
            f"""
            background-color: {COLOR_GREEN_DARK};
            border: 1px solid {COLOR_GREEN};
            border-radius: 8px;
            padding: 10px;
            color: #4ADE80;
            font-weight: 700;
            """
        )

        self.show_conflict_result(
            conflict_result
        )

        if free_candidates:
            lines = []

            for index, ip in enumerate(
                free_candidates,
                start=1,
            ):
                lines.append(
                    f"{index:02d}. {ip}"
                )

            self.free_ips_output.setPlainText(
                "\n".join(lines)
            )

        else:
            self.free_ips_output.setPlainText(
                "Boş görünen IP adayı bulunamadı."
            )

        self.statusBar().showMessage(
            (
                f"LAN taraması tamamlandı: "
                f"{len(devices)} cihaz bulundu."
            )
        )

    def show_conflict_result(
        self,
        result,
    ):
        if result.conflict_suspected:
            observed = (
                result.observed_mac
                or "-"
            )

            local = (
                result.local_mac
                or "-"
            )

            self.conflict_label.setText(
                "⚠ IP ÇAKIŞMASI ŞÜPHESİ\n\n"
                f"IP: {result.ip or '-'}\n"
                f"Yerel MAC: {local}\n"
                f"Gözlenen MAC: {observed}\n"
                f"Güven: {result.confidence.upper()}\n\n"
                f"{result.message}"
            )

            self.conflict_label.setStyleSheet(
                f"""
                background-color: {COLOR_RED_DARK};
                border: 1px solid {COLOR_RED};
                border-radius: 8px;
                padding: 12px;
                color: #F87171;
                font-weight: 700;
                """
            )

        else:
            local = (
                result.local_mac
                or "-"
            )

            confidence = (
                result.confidence.upper()
            )

            self.conflict_label.setText(
                "✓ IP ÇAKIŞMASI BELİRTİSİ YOK\n\n"
                f"IP: {result.ip or '-'}\n"
                f"MAC: {local}\n"
                f"Güven: {confidence}\n\n"
                f"{result.message}"
            )

            if result.confidence == "high":
                border = COLOR_GREEN
                background = COLOR_GREEN_DARK
                color = "#4ADE80"
            else:
                border = COLOR_YELLOW
                background = COLOR_YELLOW_DARK
                color = "#FBBF24"

            self.conflict_label.setStyleSheet(
                f"""
                background-color: {background};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 12px;
                color: {color};
                font-weight: 700;
                """
            )

    def show_lan_error(
        self,
        message,
    ):
        self.lan_scan_button.setEnabled(
            True
        )

        self.test_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

        self.lan_status_label.setText(
            "✗ LAN taraması başarısız."
        )

        self.lan_status_label.setStyleSheet(
            f"""
            background-color: {COLOR_RED_DARK};
            border: 1px solid {COLOR_RED};
            border-radius: 8px;
            padding: 10px;
            color: #F87171;
            font-weight: 700;
            """
        )

        QMessageBox.critical(
            self,
            "LAN Tarama Hatası",
            message,
        )

        self.statusBar().showMessage(
            "LAN taraması sırasında hata oluştu."
        )

    # =====================================================
    # REPAIR OPTIONS
    # =====================================================

    def clear_repair_options(self):
        for checkbox in (
            self.repair_checkboxes.values()
        ):
            self.repair_layout.removeWidget(
                checkbox
            )

            checkbox.deleteLater()

        self.repair_checkboxes.clear()

        self.repair_button.setEnabled(
            False
        )

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
            for recommendation
            in recommendations
        )

        if any_recommended:
            self.repair_info_label.setText(
                "⚠ Tespit edilen sorun için "
                "önerilen işlemler otomatik seçildi."
            )

            self.repair_info_label.setStyleSheet(
                f"""
                color: {COLOR_YELLOW};
                font-weight: 700;
                padding-bottom: 6px;
                """
            )

        else:
            self.repair_info_label.setText(
                "✓ Şu anda otomatik önerilen "
                "bir onarım bulunmuyor."
            )

            self.repair_info_label.setStyleSheet(
                f"""
                color: {COLOR_GREEN};
                font-weight: 700;
                padding-bottom: 6px;
                """
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
                recommendation.title
                + suffix
            )

            admin_blocked = (
                recommendation.requires_admin
                and not RepairService.is_admin()
            )

            if admin_blocked:
                checkbox.setEnabled(
                    False
                )

                checkbox.setChecked(
                    False
                )

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

    def update_repair_button_state(
        self,
    ):
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

    def apply_selected_repairs(
        self,
    ):
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

        self.repair_button.setEnabled(
            False
        )

        self.test_button.setEnabled(
            False
        )

        self.lan_scan_button.setEnabled(
            False
        )

        self.adapter_combo.setEnabled(
            False
        )

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

    def on_repairs_finished(
        self,
    ):
        self.repair_output.append(
            "\nOnarım işlemleri tamamlandı."
        )

        self.test_button.setEnabled(
            True
        )

        self.lan_scan_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

        self.update_repair_button_state()

        self.statusBar().showMessage(
            "Onarım işlemleri tamamlandı."
        )

        QMessageBox.information(
            self,
            "Onarım Tamamlandı",
            (
                "Seçilen ağ onarımları tamamlandı.\n\n"
                "Sonucu doğrulamak için tekrar "
                "\"AĞI TEST ET\" çalıştırabilirsiniz."
            ),
        )

    def on_repair_error(
        self,
        message,
    ):
        self.test_button.setEnabled(
            True
        )

        self.lan_scan_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

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
        self.test_button.setEnabled(
            True
        )

        self.lan_scan_button.setEnabled(
            True
        )

        self.adapter_combo.setEnabled(
            True
        )

        self.progress_status.setText(
            "Test sırasında hata oluştu."
        )

        self.health_status_label.setText(
            "ERROR"
        )

        self.health_status_label.setStyleSheet(
            f"""
            font-size: 22px;
            font-weight: 800;
            color: {COLOR_RED};
            """
        )

        self.health_score_label.setText(
            "!"
        )

        self.health_score_label.setStyleSheet(
            f"""
            font-size: 42px;
            font-weight: 900;
            color: {COLOR_RED};
            """
        )

        self.health_description_label.setText(
            "Teşhis işlemi tamamlanamadı."
        )

        self.diagnosis_output.setPlainText(
            "Beklenmeyen hata:\n\n"
            f"{message}"
        )

        self.statusBar().showMessage(
            "Test sırasında hata oluştu."
        )