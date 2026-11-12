"""
The Events tab's rows (issue #214): a fight's deaths, the bosses' casts and
health, the big hits on the group, the taunt swaps and the fight's phases,
one row per happening, in time order. Qt-free: the tab draws what this
gives (gui.events_tab).

Design: the Events tab's rows. The rules are the #214 study's, written as
code and measured on six fights (build/surveys/timeline-214-2026-11-11,
design/lists): 5.5 to 16.3 rows a minute by default, never more than 9 in
any ten seconds, so a fight reads as a story rather than a log.

- Deaths are the entry's own recaps (death_recaps), with the death the log
  wrote no line for said so. Deaths to one ability within DEATH_CHAIN_MS
  are one row ("Died x3"). Each return from the dead is a "Back" row with
  how long the player was down and who raised them: a resurrection line
  for the player at most RAISED_BEFORE_MS before the return, else "no line
  says how" (a release and run back writes none).
- A boss's casts of one ability, each within BURST_MS of the last, are one
  row ("Hemorrhage x12"), with whom they were aimed at and whether one was
  stopped: by a player ("interrupted by"), or by the boss's own script.
  Rows are keyed by names, not unit ids: a boss the game adds again as a
  new unit is the same boss to a reader.
- A boss's health marks (75, 50 and 25%), the stretches of UNTOUCHED_MS or
  more in which it lost no health, and its death.
- Big hits: BIG_HIT_SHARE of the player's maximum health or more, the part
  a damage shield absorbed and the overkill counted in. One source's hits
  with one ability, each within HIT_CHAIN_MS of the last and all within
  HIT_SPAN_MS, are one row. A lone hit on a player who died to it within
  KILLING_HIT_MS is left to the death's row.
- Taunt swaps: the first taunt on a boss, and a taunt by another player
  than the last one to taunt it. A player taunting again is no row.
- Phases: the map changing, the game ending combat and beginning it again
  in one fight, and a trial's end, at the fight's end.
"""

from collections import namedtuple

import fight_events as fe

# The categories, in the filter's order: the first five are shown at first,
# the rest are a click away (MORE)
CATEGORIES = (("deaths", "Deaths"), ("boss", "Boss"), ("hits", "Big hits"),
              ("taunts", "Taunt swaps"), ("phases", "Phases"),
              ("tank", "Boss casts at the tank"), ("auto", "Boss auto-attacks"),
              ("hits30", "Hits 30 to 49%"))
DEFAULT_CATEGORIES = ("deaths", "boss", "hits", "taunts", "phases")
MORE = tuple(key for key, _label in CATEGORIES if key not in DEFAULT_CATEGORIES)

DEATH_CHAIN_MS = 1000
RAISED_BEFORE_MS = 1500
BURST_MS = 3000
HIT_CHAIN_MS = 3000
HIT_SPAN_MS = 15000
KILLING_HIT_MS = 1000
BIG_HIT_SHARE = 0.50
# A taunt holds its boss this long (a taunt lasts 15 s)
TAUNT_HOLD_MS = 16000
# Rule C, a boss's auto-attack: an ability of a boss cast AUTO_MIN_CASTS
# times or more, at a player AUTO_AT_PLAYER of the time or more, its median
# cast AUTO_LENGTH_MS or shorter, AUTO_PER_MIN a minute or more, and fewer
# big hits than half its casts
AUTO_MIN_CASTS, AUTO_AT_PLAYER, AUTO_LENGTH_MS, AUTO_PER_MIN = 8, 0.9, 1000, 3

# t: ms from the fight's start; category; what (Died, Back, Boss cast, ...);
# ability and icon (stem); who (the text) and who_keys (the players' record
# ids it names, for the Hide names mask and links); detail; strong (a death
# or a boss's); death (the recap's (unit id, its number among the player's
# deaths) a death row opens, or None)
Row = namedtuple("Row", "t category what ability icon who who_keys detail strong death")


def clock(ms: int) -> str:
    """'1:50.6' (or '-0:03.2') from fight ms."""
    sign = "-" if ms < 0 else ""
    minutes, rest = divmod(abs(int(ms)), 60000)
    return f"{sign}{minutes}:{rest / 1000:04.1f}"


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.1f} s"


def _names(names: list, limit: int = 2) -> str:
    unique = list(dict.fromkeys(name for name in names if name))
    if len(unique) <= limit:
        return ", ".join(unique)
    return f"{len(unique)} players"


def _chain(items: list, key, window: int, span: int | None = None) -> list[list]:
    """Group *items* (in time order, each with .t or [0]) whose key matches,
    each within *window* ms of the group's last (and *span* of its first)."""
    open_groups: dict = {}
    groups = []
    for item in items:
        k = key(item)
        group = open_groups.get(k)
        t = item.t if hasattr(item, "t") else item["time_ms"]
        if group is not None:
            last = group[-1].t if hasattr(group[-1], "t") else group[-1]["time_ms"]
            first = group[0].t if hasattr(group[0], "t") else group[0]["time_ms"]
            if t - last <= window and (span is None or t - first <= span):
                group.append(item)
                continue
        group = [item]
        open_groups[k] = group
        groups.append(group)
    return groups


def event_rows(entry) -> list[Row]:
    """The entry's rows in time order; [] for an entry built before the
    events were recorded (FightHistoryEntry.events None)."""
    events = getattr(entry, "events", None)
    if events is None:
        return []
    records = list(events.records())
    abilities = events.abilities()
    rows = (_death_rows(entry, records) + _boss_rows(entry, records, abilities)
            + _hit_rows(entry, records, abilities) + _taunt_rows(records, abilities)
            + _phase_rows(entry, records))
    rows.sort(key=lambda row: row.t)
    return rows


def _ability(abilities: dict, ability_id: str) -> tuple[str, str]:
    return abilities.get(ability_id, (f"Ability {ability_id}" if ability_id else "", ""))


# ---------------------------------------------------------------- deaths --

def _death_rows(entry, records: list) -> list[Row]:
    rows = []
    recaps = list(getattr(entry, "death_recaps", None) or [])
    revived = [r for r in records if r.kind == fe.REVIVED]
    raised = [r for r in records if r.kind == fe.RESURRECT]
    # Each death's number among its player's deaths, for its recap
    numbers, seen = [], {}
    for recap in recaps:
        unit = str(recap.get("unit_id", ""))
        seen[unit] = seen.get(unit, 0) + 1
        numbers.append(seen[unit])
    deaths = [dict(recap, _number=number) for recap, number in zip(recaps, numbers)]
    for group in _chain(deaths, key=lambda d: d.get("ability") or ("?", d.get("unit_id")),
                        window=DEATH_CHAIN_MS):
        first = group[0]
        parts = []
        if first.get("killer"):
            parts.append(f"from {first['killer']}")
        if any(d.get("cause") == "health" for d in group):
            parts.append("no death line; read from health reaching 0")
        if len(group) == 1:
            back = next((r for r in revived if r.who_key == str(first.get("unit_id"))
                         and r.t >= first["time_ms"]), None)
            if back is None:
                end_ms = round(getattr(entry, "duration_s", 0) * 1000)
                parts.append(f"dead to the end ({_seconds(max(0, end_ms - first['time_ms']))})")
            else:
                parts.append(f"dead {_seconds(back.value)}, {_how_back(back, raised)} "
                             f"at {clock(back.t)}")
        else:
            span = group[-1]["time_ms"] - first["time_ms"]
            parts.append(f"{len(group)} deaths in {_seconds(span)}")
        rows.append(Row(first["time_ms"], "deaths", "Died" if len(group) == 1
                        else f"Died x{len(group)}", first.get("ability") or "(no cause logged)",
                        first.get("icon") or "", _names([d.get("name", "") for d in group]),
                        tuple(str(d.get("unit_id", "")) for d in group), " · ".join(parts), True,
                        (str(first.get("unit_id", "")), first["_number"])
                        if len(group) == 1 else None))
    for back in revived:
        rows.append(Row(back.t, "deaths", "Back", "", "", back.who, (back.who_key,),
                        f"{_how_back(back, raised)} · dead {_seconds(back.value)}", False, None))
    return rows


def _how_back(back, raised: list) -> str:
    """'resurrected by X', or that no line says how."""
    by = next((r for r in reversed(raised) if r.who_key == back.who_key
               and back.t - RAISED_BEFORE_MS <= r.t <= back.t + 500), None)
    if by is None:
        return "back, no line says how"
    if by.other_key == by.who_key or not by.other:
        return "raised themselves"
    return f"resurrected by {by.other}"


# ------------------------------------------------------------------ boss --

def _auto_attacks(entry, casts: list, hits: list, abilities: dict) -> set:
    """(boss, ability name) of each boss ability rule C calls an
    auto-attack (see AUTO_MIN_CASTS)."""
    by_name: dict[tuple, list] = {}
    for r in casts:
        by_name.setdefault((r.who, _ability(abilities, r.ability_id)[0]), []).append(r)
    big = {}
    for r in hits:
        key = (r.other, _ability(abilities, r.ability_id)[0])
        big[key] = big.get(key, 0) + 1
    minutes = max(getattr(entry, "duration_s", 0) / 60, 0.5)
    autos = set()
    for key, group in by_name.items():
        if len(group) < AUTO_MIN_CASTS:
            continue
        lengths = sorted(r.value for r in group)
        if (sum(1 for r in group if r.flags & fe.AT_PLAYER) >= AUTO_AT_PLAYER * len(group)
                and lengths[len(lengths) // 2] <= AUTO_LENGTH_MS
                and len(group) / minutes >= AUTO_PER_MIN and big.get(key, 0) < len(group) / 2):
            autos.add(key)
    return autos


def _holders(records: list) -> dict[str, list]:
    """Each boss's taunts by name, in time order: [(time, taunter key)]."""
    holders: dict[str, list] = {}
    for r in records:
        if r.kind == fe.TAUNT and r.flags & fe.ON_BOSS:
            holders.setdefault(r.other, []).append((r.t, r.who_key))
    return holders


def _holder_at(holders: dict, boss: str, t: int) -> str | None:
    """Who held taunt on *boss* at *t*: the last taunter in TAUNT_HOLD_MS."""
    held = None
    for at, key in holders.get(boss, ()):
        if at > t:
            break
        held = (at, key)
    return held[1] if held is not None and t - held[0] <= TAUNT_HOLD_MS else None


def _boss_rows(entry, records: list, abilities: dict) -> list[Row]:
    rows = []
    casts = [r for r in records if r.kind == fe.BOSS_CAST]
    stops = [r for r in records if r.kind == fe.CAST_STOPPED]
    hits = [r for r in records if r.kind == fe.HIT]
    autos = _auto_attacks(entry, casts, hits, abilities)
    holders = _holders(records)
    for group in _chain(casts, key=lambda r: (r.who, _ability(abilities, r.ability_id)[0]),
                        window=BURST_MS):
        first = group[0]
        name, icon = _ability(abilities, first.ability_id)
        aimed = {r.other_key for r in group if r.other_key and r.other_key != r.who_key}
        category = "boss"
        if (first.who, name) in autos:
            category = "auto"
        elif aimed and aimed == {_holder_at(holders, first.who, first.t)}:
            # Aimed at the player holding taunt, and at no one else
            category = "tank"
        parts = []
        if len(group) > 1:
            parts.append(f"{len(group)} casts over {_seconds(group[-1].t - first.t)}")
        targets = [r.other for r in group if r.other and r.other_key != r.who_key]
        if targets:
            parts.append("at " + _names(targets))
        stopped = [s for s in stops if s.who == first.who and s.ability_id in
                   {r.ability_id for r in group} and first.t <= s.t <= group[-1].t + BURST_MS]
        if stopped:
            parts.append("stopped by its own script" if stopped[0].flags & fe.BY_ITSELF
                         else f"interrupted by {stopped[0].other}")
        rows.append(Row(first.t, category, "Boss cast",
                        name + (f" x{len(group)}" if len(group) > 1 else ""), icon, first.who,
                        (), " · ".join(parts), False, None))
    for r in records:
        if r.kind == fe.BOSS_HEALTH:
            rows.append(Row(r.t, "boss", "Boss health", f"{r.value}%", "", r.who, (),
                            f"{r.who} at or under {r.value}%", False, None))
        elif r.kind == fe.UNTOUCHED:
            rows.append(Row(r.t, "boss", "Untouched", "", "", r.who, (),
                            f"lost no health for {_seconds(r.value)} "
                            f"({clock(r.t)} to {clock(r.t + r.value)})", False, None))
        elif r.kind == fe.BOSS_DIED:
            rows.append(Row(r.t, "boss", "Boss died", "", "", r.who, (), "killed", True, None))
    return rows


# ------------------------------------------------------------------ hits --

def _hit_rows(entry, records: list, abilities: dict) -> list[Row]:
    """The big hits (category 'hits'), and those of 30 to 49% of max
    health ('hits30', which fight_events keeps from 30% on)."""
    deaths = [(str(d.get("unit_id", "")), d.get("time_ms", 0), str(d.get("ability_id", "")))
              for d in getattr(entry, "death_recaps", None) or []]
    hits = [r for r in records if r.kind == fe.HIT and r.value2]
    big = [r for r in hits if (r.value + r.value3) >= BIG_HIT_SHARE * r.value2]
    smaller = [r for r in hits if (r.value + r.value3) < BIG_HIT_SHARE * r.value2]
    return (_hit_group_rows(big, "hits", deaths, abilities)
            + _hit_group_rows(smaller, "hits30", deaths, abilities))


def _hit_group_rows(hits: list, category: str, deaths: list, abilities: dict) -> list[Row]:
    rows = []
    for group in _chain(hits, key=lambda r: (r.other, r.ability_id), window=HIT_CHAIN_MS,
                        span=HIT_SPAN_MS):
        first = group[0]
        if len(group) == 1 and any(unit == first.who_key and ability == first.ability_id
                                   and 0 <= died - first.t <= KILLING_HIT_MS
                                   for unit, died, ability in deaths):
            continue  # the killing hit: the death's row tells it
        name, icon = _ability(abilities, first.ability_id)
        shares = [round((r.value + r.value3) * 100 / r.value2) for r in group]
        players = list(dict.fromkeys(r.who for r in group))
        if len(group) == 1:
            text = f"{shares[0]}% of max health"
            if first.value3:
                text += f", {first.value3:,} of it shielded"
            parts = [text]
        else:
            span = group[-1].t - first.t
            parts = [f"{len(group)} hits on {len(players)} player{'s' if len(players) > 1 else ''}"
                     + (f" over {_seconds(span)}" if span >= 1000 else "")
                     + f", {min(shares)} to {max(shares)}% of max health"]
        if first.other:
            parts.append(f"from {first.other}")
        shielded = sum(1 for r in group if r.value3)
        if len(group) > 1 and shielded:
            parts.append(f"{shielded} partly shielded")
        blocked = sum(1 for r in group if r.flags & fe.BLOCKED)
        if blocked:
            parts.append("blocked" if len(group) == 1 else f"{blocked} blocked")
        rows.append(Row(first.t, category, "Hit", name + (f" x{len(group)}" if len(group) > 1 else ""),
                        icon, _names(players), tuple(dict.fromkeys(r.who_key for r in group)),
                        " · ".join(parts), False, None))
    return rows


# ---------------------------------------------------------------- taunts --

def _taunt_rows(records: list, abilities: dict) -> list[Row]:
    rows = []
    holder: dict[str, tuple[str, str]] = {}
    for r in records:
        if r.kind != fe.TAUNT or not r.flags & fe.ON_BOSS:
            continue
        name, icon = _ability(abilities, r.ability_id)
        last = holder.get(r.other)
        holder[r.other] = (r.who, r.who_key)
        if last is None:
            rows.append(Row(r.t, "taunts", "Taunt", name, icon, r.who, (r.who_key,),
                            f"first taunt on {r.other}", False, None))
        elif last[1] != r.who_key:
            rows.append(Row(r.t, "taunts", "Taunt", name, icon, r.who, (r.who_key, last[1]),
                            f"took {r.other} from {last[0]}", False, None))
    return rows


# ---------------------------------------------------------------- phases --

def _phase_rows(entry, records: list) -> list[Row]:
    rows = []
    for r in records:
        if r.kind == fe.MAP:
            rows.append(Row(r.t, "phases", "Map", r.other, "", "", (),
                            "positions are on this map from here", False, None))
        elif r.kind == fe.RESUMED:
            rows.append(Row(r.t, "phases", "Combat", "resumed", "", "", (),
                            f"the game ended combat and began it again {r.value} ms later; "
                            "one fight", False, None))
    if getattr(entry, "trial_result", None):
        rows.append(Row(round(getattr(entry, "duration_s", 0) * 1000), "phases", "Trial",
                        "ended", "", "", (), "the trial's end line (END_TRIAL)", False, None))
    return rows


def shown(rows: list[Row], categories) -> list[Row]:
    """The rows of the *categories* chosen."""
    chosen = set(categories)
    return [row for row in rows if row.category in chosen]
