"""
The bundled game data against the game the log was written by (engine
side, no Qt). Issue #173.

Design: the app ships tables built from the game and from sites that follow
it: set names (the client's language file and the LibSets workbook), set
bonus texts and set buffs, the ESO-Hub link maps, the ability icons, armor
weights, weapon types, poison names, food, class passives and masteries,
weapon skill lines and skill target kinds. After a game update some of it
lags, and until now the app showed the symptoms one at a time, each in its
own place: ``Set#<id>`` for a set the tables do not name, a dash in the
build window's Type column for an item they do not know, a skill's name as
text where its icon would be, a set name with no ESO-Hub link. Nothing said
that the data was behind, so the maintainer learned it from a user.

Two facts make the check cheap. Every logging session's first line names
the game version, ``BEGIN_LOG, time, 15, "NA Megaserver", "en",
"eso.live.12.1"``; and ``data/version.json`` names the version the bundle
was built against, written by ``scripts/stamp_data_version.py`` after a
refresh, with each table's own date. Only the two numbers after the branch
count (12.1): the client's build number never reaches the log, and a PTS
log (another branch) compares by the same numbers. A log written by a newer
version than the bundle's says the data is behind before any symptom shows.

The symptoms are counted where the log first names them, a player's
PLAYER_INFO line: the gear's set ids and item ids, and the abilities on the
two bars with the icons their ABILITY_INFO lines named. Counted, per logging
session (a new BEGIN_LOG starts again):

- a set id the bundled set data does not name;
- an armor or weapon item id the bundled weight or type table does not
  know, for an item at champion level or of a set. A new character's
  starting clothes, the Soul-Shriven Shirt (item 35029) and Sandals (35036),
  are in neither UESP table and were the only unknown items in a year of
  split logs (two logs, 2026-08 and -10): plain low-level items are left out
  so they never read as stale data;
- an ability on a bar whose icon the bundle lacks (icons are looked up by
  the stem of the path the log names);
- a set name with no ESO-Hub page in the link map.

Measured over the 378 distinct split logs of January to October 2026
(four game versions, 11.2 to 12.1), every counter was zero with the data of
1 November 2026, so the status line stays empty in normal play.

Two symptoms are not counted. Food, because no test from the log is
reliable: the 47 listed foods seen use 24 icons of their own
(``crafting_meat_001``, ``plate_of_sugarskulls``,
``disastrously_bloody_mara``), and the family test the food script uses as
a hint (icons starting crafting_, store_, event_ or plate_) flagged a quest
disguise, Q3854 Goblin Disguise, as a food on one of the 2,188 PLAYER_INFO
lines with no listed food, while a new food with an icon like the Bloody
Mara's would pass it unseen. The maintainer's script reports that hint
instead (``scripts/check_data_staleness.py``). And monsters' icons: the bundle
carries the player skills' icons and the ``death_recap_`` family, so 24 of
the 617 killing abilities logged on 12.1 read as text in a death recap by
design, not because the data is old.

The engine sends a check when a session begins and whenever a PLAYER_INFO
line names something new, so a session costs one message when nothing is
found. The check is an immutable value the GUI can keep.
"""

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache

from ability_icons import bundle_root, esohub_set_url, icons_dir

# The build window's own rules for a set id and its name, so the counter and
# the Set#<id> it explains cannot drift apart
from player_build import (
    ARMOR_SLOTS,
    WEAPON_SLOTS,
    _default_set_name,
    _set_id,
    armor_weight,
    weapon_type,
)

# 'eso.live.12.1' and 'eso.pts.12.2.3': the branch, then the update's numbers
_VERSION = re.compile(r"^\s*eso\.[a-z]+\.(\d+)\.(\d+)", re.IGNORECASE)
# Items, abilities and sets listed in the hover, each kind at most
HOVER_ITEMS = 10


def parse_game_version(text) -> tuple[int, int] | None:
    """'eso.live.12.1' -> (12, 1); a build number after the two is ignored
    ('eso.live.12.1.5' -> (12, 1)); None for anything else."""
    match = _VERSION.match(str(text or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def short_version(text) -> str:
    """'eso.live.12.1' -> '12.1'; the text itself when it is no version."""
    parsed = parse_game_version(text)
    return f"{parsed[0]}.{parsed[1]}" if parsed else str(text or "")


def is_newer(log_version, data_version) -> bool:
    """Whether the log's game version is newer than the data's; False when
    either is unknown."""
    log, data = parse_game_version(log_version), parse_game_version(data_version)
    return bool(log and data and log > data)


@lru_cache(maxsize=1)
def bundle_version() -> dict:
    """data/version.json as parsed: 'game_version', 'built' and 'tables' (a
    list of {'name', 'file', 'generated'}); {} when absent or unreadable."""
    try:
        data = json.loads((bundle_root() / "data" / "version.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def bundled_icon_stems() -> frozenset:
    """The stems of the bundled ability icons (data/icons/abilities)."""
    try:
        return frozenset(path.stem.lower() for path in icons_dir().glob("*.png"))
    except OSError:
        return frozenset()


@dataclass(frozen=True)
class DataCheck:
    """The bundled data against one logging session: what the log named
    that the data does not know, in the order it was found."""
    game_version: str = ""  # the log's, from BEGIN_LOG ('eso.live.12.1')
    data_version: str = ""  # the bundle's, from data/version.json
    data_built: str = ""  # the date the bundle was stamped
    unknown_sets: tuple[str, ...] = ()  # set ids
    unknown_armor: tuple[str, ...] = ()  # item ids
    unknown_weapons: tuple[str, ...] = ()  # item ids
    missing_icons: tuple[tuple[str, str], ...] = ()  # (ability id, name)
    unlinked_sets: tuple[str, ...] = ()  # set names

    @property
    def newer(self) -> bool:
        """The log was written by a newer game version than the data's."""
        return is_newer(self.game_version, self.data_version)

    @property
    def counts(self) -> dict[str, int]:
        return {"sets": len(self.unknown_sets),
                "items": len(self.unknown_armor) + len(self.unknown_weapons),
                "icons": len(self.missing_icons),
                "links": len(self.unlinked_sets)}

    @property
    def clear(self) -> bool:
        """Nothing to say: the versions agree (or one is unknown) and every
        counter is zero."""
        return not self.newer and not any(self.counts.values())


class DataCheckTracker:
    """Counts, over a logging session, what the players' PLAYER_INFO lines
    name that the bundled data does not know (see the module's design note).
    The lookups default to the bundled tables; tests pass their own."""

    def __init__(self, data_version: str | None = None, data_built: str | None = None,
                 set_name_of: Callable[[str], str | None] | None = None,
                 armor_weight_of: Callable[[str], str] | None = None,
                 weapon_type_of: Callable[[str], str] | None = None,
                 icon_stems: Iterable[str] | None = None,
                 set_link_of: Callable[[str], str | None] | None = None):
        bundle = bundle_version() if data_version is None or data_built is None else {}
        self.data_version = str(data_version if data_version is not None
                                else bundle.get("game_version") or "")
        self.data_built = str(data_built if data_built is not None
                              else bundle.get("built") or "")
        self._set_name_of = set_name_of or _default_set_name
        self._armor_weight_of = armor_weight_of or armor_weight
        self._weapon_type_of = weapon_type_of or weapon_type
        self._icon_stems = (frozenset(stem.lower() for stem in icon_stems)
                            if icon_stems is not None else None)
        self._set_link_of = set_link_of or esohub_set_url
        self.reset()

    def reset(self, game_version: str = "") -> None:
        """A new logging session, written by *game_version*."""
        self.game_version = str(game_version or "")
        self._checked_sets: set = set()
        self._checked_items: set = set()
        self._checked_abilities: set = set()
        self._unknown_sets: dict[str, None] = {}
        self._unknown_armor: dict[str, None] = {}
        self._unknown_weapons: dict[str, None] = {}
        self._missing_icons: dict[str, str] = {}
        self._unlinked_sets: dict[str, None] = {}

    def _has_icon(self, stem: str) -> bool:
        stems = self._icon_stems if self._icon_stems is not None else bundled_icon_stems()
        return stem.lower() in stems

    def note_player(self, gear: Iterable[list[str]], bar_slots: Iterable[dict]) -> bool:
        """One PLAYER_INFO line: *gear* as the parser's item lists (slot, item
        id, champion flag, level, trait, quality, set id, ...), *bar_slots*
        as the engine's slots ({'id', 'name', 'icon'}). True when it named
        something the session had not found before."""
        found = False
        for item in gear or ():
            if len(item) < 7:
                continue
            slot, item_id = str(item[0]), str(item[1])
            set_id = _set_id(item)
            has_set = bool(set_id)
            if has_set and set_id not in self._checked_sets:
                self._checked_sets.add(set_id)
                name = self._set_name_of(set_id)
                if not name:
                    self._unknown_sets[set_id] = None
                    found = True
                elif not self._set_link_of(name):
                    self._unlinked_sets[name] = None
                    found = True
            armor = slot in ARMOR_SLOTS
            if not (armor or slot in WEAPON_SLOTS) or item_id in self._checked_items:
                continue
            # Plain low-level items (a new character's starting clothes) are
            # in no table; only champion-level and set items count. An item
            # id is the same at every level, so a plain one is not marked
            # checked: worn later at champion level, it is looked up then
            if str(item[2]) != "T" and not has_set:
                continue
            self._checked_items.add(item_id)
            if armor and not self._armor_weight_of(item_id):
                self._unknown_armor[item_id] = None
                found = True
            elif not armor and not self._weapon_type_of(item_id):
                self._unknown_weapons[item_id] = None
                found = True
        for slot in bar_slots or ():
            ability_id = str(slot.get("id") or "")
            stem = str(slot.get("icon") or "")
            if not ability_id or not stem or ability_id in self._checked_abilities:
                continue
            self._checked_abilities.add(ability_id)
            if not self._has_icon(stem):
                self._missing_icons[ability_id] = str(slot.get("name") or f"Ability {ability_id}")
                found = True
        return found

    def check(self) -> DataCheck:
        """The session so far, as a value the GUI can keep."""
        return DataCheck(game_version=self.game_version, data_version=self.data_version,
                         data_built=self.data_built,
                         unknown_sets=tuple(self._unknown_sets),
                         unknown_armor=tuple(self._unknown_armor),
                         unknown_weapons=tuple(self._unknown_weapons),
                         missing_icons=tuple(self._missing_icons.items()),
                         unlinked_sets=tuple(self._unlinked_sets))


def _counted(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _found_parts(check: DataCheck) -> list[str]:
    counts = check.counts
    parts = []
    if counts["sets"]:
        parts.append(_counted(counts["sets"], "unknown set", "unknown sets"))
    if counts["items"]:
        parts.append(_counted(counts["items"], "unknown item", "unknown items"))
    if counts["icons"]:
        parts.append(_counted(counts["icons"], "icon missing", "icons missing"))
    if counts["links"]:
        parts.append(_counted(counts["links"], "set with no ESO-Hub link",
                              "sets with no ESO-Hub link"))
    return parts


def status_text(check: DataCheck | None) -> str:
    """The status bar's line: '' when there is nothing to say, else e.g.
    'Game 12.2, data built for 12.1: 3 unknown sets, 2 icons missing'."""
    if check is None or check.clear:
        return ""
    parts = _found_parts(check)
    data = short_version(check.data_version)
    if check.newer:
        head = f"Game {short_version(check.game_version)}, data built for {data}"
    elif data:
        head = f"Data built for game {data}"
    else:
        head = "Game data"
    return f"{head}: {', '.join(parts)}" if parts else head


def _listed(values: list[str]) -> str:
    shown = ", ".join(values[:HOVER_ITEMS])
    more = len(values) - HOVER_ITEMS
    return f"{shown} and {more} more" if more > 0 else shown


def status_tooltip(check: DataCheck | None) -> str:
    """The line's hover, plain text: what the versions are, what the symptoms
    look like, then the ids and names found, each kind on a line."""
    if check is None or check.clear:
        return ""
    data = short_version(check.data_version)
    built = f" on {check.data_built}" if check.data_built else ""
    game = short_version(check.game_version)
    if check.newer:
        lines = [(f"This log was written by game version {game}, newer than the {data} "
                  f"the app's game data was built for{built}.")]
    elif data and game:
        lines = [(f"The app's game data was built for game version {data}{built}; "
                  f"this log was written by {game}.")]
    elif data:
        lines = [f"The app's game data was built for game version {data}{built}."]
    else:
        lines = ["The app's game data carries no version."]
    lines.append("What the game added since shows as Set#<id>, as a dash in the build "
                 "window's Type column, or as a skill's name where its icon would be, "
                 "until a release of the app brings new data.")
    if check.unknown_sets:
        lines.append("Unknown sets: " + _listed([f"Set#{s}" for s in check.unknown_sets]))
    if check.unknown_armor:
        lines.append("Unknown armor: item " + _listed(list(check.unknown_armor)))
    if check.unknown_weapons:
        lines.append("Unknown weapons: item " + _listed(list(check.unknown_weapons)))
    if check.missing_icons:
        lines.append("Icons missing: " + _listed([name for _id, name in check.missing_icons]))
    if check.unlinked_sets:
        lines.append("Sets with no ESO-Hub link: " + _listed(list(check.unlinked_sets)))
    return "\n".join(lines)


def data_stamps(info: dict | None = None) -> tuple[str, str, list[tuple[str, str]]]:
    """(game version, date built, [(table name, date)]) from
    data/version.json, for the About dialog; empty parts when it is absent."""
    info = bundle_version() if info is None else info
    tables = []
    for table in info.get("tables") or ():
        if isinstance(table, dict) and table.get("name"):
            tables.append((str(table["name"]), str(table.get("generated") or "")))
    return str(info.get("game_version") or ""), str(info.get("built") or ""), tables
