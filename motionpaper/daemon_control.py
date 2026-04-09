import os
import shutil
import subprocess
import sys
import threading
import time

from .constants import DAEMON_LAUNCH_SCRIPT, PID_FILE, PROJECT_ROOT


def _read_pid():
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_daemon_running():
    pid = _read_pid()
    if not pid:
        return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _daemon_launch_command():
    if DAEMON_LAUNCH_SCRIPT.exists():
        return [str(DAEMON_LAUNCH_SCRIPT)]

    daemon_bin = shutil.which("motionpaper-daemon")
    if daemon_bin:
        return [daemon_bin]

    fallback_main = PROJECT_ROOT / "main.py"
    if fallback_main.exists():
        return [sys.executable, str(fallback_main)]

    return None


def launch_daemon():
    launch_cmd = _daemon_launch_command()
    if launch_cmd is None:
        print("daemon launcher not found (script, command, or main.py fallback)")
        return False

    try:
        proc = subprocess.Popen(
            launch_cmd,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            _, stderr = proc.communicate(timeout=2)
            if proc.returncode and proc.returncode != 0:
                if "Invalid vector format" in stderr or "not a valid image" in stderr:
                    return "incompatible"
                return False
        except subprocess.TimeoutExpired:
            return True

        return True
    except Exception as e:
        print(f"failed to launch daemon: {e}")
        return False


def kill_daemon():
    pid = _read_pid()
    if not pid:
        print("no pid file found")
        return False

    try:
        subprocess.run(["kill", str(pid)], check=True)
        killed_properly = False

        for _ in range(40):
            if not PID_FILE.exists():
                try:
                    os.kill(pid, 0)
                except OSError:
                    killed_properly = True
                    break
            time.sleep(0.1)

        if not killed_properly:
            subprocess.run(["kill", "-9", str(pid)], check=False)
            if PID_FILE.exists():
                PID_FILE.unlink()

        return True
    except Exception as e:
        print(f"failed to kill daemon: {e}")
        return False


def restart_daemon():
    killed = kill_daemon()
    if not killed:
        return False

    threading.Timer(0.5, launch_daemon).start()
    return True
