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

from effect_rules import DEFAULT_RULES, UPTIME_LINE_RULES, lines_to_add

APP_NAME = "esolog-tail"

# The rules text's layout: 1 held the user's additions to a line whose
# group buffs and taunt were built in; 2 has those as rules too
TRACKING_VERSION = 2

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
    "tracking": {
        "rules": DEFAULT_RULES,  # tracked effects, one rule per line (effect_rules)
        "version": TRACKING_VERSION,
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
        """Read the file over DEFAULTS. A rules text saved before the uptime
        line's group buffs and taunt became rules (tracking.version absent,
        0.8.0 and earlier) kept only the user's own additions, so the line
        would lose those items on upgrade: the missing ones are put in
        front of it, by name, so a rule the user had already written under
        the same name stays theirs. Nothing is written back; the version
        is saved with the next Save, and the top-up is harmless to repeat.
        """
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        self.data = _deep_merge(DEFAULTS, stored)
        tracking = stored.get("tracking")
        if (isinstance(tracking, dict) and isinstance(tracking.get("rules"), str)
                and "version" not in tracking):
            missing = lines_to_add(UPTIME_LINE_RULES.splitlines(), tracking["rules"])
            if missing:
                self.data["tracking"]["rules"] = ("\n".join(missing) + "\n"
                                                  + tracking["rules"])
            self.data["tracking"]["version"] = TRACKING_VERSION

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
