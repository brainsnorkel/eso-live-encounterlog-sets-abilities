"""
A set's bonus text, and the set behind a Major or Minor buff (issue #79).

Design: Set text in the hovers. The game's client holds no set bonus text
the app can read (it comes from the server through the add-on API), so the
text is UESP's, bundled per set id in data/sets/bonuses_en.json by
scripts/generate_set_offense.py (CC-BY-SA 2.5, credited in the README and
the About box, and by a short line under each hover that shows it). A set
link's click target stays the set's ESO-Hub page.

What a hover shows is the lines the player has, not the set's whole text:
the lines at or below the pieces active on their better bar. A set's whole
text runs to 573 characters and one five-piece line to 496, and a player
wearing three pieces has no use for the five-piece line. A set worn in both
versions has the lines the two share at the two counts added, as the game
counts them (player_build.family_counts), and the perfected version's own
extra line only at its count in perfected pieces.

Figures are shown at their top value: UESP writes a figure that scales with
level as a range, "Adds 15-657 Critical Chance", low value first, and every
one of the 1,970 ranges in the bundled text reads that way (18 of them
percentages from 0, 12 plain figures from 0; none is a duration or a
distance; tests/unit/test_set_text.py holds the file to it). A player at
the level cap has the high value, so the text reads "Adds 657 Critical
Chance". The bundled file keeps UESP's text as it came.
"""

import json
import re
from collections.abc import Iterable
from functools import lru_cache

from ability_icons import bundle_root

CREDIT = "Set text: UESP"

# A figure UESP writes as a range over the levels, low value first
_RANGE_RE = re.compile(r"(?<![\d.,-])\d[\d,]*(?:\.\d+)?-(\d[\d,]*(?:\.\d+)?)(?![\d-])")


def _load(name: str, key: str) -> dict:
    try:
        data = json.loads((bundle_root() / "data" / "sets" / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table = data.get(key) if isinstance(data, dict) else None
    return table if isinstance(table, dict) else {}


@lru_cache(maxsize=1)
def bonus_table() -> dict[str, dict]:
    """set id -> {'name', 'bonuses': [{'pieces', 'text', 'perfected'?}]},
    the bundled UESP text; {} when the file is absent."""
    return _load("bonuses_en.json", "sets")


@lru_cache(maxsize=1)
def buff_table() -> dict[str, dict]:
    """effect id -> {'name', 'set', ...}: the Major and Minor buffs a set
    writes under an id of its own (data/sets/set_buffs.json)."""
    return _load("set_buffs.json", "buffs")


@lru_cache(maxsize=1)
def buff_ids() -> frozenset:
    """The effect ids of buff_table, for the engine to note their casters."""
    return frozenset(str(ability_id) for ability_id in buff_table())


class SetBuffRecorder:
    """Who had a set's own buff id up on anyone, and when, in raw log
    milliseconds: given_in() reads a fight's window out of it, as the buff
    timeline's recorder does for the strip's rows.

    A fight's casters are those with the id up during the fight, not those
    whose GAINED line fell inside it: a buff gained just before the pull
    and still up is the wearer's in that fight, as the row shows it, and a
    refresh (UPDATED) of a buff this recorder never saw gained counts too.
    An interval runs from the first GAINED or UPDATED of an id on a unit to
    its FADED, and is credited to every caster seen on it while it was up
    (two wearers refresh each other's buff, and FADED is not relied on to
    name the caster). The game writes no FADED for a unit that is removed
    or dies, and unit ids start afresh in a new zone, so forget_unit and
    zone_changed end the open intervals, as effect_rules' tracker does."""

    MAX_CLOSED = 20000  # a runaway guard; prune_before keeps it far lower

    def __init__(self, ids: Iterable[str] | None = None):
        self._ids = buff_ids() if ids is None else frozenset(str(i) for i in ids)
        # (target id, ability id) -> [start ms, {source ids}]
        self._open: dict[tuple, list] = {}
        # [start ms, end ms, ability id, frozenset of source ids]
        self._closed: list[tuple] = []

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()

    def record(self, effect_type: str, ability_id: str, source_id: str, target_id: str,
               timestamp_ms: int) -> None:
        if ability_id not in self._ids:
            return
        key = (str(target_id), ability_id)
        if effect_type in ("GAINED", "UPDATED"):
            opened = self._open.setdefault(key, [timestamp_ms, set()])
            if source_id and str(source_id) != "0":
                opened[1].add(str(source_id))
        elif effect_type == "FADED":
            self._close(key, timestamp_ms)

    def _close(self, key: tuple, timestamp_ms: int) -> None:
        opened = self._open.pop(key, None)
        if opened is None or not opened[1]:
            return
        if len(self._closed) >= self.MAX_CLOSED:
            del self._closed[:self.MAX_CLOSED // 2]
        self._closed.append((opened[0], max(opened[0], timestamp_ms), key[1],
                             frozenset(opened[1])))

    def forget_unit(self, unit_id: str, timestamp_ms: int) -> None:
        """The unit died or was removed: the buffs on it end here."""
        unit_id = str(unit_id)
        for key in [key for key in self._open if key[0] == unit_id]:
            self._close(key, timestamp_ms)

    def zone_changed(self, timestamp_ms: int) -> None:
        """A new zone hands unit ids out afresh: every open interval ends."""
        for key in list(self._open):
            self._close(key, timestamp_ms)

    def given_in(self, start_ms: int, end_ms: int) -> dict[str, set[str]]:
        """source unit id -> the set-buff ids it had up on anyone at some
        moment of [start_ms, end_ms]."""
        out: dict[str, set[str]] = {}
        for start, end, ability_id, sources in self._closed:
            if end >= start_ms and start <= end_ms:
                for source in sources:
                    out.setdefault(source, set()).add(ability_id)
        for (_target, ability_id), (start, sources) in self._open.items():
            if start <= end_ms:
                for source in sources:
                    out.setdefault(source, set()).add(ability_id)
        return out

    def prune_before(self, timestamp_ms: int) -> None:
        """Free the intervals that ended before *timestamp_ms*."""
        self._closed = [iv for iv in self._closed if iv[1] >= timestamp_ms]


def top_figures(text: str) -> str:
    """*text* with each level range reduced to its top value: 'Adds 15-657
    Critical Chance' gives 'Adds 657 Critical Chance' (see the module
    notes)."""
    return _RANGE_RE.sub(r"\1", text or "")


def has_text(set_id) -> bool:
    return bool((bonus_table().get(str(set_id)) or {}).get("bonuses"))


def active_lines(set_id, pieces: int, perfected_pieces: int | None = None,
                 table: dict[str, dict] | None = None) -> list[tuple[int, str]]:
    """[(pieces needed, text)] of the bonus lines of *set_id* a player has
    with *pieces* of the set active, figures at their top value. A line that
    is the perfected set's own needs *perfected_pieces*, the perfected
    pieces among them (all of them when None: a set worn in one version).
    [] for a set without bundled text."""
    if table is None:
        # A pane redraw asks for every worn set again: the bundled table's
        # answers are kept
        return list(_bundled_lines(str(set_id), pieces, perfected_pieces))
    return _lines(table, set_id, pieces, perfected_pieces)


@lru_cache(maxsize=4096)
def _bundled_lines(set_id: str, pieces: int, perfected_pieces: int | None) -> tuple:
    return tuple(_lines(bonus_table(), set_id, pieces, perfected_pieces))


def _lines(table: dict[str, dict], set_id, pieces: int,
           perfected_pieces: int | None) -> list[tuple[int, str]]:
    entry = table.get(str(set_id)) or {}
    own = pieces if perfected_pieces is None else perfected_pieces
    lines = []
    for bonus in entry.get("bonuses") or ():
        try:
            need = int(bonus.get("pieces") or 0)
        except (TypeError, ValueError):
            continue
        if need <= (own if bonus.get("perfected") else pieces):
            lines.append((need, top_figures(str(bonus.get("text") or ""))))
    return lines


def sets_behind(buff_name: str, given: Iterable[str],
                table: dict[str, dict] | None = None) -> list[str]:
    """The sets whose own id of the buff *buff_name* is among *given*, the
    set-buff ids a caster had up in a fight; in name order. [] for a row
    that is not named after a buff of the table.

    Design: The set behind a buff. A group buff from a set is written to the
    log twice: once under the buff's own id, the one the uptime strip's row
    follows (Major Courage 109966, Major Slayer 93109, Major Force 61747), and
    once under an id of the set's own (Spell Power Cure's 66902, Roaring
    Opportunist's 135923, Saxhleel Champion's 154830), from the same caster to
    the same receivers. In a Dreadsail Reef log both ids of each pair were
    gained the same number of times by the same casters on the same receivers
    (288, 56 and 122 times). So a row's own intervals cannot say which set a
    caster's share came from: they carry the buff's id whatever its source.
    What can is the set's own id: the engine notes, per fight, which of the
    ids in data/sets/set_buffs.json each player had up on anyone during it
    (SetBuffRecorder; the entry's player 'set_buffs'), and a row named after a
    buff reads its casters' sets from there (sets_behind). The label is per caster and fight:
    a caster who gave the buff from a set and by another means too reads
    "from <set>" for their whole share. The table (scripts/generate_set_buffs.py)
    knows 34 ids of 24 sets, those someone in the surveyed logs wore, and no id
    that several sets write.
    """
    table = buff_table() if table is None else table
    wanted = (buff_name or "").strip().lower()
    names = {str(row.get("set") or "") for ability_id in given
             for row in [table.get(str(ability_id)) or {}]
             if wanted and str(row.get("name") or "").lower() == wanted}
    return sorted(name for name in names if name)
