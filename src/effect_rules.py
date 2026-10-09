"""Tracked effects: rules anyone can paste, and the tracker they drive
(engine side, no Qt). Issue #10.

Design: every item on the uptime line is a rule. A rule names an effect by
its ability ids and asks for its uptime or its stack count on a chosen kind
of unit, in a plain text anyone can copy to others. One rule per line::

    # Name = ability ids... on <scope> [stacks | each]
    Major Courage = 109966 on group
    Taunt         = 38254 on boss each
    Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
    Touch of Z'en = 126597 on boss stacks
    Crux          = 184220 on self stacks

A rule matches any of its ids (an effect such as Off-Balance has one id
per skill that applies it). The scope says whose effects count: ``self``
is the player who writes the log, ``group`` any group member, ``pets`` a
group member's pet, ``boss`` an enemy the game flags as a boss, ``enemies``
any hostile. Three measurements: ``uptime`` (the default) is the share of
the fight the effect was on at least one unit in scope, the question "was
it up?"; ``stacks`` is the mean stack count while it was up, with the peak,
for effects that stack (Crux, Touch of Z'en, Arms of Relequen); ``each``
measures the effect on every unit of the scope separately, over the time
that unit was alive in the fight, and shows the mean of those shares, the
question "was each boss taunted?". ``each`` is the taunt's measure since
issue #9: a fight with two bosses averages them, and a boss killed before
the fight ends is measured to its death. The difference is not academic:
in 95 boss fights of twelve 2026 logs, the taunt's union to the fight's
end differed from its per-boss mean in 39, reading lower by up to 83
points where a boss died early and the fight ran on against its adds.

The uptime line's six group buffs (Major Courage, Major Force, Major
Slayer, Powerful Assault, Lucent Echoes, Pearlescent Ward) and the taunt
were tracked in code until 0.8.0; they are the first seven of
DEFAULT_RULES now, so anyone can rename, edit or delete them, and the
example picker holds them for whoever wants one back. As rules they read
the same, with two differences: a group buff is measured whatever the
group size (the code needed three players), and one that never appeared
in a fight reads 0% rather than being left off the line. Replaying the
twelve logs (376 fights) through both: the six buffs agreed in 690 of 745
readings; in the other 55 (46 of them Major Courage, the buff refreshed
most) the rule read higher, never lower, because the code ignored an
UPDATED refresh when it had missed the GAINED before it, though the buff
was up: a 12 s fight that read 7% reads 100%. The taunt agreed in 52 of 79
boss fights and read higher in 27 (lower in one, by 5 points): the code
kept its taunt spans in the encounter, which BEGIN_COMBAT replaces, so a
taunt already on the boss at the pull was lost until the tank's next
refresh (twelve fights, a 7.7 s fight reading 0% that reads 100%), and it
measured every boss from the fight's start whether or not it had arrived,
where ``each`` measures a unit over the time it was there.

Fights without a boss: trash packs are most fights (281 of the 376, with
up to 71 mobs hit). A ``boss`` rule has nothing to measure there, so it
measures every hostile the group fought instead, and both it and an
``enemies`` rule then say how many of the pack's mobs the effect reached,
``Alkosh:45% on 7 of 12 mobs`` (the pack is the mobs the group hit, plus
any a tracked effect landed on). In those fights Off-Balance reached up to
27 of 32 mobs with 7 at once, Major Vulnerability 7 of 18, Minor Brittle
18 of 32, the taunt 20 of 32. In a boss fight nothing changes: the boss
rule reads the boss alone (its effect was on the adds too in about half
the boss fights, almost never on the adds alone).

Dead units: the game does not always write FADED for an effect on a unit
that dies or is removed. 124 of the 376 fights ended with a span still
open on a dead or removed mob, and such a span runs into every later fight
of the zone. The engine tells the tracker when a unit dies or is removed
(forget_unit) and when the zone changes (zone_changed), which ends those
spans there.

A line that starts with ``$`` is a HyperTools export string, pasted as
is: HyperTools (the in-game tracker addon) serialises a tracker as nested
``$...&`` records, and its name, ability ids and target ("Yourself",
"Group", "Boss", "Current Target") become a rule here; ``stacks`` or
``on <scope>`` after the string override what it says.

What the logs carry (nine trial and dungeon logs of 2026): the stack
count is EFFECT_CHANGED's second field and changes arrive as UPDATED
lines, so stacks are read on GAINED and UPDATED; Off-Balance on a boss
comes under several ids at once (45902 for most sources, 62988 for
Elemental Blockade, 39077, 34733, 20806, 130139), so a union is needed,
and its uptime on a trial boss was 4 to 28% per fight; Crux stacks to 3
on the Arcanist alone; a pet-applied buff (a Glyphic's heal, Major
Protection from a netch) lands on players like any other and needs no
special case, since only the target's kind is looked at. Replaying the
bundled examples through two of those logs (Sunspire, Kyne's Aegis):
Off-Balance on the boss 12 to 28% per boss fight, to the decimal what an
independent scan of the lines gives; Crux on the logging Arcanist a mean
of 1.5 to 2.9 with a peak of 3 in every fight.
"""

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

SCOPES = ("self", "group", "pets", "boss", "enemies")
KINDS = ("uptime", "stacks", "each")

# Unit kinds the engine reports for an effect's target, per scope. A boss
# rule keeps its spans on the other hostiles too: they are what it measures
# in a fight without a boss
_SCOPE_KINDS = {
    "self": {"self"},
    "group": {"self", "group"},
    "pets": {"pet"},
    "boss": {"boss", "enemy"},
    "enemies": {"boss", "enemy"},
}
HOSTILE_KINDS = frozenset({"boss", "enemy"})
PLAYER_KINDS = frozenset({"self", "group"})

# The uptime line's own items, tracked in code until 0.8.0 (ids from the
# BuffTheGroup addon; the taunt debuff's from the logs)
UPTIME_LINE_RULES = """\
Major Courage    = 109966 on group
Major Force      = 61747 on group
Major Slayer     = 93109 on group
Powerful Assault = 61771 on group
Lucent Echoes    = 220015 on group
Pearlescent Ward = 172621 on group
Taunt            = 38254 on boss each
"""

# The rules a fresh install starts with: the uptime line's own items, then
# the maintainer's boss debuffs (2026-10-09; the Off-Balance ids beyond the
# first six are his list)
DEFAULT_RULES = (
    "# Tracked effects, one per line: Name = ability ids on <scope> [stacks | each]\n"
    "# scope: self | group | pets | boss | enemies. Share these lines as text.\n"
    "# A line that starts with $ is a HyperTools tracker export, pasted as is.\n"
    "# The uptime line's own items; delete what you do not want (Examples has them)\n"
    + UPTIME_LINE_RULES
    + "# Boss debuffs; in a fight without a boss they measure the pack instead\n"
    "Off-Balance   = 45902 62988 39077 34733 20806 130139 130145 130129 125750 62968 25256 34737 23808 137257 45834 137312 131562 on boss\n"
    "Touch of Z'en = 126597 on boss stacks\n"
    "Crux          = 184220 on self stacks\n"
    "Morag Tong    = 34384 on boss\n"
    "Minor Brittle = 145975 on boss\n"
    "Major Brittle = 263825 on boss\n"
    "Alkosh        = 76667 on boss\n"
)

# The example library Settings offers to paste from: (title, what it tells
# you, the rule line). The first fourteen are DEFAULT_RULES; the other ids
# were seen in the 2026 logs.
EXAMPLE_RULES = [
    ("Major Courage on the group",
     "Share of the fight Major Courage was on anyone in the group",
     "Major Courage = 109966 on group"),
    ("Major Force on the group",
     "Share of the fight Major Force was on anyone in the group",
     "Major Force = 61747 on group"),
    ("Major Slayer on the group",
     "Share of the fight Major Slayer was on anyone in the group",
     "Major Slayer = 93109 on group"),
    ("Powerful Assault on the group",
     "Uptime of the Powerful Assault set's buff on anyone in the group",
     "Powerful Assault = 61771 on group"),
    ("Lucent Echoes on the group",
     "Uptime of the Lucent Echoes set's buff on anyone in the group",
     "Lucent Echoes = 220015 on group"),
    ("Pearlescent Ward on the group",
     "Uptime of the Pearlescent Ward set's buff on anyone in the group",
     "Pearlescent Ward = 172621 on group"),
    ("Taunt on the boss",
     "How long each boss had a taunt on it, averaged over the bosses, a boss "
     "killed early measured to its death; the pack's mobs when there is no boss",
     "Taunt = 38254 on boss each"),
    ("Off-Balance on the boss",
     "Share of the fight the boss was off balance, under any of the skills that cause it",
     "Off-Balance = 45902 62988 39077 34733 20806 130139 130145 130129 125750 62968 25256 34737 23808 137257 45834 137312 131562 on boss"),
    ("Touch of Z'en stacks on the boss",
     "Mean and peak stacks of Z'en's Redress's debuff while it was up",
     "Touch of Z'en = 126597 on boss stacks"),
    ("Crux on yourself",
     "Mean and peak Crux an Arcanist held (the player writing the log)",
     "Crux = 184220 on self stacks"),
    ("The Morag Tong on the boss",
     "Uptime of the Morag Tong set's debuff",
     "Morag Tong = 34384 on boss"),
    ("Minor Brittle on the boss",
     "Uptime of Minor Brittle (critical damage taken up)",
     "Minor Brittle = 145975 on boss"),
    ("Major Brittle on the boss",
     "Uptime of Major Brittle",
     "Major Brittle = 263825 on boss"),
    ("Roar of Alkosh on the boss",
     "Uptime of the Roar of Alkosh set's debuff",
     "Alkosh = 76667 on boss"),
    ("Off-Balance immunity on the boss",
     "How much of the fight the boss could not be put off balance",
     "OB immunity = 134599 on boss"),
    ("Major Vulnerability on the boss",
     "Uptime under the ids the game uses for it",
     "Major Vulnerability = 106754 122389 167061 176815 on boss"),
    ("Minor Vulnerability on the boss",
     "Uptime under the ids the game uses for it",
     "Minor Vulnerability = 79717 68359 228115 228118 183271 on boss"),
    ("Arms of Relequen stacks on the boss",
     "Mean and peak stacks of the set's debuff",
     "Relequen = 107203 on boss stacks"),
    ("Hemorrhaging stacks on enemies",
     "Mean and peak stacks of the bleed status effect on any hostile",
     "Hemorrhaging = 148801 on enemies stacks"),
    ("Major Berserk on yourself",
     "Uptime of your own Major Berserk, from any source",
     "Major Berserk = 61745 263306 36973 62195 on self"),
    ("Minor Berserk on the group",
     "Uptime on any group member",
     "Minor Berserk = 61744 on group"),
    ("Minor Courage on the group",
     "Uptime on any group member",
     "Minor Courage = 147417 on group"),
    ("Major Protection on the group",
     "Uptime on any group member, a Bull Netch's included",
     "Major Protection = 61722 on group"),
    ("Major Courage on each player",
     "Mean over the group of each player's own Major Courage uptime",
     "Courage each = 109966 on group each"),
]

MERGE_GAP_MS = 50  # an effect refreshed within this is one span


@dataclass(frozen=True)
class Rule:
    name: str
    ids: FrozenSet[str]
    scope: str = "group"
    kind: str = "uptime"


def parse_rules(text: str) -> Tuple[List[Rule], List[str]]:
    """The rules in *text* and the lines it could not read, each error
    naming its line number. A bad line never stops the others."""
    rules: List[Rule] = []
    errors: List[str] = []
    for number, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("$"):
            try:
                rules.extend(hypertools_rules(line))
            except ValueError as exc:
                errors.append(f"line {number}: {exc}")
            continue
        rule, error = _parse_line(line)
        if rule is not None:
            rules.append(rule)
        else:
            errors.append(f"line {number}: {error}")
    return rules, errors


def _parse_options(tokens: List[str], scope: str, kind: str):
    """(ids, scope, kind) from the tokens after a rule's name, or raise."""
    ids: List[str] = []
    kind_given = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        low = token.lower()
        if low.isdigit():
            ids.append(low)
        elif low == "on":
            if i + 1 >= len(tokens) or tokens[i + 1].lower() not in SCOPES:
                raise ValueError("'on' needs one of " + ", ".join(SCOPES))
            scope = tokens[i + 1].lower()
            i += 1
        elif low in SCOPES:
            scope = low
        elif low in KINDS:
            if kind_given is not None and kind_given != low:
                raise ValueError(f"'{kind_given}' and '{low}' are two measurements; a rule takes one")
            kind = kind_given = low
        else:
            raise ValueError(f"'{token}' is not an ability id, 'on <scope>', 'stacks', 'each' or 'uptime'")
        i += 1
    return ids, scope, kind


def rule_name(line: str) -> str:
    """The name a rule line gives, lower-cased, for telling rules apart."""
    return line.split("=", 1)[0].strip().lower()


def lines_to_add(lines: List[str], text: str) -> List[str]:
    """Of the rule *lines*, those whose name *text* does not already have:
    what the example picker adds, and what an older config is given of
    the uptime line's items (see app_config)."""
    have = {rule.name.lower() for rule in parse_rules(text)[0]}
    return [line for line in lines if rule_name(line) not in have]


def _parse_line(line: str):
    name, sep, rest = line.partition("=")
    name = name.strip()
    if not sep or not name:
        return None, "expected: Name = ability ids on <scope> [stacks | each]"
    tokens = rest.replace(",", " ").split()
    try:
        ids, scope, kind = _parse_options(tokens, "group", "uptime")
    except ValueError as exc:
        return None, str(exc)
    if not ids:
        return None, "no ability id (a number) after '='"
    return Rule(name, frozenset(ids), scope, kind), None


# ---- HyperTools export strings ----

_HT_TARGETS = {"yourself": "self", "group": "group", "group member": "group",
               "boss": "boss", "current target": "boss"}


def decode_hypertools(text: str):
    """The table a HyperTools export string encodes. The addon writes a
    scalar as ``$N12&``, ``$Btrue&`` or ``$Stext&`` and a table as
    ``$<key><value>...&`` with keys and values written the same way."""
    value, end = _ht_value(text, 0)
    if end < len(text) and text[end:].strip():
        raise ValueError("text after the end of the HyperTools string")
    return value


def _ht_value(s: str, i: int):
    if i >= len(s) or s[i] != "$":
        raise ValueError("not a HyperTools export string")
    j = i + 1
    if j >= len(s):
        raise ValueError("unfinished HyperTools string")
    if s[j] in "NBS" and (j + 1 >= len(s) or s[j + 1] not in "$&"):
        end = s.find("&", j)
        if end < 0:
            raise ValueError("unfinished HyperTools string")
        kind, body = s[j], s[j + 1:end]
        if kind == "N":
            number = float(body)
            return (int(number) if number.is_integer() else number), end + 1
        if kind == "B":
            return body == "true", end + 1
        return body, end + 1
    items = []
    while j < len(s) and s[j] != "&":
        item, j = _ht_value(s, j)
        items.append(item)
    if j >= len(s):
        raise ValueError("unfinished HyperTools string")
    if len(items) % 2:
        raise ValueError("a HyperTools table with a key and no value")
    return dict(zip(items[0::2], items[1::2])), j + 1


def _ht_ids(tracker: dict) -> List[str]:
    ids: List[str] = []
    for value in (tracker.get("IDs") or {}).values():
        if isinstance(value, (int, float)):
            ids.append(str(int(value)))
    for event in (tracker.get("events") or {}).values():
        if isinstance(event, dict):
            for value in ((event.get("arguments") or {}).get("Ids") or {}).values():
                if isinstance(value, (int, float)):
                    ids.append(str(int(value)))
    return ids


def hypertools_rules(line: str) -> List[Rule]:
    """The rules a HyperTools export line gives: one per tracker that names
    ability ids, groups walked into. Words after the string (``stacks``,
    ``on boss``) apply to all of them."""
    end = line.rfind("&") + 1
    if end <= 0:
        raise ValueError("not a HyperTools export string")
    table = decode_hypertools(line[:end])
    tokens = line[end:].replace(",", " ").split()
    _ids, scope_override, kind_override = _parse_options(tokens, "", "")
    if _ids:
        raise ValueError("ability ids belong in a rule of their own, not after a HyperTools string")
    rules: List[Rule] = []

    def walk(tracker, inherited_scope):
        if not isinstance(tracker, dict):
            return
        target = str(tracker.get("target") or "").lower()
        scope = _HT_TARGETS.get(target, inherited_scope)
        ids = _ht_ids(tracker)
        if ids:
            name = str(tracker.get("name") or "HyperTools tracker")
            kind = "stacks" if _ht_shows_stacks(tracker) else "uptime"
            rules.append(Rule(name, frozenset(ids), scope_override or scope, kind_override or kind))
        for child in (tracker.get("children") or {}).values():
            walk(child, scope)

    walk(table, "group")
    if not rules:
        raise ValueError("the HyperTools string names no ability ids")
    return rules


def _ht_shows_stacks(tracker: dict) -> bool:
    stacks = tracker.get("stacks")
    return isinstance(stacks, dict) and bool(stacks.get("show"))


# ---- the tracker ----

class EffectTracker:
    """Open and closed spans of each rule's effect on each unit in scope,
    with the stack count and the unit's kind, in raw log milliseconds;
    snapshot() reads a fight's window out of them, as the timeline
    recorder does.

    Each id of a rule runs its own span on a unit, so overlapping ids do
    not cut each other short, and the measurement merges them. A span is
    closed by FADED, by a stack change (one span ends, the next begins),
    by the unit's death or removal (forget_unit: the game does not always
    write FADED for a corpse's effects) or by a zone change for hostiles
    and pets (zone_changed: unit ids are handed out afresh). Closed spans
    are pruned once the fight they belong to has been published."""

    def __init__(self, rules: List[Rule]):
        self.rules = list(rules)
        self._by_id: Dict[str, List[int]] = {}
        for index, rule in enumerate(self.rules):
            for ability_id in rule.ids:
                self._by_id.setdefault(ability_id, []).append(index)
        # (rule index, target id, ability id) -> [start_ms, stacks, kind]
        self._open: Dict[tuple, list] = {}
        # rule index -> [[start_ms, end_ms, stacks, target_id, kind], ...]
        self._closed: Dict[int, List[list]] = {}
        # unit id -> log ms it died or was removed (forget_unit)
        self._gone: Dict[str, int] = {}

    def __bool__(self):
        return bool(self.rules)

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()
        self._gone.clear()

    def record(self, effect_type: str, ability_id: str, target_id: str,
               stack_count, timestamp_ms: int, target_kind: Optional[str]) -> None:
        """An EFFECT_CHANGED line. *target_kind* is what the engine knows
        the target to be: 'self', 'group', 'pet', 'boss', 'enemy' or None."""
        indexes = self._by_id.get(str(ability_id))
        if not indexes or target_kind is None:
            return
        try:
            stacks = max(1, int(stack_count))
        except (TypeError, ValueError):
            stacks = 1
        target_id = str(target_id)
        for index in indexes:
            if target_kind not in _SCOPE_KINDS[self.rules[index].scope]:
                continue
            key = (index, target_id, str(ability_id))
            opened = self._open.get(key)
            if effect_type in ("GAINED", "UPDATED"):
                if opened is None:
                    self._open[key] = [timestamp_ms, stacks, target_kind]
                elif opened[1] != stacks:
                    # A stack change ends one span and starts the next
                    self._close(index, opened[0], timestamp_ms, opened[1], target_id, opened[2])
                    self._open[key] = [timestamp_ms, stacks, target_kind]
            elif effect_type == "FADED" and opened is not None:
                del self._open[key]
                self._close(index, opened[0], timestamp_ms, opened[1], target_id, opened[2])

    def forget_unit(self, unit_id: str, timestamp_ms: int) -> None:
        """The unit died or was removed at *timestamp_ms*: its open spans
        end here, and an ``each`` rule measures it to this moment."""
        unit_id = str(unit_id)
        for key in [key for key in self._open if key[1] == unit_id]:
            start, stacks, kind = self._open.pop(key)
            self._close(key[0], start, timestamp_ms, stacks, unit_id, kind)
        self._gone.setdefault(unit_id, timestamp_ms)

    def zone_changed(self, timestamp_ms: int) -> None:
        """A new zone hands unit ids out afresh: open spans on hostiles and
        pets end here. A player's buffs carry over, and so do their spans."""
        for key in [key for key, span in self._open.items() if span[2] not in PLAYER_KINDS]:
            start, stacks, kind = self._open.pop(key)
            self._close(key[0], start, timestamp_ms, stacks, key[1], kind)
        self._gone.clear()

    def _close(self, index: int, start: int, end: int, stacks: int,
               target_id: str, kind: str) -> None:
        if end <= start:
            return
        spans = self._closed.setdefault(index, [])
        if spans:
            last = spans[-1]
            if (last[3] == target_id and last[2] == stacks
                    and 0 <= start - last[1] <= MERGE_GAP_MS):
                last[1] = max(last[1], end)
                return
        spans.append([start, end, stacks, target_id, kind])

    def _window(self, index: int, fight_start_ms: int, fight_end_ms: int) -> List[tuple]:
        """A rule's spans clipped to the fight: (start, end, stacks, target,
        kind), open spans running to the fight's end."""
        spans = list(self._closed.get(index, []))
        spans.extend([start, fight_end_ms, stacks, target, kind]
                     for (ri, target, _aid), (start, stacks, kind) in self._open.items()
                     if ri == index)
        clipped = [(max(s, fight_start_ms), min(e, fight_end_ms), stacks, target, kind)
                   for s, e, stacks, target, kind in spans
                   if e > fight_start_ms and s < fight_end_ms]
        clipped.sort()
        return clipped

    def snapshot(self, fight_start_ms: int, fight_end_ms: int,
                 name_of: Optional[Callable[[str], str]] = None,
                 units: Optional[Dict[str, tuple]] = None) -> List[dict]:
        """One entry per rule for the fight window: name, scope, kind, what
        it was measured on ('units': the scope, or 'mobs' for a hostile
        rule in a fight without a boss), the uptime percentage, the mean
        and peak stacks while up, how many of the pack's mobs it reached
        and how many there were, the text the uptime line shows, and
        fight-relative intervals for a timeline.

        *units* is what the engine knows of the fight's units, unit id ->
        (kind, since_ms, gone_ms): the players ('self' or 'group'), and the
        hostiles the group hit ('boss' or 'enemy') with the log time each
        was added and the time it died or was removed, None when not in
        the fight. It says whether the fight had a boss, which mobs make
        up the pack, and the window an ``each`` rule measures each unit
        over. Without it (the tracker alone) the spans tell: a span on a
        boss means a boss fight, and a unit is measured from the fight's
        start to its death as forget_unit reported it, or the fight's end.
        """
        out: List[dict] = []
        if fight_end_ms <= fight_start_ms:
            return out
        duration = fight_end_ms - fight_start_ms
        windows = [self._window(index, fight_start_ms, fight_end_ms)
                   for index in range(len(self.rules))]
        hostiles_seen = {(span[3], span[4]) for spans in windows for span in spans
                         if span[4] in HOSTILE_KINDS}
        if units is not None:
            boss_fought = any(info[0] == "boss" for info in units.values())
            pack = {uid for uid, info in units.items() if info[0] == "enemy"}
        else:
            boss_fought = any(kind == "boss" for _uid, kind in hostiles_seen)
            pack = set()
        pack |= {uid for uid, kind in hostiles_seen if kind == "enemy"}
        for index, rule in enumerate(self.rules):
            spans = windows[index]
            measured = rule.scope
            if rule.scope == "boss":
                if boss_fought:
                    spans = [span for span in spans if span[4] == "boss"]
                else:
                    measured = "mobs"
            elif rule.scope == "enemies" and not boss_fought:
                measured = "mobs"
            up_ms, mean_stacks, peak = _measure(spans)
            if rule.kind == "each":
                shares = _unit_shares(spans, self._unit_windows(
                    rule.scope, measured, spans, units, fight_start_ms, fight_end_ms))
                uptime_pct = 100.0 * sum(shares) / len(shares) if shares else 0.0
            else:
                uptime_pct = 100.0 * up_ms / duration
            if rule.kind == "stacks":
                text = f"{rule.name}:{mean_stacks:.1f}/{peak}" if up_ms else f"{rule.name}:0"
            else:
                text = f"{rule.name}:{uptime_pct:.0f}%"
            reached = len({span[3] for span in spans}) if measured == "mobs" else 0
            mobs = len(pack) if measured == "mobs" else 0
            if reached:
                # An effect that reached nothing reads 0 on its own; "on 0
                # of 7 mobs" after every such item made a pack's line noise
                text += f" on {reached} of {mobs} mobs"
            out.append({
                "name": rule.name, "scope": rule.scope, "kind": rule.kind,
                "units": measured,
                "uptime_pct": round(uptime_pct, 1), "avg_stacks": round(mean_stacks, 2),
                "max_stacks": peak, "mobs_reached": reached, "mobs": mobs, "text": text,
                "intervals": [{"start_ms": s - fight_start_ms, "end_ms": e - fight_start_ms,
                               "stacks": stacks,
                               "target": name_of(target) if name_of else target}
                              for s, e, stacks, target, _kind in spans],
            })
        return out

    def _unit_windows(self, scope: str, measured: str, spans, units,
                      fight_start_ms: int, fight_end_ms: int) -> Dict[str, Tuple[int, int]]:
        """For an ``each`` rule, the units it is measured on and the part
        of the fight each was there for: the engine's units of the measured
        kind, and every unit the effect was on."""
        if measured == "mobs":
            kinds = {"enemy"}
        elif measured == "boss":
            kinds = {"boss"}
        else:
            kinds = _SCOPE_KINDS[scope]
        candidates = {span[3] for span in spans}
        if units is not None:
            candidates |= {uid for uid, info in units.items() if info[0] in kinds}
        windows = {}
        for unit_id in candidates:
            since, gone = None, self._gone.get(unit_id)
            if units is not None and unit_id in units:
                since, gone = units[unit_id][1], units[unit_id][2]
            start = max(fight_start_ms, since or fight_start_ms)
            end = min(fight_end_ms, gone) if gone is not None else fight_end_ms
            if end > start:
                windows[unit_id] = (start, end)
        return windows

    def prune_before(self, timestamp_ms: int) -> None:
        """Free closed spans that ended before *timestamp_ms*, and the
        deaths and removals from before it."""
        for index in list(self._closed):
            kept = [span for span in self._closed[index] if span[1] > timestamp_ms]
            if kept:
                self._closed[index] = kept
            else:
                del self._closed[index]
        for unit_id in [uid for uid, gone in self._gone.items() if gone < timestamp_ms]:
            del self._gone[unit_id]


def _measure(spans) -> Tuple[int, float, int]:
    """(ms the effect was up on any unit, mean stacks over that time taking
    the highest stack count among the units it was on, peak stacks)."""
    if not spans:
        return 0, 0.0, 0
    events = []
    for start, end, stacks, *_rest in spans:
        events.append((start, 1, stacks))
        events.append((end, -1, stacks))
    events.sort(key=lambda event: (event[0], event[1]))
    active: Dict[int, int] = {}  # stack level -> spans at it
    up_ms = 0
    weighted = 0.0
    peak = 0
    previous = None
    for at, delta, stacks in events:
        if previous is not None and at > previous and active:
            level = max(active)
            up_ms += at - previous
            weighted += level * (at - previous)
            peak = max(peak, level)
        previous = at
        if delta > 0:
            active[stacks] = active.get(stacks, 0) + 1
        else:
            active[stacks] -= 1
            if not active[stacks]:
                del active[stacks]
    return up_ms, (weighted / up_ms if up_ms else 0.0), peak


def _union_ms(pairs) -> int:
    """How many ms the (start, end) pairs cover between them."""
    total, open_from, open_to = 0, None, None
    for start, end in sorted(pairs):
        if open_to is None or start > open_to:
            if open_to is not None:
                total += open_to - open_from
            open_from, open_to = start, end
        else:
            open_to = max(open_to, end)
    if open_to is not None:
        total += open_to - open_from
    return total


def _unit_shares(spans, windows: Dict[str, Tuple[int, int]]) -> List[float]:
    """For an ``each`` rule: each unit's share of its own window the effect
    was on it."""
    shares = []
    for unit_id, (start, end) in windows.items():
        own = [(max(s, start), min(e, end)) for s, e, _n, target, _k in spans
               if target == unit_id and e > start and s < end]
        shares.append(_union_ms(own) / (end - start))
    return shares
