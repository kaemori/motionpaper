import json
from typing import Any, Dict

from .constants import CONFIG_PATH, THEMES_PATH

DEFAULT_CONFIG: Dict[str, Any] = {
    "wpid": None,
    "scaling": "fit",
    "fps": 60,
    "fullscreen_pause": True,
    "mute": False,
    "volume": 100,
    "automute": False,
    "audio_processing": True,
    "particles": True,
    "track_mouse": True,
    "parallax": True,
    "show_mature": True,
    "theme": "purple",
}


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def load_themes() -> Dict[str, Dict[str, str]]:
    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
