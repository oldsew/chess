from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


TUNING = json.loads((resource_root() / "app/config/tuning.json").read_text(encoding="utf-8"))
DEFAULT_SETTINGS = {
    "theme": "Сланец", "sound": True, "legal_highlights": True,
    "player_color": "Белые", "show_bot_rating": True,
    "analysis_depth": TUNING["analysis_depth"], "developer_mode": False,
    "time_control": "none", "animations": True,
}


def data_dir() -> Path:
    override = os.environ.get("ADAPTIVE_CHESS_DATA_DIR")
    if override:
        path = Path(override)
    else:
        from PySide6.QtCore import QStandardPaths
        path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    path.mkdir(parents=True, exist_ok=True)
    return path


def engine_path() -> Path:
    override = os.environ.get("ADAPTIVE_CHESS_ENGINE")
    if override:
        return Path(override)
    return resource_root() / "engines" / ("stockfish.exe" if sys.platform == "win32" else "stockfish")


class Settings:
    def __init__(self, directory: Path):
        self.path = directory / "settings.json"
        self.values = DEFAULT_SETTINGS.copy()
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key, default in DEFAULT_SETTINGS.items():
                    value = loaded.get(key, default)
                    if type(value) is type(default):
                        self.values[key] = value
            self.values["analysis_depth"] = max(12, min(22, self.values["analysis_depth"]))
        except (FileNotFoundError, ValueError, OSError):
            logging.getLogger(__name__).info("Using default settings")

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
