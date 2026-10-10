import os
import json
from PyQt6.QtGui import QPalette, QColor

THEME_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "theme_config.json")

DARK_PALETTE = {
    "name": "dark",
    "bg_base": "#090D16",
    "bg_card": "#0F172A",
    "bg_item": "#141E33",
    "bg_item_hover": "#1A2640",
    "bg_item_selected": "#1E2E4A",
    "border_color": "#1E293B",
    "border_active": "#0284C7",
    "accent": "#0284C7",
    "accent_hover": "#0369A1",
    "accent_pressed": "#075985",
    "text_main": "#F1F5F9",
    "text_muted": "#94A3B8",
    "text_sub": "#64748B",
    "badge_bg": "rgba(2, 132, 199, 0.16)",
    "badge_text": "#38BDF8",
    "badge_border": "rgba(56, 189, 248, 0.3)",
    "btn_bg": "#1E293B",
    "btn_hover": "#334155",
    "btn_border": "#334155",
}

WARM_PALETTE = {
    "name": "warm",
    "bg_base": "#FDE8D4",
    "bg_card": "#FFF5EC",
    "bg_item": "#FFFFFF",
    "bg_item_hover": "#FEEFE4",
    "bg_item_selected": "#FDDCC5",
    "border_color": "#F0C4A4",
    "border_active": "#C2410C",
    "accent": "#C2410C",
    "accent_hover": "#9A3412",
    "accent_pressed": "#7C2D12",
    "text_main": "#292524",
    "text_muted": "#78716C",
    "text_sub": "#A8A29E",
    "badge_bg": "rgba(194, 65, 12, 0.12)",
    "badge_text": "#C2410C",
    "badge_border": "rgba(194, 65, 12, 0.28)",
    "btn_bg": "#FFEADB",
    "btn_hover": "#FDDCC5",
    "btn_border": "#E8BA99",
}

def load_saved_theme():
    try:
        if os.path.exists(THEME_CONFIG_FILE):
            with open(THEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("theme", "dark")
    except Exception:
        pass
    return "dark"

def save_theme_preference(theme_name):
    try:
        with open(THEME_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": theme_name}, f, indent=2)
    except Exception:
        pass

def get_theme_palette(theme_name):
    return WARM_PALETTE if theme_name == "warm" else DARK_PALETTE

def apply_theme_palette_to_app(app, theme_name):
    if not app:
        return
    p = get_theme_palette(theme_name)
    pal = app.palette()
    text_color = QColor(p["text_main"])
    bg_color = QColor(p["bg_base"])
    card_color = QColor(p["bg_card"])
    item_color = QColor(p["bg_item"])
    accent_color = QColor(p["accent"])

    pal.setColor(QPalette.ColorRole.Window, bg_color)
    pal.setColor(QPalette.ColorRole.WindowText, text_color)
    pal.setColor(QPalette.ColorRole.Base, item_color)
    pal.setColor(QPalette.ColorRole.AlternateBase, card_color)
    pal.setColor(QPalette.ColorRole.ToolTipBase, item_color)
    pal.setColor(QPalette.ColorRole.ToolTipText, text_color)
    pal.setColor(QPalette.ColorRole.Text, text_color)
    pal.setColor(QPalette.ColorRole.Button, QColor(p["btn_bg"]))
    pal.setColor(QPalette.ColorRole.ButtonText, text_color)
    pal.setColor(QPalette.ColorRole.Highlight, accent_color)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

def build_stylesheet(theme_name):
    p = get_theme_palette(theme_name)
    return f"""
        * {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: {p['text_main']};
        }}

        QMainWindow, QWidget#centralWidget, QScrollArea#rootScrollArea {{
            background-color: {p['bg_base']};
            color: {p['text_main']};
        }}
        QScrollArea {{
            border: none;
            background-color: {p['bg_base']};
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {p['bg_base']};
        }}

        QLabel {{
            color: {p['text_main']};
            background: transparent;
        }}

        QLabel#brandTitle {{
            color: {p['text_main']};
            font-size: 16px;
            font-weight: 700;
        }}

        QGroupBox {{
            background-color: {p['bg_card']};
            border: 1px solid {p['border_color']};
            border-radius: 10px;
            margin-top: 14px;
            padding-top: 16px;
            font-weight: 700;
            color: {p['text_muted']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
            color: {p['accent']};
            font-size: 13px;
            font-weight: 700;
        }}

        QListWidget {{
            background-color: {p['bg_item']};
            border: 1px solid {p['border_color']};
            border-radius: 8px;
            padding: 4px;
            color: {p['text_main']};
            outline: none;
        }}
        QListWidget::item {{
            border-radius: 8px;
            margin-bottom: 3px;
            border: 1px solid transparent;
        }}
        QListWidget::item:hover {{
            background-color: {p['bg_item_hover']};
            border: 1px solid {p['border_color']};
        }}
        QListWidget::item:selected {{
            background-color: {p['bg_item_selected']};
            border: 1px solid {p['border_active']};
        }}
        
        /* Sleek Minimal Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background-color: {p['bg_card']};
            width: 8px;
            margin: 0px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {p['btn_border']};
            min-height: 26px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {p['accent']};
        }}
        QScrollBar::handle:vertical:pressed {{
            background-color: {p['accent_pressed']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            height: 0px;
        }}

        QPushButton {{
            background-color: {p['btn_bg']};
            color: {p['text_main']};
            border: 1px solid {p['btn_border']};
            border-radius: 8px;
            padding: 6px 12px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {p['btn_hover']};
            border-color: {p['border_active']};
            color: {p['text_main']};
        }}
        QPushButton:pressed {{
            background-color: {p['bg_card']};
            border-color: {p['accent']};
            padding-top: 7px;
            padding-bottom: 5px;
            color: {p['text_main']};
        }}

        QPushButton[compact="true"] {{
            padding: 4px 8px;
            font-size: 11px;
            border-radius: 6px;
        }}
        QPushButton[medium="true"] {{
            padding: 5px 10px;
            font-size: 11px;
            border-radius: 6px;
        }}

        QLineEdit, QSpinBox {{
            background-color: {p['bg_item']};
            border: 1px solid {p['border_color']};
            border-radius: 8px;
            padding: 6px 10px;
            color: {p['text_main']};
            font-size: 12px;
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border: 1px solid {p['accent']};
        }}

        QComboBox {{
            background-color: {p['bg_item']};
            border: 1px solid {p['border_color']};
            border-radius: 8px;
            padding: 6px 10px;
            color: {p['text_main']};
            font-size: 12px;
            font-weight: 600;
        }}
        QComboBox:focus, QComboBox:hover {{
            border: 1px solid {p['border_active']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {p['bg_item']};
            color: {p['text_main']};
            selection-background-color: {p['bg_item_selected']};
            selection-color: {p['text_main']};
            border: 1px solid {p['border_color']};
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            color: {p['text_main']};
            min-height: 28px;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {p['bg_item_hover']};
            color: {p['text_main']};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {p['bg_item_selected']};
            color: {p['text_main']};
        }}

        QCheckBox {{
            spacing: 8px;
            color: {p['text_main']};
            font-size: 12px;
            font-weight: 500;
        }}
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border-radius: 5px;
            border: 1px solid {p['btn_border']};
            background-color: {p['bg_item']};
        }}
        QCheckBox::indicator:hover {{
            border-color: {p['accent']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {p['accent']};
            border-color: {p['accent']};
        }}
    """
