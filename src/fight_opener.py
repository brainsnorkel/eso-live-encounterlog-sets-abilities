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
their millisecond, since fan-out casts, shield-absorb pairs and taunt ties
need all of it; within it, line order decides. BEGIN_COMBAT adopts the
pending millisecond (1,294 openers sit in the line's own millisecond,
written before it), and END_COMBAT settles it into the fight before the
fight is built.

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

A monster acted first in 1,545 fights (17.5%, a lower bound). The log has
no threat or aggro line, and the addon API has none either, so a fight
started by walking into a monster's range cannot be told from a ranged mob
opening on sight. What the log does show is that a monster acted before
anyone hit or taunted, and whom it went for: a hostile's BEGIN_CAST names
its target, and so does its COMBAT_EVENT. The line says exactly that and
never "pulled". The monster's act is kept only when the opener comes
OPENER_MONSTER_MARGIN_MS (100 ms) or more later: inside it sit same-moment
races and Tideborn Taleria's Slaughterfish pulls (186 fights). When a
player had already begun a cast at a living enemy before the monster acted
(507 fights by a recount over the logs, 191 of them only before the line),
"first" would be false, so the line names the cast instead.

Noise is never the monster's opening. A naive rule would be wrong in 1,009
fights (11.4%): a dead monster's lingering area or DoT still "hits" players
after its DIED_XP (its health on the line is 0, 859 fights first); a hazard
is a unit named as its ability (Scorching Barrier, 119); a scripted cast
reaches three or more players in one millisecond (Nahviintaas' Look At, 23);
a DOT_TICK is an effect applied earlier (8). A few scripted mechanics pass
every filter and are listed by monster id (the Arcane Knot of Lucent
Citadel, whose Temporal Splinters opened 40 fights while the first player
hit came a median 13 s later; the second Tideborn Taleria unit that throws
the Slaughterfish Attack) or by ability id (Look At, Music Musicer). A unit
that ever had a player owner is not a monster: a released pet turns
HOSTILE with owner 0.

The memory's edge. A candidate whose enemy died or left before the line is
dropped (a hit's or cast's target, a monster act's source): it belonged to
the last pack. An opener within EDGE_AFTER_START_MS of the line that started
the memory, or in the window's oldest second, may not be the first act at
all, so the line drops "first" and the time there: "@tank was already
fighting Yokeda Kai (Goading Throw) when the fight began".

Times. The line's first act gets ", 2.0 s into the fight" or ", 4.4 s
before the fight's start" only from TIME_SHOWN_MS away from the line, so a
median lead of 14 ms reads as no time at all and nothing prints "1.0 s";
an arena's first seconds are its spawn, so an arena line never says "into
the fight". A monster-first opening's player line gets ", 5.8 s later".
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from companions import NAME_SUFFIX

OPENER_WINDOW_MS = 10000  # the memory before the line, like ENGAGED_ENEMY_MS
OPENER_MONSTER_MARGIN_MS = 100  # a monster's act counts as first this far ahead
TAUNT_TIE_MS = 5  # a TAUNTED this soon after its cast's hit makes the opener a taunt
EDGE_AFTER_START_MS = 200  # an opener this soon after the memory began is at its edge
EDGE_WINDOW_MS = 1000  # ...and so is one in the window's oldest second
FANOUT_TARGETS = 3  # one monster's cast of one ability at this many players at once
CAST_MEMORY = 4096  # casts remembered by id for naming, like the engine's
TIME_SHOWN_MS = 1050  # a time is printed from this far from the line

TAUNTED = "TAUNTED"
SHIELDED = "DAMAGE_SHIELDED"
CAST = "cast"  # the result of a BEGIN_CAST act
DOT_RESULTS = frozenset(("DOT_TICK", "DOT_TICK_CRITICAL"))
# A monster's act on a player-side unit, besides the damage results: an
# attack that missed or was dodged, or crowd control (the survey's set)
MONSTER_EXTRA_RESULTS = frozenset((
    "DODGED", "IMMUNE", "MISS", "PARRIED", "REFLECTED", "STUNNED", "SNARED", "FEARED",
    "KNOCKBACK", "STAGGERED", "ROOTED", "OFFBALANCE", "INTERRUPT", "SILENCED",
    "DISORIENTED", "LEVITATED", "CHARMED", "PACIFIED", "FALLING", "PARTIAL_RESIST",
    "RESIST"))
# Scripted mechanics no filter catches, never a monster's opening
SCRIPTED_MONSTERS = frozenset((
    "122316",  # Arcane Knot (Lucent Citadel): Temporal Splinters
    "108471",  # the second Tideborn Taleria unit: Slaughterfish Attack
))
SCRIPTED_ABILITIES = frozenset((
    "121308",  # Look At (Nahviintaas)
    "157215",  # Music Musicer (Archwizard Twelvane, Tho'at Replicanum, Xalvakka)
))
# Zones whose enemies spawn in waves: the first seconds are the spawn. Known
# by zone id, which every client language writes alike (all five checked in
# the zone-name table of the game client; the split logs hold 1436, 1082 and
# 635), and by the English name for an entry without one
ARENA_ZONE_IDS = frozenset(("1436", "1082", "635", "677", "1227"))
ARENA_ZONES = frozenset((
    "Infinite Archive", "Blackrose Prison", "Dragonstar Arena", "Maelstrom Arena",
    "Vateshran Hollows"))


def is_arena(zone_id, zone_name) -> bool:
    """Whether a fight's zone spawns its enemies in waves."""
    return str(zone_id or "") in ARENA_ZONE_IDS or (zone_name or "") in ARENA_ZONES


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
    side: str  # 'player' or 'monster'
    kind: str  # 'hit', 'taunt', 'cast', 'act' (a monster's) or 'other' (a shield partner only)
    result: str
    cast_id: str
    ability_id: str
    enemy_id: str  # the hostile: a player act's target, a monster act's source
    enemy_name: str  # its name at the line
    enemy: object = None  # the engine's record of it, for died_at and removed_at
    actor: Side | None = None  # a player act's actor
    target: Side | None = None  # a monster act's target
    monster_id: str = ""  # a monster act's source
    dead: bool = False  # a monster act's source has 0 health on the line
    skill_id: str = ""  # the pressed skill: the cast's BEGIN_CAST, as known at the line
    partner_id: str = ""  # a shield absorb's attack, from the paired line
    seq: int = 0  # line order

    @property
    def source_unit(self) -> str:
        return self.actor.unit_id if self.side == "player" else self.enemy_id

    @property
    def target_unit(self) -> str:
        return self.enemy_id if self.side == "player" else self.target.unit_id


def _gone_before(enemy, ts: int) -> bool:
    """Whether the engine's record of an enemy says it died or left before
    *ts*."""
    for attr in ("died_at", "removed_at"):
        at = getattr(enemy, attr, None)
        if at is not None and at < ts:
            return True
    return False


class FightOpening:
    """One fight's opener and the monster's act before it, while they are
    decided and after. The engine keeps it on the fight's encounter."""

    def __init__(self, start_ms: int, memory_start: int | None):
        self.start = start_ms  # the fight's BEGIN_COMBAT
        self.memory_start = memory_start  # when the memory before it began
        self.opener: _Act | None = None
        self.kind = ""  # 'hit' or 'taunt'
        self.taunt: _Act | None = None  # the TAUNTED that made a hit opener a taunt
        self.monster: _Act | None = None
        self.in_flight: _Act | None = None  # a player's cast begun before the monster's act
        self._last_cast: _Act | None = None
        self.settled = False  # nothing can change any more

    def consider(self, act: _Act, margin_ms: int) -> None:
        """Weigh the next settled act, in log order."""
        if self.settled:
            return
        if act.side == "monster":
            if self.opener is None and self.monster is None:
                self.monster = act
                self.in_flight = self._last_cast
            return
        if act.kind == CAST:
            if self.opener is None and self.monster is None:
                self._last_cast = act
            return
        if self.opener is None:
            self.opener = act
            self.kind = "taunt" if act.kind == "taunt" else "hit"
            if self.monster is not None and act.ts - self.monster.ts < margin_ms:
                self.monster = self.in_flight = None
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

    def first(self) -> _Act | None:
        return self.monster if self.monster is not None else self.opener

    def at_edge(self) -> bool:
        """Whether the line's first act sits at the memory's edge, where
        nobody can be called first."""
        first = self.first()
        if first is None or first.ts >= self.start:
            return False
        if self.memory_start is not None and first.ts - self.memory_start <= EDGE_AFTER_START_MS:
            return True
        return first.ts - self.start <= -(OPENER_WINDOW_MS - EDGE_WINDOW_MS)


class OpenerRecorder:
    """Decides each fight's opener from the acts the engine hands it (see
    the module's design note). The engine owns one, calls it in log order,
    and asks *listening* before doing the work of a call.

    *ability_name* names an ability id from the session's ABILITY_INFO (None
    or '' when unknown); *damage_results* are the results that count as damage
    (the engine's DAMAGE_RESULTS). The margin, the list of scripted
    mechanics and the dead-enemy drop are options, so a replay can run the
    survey's rules."""

    def __init__(self, ability_name: Callable[[str], str], damage_results,
                 margin_ms: int = OPENER_MONSTER_MARGIN_MS, scripted: bool = True,
                 drop_gone: bool = True):
        self._ability_name = ability_name
        self._damage = frozenset(damage_results)
        self._monster_results = self._damage | MONSTER_EXTRA_RESULTS
        self.margin_ms = margin_ms
        self.scripted = scripted
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
        memory), and in a fight until its records are settled."""
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

    def note_player_cast(self, ts: int, cast_id: str, ability_id: str, actor: Side,
                         target_id: str, target_name: str, enemy=None,
                         target_dead: bool = False) -> None:
        """A player-side BEGIN_CAST at a hostile. A cast at a dead target
        (0 health on its line, or died or left before the cast) never
        counts."""
        if not self.listening or target_dead or _gone_before(enemy, ts):
            return
        self._add(_Act(ts, "player", CAST, CAST, cast_id, ability_id, target_id, target_name,
                       enemy, actor=actor, skill_id=ability_id))

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
        self._add(_Act(ts, "player", kind, result, cast_id, ability_id, target_id, target_name,
                       enemy, actor=actor, skill_id=self._cast_of(cast_id)))

    def note_monster_event(self, ts: int, result: str, cast_id: str, ability_id: str,
                           source_id: str, source_name: str, monster_id: str, enemy,
                           target: Side, source_dead: bool = False) -> None:
        """A hostile's act on a player-side unit: its BEGIN_CAST (result
        CAST) or a COMBAT_EVENT of any result; a damage, miss or
        crowd-control result counts, any other line can be a partner."""
        if not self.listening:
            return
        kind = "act" if result == CAST or result in self._monster_results else "other"
        self._add(_Act(ts, "monster", kind, result, cast_id, ability_id, source_id, source_name,
                       enemy, target=target, monster_id=str(monster_id or ""), dead=source_dead,
                       skill_id=self._cast_of(cast_id)))

    def begin_combat(self, start_ms: int) -> FightOpening:
        """A new fight's BEGIN_COMBAT: the memory becomes its candidates.
        The line's own millisecond stays pending and settles into it."""
        if self._pending and self._pending_ts < start_ms:
            self._settle()
        if self._fight is not None:  # the last fight never ended
            self._fight.close()
            self._fight = None
        opening = FightOpening(start_ms, self._memory_start)
        horizon = start_ms - OPENER_WINDOW_MS
        for act in self._memory:
            if act.ts < horizon or (self.drop_gone and _gone_before(act.enemy, start_ms)):
                continue
            opening.consider(act, self.margin_ms)
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
        the fight carries on with its records, and what came between the
        two lines is dropped."""
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
        fanned = self._fanned_out(acts)
        for act in acts:
            if act.kind == "other" or (act.side == "monster" and self._noise(act, fanned)):
                continue
            if self._fight is not None:
                self._fight.consider(act, self.margin_ms)
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
                if (later.result not in (SHIELDED, CAST) and later.cast_id == act.cast_id
                        and later.source_unit == act.source_unit
                        and later.target_unit == act.target_unit):
                    act.partner_id = later.ability_id
                    break

    @staticmethod
    def _fanned_out(acts: list[_Act]) -> set:
        """(monster, ability) cast at FANOUT_TARGETS or more player-side
        units in this millisecond: a scripted cast."""
        targets = defaultdict(set)
        for act in acts:
            if act.side == "monster" and act.result == CAST:
                targets[(act.enemy_id, act.ability_id)].add(act.target.unit_id)
        return {key for key, units in targets.items() if len(units) >= FANOUT_TARGETS}

    def _noise(self, act: _Act, fanned: set) -> bool:
        if act.dead or act.result in DOT_RESULTS:
            return True
        if act.result == CAST and (act.enemy_id, act.ability_id) in fanned:
            return True
        return is_mechanic(act.monster_id, act.ability_id, act.enemy_name,
                           self._ability_name(monster_action_id(act)), self.scripted)


def is_mechanic(monster_id: str, ability_id: str, monster_name: str,
                action_name: str | None, scripted: bool = True) -> bool:
    """A monster's act that is a mechanic, never the monster going for
    anyone: a hazard, which is a unit named as the ability it acts with
    (*action_name*: for a shield absorb, the attack's), or with *scripted*
    a listed scripted monster or ability (see the module's note on noise).
    The engine asks it too, of a combat that met no enemy."""
    if scripted and (monster_id in SCRIPTED_MONSTERS or ability_id in SCRIPTED_ABILITIES):
        return True
    return bool(monster_name) and monster_name == action_name


def hit_ability_id(act: _Act) -> str:
    """The ability a player's counted hit is named by: its own, or for a
    shield absorb the paired attack's, else its cast's; never the shield."""
    if act.result == SHIELDED:
        return act.partner_id or act.skill_id
    return act.ability_id


def monster_action_id(act: _Act) -> str:
    """The ability a monster's act is named by, as for a hit."""
    if act.result == SHIELDED:
        return act.partner_id or act.skill_id
    return act.ability_id


# -- the fight entry's records ------------------------------------------------

def opener_records(opening: FightOpening | None, ability_name: Callable[[str], str],
                   player_name: Callable[[str, str], str]) -> tuple[dict | None, dict | None]:
    """The fight entry's (opener, monster_first) dicts from a fight's
    opening, names resolved: *ability_name* gives an ability id's name
    ('' when unknown), *player_name* a player's display name from their
    record id and the name the line carried."""
    if opening is None:
        return None, None
    edge = opening.at_edge()

    def name(ability_id: str) -> str:
        return (ability_name(ability_id) or f"Ability {ability_id}") if ability_id else ""

    opener = None
    act = opening.opener
    if act is not None:
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
        opener = dict(_actor_fields(act.actor, player_name),
                      kind=opening.kind,
                      ability=name(ability_id), ability_id=ability_id,
                      skill=name(skill_id), skill_id=skill_id,
                      target=act.enemy_name, target_id=act.enemy_id,
                      time_ms=act.ts - opening.start,
                      edge=edge and opening.monster is None)
    monster = None
    act = opening.monster
    if act is not None:
        action_id = monster_action_id(act)
        target = act.target
        in_flight = None
        cast = opening.in_flight
        if cast is not None:
            in_flight = dict(_actor_fields(cast.actor, player_name),
                             skill=name(cast.ability_id), skill_id=cast.ability_id)
        monster = {
            'unit_id': act.enemy_id, 'name': act.enemy_name,
            'action': name(action_id), 'action_id': action_id,
            'target_kind': target.via, 'target_id': target.owner, 'target_row': target.row,
            'target_name': player_name(target.owner, target.name), 'target_pet': target.pet,
            'in_flight': in_flight,
            'time_ms': act.ts - opening.start,
            'edge': edge,
        }
    return opener, monster


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
    """The time rule for the line's first act ('' when none shows)."""
    if ms <= -TIME_SHOWN_MS:
        return f", {seconds_text(ms)} s before the fight's start"
    if ms >= TIME_SHOWN_MS and not arena:
        return f", {seconds_text(ms)} s into the fight"
    return ""


def opener_parts(entry) -> list[list]:
    """The opener line of a fight entry as lines of parts, each a str or a
    PlayerName; [] when the entry has neither record. A monster-first
    opening is two lines: whom the monster went for, then who hit first."""
    opener = getattr(entry, "opener", None)
    monster = getattr(entry, "monster_first", None)
    if not opener and not monster:
        return []
    rows = {str(p.get("unit_id", "")): p for p in (getattr(entry, "players", None) or [])}
    arena = is_arena(getattr(entry, "zone_id", ""), getattr(entry, "zone_name", ""))
    if monster:
        target = _target_parts(monster, rows)
        action = monster.get("action") or ""
        action_part = [f" ({action})"] if action else []
        if monster.get("edge"):
            return [[monster.get("name") or "a monster", " was already fighting ", *target,
                     *action_part, " when the fight began"]]
        flight = monster.get("in_flight")
        line = [monster.get("name") or "a monster", " went for ", *target]
        if flight:
            line += [*action_part, ", with ", *_actor_parts(flight, rows),
                     f"'s {flight.get('skill') or 'cast'} already on its way"]
        else:
            line += [" first", *action_part, ", before any hit or taunt"]
        line.append(time_text(int(monster.get("time_ms") or 0), arena))
        lines = [line]
        if opener:
            second = _opener_line(opener, rows)
            gap = int(opener.get("time_ms") or 0) - int(monster.get("time_ms") or 0)
            if gap >= TIME_SHOWN_MS:
                second.append(f", {seconds_text(gap)} s later")
            lines.append(second)
        return [_drop_empty(line) for line in lines]
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
        return [owner, *_pet_parts(fields.get("pet"))]
    if via == "companion":
        return [owner, NAME_SUFFIX]
    return [owner]


def _pet_parts(pet) -> list:
    """After the owner's name: the pet's own name, through the mask too,
    since a unit the engine does not know as a companion can carry a handle
    ("@handle's Companion"); such a unit reads as its owner's Companion."""
    pet = str(pet or "") or "pet"
    if pet.endswith(NAME_SUFFIX):
        return [NAME_SUFFIX]
    return ["'s ", PlayerName(pet)]


def _target_parts(monster: dict, rows: dict) -> list:
    owner = PlayerName(monster.get("target_name") or "anon",
                       _role_class(rows.get(str(monster.get("target_id", "")))))
    kind = monster.get("target_kind")
    if kind == "pet":
        return [owner, *_pet_parts(monster.get("target_pet"))]
    if kind == "companion":
        return [owner, NAME_SUFFIX]
    return [owner]


def _drop_empty(line: list) -> list:
    return [part for part in line if part != ""]
