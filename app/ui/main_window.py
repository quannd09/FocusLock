import os
import sys
import json
import time
import subprocess
import psutil
import win32gui
import win32process

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QCheckBox, 
    QSpinBox, QComboBox, QLineEdit, QGroupBox, QSplitter,
    QMessageBox, QDialog, QTextEdit, QFileDialog, QApplication,
    QAbstractItemView, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QFont, QIcon, QColor

import urllib.parse
from core.profile_mgr import ProfileManager
from core.system_guard import SystemGuard, SYSTEM_PROTECTED_PROCESSES
from core.ws_server import WebSocketBridge
from core.process_security import (
    protect_current_process,
    lock_session_file,
    unlock_session_file,
    set_autorun,
    remove_autorun,
    create_exit_event,
    signal_exit_event
)
from ui.floating_timer import FloatingTimerWidget
from ui.overlay_lock import OverlayLockWindow
from ui.theme_manager import (
    load_saved_theme, save_theme_preference, get_theme_palette, build_stylesheet,
    apply_theme_palette_to_app
)
from ui.item_card import ItemCardWidget

def extract_clean_domain(url):
    if not url:
        return ""
    if url.startswith("file:///"):
        fname = os.path.basename(url.split("?")[0].split("#")[0])
        clean_fname = urllib.parse.unquote(fname)
        return f"Tệp cục bộ - {clean_fname}" if clean_fname else "Tệp cục bộ"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path
        if path and path != "/" and len(path) <= 28:
            return f"{netloc}{path}"
        return netloc or url
    except Exception:
        return url

def get_extension_dir():
    """Dynamically resolves the absolute path to the extension folder."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        cand = os.path.join(base_dir, "extension")
        if os.path.exists(cand):
            return os.path.abspath(cand)
        if hasattr(sys, '_MEIPASS'):
            cand_meipass = os.path.join(sys._MEIPASS, "extension")
            if os.path.exists(cand_meipass):
                return os.path.abspath(cand_meipass)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cand = os.path.join(base_dir, "extension")
    if os.path.exists(cand):
        return os.path.abspath(cand)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "extension"))

# Common apps quick-picker
POPULAR_APPS = [
    ("🌐 Chrome", "chrome.exe"),
    ("🌐 Edge", "msedge.exe"),
    ("🟢 Cốc Cốc", "browser.exe"),
    ("💻 VS Code", "Code.exe"),
    ("📝 Notepad", "notepad.exe"),
    ("📄 MS Word", "WINWORD.EXE"),
    ("📊 MS Excel", "EXCEL.EXE"),
    ("📁 Explorer", "explorer.exe"),
    ("⌨️ UniKey", "UniKeyNT.exe"),
    ("💬 Telegram", "Telegram.exe"),
    ("💬 Discord", "Discord.exe"),
    ("⚡ Terminal", "WindowsTerminal.exe"),
]

class AppScannerWorker(QThread):
    finished = pyqtSignal(list)

    def run(self):
        try:
            apps = SystemGuard.get_running_user_apps()
        except Exception:
            apps = []
        self.finished.emit(apps)

class QtBridgeSignals(QObject):
    tabs_received = pyqtSignal(list, str)
    client_count_changed = pyqtSignal(int, list)
    app_killed = pyqtSignal(str)
    show_overlay = pyqtSignal(str)
    hide_overlay = pyqtSignal()

class SmoothListWidget(QListWidget):
    """QListWidget that propagates mouse wheel scrolling to parent QScrollArea when at boundaries."""
    def wheelEvent(self, event):
        vbar = self.verticalScrollBar()
        if vbar.maximum() == 0:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if (delta > 0 and vbar.value() <= vbar.minimum()) or (delta < 0 and vbar.value() >= vbar.maximum()):
            event.ignore()
            return
        super().wheelEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FocusLock - Chế Độ Siêu Tập Trung")
        self.resize(1100, 680)
        self.setMinimumSize(850, 480)
        self.preset_btns = {}
        self._scanned_tab_keys = set()
        self.current_theme = load_saved_theme()
        self._last_client_count = 0
        self._last_browsers = []

        self.signals = QtBridgeSignals()
        self.profile_mgr = ProfileManager()
        
        # Guard, Server & UI Helpers
        self.guard = SystemGuard(
            on_unauthorized_app_killed=lambda name: self.signals.app_killed.emit(name),
            on_show_overlay=lambda name: self.signals.show_overlay.emit(name),
            on_hide_overlay=lambda: self.signals.hide_overlay.emit()
        )
        self.ws_bridge = WebSocketBridge(
            on_tabs_received=lambda tabs, browser="Browser": self.signals.tabs_received.emit(tabs, browser),
            on_client_changed=lambda count, browsers=[]: self.signals.client_count_changed.emit(count, browsers)
        )
        self.ws_bridge.start()

        self.floating_widget = FloatingTimerWidget()
        self.overlay_window = OverlayLockWindow()
        self.watchdog_process = None
        self.session_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "active_session.json")
        self._session_file_handle = None
        self.app_paths = {}

        # Session state
        self.is_session_active = False
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)

        # Scanner thread worker
        self.scanner_worker = None

        # Wire signals
        self.signals.tabs_received.connect(self._on_tabs_received)
        self.signals.client_count_changed.connect(self._on_client_count_changed)
        self.signals.app_killed.connect(self._on_app_killed)
        self.signals.show_overlay.connect(self._on_show_overlay)
        self.signals.hide_overlay.connect(self._on_hide_overlay)

        self.init_ui()
        self.load_profiles_into_dropdown()
        
        # Trigger initial scan asynchronously
        QTimer.singleShot(200, self.scan_running_apps)

    def init_ui(self):
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("rootScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_widget.setObjectName("centralWidget")
        root_layout = QVBoxLayout(content_widget)
        root_layout.setContentsMargins(18, 16, 18, 18)
        root_layout.setSpacing(12)

        # 1. Consolidated Top Bar: Brand + Profile selector + Extension status + Theme toggle
        header = QHBoxLayout()
        header.setSpacing(10)

        # Brand
        title_label = QLabel("🛡️ FocusLock")
        title_label.setObjectName("brandTitle")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.addWidget(title_label)

        header.addSpacing(16)

        # Profile Selector
        lbl_prof = QLabel("Profile:")
        lbl_prof.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        header.addWidget(lbl_prof)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        header.addWidget(self.profile_combo)

        btn_save_profile = QPushButton("+ Lưu")
        btn_save_profile.setToolTip("Lưu danh sách hiện tại thành profile mới")
        btn_save_profile.setProperty("medium", True)
        btn_save_profile.clicked.connect(self.save_current_as_profile)
        header.addWidget(btn_save_profile)

        header.addStretch()

        # Extension status badge
        self.ext_badge = QLabel("⚪ Đang chờ Extension kết nối...")
        header.addWidget(self.ext_badge)

        btn_ext_help = QPushButton("ℹ️ Cài Extension")
        btn_ext_help.setProperty("medium", True)
        btn_ext_help.clicked.connect(self.show_extension_help)
        header.addWidget(btn_ext_help)

        # Minimalist Theme Toggle (🌙 / ☀️ icon only)
        self.btn_theme_toggle = QPushButton("☀️" if self.current_theme == "dark" else "🌙")
        self.btn_theme_toggle.setFixedSize(36, 30)
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("Đổi giao diện Tối / Sáng ấm")
        self.btn_theme_toggle.clicked.connect(self.toggle_theme)
        header.addWidget(self.btn_theme_toggle)

        root_layout.addLayout(header)

        # 2. Main Splitter: Apps (Left) vs Browser Tabs (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL: APPS ---
        app_box = QGroupBox("1. Ứng dụng máy tính được phép")
        app_layout = QVBoxLayout(app_box)
        app_layout.setSpacing(8)
        app_layout.setContentsMargins(12, 14, 12, 12)

        # Clean 1-line top action toolbar
        app_toolbar = QHBoxLayout()
        app_toolbar.setSpacing(6)

        self.btn_scan_apps = QPushButton("🔄 Quét ứng dụng")
        self.btn_scan_apps.clicked.connect(self.scan_running_apps)
        app_toolbar.addWidget(self.btn_scan_apps)

        btn_pick_window = QPushButton("🎯 Chọn cửa sổ")
        btn_pick_window.setToolTip("Nhấp vào đây rồi nhấp vào cửa sổ trên màn hình để chọn")
        btn_pick_window.setProperty("medium", True)
        btn_pick_window.clicked.connect(self.start_interactive_window_picker)
        app_toolbar.addWidget(btn_pick_window)

        btn_browse_exe = QPushButton("📁 File .exe")
        btn_browse_exe.setProperty("medium", True)
        btn_browse_exe.clicked.connect(self.browse_exe_file)
        app_toolbar.addWidget(btn_browse_exe)

        app_toolbar.addStretch()

        btn_sel_all = QPushButton("Chọn tất cả")
        btn_sel_all.setProperty("compact", True)
        btn_sel_all.clicked.connect(lambda: self._set_all_checks(self.app_list, True))
        app_toolbar.addWidget(btn_sel_all)

        btn_desel_all = QPushButton("Bỏ chọn")
        btn_desel_all.setProperty("compact", True)
        btn_desel_all.clicked.connect(lambda: self._set_all_checks(self.app_list, False))
        app_toolbar.addWidget(btn_desel_all)

        self.lbl_app_count = QLabel("0 đã chọn")
        self.lbl_app_count.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        app_toolbar.addWidget(self.lbl_app_count)

        app_layout.addLayout(app_toolbar)

        # App List Widget
        self.app_list = SmoothListWidget()
        self.app_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.app_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.app_list.setMinimumHeight(180)
        app_layout.addWidget(self.app_list, 1)

        # Compact footer: Status + Quick manual input
        app_footer = QHBoxLayout()
        app_footer.setSpacing(8)

        self.lbl_scan_status = QLabel("")
        self.lbl_scan_status.setFont(QFont("Segoe UI", 8))
        app_footer.addWidget(self.lbl_scan_status)

        app_footer.addStretch()

        self.txt_manual_app = QLineEdit()
        self.txt_manual_app.setPlaceholderText("Nhập file .exe")
        self.txt_manual_app.setMaximumWidth(210)
        btn_add_app = QPushButton("+ Thêm")
        btn_add_app.setProperty("medium", True)
        btn_add_app.clicked.connect(self.add_manual_app)
        app_footer.addWidget(self.txt_manual_app)
        app_footer.addWidget(btn_add_app)

        app_layout.addLayout(app_footer)
        splitter.addWidget(app_box)

        # --- RIGHT PANEL: BROWSER TABS ---
        tab_box = QGroupBox("2. Tab trình duyệt Chrome / Edge được phép")
        tab_layout = QVBoxLayout(tab_box)
        tab_layout.setSpacing(8)
        tab_layout.setContentsMargins(12, 14, 12, 12)

        # Clean 1-line top action toolbar
        tab_toolbar = QHBoxLayout()
        tab_toolbar.setSpacing(6)

        self.btn_scan_tabs = QPushButton("🔄 Quét tab")
        self.btn_scan_tabs.clicked.connect(self.scan_browser_tabs)
        tab_toolbar.addWidget(self.btn_scan_tabs)

        tab_toolbar.addStretch()

        btn_select_all_tabs = QPushButton("Chọn tất cả")
        btn_select_all_tabs.setProperty("compact", True)
        btn_select_all_tabs.clicked.connect(lambda: self._set_all_checks(self.tab_list, True))
        tab_toolbar.addWidget(btn_select_all_tabs)

        btn_desel_tabs = QPushButton("Bỏ chọn")
        btn_desel_tabs.setProperty("compact", True)
        btn_desel_tabs.clicked.connect(lambda: self._set_all_checks(self.tab_list, False))
        tab_toolbar.addWidget(btn_desel_tabs)

        self.lbl_tab_count = QLabel("0 đã chọn")
        self.lbl_tab_count.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        tab_toolbar.addWidget(self.lbl_tab_count)

        tab_layout.addLayout(tab_toolbar)

        # Tab List Widget
        self.tab_list = SmoothListWidget()
        self.tab_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tab_list.setMinimumHeight(180)
        tab_layout.addWidget(self.tab_list, 1)

        # Compact footer: Quick manual URL input
        tab_footer = QHBoxLayout()
        tab_footer.setSpacing(8)

        self.txt_manual_url = QLineEdit()
        self.txt_manual_url.setPlaceholderText("Nhập domain hoặc URL")
        btn_add_url = QPushButton("+ Thêm domain")
        btn_add_url.setProperty("medium", True)
        btn_add_url.clicked.connect(self.add_manual_url)
        tab_footer.addWidget(self.txt_manual_url)
        tab_footer.addWidget(btn_add_url)

        tab_layout.addLayout(tab_footer)
        splitter.addWidget(tab_box)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)

        # 3. Compact Bottom Control Center (Studio Integrated Row)
        bottom_box = QGroupBox("3. Thiết lập thời gian và Kích hoạt")
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(14, 12, 14, 12)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        lbl_dur = QLabel("Thời gian:")
        lbl_dur.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        ctrl_row.addWidget(lbl_dur)

        self.spin_hours = QSpinBox()
        self.spin_hours.setRange(0, 24)
        self.spin_hours.setValue(0)
        self.spin_hours.setSuffix(" giờ")
        self.spin_hours.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13px; font-weight: 600;")
        ctrl_row.addWidget(self.spin_hours)

        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(0, 59)
        self.spin_minutes.setValue(45)
        self.spin_minutes.setSuffix(" phút")
        self.spin_minutes.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13px; font-weight: 600;")
        ctrl_row.addWidget(self.spin_minutes)

        ctrl_row.addSpacing(6)

        # Preset pills
        self.preset_btns = {}
        for mins in [15, 25, 45, 60, 90]:
            btn_quick = QPushButton(f"{mins}m")
            btn_quick.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_quick.clicked.connect(lambda _, m=mins: self._set_preset_time(m))
            self.preset_btns[mins] = btn_quick
            ctrl_row.addWidget(btn_quick)

        ctrl_row.addSpacing(12)

        self.chk_floating_widget = QCheckBox("Hiển thị widget đếm ngược nổi")
        self.chk_floating_widget.setChecked(True)
        ctrl_row.addWidget(self.chk_floating_widget)

        ctrl_row.addStretch()

        # Primary Studio CTA Button
        self.btn_start = QPushButton("⚡ Bắt đầu tập trung")
        self.btn_start.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_lockdown_session)
        ctrl_row.addWidget(self.btn_start)

        bottom_layout.addLayout(ctrl_row)

        # Subtle clean warning line
        warning_lbl = QLabel("⚠️ Mọi ứng dụng ngoài danh sách sẽ bị chặn ngay lập tức cho đến hết thời gian.")
        warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning_lbl.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 500;")
        bottom_layout.addWidget(warning_lbl)

        root_layout.addWidget(bottom_box, 0)

        self.scroll_area.setWidget(content_widget)
        self.setCentralWidget(self.scroll_area)

        # Apply initial theme
        self.apply_theme()

    def toggle_theme(self):
        self.current_theme = "warm" if self.current_theme == "dark" else "dark"
        save_theme_preference(self.current_theme)
        self.apply_theme()

    def apply_theme(self):
        palette = get_theme_palette(self.current_theme)
        apply_theme_palette_to_app(QApplication.instance(), self.current_theme)
        self.setStyleSheet(build_stylesheet(self.current_theme))
        self.btn_theme_toggle.setText("☀️" if self.current_theme == "dark" else "🌙")

        # Update all ItemCardWidgets in app_list
        for i in range(self.app_list.count()):
            w = self.app_list.itemWidget(self.app_list.item(i))
            if isinstance(w, ItemCardWidget):
                w.apply_theme(palette)

        # Update all ItemCardWidgets in tab_list
        for i in range(self.tab_list.count()):
            w = self.tab_list.itemWidget(self.tab_list.item(i))
            if isinstance(w, ItemCardWidget):
                w.apply_theme(palette)

        # Update button visuals
        current_mins = self.spin_minutes.value() if self.spin_hours.value() == 0 else 0
        self._update_preset_buttons_visual(current_mins)
        self._update_cta_button_visual()
        self._update_badges_visual()

    def _update_cta_button_visual(self):
        palette = get_theme_palette(self.current_theme)
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        accent_pressed = palette["accent_pressed"]
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #FFFFFF;
                border: 1px solid {accent_hover};
                border-radius: 8px;
                padding: 9px 20px;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.2px;
            }}
            QPushButton:hover {{
                background-color: {accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {accent_pressed};
                padding-top: 10px;
                padding-bottom: 8px;
            }}
        """)
        if hasattr(self, 'btn_scan_apps'):
            self.btn_scan_apps.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent};
                    color: #FFFFFF;
                    border: 1px solid {accent_hover};
                    font-weight: 600;
                    padding: 6px 12px;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {accent_hover};
                }}
                QPushButton:pressed {{
                    background-color: {accent_pressed};
                }}
            """)
        if hasattr(self, 'btn_scan_tabs'):
            self.btn_scan_tabs.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent};
                    color: #FFFFFF;
                    border: 1px solid {accent_hover};
                    font-weight: 600;
                    padding: 6px 12px;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {accent_hover};
                }}
                QPushButton:pressed {{
                    background-color: {accent_pressed};
                }}
            """)

    def _update_preset_buttons_visual(self, selected_mins):
        palette = get_theme_palette(self.current_theme)
        accent = palette["accent"]
        btn_bg = palette["btn_bg"]
        btn_border = palette["btn_border"]
        text_main = palette["text_main"]
        for mins, btn in self.preset_btns.items():
            if mins == selected_mins and self.spin_hours.value() == 0:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 5px 10px;
                        font-size: 11px;
                        font-weight: 700;
                        background-color: {accent};
                        color: #FFFFFF;
                        border: 1px solid {accent};
                        border-radius: 6px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 5px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        background-color: {btn_bg};
                        color: {text_main};
                        border: 1px solid {btn_border};
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        border-color: {accent};
                    }}
                """)

    def _set_preset_time(self, minutes):
        self.spin_hours.setValue(minutes // 60)
        self.spin_minutes.setValue(minutes % 60)
        self._update_preset_buttons_visual(minutes)

    def _update_app_count(self):
        checked = len(self._get_checked_items(self.app_list))
        total = self.app_list.count()
        if hasattr(self, 'lbl_app_count'):
            self.lbl_app_count.setText(f"{checked}/{total} đã chọn" if total > 0 else "0 đã chọn")

    def _update_tab_count(self):
        checked = len(self._get_checked_items(self.tab_list))
        total = self.tab_list.count()
        if hasattr(self, 'lbl_tab_count'):
            self.lbl_tab_count.setText(f"{checked}/{total} đã chọn" if total > 0 else "0 đã chọn")

    def _set_all_checks(self, list_widget, state):
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            if isinstance(widget, ItemCardWidget):
                widget.set_checked(state)
            else:
                item.setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)
        self._update_app_count()
        self._update_tab_count()

    def scan_running_apps(self):
        """Asynchronously scans running applications without blocking the GUI."""
        self.btn_scan_apps.setEnabled(False)
        self.btn_scan_apps.setText("⏳ Đang quét...")
        self.lbl_scan_status.setText("Đang tìm cửa sổ...")

        self.scanner_worker = AppScannerWorker()
        self.scanner_worker.finished.connect(self._on_apps_scanned)
        self.scanner_worker.start()

    def _on_apps_scanned(self, running_apps):
        self.btn_scan_apps.setEnabled(True)
        self.btn_scan_apps.setText("🔄 Quét ứng dụng")

        currently_checked = set(self._get_checked_items(self.app_list))
        self.app_list.clear()

        if not running_apps:
            item = QListWidgetItem("Chưa phát hiện cửa sổ nào. Hãy mở ứng dụng lên rồi bấm 'Quét lại'!")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.app_list.addItem(item)
            self.lbl_scan_status.setText("Không tìm thấy cửa sổ.")
            self._update_app_count()
            return

        palette = get_theme_palette(self.current_theme)
        for app in running_apps:
            name = app['name']
            if app.get('path'):
                self.app_paths[name.lower()] = app['path'].lower()
            raw_title = app.get('title', '').strip()
            title = raw_title if raw_title else name
            subtitle = name if raw_title else "Ứng dụng nền"
            badge = name.replace(".exe", "").capitalize()
            if len(badge) > 9:
                badge = "App"
            is_checked = (name.lower() in [c.lower() for c in currently_checked])

            card = ItemCardWidget(
                title=title,
                subtitle=subtitle,
                badge_text=badge,
                is_checked=is_checked,
                data=name,
                palette=palette
            )
            card.toggled.connect(self._update_app_count)

            item = QListWidgetItem(self.app_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.app_list.setItemWidget(item, card)

        self.lbl_scan_status.setText(f"✅ Đã tìm thấy {len(running_apps)} cửa sổ")
        self._update_app_count()

    def start_interactive_window_picker(self):
        """Minimizes FocusLock for 2.5s to allow user to click any application on their screen."""
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMinimized)
        QTimer.singleShot(2500, self._capture_clicked_window)

    def _capture_clicked_window(self):
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            try:
                title = win32gui.GetWindowText(hwnd).strip()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                exe_name = proc.name()
                try:
                    exe_path = proc.exe()
                    self.app_paths[exe_name.lower()] = exe_path.lower()
                except Exception:
                    pass

                if exe_name.lower() not in SYSTEM_PROTECTED_PROCESSES and pid != os.getpid():
                    self.add_or_check_app(exe_name, title)
            except Exception as e:
                print(f"[Picker] Error: {e}")

        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    def browse_exe_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file ứng dụng .exe",
            "C:\\Program Files",
            "Executable Files (*.exe)"
        )
        if file_path:
            exe_name = os.path.basename(file_path)
            self.app_paths[exe_name.lower()] = os.path.abspath(file_path).lower()
            self.add_or_check_app(exe_name, exe_name)

    def add_or_check_app(self, exe_name, title=""):
        clean_name = exe_name.strip()
        if not clean_name.lower().endswith(".exe"):
            clean_name += ".exe"

        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            widget = self.app_list.itemWidget(item)
            existing = widget.data if isinstance(widget, ItemCardWidget) else item.data(Qt.ItemDataRole.UserRole)
            if existing and existing.lower() == clean_name.lower():
                if isinstance(widget, ItemCardWidget):
                    widget.set_checked(True)
                else:
                    item.setCheckState(Qt.CheckState.Checked)
                self.app_list.scrollToItem(item)
                self._update_app_count()
                return

        card_title = title if title else clean_name
        card_sub = clean_name if title else "Thủ công"
        palette = get_theme_palette(self.current_theme)

        card = ItemCardWidget(
            title=card_title,
            subtitle=card_sub,
            badge_text="App",
            is_checked=True,
            data=clean_name,
            palette=palette
        )
        card.toggled.connect(self._update_app_count)

        item = QListWidgetItem()
        item.setSizeHint(card.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, clean_name)
        self.app_list.insertItem(0, item)
        self.app_list.setItemWidget(item, card)
        self.app_list.scrollToItem(item)
        self._update_app_count()

    def add_manual_app(self):
        text = self.txt_manual_app.text().strip()
        if text:
            self.add_or_check_app(text)
            self.txt_manual_app.clear()

    def scan_browser_tabs(self):
        if not self.ws_bridge.is_connected():
            ext_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "extension"))
            QMessageBox.information(
                self, 
                "Chưa kết nối Extension", 
                "Chưa có trình duyệt Chrome hoặc Edge nào kết nối Extension!\n\n"
                "Để quét tab, hãy cài Extension vào Chrome hoặc Edge:\n"
                "1. Vào chrome://extensions hoặc edge://extensions\n"
                "2. Bật 'Developer Mode'\n"
                "3. Nhấp 'Load unpacked' và chọn thư mục:\n"
                f"{ext_path}"
            )
            return

        self.tab_list.clear()
        self._scanned_tab_keys.clear()
        self.ws_bridge.request_tabs()

    def _on_tabs_received(self, tabs, browser="Browser"):
        if not hasattr(self, "_scanned_tab_keys"):
            self._scanned_tab_keys = set()

        if not tabs:
            if self.tab_list.count() == 0:
                item = QListWidgetItem(f"Không tìm thấy tab mở nào trên {browser}.")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.tab_list.addItem(item)
                self._update_tab_count()
            return

        if self.tab_list.count() == 1:
            first_item = self.tab_list.item(0)
            first_widget = self.tab_list.itemWidget(first_item)
            if not isinstance(first_widget, ItemCardWidget):
                self.tab_list.clear()

        palette = get_theme_palette(self.current_theme)

        for t in tabs:
            url = t.get("url", "").strip()
            if not url:
                continue

            title = t.get("title", "Untitled").strip()
            tab_browser = t.get("browser") or browser
            badge = tab_browser if tab_browser and tab_browser != "Browser" else "Web"

            unique_key = f"{badge}_{url}"
            if unique_key in self._scanned_tab_keys:
                continue
            self._scanned_tab_keys.add(unique_key)

            clean_sub = extract_clean_domain(url)

            card = ItemCardWidget(
                title=title,
                subtitle=clean_sub,
                badge_text=badge,
                is_checked=True,
                data=url,
                palette=palette
            )
            card.toggled.connect(self._update_tab_count)

            item = QListWidgetItem(self.tab_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.tab_list.setItemWidget(item, card)

        self._update_tab_count()

    def add_manual_url(self):
        text = self.txt_manual_url.text().strip()
        if not text:
            return
        palette = get_theme_palette(self.current_theme)
        card = ItemCardWidget(
            title=text,
            subtitle="Thủ công",
            badge_text="Web",
            is_checked=True,
            data=text,
            palette=palette
        )
        card.toggled.connect(self._update_tab_count)

        item = QListWidgetItem(self.tab_list)
        item.setSizeHint(card.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, text)
        self.tab_list.setItemWidget(item, card)

        self.txt_manual_url.clear()
        self._update_tab_count()

    def _on_client_count_changed(self, count, browsers=None):
        self._last_client_count = count
        self._last_browsers = browsers or []
        self._update_badges_visual()

    def _update_badges_visual(self):
        count = getattr(self, "_last_client_count", 0)
        browsers = getattr(self, "_last_browsers", [])
        palette = get_theme_palette(self.current_theme)
        unique_browsers = [b for b in dict.fromkeys(browsers) if b and b != "Browser"]

        if count == 0:
            self.ext_badge.setText("⚪ Chưa kết nối Extension")
            self.ext_badge.setStyleSheet(f"color: {palette['text_muted']}; background: transparent; border: 1px solid {palette['border_color']}; padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;")
        else:
            n = len(unique_browsers) if unique_browsers else count
            if unique_browsers:
                names = " & ".join(unique_browsers)
                self.ext_badge.setText(f"🟢 Sẵn sàng ({n}): {names}")
            else:
                self.ext_badge.setText(f"🟢 Sẵn sàng ({n})")

            if self.current_theme == "warm":
                self.ext_badge.setStyleSheet("color: #047857; background: rgba(4, 120, 87, 0.12); border: 1px solid rgba(4, 120, 87, 0.35); padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;")
            else:
                self.ext_badge.setStyleSheet("color: #10B981; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;")

    def load_profiles_into_dropdown(self):
        self.profile_combo.clear()
        profiles = self.profile_mgr.load_all()
        for p in profiles:
            self.profile_combo.addItem(p.get("name", "Unnamed"), p)

    def _on_profile_selected(self, index):
        if index < 0:
            return
        profile = self.profile_combo.itemData(index)
        if not profile:
            return

        allowed_apps = [a.lower() for a in profile.get("allowed_apps", [])]
        for app in allowed_apps:
            self.add_or_check_app(app)

        self.tab_list.clear()
        palette = get_theme_palette(self.current_theme)
        for url in profile.get("allowed_urls", []):
            clean_sub = extract_clean_domain(url)
            card = ItemCardWidget(
                title=url,
                subtitle=clean_sub,
                badge_text="Web",
                is_checked=True,
                data=url,
                palette=palette
            )
            card.toggled.connect(self._update_tab_count)

            item = QListWidgetItem(self.tab_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.tab_list.setItemWidget(item, card)

        dur = profile.get("duration_minutes", 45)
        self._set_preset_time(dur)
        self.chk_floating_widget.setChecked(profile.get("show_floating_widget", True))
        self._update_app_count()
        self._update_tab_count()

    def save_current_as_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Lưu Profile Mới")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Nhập tên cho Profile mới:"))
        txt_name = QLineEdit(dialog)
        layout.addWidget(txt_name)
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Lưu", dialog)
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("Hủy", dialog)
        btn_cancel.clicked.connect(dialog.reject)
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted and txt_name.text().strip():
            prof_name = txt_name.text().strip()
            apps = self._get_checked_items(self.app_list)
            urls = self._get_checked_items(self.tab_list)
            dur = self.spin_hours.value() * 60 + self.spin_minutes.value()
            new_prof = {
                "name": prof_name,
                "allowed_apps": apps,
                "allowed_urls": urls,
                "duration_minutes": dur,
                "show_floating_widget": self.chk_floating_widget.isChecked()
            }
            self.profile_mgr.add_or_update(new_prof)
            self.load_profiles_into_dropdown()
            for idx in range(self.profile_combo.count()):
                if self.profile_combo.itemText(idx) == prof_name:
                    self.profile_combo.setCurrentIndex(idx)
                    break

    def _get_checked_items(self, list_widget):
        checked = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            if isinstance(widget, ItemCardWidget):
                if widget.is_checked() and widget.data:
                    checked.append(widget.data)
            else:
                if item and item.checkState() == Qt.CheckState.Checked:
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if data:
                        checked.append(data)
        return checked

    def show_extension_help(self):
        ext_path = get_extension_dir()
        dialog = QDialog(self)
        dialog.setWindowTitle("Hướng dẫn kết nối Extension cho trình duyệt")
        dialog.resize(620, 510)
        dialog.setStyleSheet(build_stylesheet(self.current_theme))

        palette = get_theme_palette(self.current_theme)
        accent = palette["accent"]
        text_main = palette["text_main"]
        text_muted = palette["text_muted"]
        bg_card = palette["bg_card"]
        bg_item = palette["bg_item"]
        border_color = palette["border_color"]
        success_color = "#047857" if self.current_theme == "warm" else "#10B981"
        success_bg = "rgba(4, 120, 87, 0.12)" if self.current_theme == "warm" else "rgba(16, 185, 129, 0.12)"
        code_bg = palette["bg_item_hover"] if self.current_theme == "warm" else "#1E293B"

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        
        info = QTextEdit(dialog)
        info.setReadOnly(True)
        info.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_card};
                color: {text_main};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 10px 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
        """)
        info.setHtml(f"""
        <div style="font-family: 'Segoe UI', system-ui, sans-serif; color: {text_main}; line-height: 1.45;">
            <h3 style="color: {accent}; margin: 0 0 8px 0; font-size: 15px;">Hướng dẫn kết nối tiện ích mở rộng FocusLock:</h3>
            
            <p style="margin: 0 0 8px 0; color: {text_main}; font-size: 12px;">
                Tiện ích <b>FocusLock Companion</b> đi kèm sẵn trong mã nguồn tải về từ GitHub tại thư mục <code>FocusLock/extension</code>. Hoạt động trên mọi trình duyệt nhân Chromium: <b>Google Chrome</b>, <b>Microsoft Edge</b>, <b>Cốc Cốc</b>, <b>Brave</b>.
            </p>

            <div style="margin: 0 0 10px 0;">
                <b style="color: {accent}; font-size: 12px;">Quy trình cài đặt:</b>
                <ol style="margin: 4px 0 0 0; padding-left: 20px; color: {text_main}; font-size: 12px; line-height: 1.55;">
                    <li>Mở trang quản lý tiện ích trên trình duyệt:
                        <br>&bull; Google Chrome: <code style="background: {code_bg}; color: {accent}; padding: 1px 4px; border-radius: 4px;">chrome://extensions</code>
                        <br>&bull; Microsoft Edge: <code style="background: {code_bg}; color: {accent}; padding: 1px 4px; border-radius: 4px;">edge://extensions</code>
                        <br>&bull; Cốc Cốc: <code style="background: {code_bg}; color: {accent}; padding: 1px 4px; border-radius: 4px;">coccoc://extensions</code>
                    </li>
                    <li style="margin-top: 4px;">Gạt bật công tắc <b>Developer mode</b> ở góc trình duyệt.</li>
                    <li style="margin-top: 4px;">Bấm nút <b>Load unpacked</b> rồi chọn thư mục <code>extension</code> của FocusLock.</li>
                </ol>
            </div>

            <div style="background: {bg_item}; padding: 8px 12px; border-radius: 6px; border: 1px solid {border_color}; margin-bottom: 10px;">
                <div style="color: {text_muted}; font-size: 11px; font-weight: 600; margin-bottom: 3px;">📁 Thư mục tiện ích:</div>
                <div style="color: {accent}; font-family: 'Consolas', monospace; font-size: 12px; font-weight: 600; word-break: break-all; background: {code_bg}; padding: 4px 8px; border-radius: 4px; border: 1px dashed {border_color};">
                    {ext_path}
                </div>
                <div style="color: {text_muted}; font-size: 11px; margin-top: 3px;">
                    💡 Đường dẫn trên tự động nhận diện theo vị trí bạn lưu dự án FocusLock trên máy, không bị cố định vào bất kỳ máy tính nào.
                </div>
            </div>

            <div style="color: {success_color}; background: {success_bg}; padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;">
                🟢 Sau khi nạp, biểu tượng FocusLock trên trình duyệt sẽ tự động kết nối và ứng dụng sẽ hiển thị sẵn sàng.
            </div>
        </div>
        """)
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_copy = QPushButton("📋 Sao chép đường dẫn")
        btn_copy.setProperty("medium", True)
        def _copy_path():
            QApplication.clipboard().setText(ext_path)
            btn_copy.setText("✅ Đã sao chép!")
            QTimer.singleShot(1500, lambda: btn_copy.setText("📋 Sao chép đường dẫn"))
        btn_copy.clicked.connect(_copy_path)
        btn_row.addWidget(btn_copy)

        btn_open_folder = QPushButton("📁 Mở thư mục Extension trong Explorer")
        btn_open_folder.setProperty("medium", True)
        btn_open_folder.clicked.connect(lambda: subprocess.Popen(f'explorer "{ext_path}"'))
        btn_row.addWidget(btn_open_folder)
        layout.addLayout(btn_row)

        btn_close = QPushButton("Đã hiểu")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #FFFFFF;
                border: 1px solid {palette['accent_hover']};
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {palette['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: {palette['accent_pressed']};
            }}
        """)
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
        dialog.exec()

    def start_lockdown_session(self):
        selected_apps = self._get_checked_items(self.app_list)
        selected_urls = self._get_checked_items(self.tab_list)
        total_minutes = self.spin_hours.value() * 60 + self.spin_minutes.value()

        if total_minutes <= 0:
            QMessageBox.warning(self, "Lỗi thời gian", "Vui lòng chọn thời gian tập trung lớn hơn 0 phút!")
            return

        if not selected_apps:
            confirm_no_apps = QMessageBox.question(
                self,
                "Không có ứng dụng nào được chọn",
                "Bạn chưa tích chọn ứng dụng nào được phép. Trong phiên khoá, mọi ứng dụng ngoài hệ thống sẽ bị đóng!\n\nBạn có muốn tiếp tục không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm_no_apps != QMessageBox.StandardButton.Yes:
                return

        h = total_minutes // 60
        m = total_minutes % 60
        time_desc = f"{h} giờ {m} phút" if h > 0 else f"{m} phút"
        
        reply = QMessageBox.critical(
            self,
            "⚠️ XÁC NHẬN KÍCH HOẠT CHẾ ĐỘ SIÊU TẬP TRUNG",
            f"BẠN CÓ CHẮC CHẮN MUỐN BẮT ĐẦU PHIÊN KHOÁ TRONG {time_desc}?\n\n"
            "🔴 HỆ QUẢ:\n"
            "1. Toàn bộ tab ngoài danh sách sẽ bị đóng ngay.\n"
            "2. Mọi ứng dụng ngoài danh sách sẽ bị FORCE KILL ngay khi mở.\n"
            "3. Ứng dụng này KHÔNG THỂ BỊ TẮT hay hủy bỏ trong suốt thời gian này.\n"
            "4. Ứng dụng tự động kích hoạt lại ngay cả khi đăng xuất hay khởi động lại máy.\n\n"
            "Bạn đã sẵn sàng bước vào trạng thái Siêu Tập Trung?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.is_session_active = True
        self.total_seconds = total_minutes * 60
        self.remaining_seconds = self.total_seconds

        allowed_app_paths = {}
        for app in selected_apps:
            nl = app.lower()
            if nl in self.app_paths and self.app_paths[nl]:
                allowed_app_paths[nl] = self.app_paths[nl]

        session_data = {
            "start_time": time.time(),
            "end_time": time.time() + self.total_seconds,
            "allowed_apps": selected_apps,
            "allowed_urls": selected_urls,
            "allowed_app_paths": allowed_app_paths,
            "show_floating_widget": self.chk_floating_widget.isChecked()
        }
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f)

        # Lock session file handle to prevent deletion or editing
        self._session_file_handle = lock_session_file(self.session_file)

        # Set auto-resume in registry
        set_autorun(self.session_file)

        # Create Win32 exit event
        create_exit_event()

        # Protect current process against taskkill
        protect_current_process(True)

        # 1. Start Watchdog process detached from console
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000

        watchdog_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "watchdog.py")
        self.watchdog_process = subprocess.Popen(
            [sys.executable, watchdog_script, "--target-pid", str(os.getpid()), self.session_file],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        )
        self.guard.set_watchdog_pid(self.watchdog_process.pid)

        # 2. Start SystemGuard
        self.guard.start_lockdown(selected_apps, allowed_app_paths)

        # 3. Instruct Browser Extension to lock tabs
        self.ws_bridge.start_lock(selected_urls)

        # 4. Start UI timer
        self.timer.start(1000)

        # 5. Show floating widget if requested
        if self.chk_floating_widget.isChecked():
            self.floating_widget.set_time(self.remaining_seconds)
            self.floating_widget.show()

        self.hide()

    def _on_timer_tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            if self.chk_floating_widget.isChecked():
                self.floating_widget.set_time(self.remaining_seconds)
            self.overlay_window.update_time(self.remaining_seconds)
        else:
            self._end_lockdown_session()

    def _end_lockdown_session(self):
        self.timer.stop()
        self.is_session_active = False

        self.guard.stop_lockdown()
        self.ws_bridge.stop_lock()

        # Signal clean exit to watchdog
        signal_exit_event()

        # Remove auto-resume from registry
        remove_autorun()

        # Release session file lock
        if self._session_file_handle:
            unlock_session_file(self._session_file_handle)
            self._session_file_handle = None

        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except Exception:
                pass

        # Remove process DACL protection
        protect_current_process(False)

        self.floating_widget.hide()
        self.overlay_window.hide()

        self.show()
        self.activateWindow()
        QMessageBox.information(
            self,
            "🎉 HOÀN THÀNH PHIÊN TẬP TRUNG!",
            "Chúc mừng bạn đã hoàn thành trọn vẹn phiên Siêu Tập Trung!\n"
            "Tất cả giới hạn ứng dụng và tab trình duyệt đã được gỡ bỏ."
        )

    def _on_app_killed(self, app_name):
        print(f"[UI] Forbidden app terminated: {app_name}")

    def _on_show_overlay(self, fg_name):
        if self.is_session_active:
            allowed = list(self.guard.allowed_apps)
            self.overlay_window.show_for_blocked_app(fg_name, self.remaining_seconds, allowed)

    def _on_hide_overlay(self):
        if self.overlay_window.isVisible():
            self.overlay_window.hide()

    def closeEvent(self, event):
        if self.is_session_active:
            event.ignore()
        else:
            self.ws_bridge.stop_lock()
            event.accept()
