from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

class ItemCardWidget(QWidget):
    """
    2-line hierarchical card widget for app and browser tab items.
    Line 1: Checkbox + Bold Title + Pill Badge
    Line 2: Muted domain or secondary path info
    """
    toggled = pyqtSignal(bool)

    def __init__(self, title, subtitle, badge_text="", is_checked=True, data="", palette=None):
        super().__init__()
        self.data = data
        self.palette = palette or {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        # Left: Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(is_checked)
        self.checkbox.toggled.connect(self._on_check_toggled)
        layout.addWidget(self.checkbox)

        # Center: Two-line title & subtitle
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.lbl_title.setWordWrap(False)
        self.lbl_title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_layout.addWidget(self.lbl_title)

        clean_sub = subtitle or ""
        self.lbl_sub = QLabel(clean_sub)
        self.lbl_sub.setFont(QFont("Segoe UI", 9))
        self.lbl_sub.setWordWrap(False)
        self.lbl_sub.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_layout.addWidget(self.lbl_sub)

        layout.addLayout(text_layout, 1)

        # Right: Pill Badge (Edge, Cốc Cốc, Chrome, App, etc.)
        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not badge_text:
            self.lbl_badge.hide()
        layout.addWidget(self.lbl_badge)

        self.apply_theme(self.palette)

    def _on_check_toggled(self, checked):
        self.toggled.emit(checked)

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked):
        self.checkbox.setChecked(checked)

    def apply_theme(self, palette):
        if not palette:
            return
        self.palette = palette
        text_main = palette.get("text_main", "#F1F5F9")
        text_muted = palette.get("text_muted", "#94A3B8")
        badge_bg = palette.get("badge_bg", "rgba(2, 132, 199, 0.16)")
        badge_text = palette.get("badge_text", "#38BDF8")
        badge_border = palette.get("badge_border", "rgba(56, 189, 248, 0.3)")

        self.lbl_title.setStyleSheet(f"color: {text_main}; background: transparent;")
        self.lbl_sub.setStyleSheet(f"color: {text_muted}; background: transparent;")
        self.lbl_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {badge_bg};
                color: {badge_text};
                border: 1px solid {badge_border};
                border-radius: 4px;
                padding: 2px 7px;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Clicking card toggles checkbox
            self.checkbox.toggle()
        super().mousePressEvent(event)
