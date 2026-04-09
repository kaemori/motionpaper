from pathlib import Path

APP_NAME = "motionpaper"
VERSION = "1.23.2"

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"
SCREENSHOT_PATH = CONFIG_DIR / "motionpaper.png"
TEMP_WALLPAPER_PATH = CONFIG_DIR / "motionpaper_temp.png"
PID_FILE = Path("/tmp/motionpaper-daemon.pid")
DAEMON_LOG_PATH = Path("/tmp/motionpaper-daemon.log")

WPE_WORKSHOP_DIR = (
    Path.home()
    / ".local"
    / "share"
    / "Steam"
    / "steamapps"
    / "workshop"
    / "content"
    / "431960"
)

THEMES_PATH = PACKAGE_ROOT / "resources" / "themes.json"

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
GUI_LAUNCH_SCRIPT = SCRIPTS_DIR / "launch_gui.sh"
DAEMON_LAUNCH_SCRIPT = SCRIPTS_DIR / "launch_daemon.sh"
