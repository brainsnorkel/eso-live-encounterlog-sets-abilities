"""
Pull outcome: whether a boss fight was a kill or a wipe, the boss's health
when it ended, each player's time dead, and a boss's pulls in a row
(issues #168 and #169; engine side and plain text, no Qt).

Design: the log writes no verdict, so a fight's ending is read from what
the log shows of the boss and the group. The log shows what happened
around the player writing it, and an ending that player did not see must
never be called a wipe: ESO Logs sometimes calls a kill a wipe (the
maintainer's warning, 2026-11-01), and so did the first versions of these
rules. Each rule below was checked against what the group did next, the
same boss again or the next boss, on the split logs of January to October
2026 (378 sessions once byte-identical copies are dropped). Replayed
through the engine they hold 2,362 fights with a pull: 1,548 kills, 708
wipes, 40 lost sight and 66 left. Of the non-kills, 736 were followed by
another pull of the same boss; 18 were never pulled again while another
boss came after, and none of those reads as a missed kill: Infinite
Archive runs that ended, a Turlassil wipe with all twelve dead, Cloudrest's
shades, and a few seconds-long scripted starts.

- **The boss** is the named unit the game flags as a boss (less the units
  boss_units demotes) that took the most of the players' damage. Unnamed
  boss-flagged units, a mechanic's helpers, took more in 143 fights and
  never decide. The pull's bosses are that unit and every other named
  boss unit with BOSS_SHARE or more of the boss damage, so encounters whose
  top unit alternates from pull to pull (Lylanar and Turlassil, Positrox
  and Negatrix, Reactor and Reducer) stay one encounter: grouped by the
  top unit alone, 50 wipes looked like a group moving on to another boss,
  grouped by shared bosses 25, every one of them a real wipe (arena and
  Infinite Archive runs that ended, gauntlet resets, nights that gave up).
- **Kill**: the boss's death line (DIED, or DIED_XP, which in 13 fights
  carried the only 0 health a health-only rule would have missed), a line
  showing it at 0 health, the run's END_TRIAL inside the fight, or its
  health under LOW_HEALTH_KILL_PCT at its last line with fewer than half
  the group dead when the fight ended. That last test caught 5 fights
  whose death line never reached the log (Tremorscale at 0.2%, Eliam
  Merick at 0.1%): none was pulled again, and 4 were followed by the next
  boss. A kill with half the group dead is still a kill: 174 fights.
- **Wipe**: not a kill, and at least half the fight's players were dead
  when it ended, not revived before END_COMBAT. "Half the group died at
  some point" is the wrong test: in a long fight with resurrections every
  player can die once while the group goes on to kill the boss.
- **Lost sight** (UNSEEN): neither, and the logging player was dead when
  the fight ended. BEGIN_COMBAT and END_COMBAT follow that player's own
  combat state, so their death ends the log's fight (a median 9 s later)
  whatever the group does next. "group went on" is added when a later
  pull in the instance is of another boss and this one never returns,
  which is the log's only trace of a kill it did not see. It is said of
  Lost sight only: a wipe or a reset followed by the next boss is a group
  that gave up on that boss, not one that killed it out of sight.
- **Left**: none of these; the group reset or walked away.
- **A late verdict**: a death logged just after END_COMBAT
  (LATE_DEATH_GRACE_MS) and an END_TRIAL logged after the fight was sent
  (an arena's, about 4 s later) change the sent pull, and the engine sends
  the fight again.

A first version also called a pull a wipe when another boss unit with 10%
of the damage was left standing with half the group dead (twin bosses):
of the 20 fights that turned into wipes, 15 were never pulled again and
the group went on to the next boss (the unit left was a helper or
Archwizard Twelvane at 0%), so the rule was dropped; 3 real twin wipes now
read as kills, and the next pull of the pair shows the group still at it.

Time dead: a player's DIED, KILLING_BLOW or KILLED_BY_SUBZONE (a fall,
issue #184) opens a span; the next line that carries their state with
health above 0 closes it, at least
REVIVE_MIN_MS after the death, since the lines of the killing blow carry
the corpse's 0. END_COMBAT closes any span still open, and those still
open are the players dead when the fight ended. A fight the game cut in
two (COMBAT_RESUME_MS) reopens them. A span starts at the fight's start
at the earliest: a player who fell before the pull is dead from it, not
from the fall. Deaths the log never saw (the others' after the logging
player released) are missing from the counts, so time dead, read from
each player's own states, is the fairer measure of who spent the fight
on the floor.

A pull the log cut in two: when the logging player dies the fight ends
for the log, and when they are revived a new one begins on a boss still
part way down. A fight that begins within CONTINUE_GAP_S of the last
pull's end, on a boss that pull shared, with that boss's health under
CONTINUE_MAX_PCT and within CONTINUE_DRIFT_PCT of where the last pull left
it, ``continues`` that pull: the fights stay two entries with their own
figures (the dps stays Combat Metrics' per fight), and the pull count
takes them as one. The earlier fight reads "Cut". The players still dead
when the earlier fight ended stay dead into the later one until a line
shows them up (TimeDead.carried), so a wipe that spans the cut is still
a wipe; a fight that does not continue the last pull ignores them, since
after a wipe the dead release and run back unseen.

Pulls in a row: the pulls of one block (gui.fight_list: one instance)
that share a boss, with fights without a boss between them, form a run
until a kill. A run of two or more pulls gets a summary row: the pulls,
the kill or the best pull, the wipes that keep ending in one band of
WALL_BAND_PCT (WALL_MIN_WIPES or more, half of them in the band), and the
median time between pulls; its hover adds the first death of each pull,
the killers over the run and the players who spent longest dead.
"""

from collections import Counter
from itertools import pairwise
from statistics import median

KILL, WIPE, LEFT, UNSEEN = "kill", "wipe", "left", "unseen"

# Another named boss unit with this share of the boss damage is one of
# the pull's bosses
BOSS_SHARE = 0.10
# A boss under this much health at its last line, the group standing, died
# out of the log's sight
LOW_HEALTH_KILL_PCT = 2.0
# A state with health this soon after a death is the dying line's own
REVIVE_MIN_MS = 1000
# A fight that carries on the last pull (see the module)
CONTINUE_GAP_S = 60.0
CONTINUE_MAX_PCT = 97.0
CONTINUE_DRIFT_PCT = 5.0
# A player's time dead shows on their row from this share of the fight
DEAD_ROW_SHARE = 0.10
# Wipes that keep ending in one band of health
WALL_MIN_WIPES = 4
WALL_BAND_PCT = 10
# Lines in the run's hover lists
TOP = 3
# A second boss names the run with the first when it was the top unit in
# this share of the run's pulls
RUN_NAME_SHARE = 0.25

WORDS = {KILL: "Kill", WIPE: "Wipe", LEFT: "Left", UNSEEN: "Lost sight"}
ANON = "anon"  # the engine's name for a player the log gives no name
CUT_WORD = "Cut"
WENT_ON = "group went on"


# ------------------------------------------------------------- engine --

def health_of(field) -> tuple[int, int] | None:
    """(current, max) from a unit state's 'current/max' health; None when
    the field is not one or the maximum is 0."""
    current, _, maximum = str(field).partition("/")
    try:
        current, maximum = int(current), int(maximum)
    except ValueError:
        return None
    return (current, maximum) if maximum > 0 else None


def pct(health) -> float | None:
    """A (current, max) pair as a percentage; None for none."""
    if not health:
        return None
    return 100.0 * health[0] / health[1]


def has_health(field) -> bool:
    """Whether a unit state's health field is above 0."""
    health = health_of(field)
    return health is not None and health[0] > 0


class BossHealth:
    """The bosses' health in one fight: per unit the first and the last
    'current/max' field a line carried, kept as written and read once
    when the pull is built (most of a boss fight's lines carry the boss,
    so the per-line work is two dict writes)."""

    __slots__ = ("first", "last")

    def __init__(self):
        self.first: dict[str, str] = {}
        self.last: dict[str, str] = {}

    def note(self, unit_id: str, field: str) -> None:
        if unit_id not in self.first:
            self.first[unit_id] = field
        self.last[unit_id] = field

    def first_of(self, unit_id: str) -> tuple[int, int] | None:
        return health_of(self.first[unit_id]) if unit_id in self.first else None

    def last_of(self, unit_id: str) -> tuple[int, int] | None:
        return health_of(self.last[unit_id]) if unit_id in self.last else None


class TimeDead:
    """Each player's time dead in one fight (see the module), keyed by the
    player's record id. A span is counted from the fight's start at the
    earliest: a player who fell before the pull is dead from its start.

    Players still dead when the last fight ended are carried into this
    one (carry): they stay down until a line shows them with health. Their
    time and their being dead at the end count only when this fight turns
    out to carry on the last pull (pull_outcome.continues); after a wipe
    the dead release and run back, and the log seldom shows them before
    the next pull."""

    __slots__ = ("_ended", "_paused", "_paused_carried", "at_end", "carried", "carried_at_end",
                 "carried_ms", "ms", "since", "start")

    def __init__(self):
        self.start = 0  # the fight's start, set at BEGIN_COMBAT
        self.since: dict[str, tuple[int, int]] = {}  # key -> (span start, death)
        self.ms: dict[str, int] = {}
        self.at_end: frozenset | None = None  # dead when the fight ended
        self.carried: dict[str, int] = {}  # key -> when the carried span began
        self.carried_ms: dict[str, int] = {}
        self.carried_at_end: frozenset = frozenset()
        self._ended = 0
        self._paused: dict[str, tuple[int, int]] = {}
        self._paused_carried: dict[str, int] = {}

    def begin(self, start_ms: int, carried=()) -> None:
        """BEGIN_COMBAT: the fight's start, and the players still dead
        when the last fight ended. The encounter a zone change made is
        used for the zone's first fight, so a death before the pull is
        already here: its span starts at the fight's start, and time dead
        before the pull is dropped."""
        self.start = start_ms
        self.since = {key: (max(start, start_ms), death)
                      for key, (start, death) in self.since.items()}
        self.ms.clear()
        self.carried_ms.clear()
        for key in carried:
            if key not in self.since:
                self.carried.setdefault(key, start_ms)

    def died(self, key: str, timestamp_ms: int) -> None:
        self.carried.pop(key, None)
        if key not in self.since:
            self.since[key] = (max(timestamp_ms, self.start), timestamp_ms)

    def alive(self, key: str, timestamp_ms: int) -> None:
        began = self.carried.pop(key, None)
        if began is not None:
            self.carried_ms[key] = self.carried_ms.get(key, 0) + max(0, timestamp_ms - began)
        span = self.since.get(key)
        if span is None or timestamp_ms - span[1] < REVIVE_MIN_MS:
            return
        del self.since[key]
        self.ms[key] = self.ms.get(key, 0) + max(0, timestamp_ms - span[0])

    def watching(self) -> bool:
        """Whether any player is down (a line with their health matters)."""
        return bool(self.since or self.carried)

    def watches(self, key: str) -> bool:
        return key in self.since or key in self.carried

    def end(self, timestamp_ms: int) -> None:
        """END_COMBAT: close every span; those were dead at the end."""
        self.at_end = frozenset(self.since)
        for key, (start, _death) in self.since.items():
            self.ms[key] = self.ms.get(key, 0) + max(0, timestamp_ms - start)
        self.carried_at_end = frozenset(self.carried)
        for key, began in self.carried.items():
            self.carried_ms[key] = self.carried_ms.get(key, 0) + max(0, timestamp_ms - began)
        self._ended = timestamp_ms
        self._paused = dict(self.since)
        self._paused_carried = dict(self.carried)
        self.since.clear()
        self.carried.clear()

    def late_death(self, key: str, timestamp_ms: int) -> None:
        """A death logged just after END_COMBAT (LATE_DEATH_GRACE_MS): dead
        at the end, and still dead should the fight carry on."""
        self.at_end = (self.at_end or frozenset()) | {key}
        self._paused.setdefault(key, (timestamp_ms, timestamp_ms))

    def resume(self) -> None:
        """The fight carries on (COMBAT_RESUME_MS): reopen, from the end,
        the spans the end closed."""
        for key, (_start, death) in self._paused.items():
            self.since[key] = (self._ended, death)
        for key, began in self._paused_carried.items():
            self.carried_ms[key] = self.carried_ms.get(key, 0) - max(0, self._ended - began)
            self.carried[key] = began
        self._paused = {}
        self._paused_carried = {}
        self.at_end = None
        self.carried_at_end = frozenset()

    def dead_at_end(self) -> frozenset:
        return self.at_end if self.at_end is not None else frozenset(self.since)

    def totals(self, end_ms: int, carried: bool = False) -> dict[str, int]:
        """Milliseconds dead per player, spans still open counted to
        *end_ms*; with *carried*, the carried players' time too."""
        out = dict(self.ms)
        for key, (start, _death) in self.since.items():
            out[key] = out.get(key, 0) + max(0, end_ms - start)
        if carried:
            for key, ms in self.carried_ms.items():
                out[key] = out.get(key, 0) + ms
            for key, began in self.carried.items():
                out[key] = out.get(key, 0) + max(0, end_ms - began)
        return {key: ms for key, ms in out.items() if ms > 0}


def verdict(pull: dict) -> str:
    """KILL, WIPE, UNSEEN or LEFT from a pull record's facts (see the
    module)."""
    dead = len(pull.get("dead_at_end") or ())
    half = dead >= 1 and dead * 2 >= max(int(pull.get("players") or 0), 1)
    left = pull.get("health_left")
    if pull.get("boss_died") or (left is not None and left < LOW_HEALTH_KILL_PCT and not half):
        return KILL
    if half:
        return WIPE
    if pull.get("local_dead_at_end"):
        return UNSEEN
    return LEFT


def pull_record(bosses, health: BossHealth, trial_done: bool, players: int,
                dead_at_end, local_dead_at_end: bool, start_s=None, end_s=None,
                zone: str = "") -> dict | None:
    """The fight's pull, or None in a fight without a named boss the
    players damaged. *bosses*: (unit id, name, damage, died) per boss unit
    the players damaged, died meaning a death line in the fight."""
    named = [b for b in bosses if b[1] and b[2] > 0]
    if not named:
        return None
    named.sort(key=lambda b: -b[2])
    total = sum(b[2] for b in bosses if b[2] > 0)
    main_id, main_name, _damage, main_died = named[0]
    pull_bosses, by_name = [], {}
    for unit_id, name, damage, _died in named:
        if unit_id != main_id and damage < BOSS_SHARE * total:
            continue
        if name not in by_name:
            pull_bosses.append(name)
            by_name[name] = [pct(health.first_of(unit_id)), pct(health.last_of(unit_id))]
    last = health.last_of(main_id)
    record = {
        "boss": main_name,
        "bosses": pull_bosses,
        "health_start": pct(health.first_of(main_id)),
        "health_left": pct(last),
        "health": by_name,
        "boss_died": bool(main_died or trial_done or (last is not None and last[0] == 0)),
        "players": int(players),
        "dead_at_end": sorted(str(key) for key in dead_at_end),
        "local_dead_at_end": bool(local_dead_at_end),
        "start_s": start_s,
        "end_s": end_s,
        "zone": zone,
        "continues": False,
        # Set from the fights after it (mark_context): the next fight
        # carries this one on; a Lost sight pull whose boss never came back
        # while another was pulled
        "cut": False,
        "went_on": False,
    }
    record["outcome"] = verdict(record)
    return record


def continues(previous: dict | None, pull: dict | None) -> bool:
    """Whether *pull* carries on *previous*, the last pull (see the
    module)."""
    if not previous or not pull or previous.get("outcome") == KILL:
        return False
    if previous.get("zone") != pull.get("zone"):
        return False
    gap = None
    if previous.get("end_s") is not None and pull.get("start_s") is not None:
        gap = pull["start_s"] - previous["end_s"]
    if gap is None or not 0 <= gap <= CONTINUE_GAP_S:
        return False
    for name, (start, _left) in (pull.get("health") or {}).items():
        before = (previous.get("health") or {}).get(name)
        if before is None or start is None or before[1] is None:
            continue
        if start < CONTINUE_MAX_PCT and abs(start - before[1]) <= CONTINUE_DRIFT_PCT:
            return True
    return False


def note_late_death(pull: dict | None, key: str, local: bool) -> None:
    """A death logged just after END_COMBAT (LATE_DEATH_GRACE_MS): the
    player was dead at the end, which can turn the verdict."""
    if not pull:
        return
    if str(key) not in pull["dead_at_end"]:
        pull["dead_at_end"] = sorted(pull["dead_at_end"] + [str(key)])
    if local:
        pull["local_dead_at_end"] = True
    pull["outcome"] = verdict(pull)


def note_trial_end(pull: dict | None) -> None:
    """The run's END_TRIAL, logged after the fight that completed it was
    sent (an arena's, about 4 s later): that fight's boss died."""
    if not pull:
        return
    pull["boss_died"] = True
    pull["outcome"] = verdict(pull)


def carry_dead(pull: dict | None, keys) -> None:
    """The players carried into a fight that turned out to continue the
    last pull, still down when it ended (TimeDead.carried_at_end)."""
    if not pull or not keys:
        return
    pull["dead_at_end"] = sorted(set(pull["dead_at_end"]) | {str(key) for key in keys})
    pull["outcome"] = verdict(pull)


def mark_context(entries) -> list:
    """Set each pull's 'cut' and 'went_on' from the fights after it in
    one instance (*entries*, in order; see the module): cut for a fight
    the next fight of its pull carries on, went_on for the last fight of a
    Lost sight pull when a later pull is of another boss and none of this
    one. Returns the entries whose flags changed."""
    changed = []
    all_pulls = pulls(entries)
    for index, pull in enumerate(all_pulls):
        later = [_pull_of(p[0]) for p in all_pulls[index + 1:]]
        for position, fight in enumerate(pull):
            record = _pull_of(fight)
            cut = position < len(pull) - 1
            went_on = (not cut and record.get("outcome") == UNSEEN and bool(later)
                       and not any(_shares_boss(record, other) for other in later))
            if bool(record.get("cut")) != cut or bool(record.get("went_on")) != went_on:
                changed.append(fight)
            record["cut"], record["went_on"] = cut, went_on
    return changed


# --------------------------------------------------------------- text --

def health_text(value) -> str:
    """'62%', '8.1%', '0.04%'; '' for none."""
    if value is None:
        return ""
    if value < 1:
        return f"{value:.2f}%"
    if value < 10:
        return f"{value:.1f}%"
    return f"{value:.0f}%"


def clock(seconds) -> str:
    """A span: '48s', '1:12' (rounded), as the fight list writes a fight's
    duration (fight_render's _fmt_duration is this)."""
    whole = max(0, round(float(seconds or 0)))
    return f"{whole}s" if whole < 60 else f"{whole // 60}:{whole % 60:02d}"


def dps_text(dps) -> str:
    """A dps figure: '1.50M', '61.8k', '950' (fight_render's _fmt_dps is
    this, so the pane, Copy fight and the session recap agree)."""
    dps = float(dps or 0)
    if dps >= 1_000_000:
        return f"{dps / 1_000_000:.2f}M"
    if dps >= 1_000:
        return f"{dps / 1_000:.1f}k"
    return f"{dps:.0f}"


def mmss(seconds) -> str:
    """A time into a fight: '1:38' (whole seconds, cut down), as the death
    recap writes it (fight_render's _clock_s and death_render's _clock are
    this)."""
    whole = max(0, int(seconds or 0))
    return f"{whole // 60}:{whole % 60:02d}"


def at_clock(ms) -> str:
    """mmss from milliseconds into the fight: '1:42'."""
    return mmss(max(0, int(ms or 0)) // 1000)


def outcome_text(pull: dict | None, title: str = "") -> str:
    """'Kill', 'Wipe 62%', 'Left 84%', 'Lost sight 31%, group went on',
    'Cut 63%' for a fight the next one carries on (the pull's 'cut' and
    'went_on', mark_context); '' without a pull. The boss is named when it
    is not the row's *title* (another unit took more damage than it)."""
    if not pull:
        return ""
    outcome = pull.get("outcome")
    if outcome == KILL:
        word = WORDS[KILL]
        boss = pull.get("boss") or ""
        return f"{word} ({boss})" if title and boss and boss != title else word
    cut = bool(pull.get("cut"))
    word = CUT_WORD if cut else WORDS.get(outcome, "")
    health = health_text(pull.get("health_left"))
    boss = pull.get("boss") or ""
    if title and boss and boss != title:
        text = f"{word}, {boss} {health}".rstrip()
    else:
        text = f"{word} {health}".rstrip()
    if pull.get("went_on") and not cut:
        text += f", {WENT_ON}"
    return text


def _pull_of(entry):
    return getattr(entry, "pull", None)


def _shares_boss(a: dict, b: dict) -> bool:
    return bool(set(a.get("bosses") or [a.get("boss")]) & set(b.get("bosses") or [b.get("boss")]))


def pulls(entries) -> list:
    """The pulls among *entries*, in order: each the list of fights that
    make it (a pull the log cut in two is two fights)."""
    out = []
    for entry in entries:
        pull = _pull_of(entry)
        if not pull:
            continue
        if pull.get("continues") and out and _shares_boss(_pull_of(out[-1][-1]), pull):
            out[-1].append(entry)
        else:
            out.append([entry])
    return out


def runs(entries) -> list:
    """Pulls in a row on one encounter: lists of pulls (see pulls), a new
    run at a pull that shares no boss with the last, and after a kill."""
    out = []
    for pull in pulls(entries):
        first = _pull_of(pull[0])
        if out:
            last = _pull_of(out[-1][-1][-1])
            if last.get("outcome") != KILL and _shares_boss(last, first):
                out[-1].append(pull)
                continue
        out.append([pull])
    return out


def run_name(run) -> str:
    """The run's boss: its pulls' top boss, and the second most frequent
    joined to it ('Lylanar and Turlassil') only when it was the top in
    RUN_NAME_SHARE of the pulls or more: an add on top once in a long
    run does not name it."""
    counts = Counter(_pull_of(pull[-1]).get("boss") for pull in run)
    common = [(name, n) for name, n in counts.most_common(2) if name]
    if not common:
        return "Boss"
    names = [common[0][0]]
    if len(common) > 1 and common[1][1] >= RUN_NAME_SHARE * len(run):
        names.append(common[1][0])
    return " and ".join(names)


def _fight_entries(run) -> list:
    return [fight for pull in run for fight in pull]


def run_summary(run) -> str:
    """'Lord Falgravn: 13 pulls, best 48%, 9 wipes at 80 to 90%, 48s
    between pulls'; 'Captain Vrol: 2 pulls, killed on pull 2, ...'."""
    count = len(run)
    parts = [f"{count} pull{'s' if count != 1 else ''}"]
    finals = [_pull_of(pull[-1]) for pull in run]
    last = finals[-1]
    if last.get("outcome") == KILL:
        parts.append(f"killed on pull {count}")
    else:
        healths = [p.get("health_left") for p in finals if p.get("health_left") is not None]
        if healths:
            parts.append(f"best {health_text(min(healths))}")
        if last.get("outcome") == UNSEEN and last.get("went_on"):
            parts.append(f"lost sight on pull {count}, {WENT_ON}")
    wipes = [p.get("health_left") for p in finals
             if p.get("outcome") == WIPE and p.get("health_left") is not None]
    if len(wipes) >= WALL_MIN_WIPES:
        band, inside = Counter(min(int(h // WALL_BAND_PCT), 100 // WALL_BAND_PCT - 1)
                               for h in wipes).most_common(1)[0]
        if inside * 2 >= len(wipes):
            low = band * WALL_BAND_PCT
            parts.append(f"{inside} wipes at {low} to {low + WALL_BAND_PCT}%")
    gaps = []
    for before, after in pairwise(run):
        end, start = _pull_of(before[-1]).get("end_s"), _pull_of(after[0]).get("start_s")
        if end is not None and start is not None and 0 <= start - end <= 3600:
            gaps.append(start - end)
    if gaps:
        parts.append(f"{clock(median(gaps))} between pulls")
    return f"{run_name(run)}: " + ", ".join(parts)


def _death_label(recap: dict, bosses, names) -> str:
    """'Grievous Pulse', or 'Sanguine Grasp (Lieutenant Njordal)' when the
    killer is not one of the run's bosses; a player killer is masked."""
    ability = str(recap.get("ability") or "unknown")
    killer = str(recap.get("killer") or "")
    if not killer or killer in bosses:
        return ability
    return f"{ability} ({names.text(killer) if names is not None else killer})"


def _counted(counter: Counter) -> str:
    return ", ".join(f"{label} {n}" for label, n in counter.most_common(TOP))


def run_details(run, names=None) -> list:
    """The run's hover lines under its summary: the first death of each
    pull, the killers over every death of the run and the share by its
    bosses, and the players who spent longest dead (*names*: the Hide
    names mask; None keeps every name)."""
    bosses = set()
    for pull in run:
        for fight in pull:
            bosses.update(_pull_of(fight).get("bosses") or [])
    lines = []
    firsts = Counter()
    for pull in run:
        # The pull's first death: in its first fight with one (a pull the
        # log cut in two is in order), the earliest
        for fight in pull:
            fight_recaps = getattr(fight, "death_recaps", None) or []
            if fight_recaps:
                first = min(fight_recaps, key=lambda r: int(r.get("time_ms") or 0))
                firsts[_death_label(first, bosses, names)] += 1
                break
    if firsts:
        lines.append(f"First deaths: {_counted(firsts)}")
    killers = Counter()
    by_boss = total = 0
    for fight in _fight_entries(run):
        for recap in getattr(fight, "death_recaps", None) or []:
            killers[_death_label(recap, bosses, names)] += 1
            total += 1
            if str(recap.get("killer") or "") in bosses:
                by_boss += 1
    if killers:
        line = f"Killers: {_counted(killers)}"
        if by_boss:
            line += f"; {100 * by_boss / total:.0f}% by {run_name(run)}"
        lines.append(line)
    dead, labels = Counter(), {}
    for fight in _fight_entries(run):
        who = {str(r.get("unit_id", "")): str(r.get("name") or "") for r in
               (getattr(fight, "death_recaps", None) or [])}
        rows = {str(p.get("unit_id", "")): p for p in (getattr(fight, "players", None) or [])}
        for key, ms in (getattr(fight, "time_dead", None) or {}).items():
            name = who.get(str(key))
            if not name:
                continue
            if name == ANON:
                # Players with no name in the log each keep their own
                # entry, told apart by their row's role and class
                row = rows.get(str(key))
                ident, label = (ANON, str(key)), ANON
                if row:
                    label = f"{ANON} ({row.get('role') or '?'}, {row.get('class_abbr') or '?'})"
            else:
                ident = label = name
            dead[ident] += int(ms)
            labels[ident] = label
    if dead:
        lines.append("Most time dead: " + ", ".join(
            f"{names.text(labels[ident]) if names is not None else labels[ident]} {clock(ms / 1000)}"
            for ident, ms in dead.most_common(TOP)))
    return lines


NAME = "name"  # a part of a line that is a name the Hide names mask may hide


def first_death_parts(entry) -> list:
    """The first-death line as parts: strings, and (NAME, name) for the
    player and the killer, which a frontend passes through its Hide names
    mask (a killer is an enemy, which the mask keeps, or a player). []
    for a fight without a death. See first_death_text."""
    recaps = getattr(entry, "death_recaps", None) or []
    if not recaps:
        return []
    first = min(recaps, key=lambda r: int(r.get("time_ms") or 0))
    parts = ["First death: ", (NAME, str(first.get("name") or "unknown")),
             f" to {first.get('ability') or 'unknown'}"]
    killer = str(first.get("killer") or "")
    if killer:
        parts += [" (", (NAME, killer), ")"]
    deaths = int(getattr(entry, "deaths", 0) or len(recaps))
    parts.append(f" at {at_clock(first.get('time_ms'))} · {deaths} death{'s' if deaths != 1 else ''}")
    pull = _pull_of(entry)
    if pull and pull.get("outcome") == WIPE:
        later = float(getattr(entry, "duration_s", 0) or 0) - int(first.get("time_ms") or 0) / 1000
        if later >= 1:
            parts.append(f" · the pull ended {clock(later)} later")
    return parts


def first_death_text(entry, names=None) -> str:
    """'First death: @x to Grievous Pulse (Lord Falgravn) at 1:42 · 14
    deaths · the pull ended 1:12 later'; the last part only on a wipe;
    '' for a fight without a death. *names*: the Hide names mask."""
    out = []
    for part in first_death_parts(entry):
        if isinstance(part, tuple):
            out.append(names.text(part[1]) if names is not None else part[1])
        else:
            out.append(part)
    return "".join(out)


def dead_ms_of(entry, unit_id) -> int:
    """The player's time dead in the fight, in milliseconds."""
    return int((getattr(entry, "time_dead", None) or {}).get(str(unit_id), 0) or 0)


def dead_row_text(entry, unit_id) -> str:
    """'dead 1:32' for a player dead DEAD_ROW_SHARE or more of the fight;
    '' otherwise."""
    ms = dead_ms_of(entry, unit_id)
    duration = float(getattr(entry, "duration_s", 0) or 0)
    if ms <= 0 or duration <= 0 or ms / 1000 < DEAD_ROW_SHARE * duration:
        return ""
    return f"dead {clock(ms / 1000)}"


def dead_hover_text(entry, unit_id) -> str:
    """'Dead for 1:32 of 5:10 (30%)'; '' for a player never down."""
    ms = dead_ms_of(entry, unit_id)
    duration = float(getattr(entry, "duration_s", 0) or 0)
    if ms <= 0 or duration <= 0:
        return ""
    share = min(100.0, 100.0 * ms / 1000 / duration)
    return f"Dead for {clock(ms / 1000)} of {clock(duration)} ({share:.0f}%)"
