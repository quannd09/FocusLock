import os
import sys
import time
import json
import subprocess
import psutil

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

def run_watchdog(target_pid, session_file):
    print(f"[Watchdog] Active. Guarding Main PID: {target_pid}, Session: {session_file}")

    python_executable = sys.executable
    if "python.exe" in python_executable.lower():
        pythonw_path = python_executable.lower().replace("python.exe", "pythonw.exe")
        if os.path.exists(pythonw_path):
            python_executable = pythonw_path

    while True:
        # Check if session file still exists
        if not os.path.exists(session_file):
            print("[Watchdog] Session completed cleanly. Exiting.")
            break

        # Read session data to check expiry
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            end_time = data.get("end_time", 0)
            if time.time() >= end_time:
                print("[Watchdog] Session duration has ended. Cleaning up.")
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                    except Exception:
                        pass
                break
        except Exception:
            pass

        # Check if target process is still alive
        if not psutil.pid_exists(target_pid):
            print(f"[Watchdog] TARGET PID {target_pid} WAS TERMINATED! Reviving main app immediately...")
            
            # Relaunch main.py with --resume-session in detached mode
            main_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
            cmd = [python_executable, main_script, "--resume-session", session_file]
            
            new_proc = subprocess.Popen(
                cmd, 
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            )
            target_pid = new_proc.pid
            print(f"[Watchdog] Main app revived with new PID: {target_pid}")

        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--target-pid":
        target_pid = int(sys.argv[2])
        session_file = sys.argv[3] if len(sys.argv) > 3 else ""
        run_watchdog(target_pid, session_file)
    else:
        print("Usage: python watchdog.py --target-pid <PID> <session_file>")
