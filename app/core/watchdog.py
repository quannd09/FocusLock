import os
import sys
import time
import json
import subprocess
import psutil

# Ensure app package is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.process_security import (
    protect_current_process,
    is_exit_event_signaled
)

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def run_watchdog(target_pid, session_file):
    # Enable DACL protection against taskkill
    protect_current_process(True)

    print(f"[Watchdog] Active. Guarding Main PID: {target_pid}, Session: {session_file}")

    python_executable = sys.executable
    if "python.exe" in python_executable.lower():
        pythonw_path = python_executable.lower().replace("python.exe", "pythonw.exe")
        if os.path.exists(pythonw_path):
            python_executable = pythonw_path

    # Cache session data in memory to defend against file deletion
    cached_session_data = {}
    end_time = 0
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                cached_session_data = json.load(f)
            end_time = cached_session_data.get("end_time", 0)
        except Exception:
            pass

    while True:
        # Check if clean exit was signaled by the main window
        if is_exit_event_signaled():
            print("[Watchdog] Clean exit event detected. Exiting.")
            break

        # Check if session expired
        if end_time > 0 and time.time() >= end_time:
            print("[Watchdog] Session duration has ended. Cleaning up.")
            if session_file and os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception:
                    pass
            break

        # If session file was deleted while session is still active: regenerate it from cache
        if session_file and not os.path.exists(session_file):
            if end_time > 0 and time.time() < end_time and not is_exit_event_signaled():
                print("[Watchdog] Session file deleted unexpectedly! Recreating from memory cache...")
                try:
                    with open(session_file, "w", encoding="utf-8") as f:
                        json.dump(cached_session_data, f)
                except Exception as e:
                    print(f"[Watchdog] Failed to recreate session file: {e}")

        # Check if target process is still alive
        if not psutil.pid_exists(target_pid):
            if end_time > 0 and time.time() < end_time and not is_exit_event_signaled():
                print(f"[Watchdog] Target PID {target_pid} terminated unexpectedly! Reviving main app...")
                main_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
                cmd = [python_executable, main_script, "--resume-session", session_file]
                new_proc = subprocess.Popen(
                    cmd,
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
                )
                target_pid = new_proc.pid
                print(f"[Watchdog] Main app revived with new PID: {target_pid}")
            else:
                break

        time.sleep(1)

    protect_current_process(False)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--target-pid":
        target_pid = int(sys.argv[2])
        session_file = sys.argv[3] if len(sys.argv) > 3 else ""
        run_watchdog(target_pid, session_file)
    else:
        print("Usage: python watchdog.py --target-pid <PID> <session_file>")
