import argparse
import json
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


logging.basicConfig(
    filename=str(DAEMON_LOG_PATH),
    level=logging.DEBUG,
    format="%(asctime)s - %(message)s",
)


def _detect_screen_root():
    env_override = os.getenv("MOTIONPAPER_SCREEN_ROOT", "").strip()
    if env_override:
        logging.info(
            f"using MOTIONPAPER_SCREEN_ROOT override for linux-wallpaperengine: {env_override}"
        )
        return env_override

    hyprctl = shutil.which("hyprctl")
    if hyprctl:
        try:
            result = subprocess.run(
                [hyprctl, "-j", "monitors"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                monitors = json.loads(result.stdout or "[]")
                if isinstance(monitors, list) and monitors:
                    focused = next(
                        (monitor for monitor in monitors if monitor.get("focused")),
                        monitors[0],
                    )
                    output_name = str(focused.get("name", "")).strip()
                    if output_name:
                        logging.info(f"detected screen-root via hyprctl: {output_name}")
                        return output_name
        except Exception as e:
            logging.warning(f"failed to detect outputs from hyprctl: {e}")

    xrandr = shutil.which("xrandr")
    if xrandr:
        try:
            result = subprocess.run(
                [xrandr, "--query"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if " connected" in line:
                        output_name = line.split()[0].strip()
                        if output_name:
                            logging.info(
                                f"detected screen-root via xrandr: {output_name}"
                            )
                            return output_name
        except Exception as e:
            logging.warning(f"failed to detect outputs from xrandr: {e}")

    try:
        from screeninfo import get_monitors

        monitors = get_monitors()
        if monitors:
            output_name = str(getattr(monitors[0], "name", "") or "").strip()
            if output_name:
                logging.info(f"detected screen-root via screeninfo: {output_name}")
                return output_name
    except Exception as e:
        logging.warning(f"failed to detect monitors via screeninfo: {e}")

    logging.warning(
        "could not detect monitor output name; running without --screen-root (set MOTIONPAPER_SCREEN_ROOT to override)"
    )
    return None


SCREEN_ROOT = _detect_screen_root()

current_process = None

ENGINE_RELEVANT_KEYS = (
    "wpid",
    "scaling",
    "screen_root",
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


def _build_creation_command(wpid, config, force_silent=False, set_static=False):
    command = [
        "linux-wallpaperengine",
        "--screenshot-delay",
        str(60 * 1),  # 1 second
        "--screenshot",
        str(SCREENSHOT_PATH),
        "--bg",
        str(wpid),
    ]

    screen_root = str(config.get("screen_root") or SCREEN_ROOT or "").strip()
    if screen_root:
        command.extend(["--screen-root", screen_root])

    scaling = config.get("scaling", "default")
    if scaling and scaling != "default":
        command.extend(["--scaling", scaling])

    cmd = _apply_engine_options(command, config, force_silent=force_silent)

    if set_static:
        static_fps = 5
        if "--fps" in cmd:
            fps_index = cmd.index("--fps")
            cmd[fps_index + 1] = str(static_fps)
        else:
            cmd.extend(["--fps", str(static_fps)])
    return cmd


def _create_black_image():
    return Image.new("RGB", (1920, 1080), color=(1, 1, 1))


def _set_wallpaper(file_path):
    path = str(file_path)

    successes = []

    def _try_cmd(cmd):
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                return True
        except Exception as e:
            logging.debug(f"backend command failed: {cmd}: {e}")
        return False

    # caelestia
    if shutil.which("caelestia"):
        try:
            if _try_cmd(["caelestia", "wallpaper", "-f", path]):
                _try_cmd(
                    ["caelestia", "scheme", "set", "--mode", "dark"]
                )  # best-effort
                successes.append("caelestia")
        except Exception:
            logging.exception("caelestia set failed")

    # swww
    if shutil.which("swww"):
        try:
            if _try_cmd(["swww", "img", path, "--transition-steps", "255"]) or _try_cmd(
                ["swww", "img", path]
            ):
                successes.append("swww")
        except Exception:
            logging.exception("swww set failed")

    # awww
    if shutil.which("awww"):
        try:
            if _try_cmd(["awww", "img", path]):
                successes.append("awww")
        except Exception:
            logging.exception("awww set failed")

    # hyprctl / hyprpaper
    if shutil.which("hyprctl"):
        try:
            if _try_cmd(["hyprctl", "hyprpaper", "preload", path]):
                if _try_cmd(["hyprctl", "hyprpaper", "wallpaper", f",{path}"]):
                    successes.append("hyprctl")
        except Exception:
            logging.exception("hyprctl set failed")

    if not successes:
        logging.warning("no supported wallpaper backend found to set wallpaper")
        _notify(
            "motionpaper", "static wallpaper not set; unsupported wallpaper backend"
        )
    else:
        logging.info(f"wallpaper set via backends: {', '.join(successes)}")


def _reset_wallpaper_backend():
    successes = []

    def _try_cmd(cmd):
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                return True
        except Exception as e:
            logging.debug(f"reset backend command failed: {cmd}: {e}")
        return False

    # caelestia
    if shutil.which("caelestia"):
        try:
            if _try_cmd(["caelestia", "wallpaper", "-r"]):
                successes.append("caelestia")
        except Exception:
            logging.exception("caelestia reset failed")

    # swww
    if shutil.which("swww"):
        try:
            if _try_cmd(["swww", "img", "clear"]) or _try_cmd(["swww", "img", "reset"]):
                successes.append("swww")
        except Exception:
            logging.exception("swww reset failed")

    # awww
    if shutil.which("awww"):
        try:
            if _try_cmd(["awww", "reset"]) or _try_cmd(["awww", "clear"]):
                successes.append("awww")
        except Exception:
            logging.exception("awww reset failed")

    # hyprctl
    if shutil.which("hyprctl"):
        try:
            if _try_cmd(["hyprctl", "hyprpaper", "unload", "all"]):
                successes.append("hyprctl")
        except Exception:
            logging.exception("hyprctl reset failed")

    if not successes:
        logging.warning("no supported wallpaper backend found to reset wallpaper")
    else:
        logging.info(f"wallpaper reset via backends: {', '.join(successes)}")


def _notify(title: str, message: str):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        toast_path = CONFIG_DIR / "toast.json"
        payload = {
            "title": title,
            "message": message,
            "ts": time.time(),
            "shown": False,
        }
        # atomic-ish write
        tmp = toast_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        try:
            tmp.replace(toast_path)
        except Exception:
            # fallback to rename
            os.replace(str(tmp), str(toast_path))
        logging.info(f"wrote gui toast to {toast_path}")
    except Exception as e:
        logging.debug(f"failed to write gui toast file: {e}")


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
        _terminate_process_group(current_process, "wallpaper process")
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


def _terminate_process_group(process, name):
    if not process or process.poll() is not None:
        return

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logging.warning(f"{name} didn't die nicely, force killing")
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception as e:
            logging.warning(f"killpg failed for {name}: {e}, trying regular kill")
            try:
                process.kill()
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"error killing {name}: {e}")
        try:
            process.kill()
        except Exception:
            pass


def _prepare_capture_state():
    _create_black_image().save(TEMP_WALLPAPER_PATH, format="png")
    _set_wallpaper(TEMP_WALLPAPER_PATH)
    _try_delete(SCREENSHOT_PATH)


def _capture_screenshot(command, timeout=15):
    logging.info("starting static wallpaper capture")
    capture_process = subprocess.Popen(command, start_new_session=True)

    try:
        logging.info("waiting for screenshot to be created...")
        return _wait_for_screenshot(SCREENSHOT_PATH, timeout=timeout)
    finally:
        _terminate_process_group(capture_process, "capture process")


def start_wallpaper_engine(wpid):
    global current_process

    if not wpid:
        logging.error("no wpid provided, skipping")
        return

    kill_all_wallpaper_engines()

    logging.info(f"starting wallpaper with id: {wpid}")

    config = load_config()

    creation_command = _build_creation_command(wpid, config, force_silent=False)
    capture_command = _build_creation_command(
        wpid, config, force_silent=True, set_static=True
    )

    logging.info(f"full command: {' '.join(creation_command)}")

    _prepare_capture_state()

    try:
        if not _capture_screenshot(capture_command, timeout=15):
            raise RuntimeError(
                "linux-wallpaperengine did not produce a screenshot in time"
            )

        logging.info("setting static wallpaper")
        _reset_wallpaper_backend()
        _set_wallpaper(SCREENSHOT_PATH)
        logging.info("wallpaper update complete!!")
        try:
            _notify("motionpaper", "Wallpaper set")
        except Exception:
            pass
        logging.info("recreating current process...")
        kill_existing_wallpaper()
        logging.info("current process killed, recreating...")
        current_process = subprocess.Popen(creation_command, start_new_session=True)
        logging.info(f"new wallpaper process started with pid: {current_process.pid}")
        _try_delete(TEMP_WALLPAPER_PATH)
    except Exception as e:
        logging.warning(f"failed to set wallpaper: {e}")
        logging.warning("using black image as fallback wallpaper")
        try:
            _set_wallpaper(TEMP_WALLPAPER_PATH)
        except Exception as fallback_error:
            logging.warning(f"failed to set fallback wallpaper: {fallback_error}")
        try:
            _notify("motionpaper", "Static wallpaper not set; using fallback")
        except Exception:
            pass


def set_static_wallpaper(wpid):
    if not wpid:
        logging.error("no wpid provided, skipping")
        return

    kill_all_wallpaper_engines()
    kill_existing_wallpaper()

    config = load_config()
    creation_command = _build_creation_command(
        wpid, config, force_silent=True, set_static=True
    )

    _prepare_capture_state()

    try:
        if _capture_screenshot(creation_command, timeout=15):
            logging.info("setting static wallpaper")
            try:
                _reset_wallpaper_backend()
                _set_wallpaper(SCREENSHOT_PATH)
                logging.info("static wallpaper set")
                try:
                    _notify("motionpaper", "Static wallpaper set")
                except Exception:
                    pass
            except Exception as e:
                logging.warning(
                    f"failed to set captured static wallpaper: {e}; using fallback image"
                )
                _set_wallpaper(TEMP_WALLPAPER_PATH)
                try:
                    _notify("motionpaper", "Static wallpaper set (fallback)")
                except Exception:
                    pass
        else:
            logging.warning("screenshot not ready; using fallback image")
            _set_wallpaper(TEMP_WALLPAPER_PATH)
    finally:
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
