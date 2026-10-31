"""
Who opened the fight, and with what (engine side, no Qt). Issue #159.

Design: the fight's opener is the first hit or taunt by a player, a
player's pet or a companion on a hostile enemy, named by the ability or
effect that damaged or taunted. Until 0.29 the fight pane put a `*` after
the player who dealt the fight's first damage after BEGIN_COMBAT. A survey
of 393 split logs (8,816 fights, January to October 2026) showed why that
mark was often wrong, and what a line could say instead.

BEGIN_COMBAT is the logging player's line, not the group's. The game writes
it when the logging player's client enters combat, and a group member's hit
usually lands a moment earlier: a player hit or taunt came before the line
in 4,243 fights (48.1%), a median 14 ms early, and the opener itself landed
before the line in 4,080 of 7,204 player-first fights. Such a hit fell on
the previous, finalized encounter and was lost to the new one, except in a
zone's first fight, so the star marked someone other than the opener in
1,385 of 7,176 player-first fights (19.3%; 32.6% in trials). The recorder
therefore reads a bounded memory of the moments before the line: the
settled acts of the last OPENER_WINDOW_MS (10 s) after the previous
END_COMBAT, ZONE_CHANGED or BEGIN_LOG. The fight's clock does not move; the
fight time and every figure stay BEGIN_COMBAT to END_COMBAT.

A millisecond is judged whole. Acts are buffered until the log moves past
their millisecond, since shield-absorb pairs and taunt ties need all of it;
within it, line order decides. BEGIN_COMBAT adopts the pending millisecond
(1,294 openers sit in the line's own millisecond, written before it), and
END_COMBAT settles it into the fight before the fight is built.

A quarter of openers taunt (1,822 of 7,204; 43.3% in trials). The game
writes a TAUNTED that shares its cast id with the taunting skill's cast and
hits; it can trail the hit by a millisecond (173 of 5,382 hit openers had
the same player's TAUNTED 1 to 5 ms later). So the opener is a taunt when
the same unit's TAUNTED lands in its millisecond, or carries its cast id
within TAUNT_TIE_MS; a TAUNTED before any counted hit opens by itself, and
another player's never counts.

Naming. A hit is named by its own ability. The pressed skill comes from the
cast's BEGIN_CAST, kept by cast id, and is added only when its name
differs: compared by id, 2,695 of 7,122 opening hits would print "Razor
Caltrops, from Razor Caltrops" (a DoT tick carries another id than its cast
under the same name), while 189 are real renames ("Concussion, from
Elemental Susceptibility"). A DAMAGE_SHIELDED line names the absorbing
shield, not the attack; the attack is the line after it with the same cast
id, source, target and millisecond, carrying the rest of the damage or 0.
An absorb is named by that partner, else by its cast's BEGIN_CAST, never by
the shield. A hit counts only above 0, as in the dps rules.

The memory's edge. A hit whose enemy died or left before the line is
dropped: it belonged to the last pack. An opener within EDGE_AFTER_START_MS
of the line that started the memory, or in the window's oldest second, may
not be the first act at all, so the line drops "first" and the time there:
"@tank was already fighting Yokeda Kai (Goading Throw) when the fight
began".

Times. The opener gets ", 2.0 s into the fight" or ", 4.4 s before the
fight's start" only from TIME_SHOWN_MS away from the line, so a median lead
of 14 ms reads as no time at all and nothing prints "1.0 s"; an arena's
first seconds are its spawn, so an arena line never says "into the fight".
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

OPENER_WINDOW_MS = 10000  # the memory before the line, like ENGAGED_ENEMY_MS
TAUNT_TIE_MS = 5  # a TAUNTED this soon after its cast's hit makes the opener a taunt
EDGE_AFTER_START_MS = 200  # an opener this soon after the memory began is at its edge
EDGE_WINDOW_MS = 1000  # ...and so is one in the window's oldest second
CAST_MEMORY = 4096  # casts remembered by id for naming, like the engine's
TIME_SHOWN_MS = 1050  # a time is printed from this far from the line

TAUNTED = "TAUNTED"
SHIELDED = "DAMAGE_SHIELDED"
# Zones whose enemies spawn in waves: the first seconds are the spawn
ARENA_ZONES = frozenset((
    "Infinite Archive", "Blackrose Prison", "Dragonstar Arena", "Maelstrom Arena",
    "Vateshran Hollows"))


@dataclass(frozen=True)
class Side:
    """A player-side unit as the engine knows it at the line: a player, a
    player's pet or a companion."""
    unit_id: str  # the unit on the line
    via: str  # 'player', 'pet' or 'companion'
    row: str  # the row the act is the player's on: their record id, the owner's, a companion's row key
    owner: str  # the player whose name the line uses: their own record id or the owner's
    name: str  # that player's display name at the line, the fallback at build time
    pet: str = ""  # a pet's own name


@dataclass
class _Act:
    """One act the recorder weighs, as read from its line."""
    ts: int
    kind: str  # 'hit', 'taunt' or 'other' (a shield partner only)
    result: str
    cast_id: str
    ability_id: str
    enemy_id: str  # the hostile it was aimed at
    enemy_name: str  # its name at the line
    enemy: object = None  # the engine's record of it, for died_at and removed_at
    actor: Side | None = None
    skill_id: str = ""  # the pressed skill: the cast's BEGIN_CAST, as known at the line
    partner_id: str = ""  # a shield absorb's attack, from the paired line
    seq: int = 0  # line order


def _gone_before(enemy, ts: int) -> bool:
    """Whether the engine's record of an enemy says it died or left before
    *ts*."""
    for attr in ("died_at", "removed_at"):
        at = getattr(enemy, attr, None)
        if at is not None and at < ts:
            return True
    return False


class FightOpening:
    """One fight's opener, while it is decided and after. The engine keeps
    it on the fight's encounter."""

    def __init__(self, start_ms: int, memory_start: int | None):
        self.start = start_ms  # the fight's BEGIN_COMBAT
        self.memory_start = memory_start  # when the memory before it began
        self.opener: _Act | None = None
        self.kind = ""  # 'hit' or 'taunt'
        self.taunt: _Act | None = None  # the TAUNTED that made a hit opener a taunt
        self.settled = False  # nothing can change any more

    def consider(self, act: _Act) -> None:
        """Weigh the next settled act, in log order."""
        if self.settled:
            return
        if self.opener is None:
            self.opener = act
            self.kind = "taunt" if act.kind == "taunt" else "hit"
            return
        opener = self.opener
        if (self.kind == "hit" and act.kind == "taunt"
                and act.actor.unit_id == opener.actor.unit_id
                and (act.ts == opener.ts
                     or (act.cast_id == opener.cast_id and act.cast_id not in ("", "0")
                         and act.ts - opener.ts <= TAUNT_TIE_MS))):
            self.kind = "taunt"
            self.taunt = act

    def tick(self, ts: int) -> None:
        """The log has reached *ts*: an opener's taunt tie has run out."""
        if not self.settled and self.opener is not None and ts > self.opener.ts + TAUNT_TIE_MS:
            self.settled = True

    def close(self) -> None:
        self.settled = True

    def reopen(self) -> None:
        """A fight the game cut in two carries on: still open if nobody
        opened it in its first part."""
        self.settled = self.opener is not None

    def at_edge(self) -> bool:
        """Whether the opener sits at the memory's edge, where nobody can be
        called first."""
        first = self.opener
        if first is None or first.ts >= self.start:
            return False
        if self.memory_start is not None and first.ts - self.memory_start <= EDGE_AFTER_START_MS:
            return True
        return first.ts - self.start <= -(OPENER_WINDOW_MS - EDGE_WINDOW_MS)


class OpenerRecorder:
    """Decides each fight's opener from the acts the engine hands it (see
    the module's design note). The engine owns one, calls it in log order,
    and asks *listening* before doing the work of a call.

    *damage_results* are the results that count as damage (the engine's
    DAMAGE_RESULTS). The dead-enemy drop is an option, so a replay can run
    the survey's rules."""

    def __init__(self, damage_results, drop_gone: bool = True):
        self._damage = frozenset(damage_results)
        self.drop_gone = drop_gone
        self._casts: dict[str, str] = {}
        self._pending: list[_Act] = []
        self._pending_ts: int | None = None
        self._memory: deque[_Act] = deque()
        self._memory_start: int | None = None
        self._fight: FightOpening | None = None
        self._last: FightOpening | None = None
        self._seq = 0

    @property
    def listening(self) -> bool:
        """Whether an act could still matter: always between fights (the
        memory), and in a fight until its opener is settled."""
        return self._fight is None or not self._fight.settled

    # -- what the engine hands in -------------------------------------------

    def note_cast(self, cast_id: str, ability_id: str) -> None:
        """A BEGIN_CAST of anyone: the ability its cast id names. The first
        word stands; bounded, the oldest half goes when full."""
        if not cast_id or cast_id == "0" or cast_id in self._casts:
            return
        if len(self._casts) >= CAST_MEMORY:
            for key in list(self._casts)[:CAST_MEMORY // 2]:
                del self._casts[key]
        self._casts[cast_id] = ability_id

    def note_player_event(self, ts: int, result: str, hit_value: int, cast_id: str,
                          ability_id: str, actor: Side, target_id: str, target_name: str,
                          enemy=None) -> None:
        """A player-side COMBAT_EVENT on a hostile, of any result: a hit
        above 0 or a TAUNTED counts, any other line can be a shield
        absorb's partner."""
        if not self.listening:
            return
        if result == TAUNTED:
            kind = "taunt"
        elif result in self._damage and hit_value > 0:
            kind = "hit"
        else:
            kind = "other"
        self._add(_Act(ts, kind, result, cast_id, ability_id, target_id, target_name,
                       enemy, actor=actor, skill_id=self._cast_of(cast_id)))

    def begin_combat(self, start_ms: int) -> FightOpening:
        """A new fight's BEGIN_COMBAT: the memory becomes its candidates.
        The line's own millisecond stays pending and settles into it."""
        if self._fight is not None:  # the last fight never ended
            self._settle_all()
            self._fight.close()
        elif self._pending and self._pending_ts < start_ms:
            self._settle()
        opening = FightOpening(start_ms, self._memory_start)
        horizon = start_ms - OPENER_WINDOW_MS
        for act in self._memory:
            if act.ts < horizon or (self.drop_gone and _gone_before(act.enemy, start_ms)):
                continue
            opening.consider(act)
        self._memory.clear()
        self._fight = self._last = opening
        return opening

    def end_combat(self, ts: int) -> None:
        """END_COMBAT: what is pending settles into the fight, which is
        then final, and a new memory starts."""
        self._settle_all()
        if self._fight is not None:
            self._fight.close()
            self._fight = None
        self._memory.clear()
        self._memory_start = ts

    def resume(self) -> None:
        """The game cut the fight in two (the engine's COMBAT_RESUME_MS):
        the fight carries on with its opener, and what came between the two
        lines is dropped."""
        self._pending = []
        self._pending_ts = None
        self._memory.clear()
        if self._last is not None:
            self._last.reopen()
            self._fight = self._last

    def reset(self, ts: int, new_session: bool = False) -> None:
        """ZONE_CHANGED or BEGIN_LOG: unit ids are handed out afresh, so the
        memory goes and a new one starts at *ts*; a new session's cast ids
        start over too."""
        if self._fight is not None:
            self._settle_all()
            self._fight.close()
            self._fight = None
        self._pending = []
        self._pending_ts = None
        self._memory.clear()
        self._memory_start = ts
        self._last = None
        if new_session:
            self._casts.clear()

    # -- inside -------------------------------------------------------------

    def _cast_of(self, cast_id: str) -> str:
        return self._casts.get(cast_id, "") if cast_id and cast_id != "0" else ""

    def _add(self, act: _Act) -> None:
        if self._pending and act.ts > self._pending_ts:
            self._settle()
        if self._fight is not None:
            self._fight.tick(act.ts)
            if self._fight.settled:
                return
        self._seq += 1
        act.seq = self._seq
        self._pending.append(act)
        self._pending_ts = act.ts

    def _settle_all(self) -> None:
        if self._pending:
            self._settle()

    def _settle(self) -> None:
        """Judge the pending millisecond whole, then hand its acts on in
        line order: to the open fight, or to the memory."""
        acts, self._pending, self._pending_ts = self._pending, [], None
        self._pair_absorbs(acts)
        for act in acts:
            if act.kind == "other":
                continue
            if self._fight is not None:
                self._fight.consider(act)
            else:
                self._memory.append(act)
                horizon = act.ts - OPENER_WINDOW_MS
                while self._memory and self._memory[0].ts < horizon:
                    self._memory.popleft()
        if self._fight is not None and acts:
            self._fight.tick(acts[-1].ts)

    @staticmethod
    def _pair_absorbs(acts: list[_Act]) -> None:
        """A shield absorb takes the attack of the later line in its
        millisecond with the same cast id, source and target."""
        for i, act in enumerate(acts):
            if act.result != SHIELDED:
                continue
            for later in acts[i + 1:]:
                if (later.result != SHIELDED and later.cast_id == act.cast_id
                        and later.actor.unit_id == act.actor.unit_id
                        and later.enemy_id == act.enemy_id):
                    act.partner_id = later.ability_id
                    break


def hit_ability_id(act: _Act) -> str:
    """The ability a counted hit is named by: its own, or for a shield
    absorb the paired attack's, else its cast's; never the shield."""
    if act.result == SHIELDED:
        return act.partner_id or act.skill_id
    return act.ability_id


# -- the fight entry's record -------------------------------------------------

def opener_record(opening: FightOpening | None, ability_name: Callable[[str], str],
                  player_name: Callable[[str, str], str]) -> dict | None:
    """The fight entry's opener dict from a fight's opening, names resolved:
    *ability_name* gives an ability id's name ('' when unknown),
    *player_name* a player's display name from their record id and the name
    the line carried. None when nobody hit or taunted an enemy."""
    if opening is None or opening.opener is None:
        return None
    act = opening.opener

    def name(ability_id: str) -> str:
        return (ability_name(ability_id) or f"Ability {ability_id}") if ability_id else ""

    if opening.kind == "taunt":
        taunt = opening.taunt or act
        ability_id = taunt.skill_id or act.skill_id or (
            hit_ability_id(act) if act.kind == "hit" else "")
        skill_id = ""
    else:
        ability_id = hit_ability_id(act)
        skill_id = act.skill_id
        if not ability_id or not skill_id or name(skill_id) == name(ability_id):
            skill_id = ""
    return dict(_actor_fields(act.actor, player_name),
                kind=opening.kind,
                ability=name(ability_id), ability_id=ability_id,
                skill=name(skill_id), skill_id=skill_id,
                target=act.enemy_name, target_id=act.enemy_id,
                time_ms=act.ts - opening.start,
                edge=opening.at_edge())


def _actor_fields(side: Side, player_name: Callable[[str, str], str]) -> dict:
    return {'unit_id': side.row, 'via': side.via, 'owner_id': side.owner,
            'name': player_name(side.owner, side.name), 'pet': side.pet}


# -- the line ------------------------------------------------------------------

@dataclass(frozen=True)
class PlayerName:
    """A player's name in the line. The renderer passes it through the Hide
    names mask, and adds the row's role and class (*role_class*, 'T, DK')
    when the name picks out no single row: 'anon', or a name the mask
    hides."""
    name: str
    role_class: str = ""


def seconds_text(ms: int) -> str:
    """A time in seconds with one decimal, rounded half up: 1050 -> '1.1'."""
    tenths = (abs(int(ms)) + 50) // 100
    return f"{tenths // 10}.{tenths % 10}"


def time_text(ms: int, arena: bool) -> str:
    """The time rule for the opener ('' when none shows)."""
    if ms <= -TIME_SHOWN_MS:
        return f", {seconds_text(ms)} s before the fight's start"
    if ms >= TIME_SHOWN_MS and not arena:
        return f", {seconds_text(ms)} s into the fight"
    return ""


def opener_parts(entry) -> list[list]:
    """The opener line of a fight entry as lines of parts, each a str or a
    PlayerName; [] when the entry has no opener."""
    opener = getattr(entry, "opener", None)
    if not opener:
        return []
    rows = {str(p.get("unit_id", "")): p for p in (getattr(entry, "players", None) or [])}
    arena = (getattr(entry, "zone_name", "") or "") in ARENA_ZONES
    if opener.get("edge"):
        line = [*_actor_parts(opener, rows), " was already fighting ",
                opener.get("target") or "an enemy"]
        if opener.get("ability"):
            line.append(f" ({opener['ability']})")
        line.append(" when the fight began")
        return [line]
    line = _opener_line(opener, rows)
    line.append(time_text(int(opener.get("time_ms") or 0), arena))
    return [_drop_empty(line)]


def _opener_line(opener: dict, rows: dict) -> list:
    verb = " taunted " if opener.get("kind") == "taunt" else " hit "
    line = [*_actor_parts(opener, rows), verb, opener.get("target") or "an enemy", " first"]
    if opener.get("ability"):
        line.append(f": {opener['ability']}")
        if opener.get("skill"):
            line.append(f", from {opener['skill']}")
    return line


def _role_class(row: dict | None) -> str:
    if not row:
        return ""
    role, cls = str(row.get("role") or ""), str(row.get("class_abbr") or "")
    return f"{role}, {cls}" if role and cls else role or cls


def _actor_parts(fields: dict, rows: dict) -> list:
    """A player, a player's pet or a companion, named from its owner."""
    owner = PlayerName(fields.get("name") or "anon",
                       _role_class(rows.get(str(fields.get("owner_id", "")))))
    via = fields.get("via")
    if via == "pet":
        return [owner, f"'s {fields.get('pet') or 'pet'}"]
    if via == "companion":
        return [owner, "'s Companion"]
    return [owner]


def _drop_empty(line: list) -> list:
    return [part for part in line if part != ""]
