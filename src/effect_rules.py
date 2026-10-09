"""Tracked effects: rules anyone can paste, and the tracker they drive
(engine side, no Qt). Issue #10.

Design: the six group buffs and the taunt on the uptime line are built in;
this lets a user name any effect by its ability ids and ask for its uptime
or its stack count on a chosen kind of unit, in a plain text they can copy
to others. One rule per line::

    # Name = ability ids... on <scope> [stacks]
    Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
    Touch of Z'en = 126597 on boss stacks
    Crux          = 184220 on self stacks
    Minor Courage = 147417 on group

A rule matches any of its ids (an effect such as Off-Balance has one id
per skill that applies it). The scope says whose effects count: ``self``
is the player who writes the log, ``group`` any group member, ``pets`` a
group member's pet, ``boss`` an enemy the game flags as a boss, ``enemies``
any hostile. ``uptime`` (the default) is the share of the fight the
effect was on at least one unit in scope, the question "was it up?";
``stacks`` is the mean stack count while it was up, with the peak, for
effects that stack (Crux, Touch of Z'en, Arms of Relequen).

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
KINDS = ("uptime", "stacks")

# Unit kinds the engine reports for an effect's target, per scope
_SCOPE_KINDS = {
    "self": {"self"},
    "group": {"self", "group"},
    "pets": {"pet"},
    "boss": {"boss"},
    "enemies": {"boss", "enemy"},
}

# The rules a fresh install starts with: the examples of issue #10, with
# the ids the logs show (Morag Tong's from LuiExtended's effect table)
DEFAULT_RULES = """\
# Tracked effects, one per line: Name = ability ids on <scope> [stacks]
# scope: self | group | pets | boss | enemies. Share these lines as text.
# A line that starts with $ is a HyperTools tracker export, pasted as is.
Off-Balance   = 45902 62988 39077 34733 20806 130139 130145 130129 125750 62968 25256 34737 23808 137257 45834 137312 131562 on boss
Touch of Z'en = 126597 on boss stacks
Crux          = 184220 on self stacks
Morag Tong    = 34384 on boss
"""

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
            kind = low
        else:
            raise ValueError(f"'{token}' is not an ability id, 'on <scope>', 'stacks' or 'uptime'")
        i += 1
    return ids, scope, kind


def _parse_line(line: str):
    name, sep, rest = line.partition("=")
    name = name.strip()
    if not sep or not name:
        return None, "expected: Name = ability ids on <scope> [stacks]"
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
    with the stack count, in raw log milliseconds; snapshot() reads a
    fight's window out of them, as the timeline recorder does."""

    def __init__(self, rules: List[Rule]):
        self.rules = list(rules)
        self._by_id: Dict[str, List[int]] = {}
        for index, rule in enumerate(self.rules):
            for ability_id in rule.ids:
                self._by_id.setdefault(ability_id, []).append(index)
        # (rule index, target id, ability id) -> [start_ms, stacks]: each id
        # of a rule runs its own span on a unit, and the union is measured
        self._open: Dict[tuple, list] = {}
        # rule index -> [[start_ms, end_ms, stacks, target_id], ...]
        self._closed: Dict[int, List[list]] = {}

    def __bool__(self):
        return bool(self.rules)

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()

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
        for index in indexes:
            if target_kind not in _SCOPE_KINDS[self.rules[index].scope]:
                continue
            key = (index, str(target_id), str(ability_id))
            opened = self._open.get(key)
            if effect_type in ("GAINED", "UPDATED"):
                if opened is None:
                    self._open[key] = [timestamp_ms, stacks]
                elif opened[1] != stacks:
                    # A stack change ends one span and starts the next
                    self._close(index, opened[0], timestamp_ms, opened[1], key[1])
                    self._open[key] = [timestamp_ms, stacks]
            elif effect_type == "FADED" and opened is not None:
                del self._open[key]
                self._close(index, opened[0], timestamp_ms, opened[1], key[1])

    def _close(self, index: int, start: int, end: int, stacks: int, target_id: str) -> None:
        if end <= start:
            return
        spans = self._closed.setdefault(index, [])
        if spans:
            last = spans[-1]
            if (last[3] == target_id and last[2] == stacks
                    and 0 <= start - last[1] <= MERGE_GAP_MS):
                last[1] = max(last[1], end)
                return
        spans.append([start, end, stacks, target_id])

    def snapshot(self, fight_start_ms: int, fight_end_ms: int,
                 name_of: Optional[Callable[[str], str]] = None) -> List[dict]:
        """One entry per rule for the fight window: name, scope, kind, the
        uptime percentage, the mean and peak stacks while up, the text the
        uptime line shows, and fight-relative intervals for a timeline."""
        out = []
        if fight_end_ms <= fight_start_ms:
            return out
        duration = fight_end_ms - fight_start_ms
        for index, rule in enumerate(self.rules):
            spans = list(self._closed.get(index, []))
            spans.extend([start, fight_end_ms, stacks, target]
                         for (ri, target, _aid), (start, stacks) in self._open.items() if ri == index)
            clipped = [(max(s, fight_start_ms), min(e, fight_end_ms), stacks, target)
                       for s, e, stacks, target in spans
                       if e > fight_start_ms and s < fight_end_ms]
            clipped.sort()
            up_ms, mean_stacks, peak = _measure(clipped)
            uptime_pct = 100.0 * up_ms / duration
            if rule.kind == "stacks":
                text = f"{rule.name}:{mean_stacks:.1f}/{peak}" if up_ms else f"{rule.name}:0"
            else:
                text = f"{rule.name}:{uptime_pct:.0f}%"
            out.append({
                "name": rule.name, "scope": rule.scope, "kind": rule.kind,
                "uptime_pct": round(uptime_pct, 1), "avg_stacks": round(mean_stacks, 2),
                "max_stacks": peak, "text": text,
                "intervals": [{"start_ms": s - fight_start_ms, "end_ms": e - fight_start_ms,
                               "stacks": stacks,
                               "target": name_of(target) if name_of else target}
                              for s, e, stacks, target in clipped],
            })
        return out

    def prune_before(self, timestamp_ms: int) -> None:
        """Free closed spans that ended before *timestamp_ms*."""
        for index in list(self._closed):
            kept = [span for span in self._closed[index] if span[1] > timestamp_ms]
            if kept:
                self._closed[index] = kept
            else:
                del self._closed[index]


def _measure(spans) -> Tuple[int, float, int]:
    """(ms the effect was up on any unit, mean stacks over that time taking
    the highest stack count among the units it was on, peak stacks)."""
    if not spans:
        return 0, 0.0, 0
    edges = sorted({t for s, e, _n, _u in spans for t in (s, e)})
    up_ms = 0
    weighted = 0.0
    peak = 0
    for a, b in zip(edges, edges[1:]):
        level = max((n for s, e, n, _u in spans if s <= a and e >= b), default=0)
        if level:
            up_ms += b - a
            weighted += level * (b - a)
            peak = max(peak, level)
    return up_ms, (weighted / up_ms if up_ms else 0.0), peak
