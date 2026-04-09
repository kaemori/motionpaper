import json
from pathlib import Path
from typing import Any, Dict, List

from .constants import WPE_WORKSHOP_DIR
from .romanization import romanize_text


def load_wallpapers() -> List[Dict[str, Any]]:
    wallpapers: List[Dict[str, Any]] = []

    if not WPE_WORKSHOP_DIR.exists():
        return wallpapers

    for item in WPE_WORKSHOP_DIR.iterdir():
        if not item.is_dir():
            continue

        project_file = item / "project.json"
        if not project_file.exists():
            continue

        try:
            with open(project_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            preview_path = item / data.get("preview", "preview.jpg")
            if not preview_path.exists():
                continue

            title = data.get("title", item.name)
            workshop_id = item.name.strip()
            workshop_url = (
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
                if workshop_id
                else ""
            )

            wallpapers.append(
                {
                    "id": item.name,
                    "title": title,
                    "romanized": romanize_text(title),
                    "preview_path": preview_path,
                    "is_gif": preview_path.suffix.lower() == ".gif",
                    "tags": data.get("tags", []),
                    "contentrating": data.get("contentrating", "Everyone"),
                    "file": data.get("file", "Unknown file"),
                    "type": data.get("type", "Unknown"),
                    "version": data.get("version", "Unknown"),
                    "workshopid": workshop_id,
                    "workshopurl": workshop_url,
                }
            )
        except Exception as e:
            print(f"error loading {item.name}: {e}")

    return wallpapers
