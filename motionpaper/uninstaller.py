from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from .constants import APP_NAME, CONFIG_DIR, DAEMON_LOG_PATH, PID_FILE

DESKTOP_FILES = (
    "motionpaper.desktop",
    "motionpaper-daemon.desktop",
    "motionpaperdaemon.desktop",
)


def _stop_daemon() -> None:
    if PID_FILE.exists():
        pid = PID_FILE.read_text(encoding="utf-8").strip()
        if pid:
            try:
                os.kill(int(pid), 0)
                os.kill(int(pid), 15)
                print(f"stopped daemon pid: {pid}")
            except Exception:
                pass
        PID_FILE.unlink(missing_ok=True)

    DAEMON_LOG_PATH.unlink(missing_ok=True)


def _remove_desktop_entries() -> None:
    applications_dir = Path.home() / ".local" / "share" / "applications"
    autostart_dir = Path.home() / ".config" / "autostart"

    for desktop_file in DESKTOP_FILES:
        (applications_dir / desktop_file).unlink(missing_ok=True)
        (autostart_dir / desktop_file).unlink(missing_ok=True)

    update_db = shutil.which("update-desktop-database")
    if update_db:
        subprocess.run(
            [update_db, str(applications_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _remove_icon() -> None:
    icon_path = (
        Path.home()
        / ".local"
        / "share"
        / "icons"
        / "hicolor"
        / "256x256"
        / "apps"
        / f"{APP_NAME}.png"
    )
    icon_path.unlink(missing_ok=True)


def uninstall_local_integration(purge_config: bool = False) -> None:
    _stop_daemon()
    _remove_desktop_entries()
    _remove_icon()

    if purge_config:
        shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        print(f"removed config directory: {CONFIG_DIR}")
    else:
        print(f"kept config directory: {CONFIG_DIR}")

    print("motionpaper local integration cleanup complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="remove MotionPaper local desktop integration files"
    )
    parser.add_argument(
        "--purge-config",
        action="store_true",
        help="also remove ~/.config/motionpaper",
    )
    args = parser.parse_args()

    uninstall_local_integration(purge_config=args.purge_config)


if __name__ == "__main__":
    main()
