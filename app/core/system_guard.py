import os
import sys
import time
import ctypes
import threading
import psutil
import win32gui
import win32process
import win32con
import win32api
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# Compilers, build tools, debuggers and language servers that must NEVER be terminated
DEV_TOOLS_PROCESSES = {
    "gcc.exe", "g++.exe", "clang.exe", "clang++.exe", "cc1.exe", "cc1plus.exe",
    "as.exe", "ld.exe", "make.exe", "cmake.exe", "ninja.exe", "gdb.exe", "lldb.exe",
    "cpptools.exe", "cpptools-srv.exe", "clangd.exe", "git.exe",
    "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe"
}

# Windows system, drivers, hardware OSD & background services that must NEVER be killed
SYSTEM_PROTECTED_PROCESSES = {
    # Core Windows OS
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", 
    "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", "dwm.exe",
    "fontdrvhost.exe", "sihost.exe", "svchost.exe", "explorer.exe", 
    "ctfmon.exe", "taskhostw.exe", "runtimebroker.exe", "shellexperiencehost.exe",
    "searchhost.exe", "startmenuexperiencehost.exe", "textinputhost.exe",
    "lockapp.exe", "conhost.exe", "audiodg.exe", "spoolsv.exe",
    "securityhealthservice.exe", "msmpeng.exe", "nissrv.exe", "antigravity.exe",
    "python.exe", "pythonw.exe", "focuslock.exe",
    # Hardware OEM / Drivers / Volume & Brightness OSD
    "snapos64.exe", "snaposs64.exe", "hotkeyserviceuwp.exe", "hpsfuservice.exe",
    "hpsvcsscan.exe", "rtkauduservice64.exe", "intelaudioservice.exe",
    "elan_moc_service.exe", "defendersessionhelper.exe", "crossdeviceresume.exe",
    "widgets.exe", "widgetservice.exe", "backgroundtaskhost.exe", "appactions.exe",
    "apphelpercap.exe", "aggregatorhost.exe", "dllhost.exe", "wmiprvse.exe",
    "useroobebroker.exe", "smartscreen.exe", "applicationframehost.exe",
    # Windows system services
    "gameinputsvc.exe", "searchfilterhost.exe", "searchprotocolhost.exe",
    "dashost.exe", "lsaiso.exe", "wudfhost.exe", "intelcphdcpsvc.exe",
    "memcompression", "networkcap.exe", "diagscap.exe", "sysinfocap.exe",
    "touchpointanalyticsclientservice.exe", "unsecapp.exe", "warp-svc.exe",
    "foxitreaderupdateservice.exe", "fmservice64.exe", "officeclicktorun.exe",
    "ipfsvc.exe", "ngciso.exe", "gameinputredistservice.exe", "ipf_uf.exe",
    "mysqld.exe", "jhi_service.exe", "mpdefendercorereservice.exe", "mpdefendercore.exe",
    "gamingservicesnet.exe", "gamingservices.exe", "wmiregistrationservice.exe",
    "wlanext.exe", "codex-windows-sandbox-service.exe", "lanwlanwwanswitchingserviceuwp.exe",
    "presentmonservice.exe", "searchindexer.exe"
}.union(DEV_TOOLS_PROCESSES)

# Daemon / noise processes to ignore in UI window selection
DAEMON_NOISE_PROCESSES = {
    "dwm.exe", "svchost.exe", "taskhostw.exe", "shellhost.exe",
    "searchhost.exe", "startmenuexperiencehost.exe", "rtkauduservice64.exe",
    "textinputhost.exe", "shellexperiencehost.exe", "python.exe", "cmd.exe",
    "conhost.exe", "crossdeviceresume.exe", "lockapp.exe", "applicationframehost.exe",
    "smartscreen.exe", "widgets.exe", "widgetservice.exe", "backgroundtaskhost.exe",
    "appactions.exe", "apphelpercap.exe", "aggregatorhost.exe", "dllhost.exe", 
    "wmiprvse.exe", "useroobebroker.exe", "hpaudioanalytics.exe", "securityhealthsystray.exe",
    "defendersessionhelper.exe", "ipf_helper.exe", "explorer.exe", "powershell.exe"
}

# Windows Low-Level Keyboard Hook
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
VK_F4 = 0x73


class SystemGuard:
    def __init__(self, on_unauthorized_app_killed=None, on_show_overlay=None, on_hide_overlay=None):
        self.allowed_apps = set()
        self.is_locked = False
        self.watchdog_pid = None
        self.own_pid = os.getpid()
        self.on_unauthorized_app_killed = on_unauthorized_app_killed
        self.on_show_overlay = on_show_overlay
        self.on_hide_overlay = on_hide_overlay

        self._guard_thread = None
        self._hook_thread = None
        self._hook_id = None
        self._stop_event = threading.Event()
        self._active_session_id = kernel32.WTSGetActiveConsoleSessionId()

    def set_watchdog_pid(self, pid):
        self.watchdog_pid = pid

    @staticmethod
    def get_running_user_apps():
        """
        Ultra-fast (<5ms) native Win32 window scanner.
        Scans ONLY actual interactive application windows currently open on the user desktop.
        """
        results = {}
        active_sess = kernel32.WTSGetActiveConsoleSessionId()

        hdesk = user32.OpenInputDesktop(0, False, 0x0100)
        if not hdesk:
            hdesk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())

        def enum_proc(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()

            if not title or title in ('Program Manager', 'Settings', 'Default IME', 'MSCTFIME UI', 'OleMainThreadWndName'):
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0 or pid.value == os.getpid():
                return True

            sess = wintypes.DWORD()
            if kernel32.ProcessIdToSessionId(pid.value, ctypes.byref(sess)):
                if sess.value != active_sess:
                    return True

            try:
                p = psutil.Process(pid.value)
                pname = p.name()
            except Exception:
                return True

            pname_lower = pname.lower()
            if pname_lower in DAEMON_NOISE_PROCESSES:
                return True

            if pname not in results or len(title) > len(results[pname]['title']):
                results[pname] = {
                    'name': pname,
                    'title': title,
                    'pid': pid.value,
                    'hwnd': hwnd
                }

            return True

        cb = WNDENUMPROC(enum_proc)
        try:
            if hdesk:
                user32.EnumDesktopWindows(hdesk, cb, 0)
                user32.CloseDesktop(hdesk)
            else:
                user32.EnumWindows(cb, 0)
        except Exception as e:
            print(f"[SystemGuard] EnumDesktopWindows warning: {e}")

        # Ensure active popular browsers or code editors are listed
        try:
            for p in psutil.process_iter(['name', 'pid']):
                pname = p.info.get('name')
                if not pname:
                    continue
                pname_lower = pname.lower()
                if pname_lower in ('chrome.exe', 'msedge.exe', 'browser.exe', 'brave.exe', 'firefox.exe', 'code.exe', 'devcpp.exe'):
                    if pname not in results:
                        results[pname] = {
                            "name": pname,
                            "title": pname.replace(".exe", "").capitalize(),
                            "pid": p.info['pid'],
                            "hwnd": 0
                        }
        except Exception:
            pass

        return sorted(list(results.values()), key=lambda x: x['title'].lower())

    def _is_descendant_of_allowed(self, proc):
        """
        Checks if a process is a child/descendant of any allowed application
        (e.g. g++.exe spawned by Code.exe or devcpp.exe).
        """
        try:
            curr = proc
            for _ in range(5):  # Check up to 5 levels of parentage
                parent = curr.parent()
                if not parent:
                    break
                pname = parent.name().lower()
                if pname in self.allowed_apps:
                    return True
                curr = parent
        except Exception:
            pass
        return False

    def start_lockdown(self, allowed_apps_list):
        """
        Starts the lockdown:
        - Stores allowed apps (case-insensitive)
        - Starts background kill-loop and foreground check
        - Installs low-level keyboard hook to block Alt+F4
        """
        self._active_session_id = kernel32.WTSGetActiveConsoleSessionId()
        self.allowed_apps = {app.strip().lower() for app in allowed_apps_list if app.strip()}
        self.allowed_apps.add("python.exe")
        self.allowed_apps.add("pythonw.exe")

        self.is_locked = True
        self._stop_event.clear()

        self._guard_thread = threading.Thread(target=self._enforcement_loop, daemon=True)
        self._guard_thread.start()

        self._hook_thread = threading.Thread(target=self._keyboard_hook_worker, daemon=True)
        self._hook_thread.start()

        print(f"[SystemGuard] Lockdown activated! Allowed apps: {self.allowed_apps}")

    def stop_lockdown(self):
        """Stops lockdown and releases hooks."""
        self.is_locked = False
        self._stop_event.set()
        if self._hook_id:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self._hook_id)
            except Exception:
                pass
            self._hook_id = None
        print("[SystemGuard] Lockdown ended. Normal operation restored.")

    def _enforcement_loop(self):
        """
        Enforcement loop:
        Target ONLY interactive desktop windows in the active user console session.
        Never touches Session 0 background services, compilers, or child processes of allowed apps.
        """
        while not self._stop_event.is_set():
            try:
                self._check_and_kill_unauthorized_windows()
                self._check_foreground_window()
            except Exception as e:
                print(f"[SystemGuard] Enforcement loop error: {e}")

            time.sleep(0.3)

    def _check_and_kill_unauthorized_windows(self):
        """
        Scans visible windows on the interactive desktop.
        If an unauthorized user app has a visible window, kill its process immediately!
        """
        hdesk = user32.OpenInputDesktop(0, False, 0x0100)
        if not hdesk:
            hdesk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())

        def scan_kill_proc(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_pid = pid.value

            if proc_pid == 0 or proc_pid == self.own_pid or (self.watchdog_pid and proc_pid == self.watchdog_pid):
                return True

            # Verify session belongs to active user console
            sess = wintypes.DWORD()
            if kernel32.ProcessIdToSessionId(proc_pid, ctypes.byref(sess)):
                if sess.value != self._active_session_id:
                    return True

            try:
                proc = psutil.Process(proc_pid)
                name = proc.name()
                name_lower = name.lower()

                # NEVER terminate system protected processes, OEM utilities, or dev tools
                if name_lower in SYSTEM_PROTECTED_PROCESSES:
                    return True

                # If this process is a child/descendant of an allowed app (e.g. runner/compiler), spare it!
                if self._is_descendant_of_allowed(proc):
                    return True

                # If this visible window belongs to a forbidden app: KILL IT!
                if name_lower not in self.allowed_apps:
                    print(f"[SystemGuard] FORBIDDEN APP DETECTED: {name} (PID: {proc_pid}). Killing...")
                    proc.kill()
                    if self.on_unauthorized_app_killed:
                        self.on_unauthorized_app_killed(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                print(f"[SystemGuard] Failed to kill PID {proc_pid}: {e}")

            return True

        cb = WNDENUMPROC(scan_kill_proc)
        try:
            if hdesk:
                user32.EnumDesktopWindows(hdesk, cb, 0)
                user32.CloseDesktop(hdesk)
            else:
                user32.EnumWindows(cb, 0)
        except Exception:
            pass

    def _check_foreground_window(self):
        try:
            fg_hwnd = win32gui.GetForegroundWindow()
            if not fg_hwnd:
                return

            _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
            if fg_pid == self.own_pid or (self.watchdog_pid and fg_pid == self.watchdog_pid):
                return

            proc = psutil.Process(fg_pid)
            fg_name = proc.name().lower()

            if fg_name in self.allowed_apps or fg_name in DEV_TOOLS_PROCESSES or self._is_descendant_of_allowed(proc):
                if self.on_hide_overlay:
                    self.on_hide_overlay()
            elif fg_name not in SYSTEM_PROTECTED_PROCESSES:
                if self.on_show_overlay:
                    self.on_show_overlay(fg_name)
        except Exception:
            pass

    def _keyboard_hook_worker(self):
        """
        Low-level keyboard hook to block Alt+F4 while locked.
        """
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_ulonglong)
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT))

        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and self.is_locked:
                kb = lParam.contents
                alt_pressed = win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if kb.vkCode == VK_F4 and alt_pressed:
                        print("[SystemGuard] Blocked Alt+F4 attempt!")
                        return 1

            return ctypes.windll.user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

        self._c_hook_proc = HOOKPROC(hook_proc)
        h_mod = kernel32.GetModuleHandleW(None)
        self._hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._c_hook_proc, h_mod, 0)

        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.05)
