import win32gui
import win32con
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class OverlayLockWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.allowed_apps_str = ""
        self.target_allowed_hwnd = None
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Warning Card adhering to taste-skill shape lock & dark palette
        self.card = QWidget(self)
        self.card.setStyleSheet("""
            QWidget {
                background-color: #0B0F17;
                border: 1px solid #EF4444;
                border-radius: 12px;
                padding: 40px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(16)

        # Icon & Title
        icon_label = QLabel("⛔", self.card)
        icon_label.setFont(QFont("Segoe UI Emoji", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)

        title_label = QLabel("ỨNG DỤNG BỊ CHẶN & ĐÃ BỊ TẮT!", self.card)
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #F87171;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        # Message
        self.msg_label = QLabel(
            "Bạn đang trong phiên Siêu Tập Trung (Hardcore Focus Mode).\n"
            "Mọi ứng dụng và tab ngoài danh sách cho phép sẽ bị chặn và đóng ngay lập tức.",
            self.card
        )
        self.msg_label.setFont(QFont("Segoe UI", 12))
        self.msg_label.setStyleSheet("color: #94A3B8; line-height: 1.5;")
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.msg_label)

        # Countdown in Overlay with tabular digits
        self.timer_label = QLabel("Thời gian còn lại: --:--", self.card)
        self.timer_label.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        self.timer_label.setStyleSheet("color: #38BDF8; margin: 10px 0;")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.timer_label)

        # Allowed Apps reminder
        self.allowed_label = QLabel("", self.card)
        self.allowed_label.setFont(QFont("Segoe UI", 11))
        self.allowed_label.setStyleSheet("color: #64748B;")
        self.allowed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.allowed_label)

        # Action Button: Back to allowed app (with singular accent & tactile state)
        self.btn_back = QPushButton("🔙 Quay lại ứng dụng được phép", self.card)
        self.btn_back.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border: 1px solid #0369A1;
                border-radius: 8px;
                padding: 12px 28px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #0369A1;
                border-color: #38BDF8;
            }
            QPushButton:pressed {
                background-color: #075985;
                padding-top: 13px;
                padding-bottom: 11px;
            }
        """)
        self.btn_back.clicked.connect(self.refocus_allowed_app)
        card_layout.addWidget(self.btn_back, alignment=Qt.AlignmentFlag.AlignCenter)

        # Bottom hint
        hint_label = QLabel("🔒 Chỉ có thể hủy bỏ bằng cách Khởi động lại hoặc Tắt máy tính.", self.card)
        hint_label.setFont(QFont("Segoe UI", 10))
        hint_label.setStyleSheet("color: #64748B; margin-top: 8px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(hint_label)

        layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_for_blocked_app(self, app_name, remaining_seconds, allowed_apps):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        m, s = divmod(remaining_seconds, 60)
        h, m = divmod(m, 60)
        time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        self.timer_label.setText(f"Thời gian còn lại: {time_str}")
        self.allowed_label.setText(f"Ứng dụng cho phép: {', '.join(allowed_apps) if allowed_apps else 'Không có'}")
        
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def update_time(self, seconds_left):
        m, s = divmod(seconds_left, 60)
        h, m = divmod(m, 60)
        time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        self.timer_label.setText(f"Thời gian còn lại: {time_str}")

    def refocus_allowed_app(self):
        # Hide overlay
        self.hide()
        # Find and restore foreground window if an allowed hwnd exists
        if self.target_allowed_hwnd and win32gui.IsWindow(self.target_allowed_hwnd):
            try:
                win32gui.ShowWindow(self.target_allowed_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.target_allowed_hwnd)
            except Exception:
                pass

    def closeEvent(self, event):
        # Never close via standard event during session
        event.ignore()
