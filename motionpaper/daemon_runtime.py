import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config_store import load_config
from .constants import (
    CONFIG_DIR,
    CONFIG_PATH,
    DAEMON_LOG_PATH,
    PID_FILE,
    SCREENSHOT_PATH,
    TEMP_WALLPAPER_PATH,
)

try:
    from screeninfo import get_monitors

    _monitors = get_monitors()
    DISPLAY = _monitors[0].name if _monitors else ":0"
except Exception:
    DISPLAY = ":0"


logging.basicConfig(
    filename=str(DAEMON_LOG_PATH),
    level=logging.DEBUG,
    format="%(asctime)s - %(message)s",
)

current_process = None

ENGINE_RELEVANT_KEYS = (
    "wpid",
    "scaling",
    "fps",
    "fullscreen_pause",
    "mute",
    "volume",
    "automute",
    "audio_processing",
    "particles",
    "track_mouse",
    "parallax",
)


def _engine_config_signature(config):
    return tuple((key, config.get(key)) for key in ENGINE_RELEVANT_KEYS)


def _apply_engine_options(command, config, force_silent=False):
    fps = config.get("fps", 30)
    command.extend(["--fps", str(fps)])

    if not config.get("fullscreen_pause", True):
        command.append("--no-fullscreen-pause")

    if not config.get("particles", True):
        command.append("--disable-particles")

    if not config.get("track_mouse", True):
        command.append("--disable-mouse")

    if not config.get("parallax", True):
        command.append("--disable-parallax")

    if force_silent or config.get("mute", False):
        command.append("--silent")
    else:
        volume = config.get("volume", 15)
        command.extend(["--volume", str(volume)])

    if not config.get("automute", True):
        command.append("--noautomute")

    if not config.get("audio_processing", True):
        command.append("--no-audio-processing")

    return command


def _build_creation_command(wpid, config, force_silent=False):
    command = [
        "linux-wallpaperengine",
        "suo" "--screenshot",
        str(SCREENSHOT_PATH),
        "--screen-root",
        DISPLAY,
        "--bg",
        str(wpid),
    ]

    scaling = config.get("scaling", "default")
    if scaling and scaling != "default":
        command.extend(["--scaling", scaling])

    return _apply_engine_options(command, config, force_silent=force_silent)


def _create_black_image():
    return Image.new("RGB", (1920, 1080), color=(1, 1, 1))


def _set_wallpaper(file_path):
    if shutil.which("caelestia"):
        subprocess.run(["caelestia", "wallpaper", "-f", str(file_path)], check=True)
        subprocess.run(["caelestia", "scheme", "set", "--mode", "dark"], check=True)
        return

    if not shutil.which("hyprctl"):
        raise RuntimeError("neither caelestia nor hyprctl was found")

    path = str(file_path)
    subprocess.run(["hyprctl", "hyprpaper", "preload", path], check=True)
    subprocess.run(["hyprctl", "hyprpaper", "wallpaper", f",{path}"], check=True)


def _reset_wallpaper_backend():
    if shutil.which("caelestia"):
        subprocess.run(["caelestia", "wallpaper", "-r"], check=True)
        return

    if not shutil.which("hyprctl"):
        raise RuntimeError("neither caelestia nor hyprctl was found")

    subprocess.run(["hyprctl", "hyprpaper", "unload", "all"], check=True)


def kill_all_wallpaper_engines():
    logging.info("hunting down all wallpaper engine processes...")
    try:
        subprocess.run(["pkill", "-9", "linux-wallpaper"], check=False)
        time.sleep(0.5)
        logging.info("all wallpaper processes have been dealt with >:3")
    except Exception as e:
        logging.warning(f"failed to pkill wallpapers: {e}")


def kill_existing_wallpaper():
    global current_process

    if current_process and current_process.poll() is None:
        logging.info(f"killing existing wallpaper process (pid: {current_process.pid})")
        try:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logging.warning("process didn't die nicely, force killing")
            try:
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            except Exception as e:
                logging.warning(f"killpg failed: {e}, trying regular kill")
                current_process.kill()
        except Exception as e:
            logging.warning(f"error killing process: {e}")
            try:
                current_process.kill()
            except Exception:
                pass
        current_process = None


def _try_delete(path: Path):
    try:
        if path.exists():
            path.unlink()
            logging.info(f"deleted file: {path}")
    except Exception as e:
        logging.warning(f"failed to delete {path}: {e}")


def _wait_for_screenshot(path: Path, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            size_before = path.stat().st_size
            time.sleep(0.5)
            if path.stat().st_size == size_before and size_before > 0:
                return True
        time.sleep(0.2)
    return False


def start_wallpaper_engine(wpid):
    global current_process

    if not wpid:
        logging.error("no wpid provided, skipping")
        return

    kill_all_wallpaper_engines()

    logging.info(f"starting wallpaper with id: {wpid}")

    config = load_config()

    creation_command = _build_creation_command(wpid, config, force_silent=False)
    capture_command = _build_creation_command(wpid, config, force_silent=True)

    logging.info(f"full command: {' '.join(creation_command)}")

    _create_black_image().save(TEMP_WALLPAPER_PATH, format="png")
    _set_wallpaper(TEMP_WALLPAPER_PATH)
    _try_delete(SCREENSHOT_PATH)

    current_process = subprocess.Popen(capture_command, start_new_session=True)

    logging.info("waiting for screenshot to be created...")
    time.sleep(5)

    try:
        logging.info("setting static wallpaper")
        _reset_wallpaper_backend()
        _set_wallpaper(SCREENSHOT_PATH)

        logging.info("wallpaper update complete!!")
        logging.info("recreating current process...")
        kill_existing_wallpaper()
        logging.info("current process killed, recreating...")
        current_process = subprocess.Popen(creation_command, start_new_session=True)
        logging.info(f"new wallpaper process started with pid: {current_process.pid}")
        _try_delete(TEMP_WALLPAPER_PATH)
    except Exception as e:
        logging.warning(f"failed to set wallpaper: {e}")
        logging.warning("using black image as fallback wallpaper")
        _set_wallpaper(TEMP_WALLPAPER_PATH)


def set_static_wallpaper(wpid):
    if not wpid:
        logging.error("no wpid provided, skipping")
        return

    kill_all_wallpaper_engines()
    kill_existing_wallpaper()

    config = load_config()
    creation_command = _build_creation_command(wpid, config, force_silent=True)

    _create_black_image().save(TEMP_WALLPAPER_PATH, format="png")
    _set_wallpaper(TEMP_WALLPAPER_PATH)
    _try_delete(SCREENSHOT_PATH)

    logging.info("starting static wallpaper capture")
    capture_process = subprocess.Popen(creation_command, start_new_session=True)

    try:
        logging.info("waiting for screenshot to be created...")
        if _wait_for_screenshot(SCREENSHOT_PATH, timeout=15):
            logging.info("setting static wallpaper")
            _reset_wallpaper_backend()
            _set_wallpaper(SCREENSHOT_PATH)
            logging.info("static wallpaper set")
        else:
            logging.warning("screenshot not ready; using fallback image")
            _set_wallpaper(TEMP_WALLPAPER_PATH)
    finally:
        if capture_process.poll() is None:
            try:
                os.killpg(os.getpgid(capture_process.pid), signal.SIGTERM)
                capture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(capture_process.pid), signal.SIGKILL)
                except Exception as e:
                    logging.warning(f"killpg failed: {e}")
            except Exception as e:
                logging.warning(f"error killing capture process: {e}")

        _try_delete(TEMP_WALLPAPER_PATH)


def cleanup_and_exit(signum=None, frame=None):
    logging.info(f"cleanup called (signal: {signum}), yeeting everything...")
    kill_existing_wallpaper()
    kill_all_wallpaper_engines()

    if PID_FILE.exists():
        PID_FILE.unlink()
        logging.info("pid file removed")

    logging.info("goodbye cruel world~")
    sys.exit(0)


class ConfigWatcher(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.last_engine_signature = None

    def on_modified(self, event):
        if event.src_path == str(CONFIG_PATH):
            logging.info("config changed!! reloading...")
            time.sleep(0.1)
            config = load_config()
            signature = _engine_config_signature(config)
            if signature == self.last_engine_signature:
                logging.info("config changed only for GUI settings; skipping restart")
                return
            self.last_engine_signature = signature
            wpid = config.get("wpid")
            if wpid:
                start_wallpaper_engine(wpid)


def _parse_args():
    parser = argparse.ArgumentParser(description="motionpaper daemon")
    parser.add_argument(
        "--set-static",
        action="store_true",
        help="capture and set a static wallpaper, then exit",
    )
    parser.add_argument("--wpid", help="wallpaper id for static mode")
    return parser.parse_args()


def main():
    logging.info("motionpaper daemon starting wheee")

    args = _parse_args()
    if args.set_static:
        config = load_config()
        wpid = args.wpid or config.get("wpid")
        set_static_wallpaper(wpid)
        return

    if PID_FILE.exists():
        old_pid = int(PID_FILE.read_text().strip())
        logging.warning(
            f"found existing pid file with pid {old_pid}, checking if still alive..."
        )
        try:
            os.kill(old_pid, 0)
            logging.error(
                f"daemon already running with pid {old_pid}!! kill it first with: kill {old_pid}"
            )
            print(f"daemon already running with pid {old_pid}")
            print(f"kill it with: kill {old_pid}")
            sys.exit(1)
        except OSError:
            logging.info("old pid is dead, cleaning up stale pid file")
            PID_FILE.unlink()

    PID_FILE.write_text(str(os.getpid()))
    logging.info(f"daemon pid: {os.getpid()}")

    signal.signal(signal.SIGTERM, cleanup_and_exit)
    signal.signal(signal.SIGINT, cleanup_and_exit)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    kill_all_wallpaper_engines()

    config = load_config()
    wpid = config.get("wpid")
    watcher = ConfigWatcher()
    watcher.last_engine_signature = _engine_config_signature(config)
    if wpid:
        start_wallpaper_engine(wpid)

    observer = Observer()
    observer.schedule(watcher, str(CONFIG_DIR), recursive=False)
    observer.start()

    logging.info("watching for config changes...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_and_exit()

    observer.join()


if __name__ == "__main__":
    main()
