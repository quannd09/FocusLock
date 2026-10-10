import sys
import os
import json
import time
import ctypes

# Force UTF-8 on Windows stdio to prevent UnicodeEncodeError on Vietnamese characters
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow

def secure_console():
    """Hides and disables the close button on any attached terminal window."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # Disable close 'X' button on the console
            hmenu = ctypes.windll.user32.GetSystemMenu(hwnd, False)
            if hmenu:
                ctypes.windll.user32.EnableMenuItem(hmenu, 0xF060, 0x00000001)  # SC_CLOSE, MF_GRAYED
            # Hide the console completely from view
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass

def main():
    # Hide any console window immediately
    secure_console()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()

    # Check if this process was launched by Watchdog to resume an active session
    if "--resume-session" in sys.argv:
        try:
            idx = sys.argv.index("--resume-session")
            session_file = sys.argv[idx + 1]
            if os.path.exists(session_file):
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                remaining = int(data.get("end_time", 0) - time.time())
                if remaining > 0:
                    print(f"[Main] Resuming active session with {remaining} seconds remaining...")
                    window.is_session_active = True
                    window.total_seconds = remaining
                    window.remaining_seconds = remaining
                    allowed_apps = data.get("allowed_apps", [])
                    allowed_urls = data.get("allowed_urls", [])

                    window.guard.start_lockdown(allowed_apps)
                    window.ws_bridge.start_lock(allowed_urls)
                    window.timer.start(1000)

                    if data.get("show_floating_widget", True):
                        window.floating_widget.set_time(remaining)
                        window.floating_widget.show()

                    window.hide()
                else:
                    window.show()
        except Exception as e:
            print(f"[Main] Error resuming session: {e}")
            window.show()
    else:
        window.show()
        window.raise_()
        window.activateWindow()

    # System Tray Icon
    tray_icon = QSystemTrayIcon(window)
    tray_icon.setIcon(window.windowIcon() if not window.windowIcon().isNull() else app.style().standardIcon(app.style().StandardPixmap.SP_MessageBoxInformation))
    tray_icon.setToolTip("FocusLock - Chế độ Siêu Tập Trung")

    def _bring_to_front():
        if not window.is_session_active:
            window.show()
            window.raise_()
            window.activateWindow()

    tray_menu = QMenu()
    action_open = QAction("Mở bảng điều khiển", window)
    action_open.triggered.connect(_bring_to_front)
    tray_menu.addAction(action_open)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
