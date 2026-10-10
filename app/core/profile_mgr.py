import os
import json

DEFAULT_PROFILES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "profiles.json")

DEFAULT_PROFILES = [
    {
        "name": "💻 Lập trình",
        "allowed_apps": ["Code.exe", "cursor.exe", "WindowsTerminal.exe", "cmd.exe", "powershell.exe"],
        "allowed_urls": ["github.com", "stackoverflow.com", "chatgpt.com", "docs.python.org", "google.com"],
        "duration_minutes": 45,
        "show_floating_widget": True
    },
    {
        "name": "📚 Học tập & Ôn thi",
        "allowed_apps": ["WINWORD.EXE", "Acrobat.exe", "Notepad.exe", "OneNote.exe"],
        "allowed_urls": ["notion.so", "wikipedia.org", "drive.google.com"],
        "duration_minutes": 60,
        "show_floating_widget": True
    },
    {
        "name": "⚡ Pomodoro Siêu Tốc",
        "allowed_apps": ["Code.exe", "WINWORD.EXE", "EXCEL.EXE"],
        "allowed_urls": ["google.com"],
        "duration_minutes": 25,
        "show_floating_widget": False
    }
]

class ProfileManager:
    def __init__(self, file_path=DEFAULT_PROFILES_PATH):
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            self.save_all(DEFAULT_PROFILES)

    def load_all(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_PROFILES

    def save_all(self, profiles):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ProfileManager] Error saving profiles: {e}")

    def add_or_update(self, profile):
        profiles = self.load_all()
        found = False
        for i, p in enumerate(profiles):
            if p.get("name") == profile.get("name"):
                profiles[i] = profile
                found = True
                break
        if not found:
            profiles.append(profile)
        self.save_all(profiles)

    def delete(self, profile_name):
        profiles = self.load_all()
        profiles = [p for p in profiles if p.get("name") != profile_name]
        self.save_all(profiles)
