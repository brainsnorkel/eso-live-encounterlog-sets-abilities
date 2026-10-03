"""
Application configuration: a JSON file in the per-user config directory.

Human-readable and toolkit-independent (usable by the engine without Qt).
The installer's uninstall step leaves it in place.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import platformdirs

APP_NAME = "esolog-tail"

DEFAULTS = {
    "log_path": None,           # None -> auto-detect
    "split": {
        "enabled": False,
        "dir": None,            # None -> log file's directory
    },
    "archive": {
        "size_threshold_mb": 1024,   # ~5 veteran trials (100-300 MB each)
        "dir": None,                 # None -> log file's directory
        "delete_original": False,    # opt-in
        "size_at_last_archive": 0,   # re-trigger marker
    },
    "history": {
        "load_recent_mb": 0,    # 0 -> attach at end; N -> parse trailing N MB
    },
    "experimental": {
        "buff_timeline": False,  # compact per-fight buff/debuff timeline strip
    },
    "update": {
        "check_enabled": True,   # check GitHub releases at startup
        "skip_version": None,    # release the user chose to skip
    },
}


def default_config_path() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False)) / "config.json"


def _deep_merge(base: dict, overrides: dict) -> dict:
    out = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class AppConfig:
    """Dotted-key access over a JSON config file merged with DEFAULTS."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_config_path()
        self.data = deepcopy(DEFAULTS)
        self.reload()

    def reload(self) -> None:
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.data = _deep_merge(DEFAULTS, stored)
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
