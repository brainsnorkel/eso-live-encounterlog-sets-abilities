"""
One player's actions on the Events tab (issue #214): their casts in the
order begun, with the events that touched them between, when the tab's Who
picks a player. Qt-free: the tab draws what this gives (gui.events_tab).

Design: one player's actions, the Events tab's second mode (issue #214).
The study's design (build/surveys/timeline-214-2026-11-11, design/lists,
section 2.2) as the maintainer trimmed it: no judgement marks (no idle
share, no amber gaps, no 'weave' or 'miss'), a gap a plain number, and the
rows below.

- A cast is a row: when it began, its bar slot, the ability, the unit it
  was aimed at, its length and the gap since the skill before. The casts
  are the fight entry's (fight_casts), the Build tab's own count of them.
- Bar: F1 to F5 and FU on the front bar, B1 to B5 and BU on the back, W
  on a werewolf bar the engine rebuilt, for the slot whose skill the cast
  is (casts.slot_holds, as the Build tab puts a count under a slot): a
  skill slotted on both bars reads 'F3/B3', since the log does not say
  which bar was up. Blank for a cast no slot holds.
- A light attack begun LA_FOLD_MS or less before a skill is that skill's
  mark in the LA column rather than a row of its own, and a weapon swap is
  a mark (SWAP_MARK) on the Bar of the next cast begun within
  SWAP_FOLD_MS. A light attack no skill follows so soon, or a swap no cast
  follows, stays a row. The tab's More holds both as rows instead.
- Length: from the cast's BEGIN_CAST to its END_CAST, shown only when the
  log wrote one and it is INSTANT_MS or longer. Over the Kyne's Aegis split
  of 2026-10-11, 15,026 of the 17,641 END_CASTs came in the cast's own
  millisecond and 234 one millisecond later (Swap Weapons, light attacks,
  Bash: casts whose BEGIN_CAST gives no duration), all instants; a
  channelled heavy attack, Claw Fury or Insatiable Hunger lasts 0.5 to 4.5
  s. The BEGIN_CAST's own duration field is never read: it is what the
  cast would take, not what it took.
- Gap: the seconds since the skill before began, for a skill (a cast that
  is none of casts.EXTRA_KINDS: no light or heavy attack, swap, potion
  and the like). A plain number.
- Between the casts, the events that touched the player, from the fight's
  events (fight_events) by their rules (event_rows): their deaths and
  returns; the hits they took of 30% of their maximum health or more,
  chained as the tab's Big hits are, the killing hit left to the death's
  row; the bosses' casts aimed at them, a burst of one ability one row;
  the taunt swaps they were in. Then context rows, drawn muted: the
  bosses' health marks, their stretches with no health lost, the map
  changing and a boss's death.
- No cast for N s: for the player who writes the log alone (the row the
  game flags isLocalPlayer), a stretch of IDLE_MS or more with no cast of
  theirs going on, from the end of a cast (its END_CAST, else its start)
  to the next one's start, the fight's start and end included, less the
  time they were dead (a death to their return, or to the end). The
  client writes every cast of its own player, so a gap there is the
  player's; another player's casts reach the log only while that player
  is near enough to the logging one, so a gap in theirs can be the log's,
  and none is drawn. The row names what the log can say of the stretch:
  big hits the player blocked (a block writes no cast), a boss that lost
  no health then, the map changing, the game ending combat and beginning
  it again; else nothing more.
"""

from collections import namedtuple

import casts as cast_rules
import event_rows
import fight_casts
import fight_events as fe
from event_rows import Row, clock

# A light attack begun this long or less before a skill is that skill's mark
LA_FOLD_MS = 300
# A weapon swap is a mark on the next cast begun this long after it or less
SWAP_FOLD_MS = 1500
# A length under this is an instant: the END_CAST in the cast's millisecond
# or the next (see the module)
INSTANT_MS = 50
# No cast this long or longer, for the logging player, is a row
IDLE_MS = 3000
SWAP_MARK = "⇄"
LA_MARK = "LA"

# The rows' categories: the casts and the stretches with no cast are always
# shown; the events' are the tab's Deaths, Boss, Big hits and Taunt swaps
# boxes; the context rows are More's Context switch
CASTS, IDLE, CONTEXT = "casts", "idle", "context"
EVENT_CATEGORIES = ("deaths", "boss", "hits", "taunts")
# The order within a millisecond: the context, the cast, the event, then a
# stretch with no cast that the cast began
_RANK = {CONTEXT: 0, CASTS: 1, IDLE: 3}

# An event_rows Row and the actions' own: the Action cell's text (the
# cast's ability, or what happened and its ability), the bar slot, the
# light attack folded in, the target, the length, the gap since the last
# skill, and whether it is a context row (drawn muted)
ActionRow = namedtuple("ActionRow", Row._fields + ("action", "bar", "la", "target", "length",
                                                   "gap", "muted"))

# A cast's words in the Detail for the extras whose ability names do not
# say what they are
_KIND_WORDS = {"potion": "potion", "synergy": "synergy"}
# What a cast row is (its 'what', which Ctrl+G's mark on the DPS graph
# names): a skill is a Cast; an extra its kind (casts.EXTRA_KINDS)
_WHAT = {None: "Cast", "light": "Light attack", "heavy": "Heavy attack", "bash": "Bash",
         "swap": "Swap", "dodge": "Dodge", "synergy": "Synergy", "potion": "Potion",
         "break_free": "Break free"}
# The role order of the Who picker: tank, healer, damage dealer
_ROLE_ORDER = {"T": 0, "H": 1, "D": 2}


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.1f} s"


def players(entry) -> list[dict]:
    """The fight's players a Who picker lists: its player rows (not the
    companions'), tanks, then healers, then damage dealers, each in the
    table's order."""
    rows = [p for p in getattr(entry, "players", None) or []
            if not p.get("companion") and p.get("unit_id")]
    return sorted(rows, key=lambda p: _ROLE_ORDER.get(str(p.get("role") or ""), 3))


def player_name(p: dict) -> str:
    """A player row's name as text (a row built by hand can hold a list)."""
    name = p.get("name") or ""
    return ", ".join(map(str, name)) if isinstance(name, (list, tuple)) else str(name)


def player_row(entry, key: str):
    """The player row of *key* in *entry*, or None."""
    return next((p for p in getattr(entry, "players", None) or []
                 if str(p.get("unit_id")) == str(key) and not p.get("companion")), None)


# ------------------------------------------------------------------ bars --

def _bar_slots(p: dict) -> list[tuple[dict, str]]:
    """(slot, label) for every slot of the player's bars: F1 to F5 and FU,
    B1 to B5 and BU, W for a rebuilt werewolf bar; the ultimate is the
    sixth slot, or the one a bar marks (gui.fight_render.ultimate_gap)."""
    out = []
    for letter, name in (("F", "front_bar_slots"), ("B", "back_bar_slots"),
                         ("W", "werewolf_bar_slots")):
        slots = p.get(name) or []
        marked = any(slot.get("ultimate") for slot in slots)
        number = 0
        for index, slot in enumerate(slots):
            if (slot.get("ultimate") if marked else index == 5):
                out.append((slot, f"{letter}U"))
            else:
                number += 1
                out.append((slot, f"{letter}{number}"))
    return out


def _bar_of(p: dict, abilities: dict):
    """A cast (id, name) -> its bar label ('F3', 'F3/B3', '')."""
    def name_of(ability_id):
        return abilities.get(str(ability_id), ("",))[0]

    holders = [(cast_rules.slot_holds(slot, name_of), label) for slot, label in _bar_slots(p)]
    known: dict[str, str] = {}

    def bar(ability_id: str, name: str) -> str:
        if ability_id not in known:
            known[ability_id] = "/".join(label for holds, label in holders
                                         if holds(ability_id, name))
        return known[ability_id]
    return bar


# ----------------------------------------------------------------- casts --

def _cast_rows(casts: list, abilities: dict, bar, light_rows: bool, swap_rows: bool) -> list:
    kinds = [cast_rules.kind_of(cast.ability_id) for cast in casts]
    folded, la = set(), set()   # light attacks folded; the skills they fold into
    if not light_rows:
        for i, cast in enumerate(casts):
            if kinds[i] != "light":
                continue
            for j in range(i + 1, len(casts)):
                if casts[j].t - cast.t > LA_FOLD_MS or kinds[j] == "light":
                    break
                if kinds[j] is None:
                    if j not in la:
                        la.add(j)
                        folded.add(i)
                    break
    swapped = set()  # the casts a swap before marks
    if not swap_rows:
        for i, cast in enumerate(casts):
            if kinds[i] != "swap":
                continue
            for j in range(i + 1, len(casts)):
                if casts[j].t - cast.t > SWAP_FOLD_MS or kinds[j] == "swap":
                    break
                if j in folded:
                    continue  # the skill it folded into, further on, takes the mark
                swapped.add(j)
                folded.add(i)
                break
    rows = []
    last_skill = None
    for i, cast in enumerate(casts):
        if i in folded:
            continue
        name, icon = abilities.get(cast.ability_id, (f"Ability {cast.ability_id}", ""))
        kind = kinds[i]
        gap = ""
        if kind is None:
            if last_skill is not None:
                gap = _seconds(cast.t - last_skill)
            last_skill = cast.t
        length = ""
        if cast.flags & fight_casts.ENDED and cast.length >= INSTANT_MS:
            length = _seconds(cast.length)
        detail = [_KIND_WORDS[kind]] if kind in _KIND_WORDS else []
        if cast.flags & fight_casts.INTERRUPTED:
            detail.append("interrupted")
        rows.append(ActionRow(cast.t, CASTS, _WHAT.get(kind, "Cast"),
                              name, icon, "", (), " · ".join(detail), False, None, name,
                              (SWAP_MARK if i in swapped else "") + (bar(cast.ability_id, name)
                                                                     if kind is None else ""),
                              LA_MARK if i in la else "", cast.target, length, gap, False))
    return rows


# ---------------------------------------------------------------- events --

def _event_row(row: Row, detail: str | None = None, muted: bool = False,
               category: str | None = None) -> ActionRow:
    action = f"{row.what}: {row.ability}" if row.ability else row.what
    return ActionRow(*row._replace(detail=row.detail if detail is None else detail,
                                   category=category or row.category),
                     action, "", "", "", "", "", muted)


def _hit_rows(records: list, key: str, abilities: dict, deaths: list) -> list:
    """The hits the player took of 30% of their maximum health or more,
    one source's with one ability chained as event_rows chains them, the
    killing hit left to the death's row."""
    hits = [r for r in records if r.kind == fe.HIT and r.who_key == key and r.value2]
    rows = []
    for group in event_rows._chain(hits, key=lambda r: (r.other, r.ability_id),
                                   window=event_rows.HIT_CHAIN_MS, span=event_rows.HIT_SPAN_MS):
        first = group[0]
        if len(group) == 1 and any(ability == first.ability_id
                                   and 0 <= died - first.t <= event_rows.KILLING_HIT_MS
                                   for died, ability in deaths):
            continue  # the killing hit: the death's row tells it
        name, icon = event_rows._ability(abilities, first.ability_id)
        shares = [round((r.value + r.value3) * 100 / r.value2) for r in group]
        if len(group) == 1:
            text = f"{shares[0]}% of max health"
            if first.value3:
                text += f", {first.value3:,} of it shielded"
        else:
            span = group[-1].t - first.t
            text = (f"{len(group)} hits" + (f" over {_seconds(span)}" if span >= 1000 else "")
                    + f", {min(shares)} to {max(shares)}% of max health")
        parts = [text]
        if first.other:
            parts.append(f"from {first.other}")
        shielded = sum(1 for r in group if r.value3)
        if len(group) > 1 and shielded:
            parts.append(f"{shielded} partly shielded")
        blocked = sum(1 for r in group if r.flags & fe.BLOCKED)
        if blocked:
            parts.append("blocked" if len(group) == 1 else f"{blocked} blocked")
        rows.append(_event_row(Row(first.t, "hits", "Hit",
                                   name + (f" x{len(group)}" if len(group) > 1 else ""), icon,
                                   first.who, (key,), " · ".join(parts), False, None)))
    return rows


def _boss_cast_rows(records: list, key: str, abilities: dict) -> list:
    """The bosses' casts aimed at the player, a burst of one ability one
    row (event_rows.BURST_MS), and whether one was stopped."""
    casts = [r for r in records if r.kind == fe.BOSS_CAST and r.other_key == key
             and r.other_key != r.who_key]
    stops = [r for r in records if r.kind == fe.CAST_STOPPED]
    rows = []
    for group in event_rows._chain(casts, key=lambda r: (r.who, event_rows._ability(
            abilities, r.ability_id)[0]), window=event_rows.BURST_MS):
        first = group[0]
        name, icon = event_rows._ability(abilities, first.ability_id)
        parts = [f"from {first.who}"]
        if len(group) > 1:
            parts.append(f"{len(group)} casts over {_seconds(group[-1].t - first.t)}")
        ids = {r.ability_id for r in group}
        stopped = [s for s in stops if s.who == first.who and s.ability_id in ids
                   and first.t <= s.t <= group[-1].t + event_rows.BURST_MS]
        if stopped:
            parts.append("stopped by its own script" if stopped[0].flags & fe.BY_ITSELF
                         else f"interrupted by {stopped[0].other}")
        rows.append(_event_row(Row(first.t, "boss", "Boss cast",
                                   name + (f" x{len(group)}" if len(group) > 1 else ""), icon,
                                   first.who, (), " · ".join(parts), False, None)))
    return rows


def _taunt_rows(records: list, key: str, abilities: dict) -> list:
    """The taunt swaps on a boss the player was in: theirs, or another
    player taking the boss from them (event_rows' rule)."""
    rows = []
    holder: dict[str, tuple[str, str]] = {}
    for r in records:
        if r.kind != fe.TAUNT or not r.flags & fe.ON_BOSS:
            continue
        last = holder.get(r.other)
        holder[r.other] = (r.who, r.who_key)
        if last is not None and last[1] == r.who_key:
            continue  # taunting again: no swap
        if key != r.who_key and (last is None or last[1] != key):
            continue
        name, icon = event_rows._ability(abilities, r.ability_id)
        detail = (f"{r.who} taunted {r.other} first" if last is None
                  else f"{r.who} took {r.other} from {last[0]}")
        rows.append(_event_row(Row(r.t, "taunts", "Taunt", name, icon, r.who,
                                   (r.who_key,) + ((last[1],) if last else ()), detail,
                                   False, None)))
    return rows


def _context_rows(records: list) -> list:
    rows = []
    for r in records:
        if r.kind == fe.BOSS_HEALTH:
            row = Row(r.t, CONTEXT, "Boss health", f"{r.value}%", "", r.who, (),
                      f"{r.who} at or under {r.value}%", False, None)
        elif r.kind == fe.UNTOUCHED:
            row = Row(r.t, CONTEXT, "Untouched", r.who, "", r.who, (),
                      f"lost no health for {_seconds(r.value)} "
                      f"({clock(r.t)} to {clock(r.t + r.value)})", False, None)
        elif r.kind == fe.MAP:
            row = Row(r.t, CONTEXT, "Map", r.other, "", "", (), "the map changed", False, None)
        elif r.kind == fe.BOSS_DIED:
            row = Row(r.t, CONTEXT, "Boss died", r.who, "", r.who, (), "killed", False, None)
        else:
            continue
        rows.append(_event_row(row, muted=True))
    return rows


def _death_rows(entry, records: list, key: str) -> tuple[list, list]:
    """(the rows of the player's deaths and returns, by event_rows' rules;
    their deaths as (time, killing ability id))."""
    recaps = [recap for recap in getattr(entry, "death_recaps", None) or []
              if str(recap.get("unit_id", "")) == key]
    mine = [r for r in records if r.kind in (fe.REVIVED, fe.RESURRECT) and r.who_key == key]
    view = _EntryView(recaps, getattr(entry, "duration_s", 0))
    rows = [_event_row(row) for row in event_rows._death_rows(view, mine)]
    return rows, [(recap.get("time_ms", 0), str(recap.get("ability_id", ""))) for recap in recaps]


class _EntryView:
    """The parts of an entry event_rows' death rules read, for one player."""

    def __init__(self, death_recaps, duration_s):
        self.death_recaps = death_recaps
        self.duration_s = duration_s


# --------------------------------------------------------- no cast for --

def dead_spans(entry, key: str, records: list) -> list[tuple[int, int]]:
    """When the player was dead, ms from the fight's start: from each death
    to their return after it, else to the fight's end; and from the start
    to the return of a player dead since an earlier pull."""
    end = round(float(getattr(entry, "duration_s", 0) or 0) * 1000)
    backs = sorted((r.t, r.value, bool(r.flags & fe.CARRIED)) for r in records
                   if r.kind == fe.REVIVED and r.who_key == key)
    spans = [(0, t) for t, _dead, carried in backs if carried]
    returns = [t for t, _dead, carried in backs if not carried]
    for recap in getattr(entry, "death_recaps", None) or []:
        if str(recap.get("unit_id", "")) != key:
            continue
        died = int(recap.get("time_ms", 0))
        back = next((t for t in returns if t >= died), None)
        spans.append((died, end if back is None else back))
    return sorted(spans)


def _cut(span: tuple[int, int], dead: list) -> list[tuple[int, int]]:
    pieces = [span]
    for low, high in dead:
        cut = []
        for start, end in pieces:
            if high <= start or low >= end:
                cut.append((start, end))
                continue
            if low > start:
                cut.append((start, low))
            if high < end:
                cut.append((high, end))
        pieces = cut
    return pieces


def idle_spans(entry, key: str, casts: list, records: list) -> list[tuple[int, int]]:
    """The stretches of IDLE_MS or more in which the player had no cast
    going on, alive (see the module), as (start, end) ms."""
    end = round(float(getattr(entry, "duration_s", 0) or 0) * 1000)
    gaps = []
    busy = 0  # the end of the casts so far: the fight's start before the first
    for cast in casts:
        if cast.t - busy >= IDLE_MS:
            gaps.append((busy, cast.t))
        busy = max(busy, cast.t + (cast.length if cast.flags & fight_casts.ENDED else 0))
    if end - busy >= IDLE_MS:
        gaps.append((busy, end))
    dead = dead_spans(entry, key, records)
    return [piece for gap in gaps for piece in _cut(gap, dead) if piece[1] - piece[0] >= IDLE_MS]


def _idle_rows(entry, key: str, casts: list, records: list) -> list:
    rows = []
    for start, end in idle_spans(entry, key, casts, records):
        reasons = []
        blocked = sum(1 for r in records if r.kind == fe.HIT and r.who_key == key
                      and r.flags & fe.BLOCKED and start <= r.t <= end)
        if blocked:
            reasons.append(f"{blocked} big hit{'s' if blocked > 1 else ''} blocked")
        for r in records:
            if r.kind == fe.UNTOUCHED and r.t < end and r.t + r.value > start:
                reasons.append(f"{r.who} lost no health from {clock(r.t)} to "
                               f"{clock(r.t + r.value)}")
            elif r.kind == fe.MAP and start <= r.t <= end:
                reasons.append(f"the map changed at {clock(r.t)}")
            elif r.kind == fe.RESUMED and start <= r.t <= end:
                reasons.append(f"the game ended combat and began it again at {clock(r.t)}")
        text = f"for {_seconds(end - start)}"
        rows.append(ActionRow(start, IDLE, "No cast", text, "", "", (), " · ".join(reasons),
                              False, None, f"No cast {text}", "", "", "", "", "", False))
    return rows


# ------------------------------------------------------------- the rows --

def action_rows(entry, key: str, light_rows: bool = False, swap_rows: bool = False) -> list:
    """The player *key*'s actions in *entry*, in time order (see the
    module): their casts, the events that touched them, the context rows,
    and for the player who writes the log, the stretches with no cast.
    *light_rows* and *swap_rows*: every light attack, every swap a row.
    [] for an entry built before the casts were kept."""
    if getattr(entry, "casts", None) is None:
        return []
    key = str(key)
    p = player_row(entry, key) or {}
    casts = entry.casts.of(key)
    abilities = entry.casts.abilities()
    rows = _cast_rows(casts, abilities, _bar_of(p, abilities), light_rows, swap_rows)
    events = getattr(entry, "events", None)
    records = list(events.records()) if events is not None else []
    event_abilities = events.abilities() if events is not None else {}
    deaths, died = _death_rows(entry, records, key)
    rows += (deaths + _hit_rows(records, key, event_abilities, died)
             + _boss_cast_rows(records, key, event_abilities)
             + _taunt_rows(records, key, event_abilities) + _context_rows(records))
    if p.get("is_local"):
        rows += _idle_rows(entry, key, casts, records)
    rows.sort(key=lambda row: (row.t, _RANK.get(row.category, 2)))
    return rows


def shown(rows: list, categories, context: bool = True) -> list:
    """The rows of *categories* (of EVENT_CATEGORIES) shown, every cast and
    stretch with no cast, and the context rows with *context*."""
    chosen = set(categories) | {CASTS, IDLE} | ({CONTEXT} if context else set())
    return [row for row in rows if row.category in chosen]


def summary_text(entry, key: str, names=None) -> str:
    """The line above the table: '@first · T · Sorcerer · 202 casts · 1
    death'."""
    p = player_row(entry, key) or {}
    name = player_name(p)
    if names is not None:
        name = names.text(name)
    deaths = sum(1 for recap in getattr(entry, "death_recaps", None) or []
                 if str(recap.get("unit_id", "")) == str(key))
    count = entry.casts.count(key) if getattr(entry, "casts", None) is not None else 0
    parts = [name, str(p.get("role") or ""), str(p.get("class_name") or ""),
             f"{count} cast{'s' if count != 1 else ''}",
             f"{deaths} death{'s' if deaths != 1 else ''}" if deaths else "no deaths"]
    return " · ".join(part for part in parts if part)
