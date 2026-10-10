import os
import sys
import ctypes
from ctypes import wintypes
import win32api

advapi32 = ctypes.windll.advapi32
kernel32 = ctypes.windll.kernel32

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = -1

WRITE_DAC = 0x00040000
DACL_SECURITY_INFORMATION = 4
SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002

EXIT_EVENT_NAME = r"Local\FocusLock_Exit_Event"


def protect_current_process(enable=True):
    """
    Applies DACL protection denying PROCESS_TERMINATE to prevent external taskkill.
    When enable is False, restores normal access.
    """
    try:
        sddl = "D:(D;;0x0001;;;WD)(A;;0x1FFFFE;;;WD)" if enable else "D:(A;;0x1FFFFF;;;WD)"
        p_sd = wintypes.LPVOID()
        if advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(p_sd), None):
            h_proc = kernel32.OpenProcess(WRITE_DAC, False, os.getpid())
            if h_proc:
                advapi32.SetKernelObjectSecurity(h_proc, DACL_SECURITY_INFORMATION, p_sd)
                kernel32.CloseHandle(h_proc)
            kernel32.LocalFree(p_sd)
            return True
    except Exception:
        pass
    return False


def create_exit_event():
    """Creates a Win32 manual-reset event for inter-process exit signaling."""
    return kernel32.CreateEventW(None, True, False, EXIT_EVENT_NAME)


def signal_exit_event():
    """Signals the exit event so watchdog knows the session finished cleanly."""
    try:
        h = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, EXIT_EVENT_NAME)
        if h:
            kernel32.SetEvent(h)
            kernel32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False


def is_exit_event_signaled():
    """Checks whether the exit event has been signaled."""
    try:
        h = kernel32.OpenEventW(SYNCHRONIZE, False, EXIT_EVENT_NAME)
        if h:
            res = kernel32.WaitForSingleObject(h, 0)
            kernel32.CloseHandle(h)
            return res == 0
    except Exception:
        pass
    return False


def lock_session_file(file_path):
    """
    Opens an exclusive read-shared handle on the session file.
    Prevents any process from deleting or writing to the session file.
    """
    try:
        handle = kernel32.CreateFileW(
            os.path.abspath(file_path),
            GENERIC_READ,
            FILE_SHARE_READ,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        if handle != INVALID_HANDLE_VALUE:
            return handle
    except Exception:
        pass
    return None


def unlock_session_file(handle):
    """Releases the locked session file handle."""
    if handle and handle != INVALID_HANDLE_VALUE:
        try:
            kernel32.CloseHandle(handle)
        except Exception:
            pass


def get_pe_original_filename(exe_path):
    """
    Reads the OriginalFilename from Windows PE version information.
    Detects if an unauthorized executable was renamed to bypass the filter.
    """
    if not exe_path or not os.path.isfile(exe_path):
        return None
    try:
        lang_trans = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")
        if not lang_trans:
            return None
        lang, codepage = lang_trans[0]
        sub_block = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\OriginalFilename"
        val = win32api.GetFileVersionInfo(exe_path, sub_block)
        if val:
            cleaned = str(val).strip().lower()
            if cleaned.endswith(".mui"):
                cleaned = cleaned[:-4]
            if not cleaned.endswith(".exe"):
                cleaned += ".exe"
            return cleaned
    except Exception:
        pass
    return None
