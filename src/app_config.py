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

from effect_rules import DEFAULT_RULES, UPTIME_LINE_RULES, lines_to_add, upgrade_rules_text

APP_NAME = "esolog-tail"

# The rules text's layout: 1 held the user's additions to a line whose
# group buffs and taunt were built in; 2 has those as rules too; 3 gives
# them ``expected`` words and Touch of Z'en the ``dots`` measure; 4 takes
# Powerful Assault's ``expected`` off again (issue #48); 5 comments out the
# default Crux line (issue #80)
TRACKING_VERSION = 5

DEFAULTS = {
    "log_path": None,           # None -> auto-detect
    "split": {
        "enabled": False,
        "dir": None,            # None -> log file's directory
        # Zip splits older than this many weeks (split_retention, issue #86)
        "zip_enabled": False,
        "zip_after_weeks": 4,
        # Move splits older than this to the Recycle Bin (issue #87); more
        # than zip_after_weeks while zipping is on
        "delete_enabled": False,
        "delete_after_weeks": 52,
    },
    "archive": {
        "size_threshold_mb": 1024,   # ~5 veteran trials (100-300 MB each)
        "dir": None,                 # None -> log file's directory
        "delete_original": False,    # opt-in
        "size_at_last_archive": 0,   # re-trigger marker
    },
    "history": {
        "load_recent_mb": 0,    # 0 -> attach at end; N -> parse trailing N MB
        # The status bar's one hint that the fight history (fight_index,
        # issue #170) can be built from the split logs has been shown
        "backfill_offered": False,
    },
    "tracking": {
        "rules": DEFAULT_RULES,  # tracked effects, one rule per line (effect_rules)
        "version": TRACKING_VERSION,
    },
    "update": {
        "check_enabled": True,   # check GitHub releases at startup
        "skip_version": None,    # release the user chose to skip
        "channel": "stable",     # "stable" or "beta" (issue #134; update_check.CHANNELS)
    },
    # The build window's Penetration and Critical damage sections (pen_crit):
    # Champion Point stars the log cannot show, assumed or not, and the
    # target's resistance ("auto": 18,200 in dungeons, trials and arenas,
    # 9,100 overland; or a number)
    "pen_crit": {
        "piercing": True,
        "fighting_finesse": True,       # in solo and small-group fights, never in a large group
        "backstabber": False,
        "force_of_nature": False,
        "force_of_nature_per_effect": 660,
        "cap": "auto",
    },
    # The Hide names switch (gui/name_mask): every player's handle and
    # character name but the logging player's hidden, for screenshots
    "privacy": {
        "hide_names": False,
    },
    # The trial completion banner grabbed from the screen after END_TRIAL
    # (banner_capture, issue #167), Windows only: off until switched on
    # (Chris, 2026-11-01); the folder, None -> <log folder>\Banners
    "banner": {
        "enabled": False,
        "dir": None,
    },
    # A companion has its own row under its owner (companions.py); this
    # also counts its damage and healing as the owner's (off: Combat
    # Metrics never does)
    "companions": {
        "accrue_to_owner": False,
    },
    # The death recap window: seconds of damage and healing kept before
    # each death (death_recap, issues #95 and #133), 1 to 10; 3 for a new
    # install, while a stored 5 from an older version is kept
    "death_recap": {
        "window_s": 3,
    },
    # The app-wide text size, a percentage of the system font (gui.text_size,
    # issue #77): 80 to 200, set in Settings or with Ctrl+=, Ctrl+- and Ctrl+0
    "display": {
        "text_scale": 100,
        # The DPS graph's colour-blind colours and strokes (gui.dps_graph)
        "colorblind_graph": False,
        # The taunt ring stays still rather than pulsing (gui.fight_view)
        "reduce_motion": False,
    },
    "window": {
        "geometry": None,        # base64 QMainWindow.saveGeometry(), set on close
        "splitter": None,        # base64 QSplitter.saveState() of the main split
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
        the same name stays theirs. A text saved before version 3 then has
        the default rules that are expected given their ``expected`` words
        and Touch of Z'en's ``stacks`` turned into ``dots``, by name (upgrade_rules_text:
        a renamed or already-flagged line is left alone), so a trial fight
        still shows a missing group buff at 0% after the upgrade. A text
        saved before version 4 has the ``expected large`` that version 3
        put on its Powerful Assault line taken off again (issue #48: the
        one default no longer expected). A text saved before version 5 has
        the default Crux line commented out (issue #80). Nothing is written back; the
        version is saved with the next Save, and every step is harmless to
        repeat.

        The timeline strip's old switch (experimental.buff_timeline, until
        issue #25 made the strip the only view of the rules) is dropped
        here, so the next Save leaves it out of the file.
        """
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        self.data = _deep_merge(DEFAULTS, stored)
        experimental = self.data.get("experimental")
        if isinstance(experimental, dict):
            experimental.pop("buff_timeline", None)
            if not experimental:
                del self.data["experimental"]
        tracking = stored.get("tracking")
        if not (isinstance(tracking, dict) and isinstance(tracking.get("rules"), str)):
            return
        if "version" not in tracking:
            missing = lines_to_add(UPTIME_LINE_RULES.splitlines(), tracking["rules"])
            if missing:
                self.data["tracking"]["rules"] = ("\n".join(missing) + "\n"
                                                  + tracking["rules"])
        version = tracking.get("version", 0)
        if not isinstance(version, int):
            version = 0
        if version < TRACKING_VERSION:
            self.data["tracking"]["rules"] = upgrade_rules_text(self.data["tracking"]["rules"], version)
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

    def snapshot(self) -> "AppConfig":
        """A copy of the settings as they are now, for work on another
        thread (a review, issue #107) while Settings may change these; it
        is read, never saved."""
        copy = object.__new__(AppConfig)
        copy.path = self.path
        copy.data = deepcopy(self.data)
        return copy

    def set(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
