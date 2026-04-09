from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .constants import APP_NAME


def _desktop_entry(
    name: str,
    comment: str,
    exec_cmd: str,
    icon: str,
    categories: str,
    no_display: bool = False,
) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={name}",
        f"Comment={comment}",
        f"Exec={exec_cmd}",
        f"Icon={icon}",
        "Terminal=false",
        f"Categories={categories}",
    ]
    if no_display:
        lines.append("NoDisplay=true")
    else:
        lines.append("StartupNotify=true")
    return "\n".join(lines) + "\n"


def _install_icon(icon_name: str) -> str:
    source_icon = Path(__file__).resolve().parent / "resources" / "icon.png"
    if not source_icon.exists():
        return icon_name

    icon_dir = (
        Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    )
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_dest = icon_dir / f"{icon_name}.png"
    shutil.copyfile(source_icon, icon_dest)
    return str(icon_dest)


def install_desktop_entries() -> None:
    applications_dir = Path.home() / ".local" / "share" / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    gui_exec = shutil.which("motionpaper") or "motionpaper"
    daemon_exec = shutil.which("motionpaper-daemon") or "motionpaper-daemon"
    icon_value = _install_icon(APP_NAME)

    gui_desktop = _desktop_entry(
        name="MotionPaper",
        comment="Wallpaper browser and launcher for linux-wallpaperengine",
        exec_cmd=gui_exec,
        icon=icon_value,
        categories="Graphics;Utility;",
    )
    daemon_desktop = _desktop_entry(
        name="MotionPaper Daemon",
        comment="Launches the MotionPaper daemon process",
        exec_cmd=daemon_exec,
        icon=icon_value,
        categories="Utility;",
        no_display=True,
    )

    gui_path = applications_dir / "motionpaper.desktop"
    daemon_path = applications_dir / "motionpaper-daemon.desktop"
    gui_path.write_text(gui_desktop, encoding="utf-8")
    daemon_path.write_text(daemon_desktop, encoding="utf-8")

    update_db = shutil.which("update-desktop-database")
    if update_db:
        subprocess.run(
            [update_db, str(applications_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print(f"installed desktop entry: {gui_path}")
    print(f"installed desktop entry: {daemon_path}")


def main() -> None:
    install_desktop_entries()


if __name__ == "__main__":
    main()
