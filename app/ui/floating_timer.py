from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

class FloatingTimerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.old_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        # Always-on-top, frameless tool window
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        # Icon
        self.icon_label = QLabel("🔒")
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)

        # Time label with monospace tabular figures to prevent jitter
        self.time_label = QLabel("00:00:00")
        self.time_label.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        self.time_label.setStyleSheet("color: #38BDF8; letter-spacing: 0.5px;")
        layout.addWidget(self.time_label)

        # Status badge
        self.status_label = QLabel("FOCUSING")
        self.status_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #F87171; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 6px; border-radius: 4px;")
        layout.addWidget(self.status_label)

        # Styling - Clean solid surface adhering to 8px shape lock
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0F17;
                border: 1px solid #1F2937;
                border-radius: 8px;
            }
        """)

        # Position at top-right by default
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen.width() - 250, 40, 210, 45)

    def set_time(self, seconds_left):
        m, s = divmod(seconds_left, 60)
        h, m = divmod(m, 60)
        if h > 0:
            self.time_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self.time_label.setText(f"{m:02d}:{s:02d}")

    # Draggable handling
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if not self.old_pos.isNull():
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = QPoint()
