"""
The kinds of damage: direct or over time, area or single target, Martial or
Magical, and what shields, blocks, heals and overheal did (issue #73).
Engine side, no Qt. The death recap and the build window draw the same
summary from the same rules, so a reader learns one vocabulary.

Design. The Warfare champion point stars act on four splits of a hit, and
the encounter log carries three of them on every COMBAT_EVENT line:

- **Direct or over time** is the result: DAMAGE, CRITICAL_DAMAGE and
  BLOCKED_DAMAGE are direct, DOT_TICK and DOT_TICK_CRITICAL are over time
  (Master-at-Arms and Thaumaturge for damage dealt, Ironclad and Enduring
  Resolve for damage taken). FALL_DAMAGE is neither and is named "fall".
- **Martial or Magical** is the damage type: PHYSICAL, BLEED, POISON and
  DISEASE are Martial (Mighty, Hardy), MAGIC, FIRE, COLD and SHOCK are
  Magical (War Mage, Elemental Aegis). OBLIVION belongs to neither and no
  star reduces it; DROWN, GENERIC, NONE, EARTH and any type a later patch
  adds are "untyped" and shown under the log's own word, never refused.
  Over 87 of Chris's split logs (11.6 million combat lines, 6,831 player
  deaths; 2026-10-27) the damage that reached players' health was 885M
  Magical, 411M Martial, 44M Oblivion and 20M fall, drowning or untyped,
  89% of it direct and 11% ticks; the death lines by type were MAGIC 1,434,
  PHYSICAL 1,391, SHOCK 1,257, FIRE 1,053, OBLIVION 770, COLD 587, POISON
  243, GENERIC 59, BLEED 17, DISEASE 17, DROWN 3. EARTH appeared on five
  hits, NONE on REFLECTED lines and on the zero-value DAMAGE line the game
  writes beside a DAMAGE_SHIELDED line when a shield took the whole hit.
- **Blocked, absorbed, avoided.** A BLOCKED_DAMAGE hit value is what got
  through the block and counts as direct damage; how much the block
  prevented is not in the log, so it is never stated. A DAMAGE_SHIELDED
  line is what a shield absorbed and is never added to the damage that
  reached health (shields absorbed 726M on players in the survey, more than
  any one damage type reached health). DODGED and MISS are counted, not
  summed. IMMUNE and REFLECTED are not counted.
- **Healing.** HEAL and CRITICAL_HEAL are direct heals, HOT_TICK and
  HOT_TICK_CRITICAL heals over time (Focused Mending, Swift Renewal); the hit
  value landed and the overflow is overheal (1.17B landed against 12.4B
  overheal in the survey; 3.1M of 3.6M heal lines were pure overheal).
  HEAL_ABSORBED is healing a healing-absorb effect ate. The killing blow's
  overflow is overkill (written on 6,039 of 6,398 killing blows; a blow
  written as BLOCKED_DAMAGE or FALL_DAMAGE carries none).

**Area or single target is not in the log** (Biting Aura and Deadly Aim,
Unassailable and Duelist's Rebuff), and is read from the cast id. Every
hostile hit on a player in the survey carried a non-zero castTrackId, and
grouping hits by (source unit, cast id) separates the mechanics that kill
groups from the attacks that pick one player: Maelstrom's 147 casts struck
up to 12 players each, Grievous Pulse's 38 casts struck more than one player
every time, Oppressive Bolts' 266 casts 98% of the time; Piercing Hailstone,
Venom Injection, Temporal Splinters, Swipe, Claw and Clash struck one unit
per cast, always. So a hit is area when its cast struck two or more distinct
units in the fight, counting hits before and after it; a hit of a cast that
struck one unit is area when a cast of the same ability struck two or more
earlier in the zone session (a repeat pull of the same boss); for a player's
or pet's own ability with no such evidence the bundled table of player
skills' target kinds decides (data/skills/ability_targets.json, Area, Cone
and Ground against Enemy, from UESP's skill table); otherwise single target.
Monster abilities never consult the table: UESP's target field calls
Oppressive Bolts and other group-wide mechanics "Enemy", and knew only 74%
of the hostile damage in the survey, so for monsters the log is the better
judge. The rule that classed a hit is kept beside it, so a reader can be
told "this cast hit 8 players" or "no cast of this ability struck two
players this session". Melee against ranged is not attempted: the log has no
range, its unit positions are normalised map coordinates whose scale differs
by map, and no Warfare star reads it.

A session's cast index and a fight's damage-taken tallies cost a few
dictionaries: the (source, cast) map is cleared at each fight's end, the
per-ability memory with the zone session (unit ids start over), and a cast's
pending amounts are dropped the moment its second target lands.
"""

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

# ----------------------------------------------------------------- results --

DIRECT_RESULTS = frozenset(("DAMAGE", "CRITICAL_DAMAGE", "BLOCKED_DAMAGE"))
DOT_RESULTS = frozenset(("DOT_TICK", "DOT_TICK_CRITICAL"))
FALL_RESULT = "FALL_DAMAGE"
# Results whose hit value reached health and is classed here
HEALTH_RESULTS = DIRECT_RESULTS | DOT_RESULTS | {FALL_RESULT}
# The results the cast index reads for the area rule: a cast's hits on units
CAST_RESULTS = DIRECT_RESULTS | DOT_RESULTS
SHIELDED_RESULT = "DAMAGE_SHIELDED"
BLOCKED_RESULT = "BLOCKED_DAMAGE"
AVOIDED_RESULTS = frozenset(("DODGED", "MISS"))
DIRECT_HEAL_RESULTS = frozenset(("HEAL", "CRITICAL_HEAL"))
HOT_RESULTS = frozenset(("HOT_TICK", "HOT_TICK_CRITICAL"))
HEAL_RESULTS = DIRECT_HEAL_RESULTS | HOT_RESULTS
HEAL_ABSORBED_RESULT = "HEAL_ABSORBED"

# ------------------------------------------------------------ damage types --

MARTIAL_TYPES = frozenset(("PHYSICAL", "BLEED", "POISON", "DISEASE"))
MAGICAL_TYPES = frozenset(("MAGIC", "FIRE", "COLD", "SHOCK"))
OBLIVION_TYPE = "OBLIVION"
# The game's words for the log's types, where they differ
TYPE_LABELS = {"COLD": "frost", "MAGIC": "magic", "FIRE": "fire", "SHOCK": "shock",
               "PHYSICAL": "physical", "BLEED": "bleed", "POISON": "poison",
               "DISEASE": "disease", "OBLIVION": "oblivion", "DROWN": "drowning",
               "GENERIC": "untyped", "NONE": "untyped"}
FALL_LABEL = "fall"

# The three sides a summary draws: (left, right) of each split
SPLITS = (("direct", "dot"), ("area", "single"), ("martial", "magical"))
SIDE_LABELS = {"direct": "direct", "dot": "over time", "area": "area",
               "single": "single target", "martial": "Martial", "magical": "Magical"}


def time_kind(result: str) -> str:
    """'direct', 'dot', 'fall' or '' for a result that is not damage."""
    if result in DIRECT_RESULTS:
        return "direct"
    if result in DOT_RESULTS:
        return "dot"
    if result == FALL_RESULT:
        return "fall"
    return ""


def school(damage_type: str) -> str:
    """'martial', 'magical', 'oblivion' or 'other'."""
    if damage_type in MARTIAL_TYPES:
        return "martial"
    if damage_type in MAGICAL_TYPES:
        return "magical"
    if damage_type == OBLIVION_TYPE:
        return "oblivion"
    return "other"


def type_label(damage_type: str, result: str = "") -> str:
    """The word a reader sees for a damage type: the game's where it differs
    ('frost'), the log's own in lower case for a type the tables do not know
    ('earth'), 'fall' for fall damage whatever its type field says."""
    if result == FALL_RESULT:
        return FALL_LABEL
    damage_type = str(damage_type or "")
    return TYPE_LABELS.get(damage_type, damage_type.lower() or "untyped")


def classify(result: str, damage_type: str) -> dict:
    """The kinds of one damage line: {'time': 'direct'|'dot'|'fall'|'',
    'school': 'martial'|'magical'|'oblivion'|'other', 'type': label}."""
    return {"time": time_kind(result), "school": school(damage_type),
            "type": type_label(damage_type, result)}


# ------------------------------------------------- player skills' targets --

TARGET_TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "skills" / "ability_targets.json"
_target_table: dict[str, str] | None = None


def _load_targets(path: Path = TARGET_TABLE_PATH) -> dict[str, str]:
    """ability id -> 'area' | 'single' from the bundled table; {} without it."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table: dict[str, str] = {}
    for kind in ("area", "single"):
        for ability_id in data.get(kind) or []:
            table[str(ability_id)] = kind
    return table


def table_target(ability_id, path: Path | None = None) -> str | None:
    """'area' or 'single' for a player skill the bundled table knows, else
    None. The table is read once; *path* reads another (tests)."""
    global _target_table
    if path is not None:
        return _load_targets(path).get(str(ability_id))
    if _target_table is None:
        _target_table = _load_targets()
    return _target_table.get(str(ability_id))


def reset_target_table() -> None:
    """Forget the loaded table (tests swap the file)."""
    global _target_table
    _target_table = None


# -------------------------------------------------------------- cast index --

class CastIndex:
    """Which units each cast struck, for the area rule (see the module
    docstring). (source, cast id) -> units struck lives for a fight;
    ability -> most units struck on one cast lives for the zone session."""

    def __init__(self):
        self._casts: dict[tuple[str, str], set[str]] = {}
        self._session_max: dict[str, int] = {}
        # (source, cast) -> callbacks for the moment the cast strikes its
        # second unit, so a tally can move the cast's damage to area
        self._watchers: dict[tuple[str, str], list[Callable[[], None]]] = {}

    def new_fight(self) -> None:
        """A fight ended: its casts are done, the session memory stays."""
        self._casts.clear()
        self._watchers.clear()

    def reset(self) -> None:
        """New zone or log session: unit ids and abilities start over."""
        self.new_fight()
        self._session_max.clear()

    def note_hit(self, source_id: str, cast_id: str, ability_id: str, target_id: str) -> int:
        """Record that *source_id*'s cast *cast_id* struck *target_id*; the
        number of distinct units it has struck in the fight."""
        key = (str(source_id), str(cast_id))
        units = self._casts.get(key)
        if units is None:
            units = self._casts[key] = set()
        before = len(units)
        units.add(str(target_id))
        count = len(units)
        ability_id = str(ability_id)
        if count > self._session_max.get(ability_id, 0):
            self._session_max[ability_id] = count
        if before < 2 <= count:
            for callback in self._watchers.pop(key, ()):
                callback()
        return count

    def targets_of(self, source_id: str, cast_id: str) -> int:
        return len(self._casts.get((str(source_id), str(cast_id)), ()))

    def session_max(self, ability_id: str) -> int:
        return self._session_max.get(str(ability_id), 0)

    def watch(self, source_id: str, cast_id: str, callback: Callable[[], None]) -> None:
        """Call *callback* once when the cast strikes a second unit (nothing
        if it already has: the caller checks targets_of first)."""
        self._watchers.setdefault((str(source_id), str(cast_id)), []).append(callback)


def area_rule(targets_hit: int, session_max: int, player_source: bool,
              ability_id: str, table: str | None = None) -> tuple[bool, str]:
    """(area?, rule) for a hit: 'cast' (this cast struck 2+ units),
    'session' (an earlier cast of the ability did), 'table' (a player
    skill's listed target kind), 'none' (nothing says area: single)."""
    if targets_hit >= 2:
        return True, "cast"
    if session_max >= 2:
        return True, "session"
    if player_source:
        kind = table if table is not None else table_target(ability_id)
        if kind == "area":
            return True, "table"
        if kind == "single":
            return False, "table"
    return False, "none"


def area_of(index: CastIndex | None, source_id: str, cast_id: str, ability_id: str,
            player_source: bool) -> tuple[bool, str, int]:
    """The area rule read from *index*: (area?, rule, units the cast struck)."""
    if index is None:
        area, rule = area_rule(0, 0, player_source, ability_id)
        return area, rule, 0
    targets = index.targets_of(source_id, cast_id)
    area, rule = area_rule(targets, index.session_max(ability_id), player_source, ability_id)
    return area, rule, targets


# ------------------------------------------------------------ taken tally --

class TakenTally:
    """What one player took and was healed for over a fight, by kind, with
    the abilities that hurt them (see summary() for the dict it becomes)."""

    def __init__(self):
        self.total = 0
        self.time = Counter()       # direct / dot / fall
        self.school = Counter()     # martial / magical / oblivion / other
        self.types = Counter()      # type label -> damage
        self.area = 0
        self.single = 0
        self.rules = Counter()      # 'cast' / 'session' / 'table' / 'none' -> damage
        self.blocked_through = 0
        self.absorbed = 0
        self.avoided = 0
        self.healed = 0
        self.heal_direct = 0
        self.heal_hot = 0
        self.overheal = 0
        self.heal_absorbed = 0
        self.overkill = 0
        self.first_ms: int | None = None
        self.last_ms: int | None = None
        # ability id -> its row; (source, cast) -> [(ability id, amount)]
        # counted as single until the cast's second target lands
        self.abilities: dict[str, dict] = {}
        self._pending: dict[tuple[str, str], list[tuple[str, int]]] = {}

    def _row(self, ability_id: str) -> dict:
        row = self.abilities.get(ability_id)
        if row is None:
            row = self.abilities[ability_id] = {
                "damage": 0, "direct": 0, "dot": 0, "fall": 0, "area": 0, "single": 0,
                "types": Counter(), "sources": Counter(), "hits": 0}
        return row

    def note_damage(self, ts: int, result: str, damage_type: str, hit: int,
                    ability_id: str, source_id: str, area: bool, rule: str,
                    index: CastIndex | None = None, cast_id: str = "") -> None:
        """A damage line that reached health (HEALTH_RESULTS)."""
        kinds = classify(result, damage_type)
        ability_id = str(ability_id)
        self.total += hit
        self.time[kinds["time"]] += hit
        self.school[kinds["school"]] += hit
        self.types[kinds["type"]] += hit
        if result == BLOCKED_RESULT:
            self.blocked_through += hit
        if self.first_ms is None or ts < self.first_ms:
            self.first_ms = ts
        if self.last_ms is None or ts > self.last_ms:
            self.last_ms = ts
        row = self._row(ability_id)
        row["damage"] += hit
        row["hits"] += 1
        row[kinds["time"]] += hit
        row["types"][kinds["type"]] += hit
        row["sources"][str(source_id)] += hit
        self.rules[rule] += hit
        if area:
            self.area += hit
            row["area"] += hit
        else:
            self.single += hit
            row["single"] += hit
            if index is not None and rule == "none" and kinds["time"] != "fall":
                key = (str(source_id), str(cast_id))
                pending = self._pending.get(key)
                if pending is None:
                    pending = self._pending[key] = []
                    index.watch(source_id, cast_id, lambda key=key: self._cast_became_area(key))
                pending.append((ability_id, hit))

    def _cast_became_area(self, key: tuple[str, str]) -> None:
        """The cast's second target landed: its earlier hits were area."""
        for ability_id, hit in self._pending.pop(key, ()):
            self.single -= hit
            self.area += hit
            self.rules["none"] -= hit
            self.rules["cast"] += hit
            row = self.abilities.get(ability_id)
            if row is not None:
                row["single"] -= hit
                row["area"] += hit

    def note_other(self, result: str, hit: int, overflow: int) -> None:
        """A recap-result line that did not reach health: a shield absorb,
        an avoided hit, a heal (landed and overheal), an absorbed heal."""
        if result == SHIELDED_RESULT:
            self.absorbed += hit
        elif result in AVOIDED_RESULTS:
            self.avoided += 1
        elif result in HEAL_RESULTS:
            self.healed += hit
            self.overheal += overflow
            if result in HOT_RESULTS:
                self.heal_hot += hit
            else:
                self.heal_direct += hit
        elif result == HEAL_ABSORBED_RESULT:
            self.heal_absorbed += hit

    def note_overkill(self, overflow: int) -> None:
        self.overkill += overflow

    def snapshot(self, name_of: Callable[[str], str], icon_of: Callable[[str], str],
                 unit_name_of: Callable[[str], str], top: int = 5) -> dict:
        """Plain dicts for a fight entry (read on the GUI thread): the
        totals by kind and the *top* abilities by damage, each with its
        kinds, its types and the source that did most of it."""
        rows = []
        for ability_id, row in self.abilities.items():
            source_id = row["sources"].most_common(1)[0][0] if row["sources"] else ""
            rows.append({
                "id": ability_id, "name": name_of(ability_id), "icon": icon_of(ability_id),
                "damage": row["damage"], "hits": row["hits"], "direct": row["direct"],
                "dot": row["dot"], "fall": row["fall"], "area": row["area"],
                "single": row["single"], "types": dict(row["types"]),
                "source": unit_name_of(source_id) if source_id else "",
            })
        rows.sort(key=lambda r: (-r["damage"], r["name"]))
        return {
            "total": self.total, "direct": self.time["direct"], "dot": self.time["dot"],
            "fall": self.time["fall"], "area": self.area, "single": self.single,
            "martial": self.school["martial"], "magical": self.school["magical"],
            "oblivion": self.school["oblivion"], "other": self.school["other"],
            "types": dict(self.types), "rules": dict(self.rules),
            "blocked_through": self.blocked_through, "absorbed": self.absorbed,
            "avoided": self.avoided, "healed": self.healed, "heal_direct": self.heal_direct,
            "heal_hot": self.heal_hot, "overheal": self.overheal,
            "heal_absorbed": self.heal_absorbed, "overkill": self.overkill,
            "first_ms": self.first_ms, "last_ms": self.last_ms,
            "abilities": rows[:top], "ability_count": len(rows),
        }


# ----------------------------------------------------------------- summary --

def _side_pct(left: int, right: int) -> tuple[int, int]:
    whole = left + right
    if whole <= 0:
        return 0, 0
    left_pct = round(100.0 * left / whole)
    return left_pct, 100 - left_pct


def summary_of_taken(taken: dict) -> dict:
    """The summary dict from a TakenTally snapshot (the player's 'taken'
    key): see summary_of_rows for the shape."""
    types = Counter(taken.get("types") or {})
    outside = {}
    for label, amount in types.items():
        if label not in {type_label(t) for t in MARTIAL_TYPES | MAGICAL_TYPES} and amount:
            outside[label] = amount
    sides = {
        "time": (int(taken.get("direct") or 0), int(taken.get("dot") or 0)),
        "target": (int(taken.get("area") or 0), int(taken.get("single") or 0)),
        "school": (int(taken.get("martial") or 0), int(taken.get("magical") or 0)),
    }
    return {
        "total": int(taken.get("total") or 0),
        "sides": sides,
        "pcts": {key: _side_pct(*pair) for key, pair in sides.items()},
        "types": types.most_common(),
        "outside": outside,
        "rules": dict(taken.get("rules") or {}),
        "blocked_through": int(taken.get("blocked_through") or 0),
        "absorbed": int(taken.get("absorbed") or 0),
        "avoided": int(taken.get("avoided") or 0),
        "healed": int(taken.get("healed") or 0),
        "heal_direct": int(taken.get("heal_direct") or 0),
        "heal_hot": int(taken.get("heal_hot") or 0),
        "overheal": int(taken.get("overheal") or 0),
        "heal_absorbed": int(taken.get("heal_absorbed") or 0),
        "overkill": int(taken.get("overkill") or 0),
    }


def rows_have_kinds(rows: list[dict]) -> bool:
    """Whether recap rows were recorded with their kinds (a row from before
    the change has no 'damage_type')."""
    return all("damage_type" in row for row in rows if row.get("kind") == "damage")


def summary_of_rows(rows: list[dict], overheal: int | None = None) -> dict:
    """The summary dict from a death recap's rows: the damage that reached
    health in the window as a total and three sides with their percentages
    (time: direct/dot, target: area/single, school: martial/magical), the
    damage types largest first, the amounts outside the two schools
    (oblivion, fall, drowning, untyped), what got through while blocking,
    what shields absorbed, hits avoided, healing landed (direct and over
    time) against overheal, absorbed healing and the killing blow's overkill.
    *overheal* is the recap's own sum when it kept one (pure overheals are
    not rows); else the rows' heal overflow is summed."""
    tally = TakenTally()
    row_overheal = 0
    for row in rows:
        kind = row.get("kind")
        result = str(row.get("result", ""))
        amount = int(row.get("amount") or 0)
        if kind == "damage":
            tally.note_damage(0, result, str(row.get("damage_type", "")), amount,
                              str(row.get("ability_id", "")), str(row.get("source", "")),
                              bool(row.get("area")), str(row.get("area_rule") or "none"))
            tally.absorbed += int(row.get("absorbed") or 0)
            if not row.get("health") and row.get("overflow"):
                tally.overkill = max(tally.overkill, int(row["overflow"]))
        elif kind == "absorbed":
            tally.absorbed += amount
        elif kind == "avoided":
            tally.avoided += 1
        elif kind == "heal":
            tally.note_other(result, amount, int(row.get("overflow") or 0))
            row_overheal += int(row.get("overflow") or 0)
        elif kind == "heal_absorbed":
            tally.heal_absorbed += amount
    snapshot = tally.snapshot(lambda a: a, lambda a: "", lambda u: u, top=0)
    if overheal is not None:
        snapshot["overheal"] = int(overheal)
    return summary_of_taken(snapshot)


# ------------------------------------------------------------ Warfare stars --

# Each side of each split, for damage dealt, damage taken and healing: the
# Warfare stars that act on it, with the game's tooltip text at the top
# stage (UESP, Online:Warfare) and the star's ESO-Hub page. The app never
# says which stars a player has: the log does not carry them.
ESOHUB_CP = "https://eso-hub.com/en/champion-points/warfare/"


def _star(name: str, text: str, slug: str) -> dict:
    return {"name": name, "text": text, "url": ESOHUB_CP + slug}


STARS: dict[tuple[str, str], list[dict]] = {
    ("dealt", "direct"): [_star("Master-at-Arms", "Increases your damage done with direct damage attacks by 6%.", "master-at-arms")],
    ("dealt", "dot"): [_star("Thaumaturge", "Increases your damage done with damage over time effects by 6%.", "thaumaturge")],
    ("dealt", "area"): [_star("Biting Aura", "Increases your damage done with area of effect attacks by 6%.", "biting-aura")],
    ("dealt", "single"): [_star("Deadly Aim", "Increases your damage done with single target attacks by 6%.", "deadly-aim")],
    ("dealt", "martial"): [_star("Mighty", "Grants 100 Weapon and Spell Damage to Martial attacks (Physical, Poison, Disease, Bleed).", "mighty")],
    ("dealt", "magical"): [_star("War Mage", "Grants 100 Weapon and Spell Damage to Magical attacks (Magic, Flame, Frost, Shock).", "war-mage")],
    ("taken", "direct"): [_star("Ironclad", "Reduces your damage taken by direct damage attacks by 6%.", "ironclad")],
    ("taken", "dot"): [_star("Enduring Resolve", "Reduces your damage taken by damage over time attacks by 6%.", "enduring-resolve")],
    ("taken", "area"): [_star("Unassailable", "Reduces your damage taken by area of effect attacks by 6%.", "unassailable")],
    ("taken", "single"): [_star("Duelist's Rebuff", "Reduces your damage taken by single target attacks by 6%.", "duelists-rebuff")],
    ("taken", "martial"): [_star("Hardy", "Reduces the damage you take from Martial attacks (Physical, Poison, Disease, Bleed) by 2%.", "hardy")],
    ("taken", "magical"): [_star("Elemental Aegis", "Reduces the damage you take from Magical attacks (Magic, Flame, Frost, Shock) by 2%.", "elemental-aegis")],
    ("heal", "direct"): [_star("Focused Mending", "Increases your Healing Done with single target heals by 10%.", "focused-mending")],
    ("heal", "dot"): [_star("Swift Renewal", "Increases your Healing Done with healing over time effects by 10%.", "swift-renewal")],
    ("heal", "landed"): [_star("Blessed", "Increases your Healing Done by 2%.", "blessed"),
                         _star("Quick Recovery", "Increases your Healing Taken by 2%.", "quick-recovery")],
    ("heal", "overheal"): [_star("Enlivening Overflow", "Overhealing yourself or an ally restores Magicka and Stamina to them, up to 150, for 6 seconds, once every 12 seconds per target.", "enlivening-overflow")],
}
# Every hit from a monster is "non-player" damage, so this star joins every
# damage-taken side
PREPARATION = _star("Preparation", "Reduces your damage taken from non-player attacks by 10%.", "preparation")


def stars_for(scope: str, side: str) -> list[dict]:
    """The Warfare stars for one side of one split: *scope* 'dealt', 'taken'
    or 'heal'; *side* a SIDE_LABELS key, or 'landed' / 'overheal' for the
    healing line. Damage taken always adds Preparation."""
    stars = list(STARS.get((scope, side), ()))
    if scope == "taken" and stars:
        stars.append(PREPARATION)
    return stars
