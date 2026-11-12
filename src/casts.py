"""
Cast counts and casts per minute (engine side, no Qt). Issue #94.

Design: every player's BEGIN_CAST lines are in the log, the group's as well
as the logging player's. One cast can write two of them under one
castTrackId: a channelled heavy attack writes one at the press and one for
the channel (11 of 11 for a Lightning staff in the Tideborn Taleria fight
of 2026-10-27), and a synergy can write two ability ids (Healing
Combustion, 63507 then 95042, on the same timestamp). A cast is therefore
one castTrackId per caster, whatever the lines under it.

Design: a track id written again after its END_CAST (issue #226). Over the
391 split logs of 2026 (5.3 million BEGIN_CAST lines), 388,764 lines reuse
a track id their caster had already used. Most are the same cast. A
channelled heavy attack's or a channel's later lines come with no END_CAST
between (145,778, 99.99% within 200 ms), and a synergy's or a multi-hit
skill's second line comes in the same millisecond. But 92,309 players'
lines, which the engine merged, came at a later millisecond after the
track's END_CAST, in two kinds:
- A synergy taken again under its first take's track id: Healing
  Combustion 477 times, Combustion 42. A new cast.
- A proc the game writes as an instant cast, never on anyone's bar, under
  the track id of its first tick, every tick: 91,230 lines. Meridia's
  Favor about every second (43,625), Highland Sentinel and Peace and
  Serenity every second, Blood Magic, the scribed banner's tick every five
  seconds, Grundwulf, Obsidian Stance.
A cast is a press (Chris's choice), so an ability its caster writes again
on its own track after END_CAST, at a later millisecond, is a proc for the
rest of the session: it leaves that caster's counts, the extras and casts
per minute, unless it is a cast of a skill on their bar, matched as the
slot counts are (on_bars): Chakram of Destiny, slotted as 186207, is
pressed as 194237 and pressed again on the same track. An extra (a light
or heavy attack, a dodge, a potion) is never a proc. Over the 391 logs the
rule finds 14 procs, all players' (none a companion's, an extra or a
werewolf skill). A proc is known from its second tick, so a fight whose
entry was built between its first two ticks keeps that first one: at most
one cast, once a session. Before, each proc counted once a fight, and a
synergy taken again not at all. A track still
written when a fight's entry is built carries over to the next fight:
the banner pressed in one fight ticks on in the next, and before, its
first tick there counted as a press (638 players' fights over the 391
logs, every one a Shocking, Magical or Fiery Banner). A cancelled cast's
END_CAST (PLAYER_CANCELLED) never reaches the engine, as the parser
rejects it, so a track id reused after one stays the same cast; a slotted
skill's own effect written later on its track (the banner's first tick, a
werewolf ultimate's form) stays with the press.

A fight's casts are those begun from its start to its end, the engine's
fight window (BEGIN_COMBAT to END_COMBAT). Combat Metrics counts the same
way: for the logging player in that fight it showed Force Pulse 37,
Subterranean Assault 12, light attacks (Lightning) 52 and every other skill
alike, and left out the pre-buffs cast in the ten seconds before the pull
(Blockade of Frost 7 in both). Its light attacks (Ice) read 15 against the
log's 14. Over 12 trial and arena splits (193 fights, 66,244 casts), 3% of
casts began in the 3 s before BEGIN_COMBAT; those are not counted.

A count sits under a bar slot when the cast's id is the slot's, or its name
is (Venom Skull is slotted as 117624 and cast as 123704, Incapacitating
Strike as 36508 and 113105, Crystal Fragments' instant proc is 114716), or
both are in one of the families of SKILL_FAMILIES. The Destruction Staff
families are there because the bar lists those skills under a base id
(Elemental Blockade 39011) or the element of the staff equipped when
PLAYER_INFO was written, while the cast
carries the element of the staff in hand: over the October splits,
Elemental Blockade was cast as Blockade of Fire 2,651 times, Frost 2,391,
Storms 1,257, and a bar listing Blockade of Storms was cast as Blockade of
Frost 253 times. A skill slotted on both bars shows its total under each
(Chris's choice: totals per skill, not per active bar).

One skill writes no BEGIN_CAST at all: the Arcanist's Fatecarver, matched
in 0 of 1,514 player-fights with Pragmatic Fatecarver slotted and 0 of 68
with Exhausting Fatecarver (no other slotted skill is systematically
unmatched; those that are never cast are slotted for their passives,
banners cast before the pull, or rarely used ultimates). Each use instead
gains its channel effects on the caster under one castTrackId: Pragmatic
writes 186369, 189533, 201265 and 201273 (6,867 casts in the October
splits; 201265 also comes alone, a shield), Exhausting 186780, sometimes
with 184291. CHANNEL_EFFECTS turns such a GAINED into a cast of the morph,
one per castTrackId like any cast. No log had the unmorphed Fatecarver.

Casts per minute counts every cast (Chris's choice), extras included,
over the fight's duration; a player who left during the fight over the
share of it they were there for.

The extras are the casts no slot holds, by kind (EXTRA_KINDS): light and
heavy attacks (every id the client's own name table, en.lang table
198758357 of Update 51, names "Light Attack (…)" or "Heavy Attack (…)"),
bashes, weapon swaps, dodges, synergies, potions and Break Free. The log
marks neither a synergy nor a potion: a synergy writes only its own
effects, and a potion is cast under its first trait's effect (Restore
Health, Major Brutality) with the generic icon Recall and Mount Up also
carry. Both come from the ids seen in the October splits: SYNERGIES holds
the skill-line synergies (class, guild, Undaunted, werewolf), not the
trials' mechanics; POTIONS the alchemy block 45221 to 45241, the vendor,
Alliance War and Crown potions. Werewolf light and heavy attacks count as
light and heavy attacks.

A companion's casts are counted the same way, under its row key
(companions.py) and over the whole fight (issue #130). Its light attacks,
block, dodge, bash and break free have ids of their own, none of them in
the player's sets (its light attacks are plain "Light Attack", one id per
weapon look), and it never heavy attacks, swaps weapons, takes a synergy
or drinks a potion: over 214 split logs with a companion its casts that
are not skills were those ids and Mount Up. So its extras line has kinds
of its own (COMPANION_EXTRA_KINDS), Block among them, which a player's
never needs (a player's block writes no cast), and a player's 'casts'
stays as it was.

Each cast the recorder keeps also holds the unit it was aimed at, named
as it is noted, and the time of the END_CAST its track wrote next, with
whether that said INTERRUPTED (issue #214): the Events tab's actions show
them, from the fight entry's packed copy (fight_casts). Nothing here
counts them, so the counts are as they were; cast_records gives the
counts' casts one by one.
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable

import werewolf

# Ids that stand for one another: the Destruction Staff skills, whose cast
# id follows the staff's element (base, fire, frost, shock), and a skill
# slotted under either of two ids
SKILL_FAMILIES: tuple[frozenset[str], ...] = tuple(frozenset(family) for family in (
    ("39011", "39012", "39028", "39018"),   # Elemental Blockade; of Fire, Frost, Storms
    ("39052", "39053", "39067", "39073"),   # Unstable Wall of Elements
    ("28858", "28807", "28849", "28854"),   # Wall of Elements
    ("39161", "39162", "39163", "39167"),   # Pulsar; Flame, Frost, Storm
    ("39143", "39145", "39146", "39147"),   # Elemental Ring
    ("28800", "28794", "28798", "28799"),   # Impulse
    ("84434", "85126", "85128", "85130"),   # Elemental Rage; Fiery, Icy, Thunderous
    ("83642", "83682", "83684", "83686"),   # Eye of the Storm; of Flame, Frost, Lightning
    ("83619", "83625", "83628", "83630"),   # Elemental Storm; Fire, Ice, Thunder Storm
    ("29091", "29073", "29078", "29089"),   # Destructive Touch
    ("38984", "38985", "38989", "38993"),   # Destructive Clench
    ("38937", "38944", "38970", "38978"),   # Destructive Reach
    ("186366", "193398"),                   # Pragmatic Fatecarver
    ("183122", "193397"),                   # Exhausting Fatecarver
))
_FAMILY_OF = {ability_id: family for family in SKILL_FAMILIES for ability_id in family}

# Channel effects gained on the caster -> the skill cast, for a skill the
# log writes no BEGIN_CAST for
CHANNEL_EFFECTS: dict[str, str] = {
    "186369": "186366", "189533": "186366",   # Pragmatic Fatecarver
    "186780": "183122",                       # Exhausting Fatecarver
}

# Every "Light Attack (…)" and "Heavy Attack (…)" id of the client
LIGHT_ATTACKS = frozenset({
    "16688", "16499", "114773", "114774", "114775", "114776", "16277", "16165", "18350",
    "15435", "24792", "26111", "26112", "27786", "180983", "233817", "114769", "114770",
    "114771", "114772", "16145", "262294", "262295", "262296", "16037", "23604", "116762",
    "32464",
})
HEAVY_ATTACKS = frozenset({
    "16691", "17173", "17174", "60761", "16420", "17169", "17170", "18622", "60758",
    "114797", "114798", "114800", "132867", "16261", "18405", "18406", "60762", "15383",
    "15385", "16321", "60763", "18396", "19277", "60764", "15279", "15282", "15829",
    "60759", "24794", "24798", "119624", "132865", "208017", "24810", "24811", "28434",
    "132866", "16212", "32760", "67022", "262108", "262109", "16041", "17162", "17163",
    "60757", "18429", "18430", "18431", "60772", "233791", "233839", "233854", "233926",
    "116763", "116765", "116766", "116767", "32477", "32479", "32480", "32494", "60773",
    "161522",
})
BASHES = frozenset({"21970", "118720"})  # Bash; Pummeling Goliath's bash
SWAPS = frozenset({"28541", "61874", "61875"})  # Swap Weapons; to weapon set 1, 2
DODGES = frozenset({"28549"})  # Roll Dodge
BREAK_FREE = frozenset({"16565"})
SYNERGIES = frozenset({
    "63507", "95042",            # Healing Combustion (Necrotic Orb)
    "39301", "95040",            # Combustion (Necrotic Orb)
    "42038",                     # Energy Orb
    "41963", "39500",            # Blood Feast, Blood Funnel (Blood Altar)
    "41838",                     # Radiate (Inner Fire)
    "41990", "41994",            # Shadow Silk, Black Widow (Trapping Webs)
    "39377",                     # Bone Wall (Bone Shield)
    "22269",                     # Purify (Cleansing Ritual)
    "26832", "95922",            # Blessed Shards, Holy Shards (Spear Shards)
    "31538",                     # Supernova (Nova)
    "23196",                     # Conduit (Lightning Splash)
    "48076",                     # Charged Lightning (Summon Storm Atronach)
    "32910", "32974",            # Shackle (Dragonknight Standard), Ignite
    "37729",                     # Hidden Refresh (Consuming Darkness)
    "25170",                     # Soul Leech (Soul Shred)
    "85572",                     # Harvest (Healing Seed)
    "115548",                    # Grave Robber (Boneyard)
    "118604",                    # Pure Agony (Agony Totem)
    "191078",                    # Runebreak
    "58775",                     # Feeding Frenzy (werewolf Roar)
})
POTIONS = frozenset({
    "45221", "45382", "17302",            # Restore Health
    "45223", "17323", "72931",            # Restore Magicka
    "17328", "72934", "78053",            # Restore Stamina
    "68401",                              # Restore All Resources
    "45227", "45228", "45241", "47193",   # Major Brutality, Major Savagery
    "45233", "45234", "45235", "45239",   # resistance potions, Major Expedition, Unstoppable
    "125026", "125039",                   # Minor Heroism
    "45460",                              # Vanish
    "86682", "86692", "92414",            # Crown elixirs
})

# The extras line's kinds, in display order, with their sets
EXTRA_KINDS: tuple[tuple[str, frozenset], ...] = (
    ("light", LIGHT_ATTACKS), ("heavy", HEAVY_ATTACKS), ("bash", BASHES),
    ("swap", SWAPS), ("dodge", DODGES), ("synergy", SYNERGIES), ("potion", POTIONS),
    ("break_free", BREAK_FREE),
)

# A companion's own ids (companions.py): its light attacks, one per weapon
# look (casts in combat over the survey: 3,125, 2,255, 1,642, 1,374, 1,064,
# 427, 416 and 112), then its block, dodge, bash and break free
COMPANION_LIGHT_ATTACKS = frozenset({
    "157069", "157065", "154302", "154279", "154304", "155514", "157035", "154282",
})
COMPANION_BLOCKS = frozenset({"156219"})
COMPANION_DODGES = frozenset({"157039"})  # Roll Dodge
COMPANION_BASHES = frozenset({"157419"})
COMPANION_BREAK_FREE = frozenset({"156633"})  # CPN Break Free
# A companion's extras line's kinds, in display order
COMPANION_EXTRA_KINDS: tuple[tuple[str, frozenset], ...] = (
    ("light", COMPANION_LIGHT_ATTACKS), ("bash", COMPANION_BASHES),
    ("block", COMPANION_BLOCKS), ("dodge", COMPANION_DODGES),
    ("break_free", COMPANION_BREAK_FREE),
)
# The extras are presses by kind, never taken for procs (#226)
_EXTRA_IDS = frozenset().union(*(ids for _kind, ids in EXTRA_KINDS + COMPANION_EXTRA_KINDS))

# A cast as CastRecorder keeps it, by place: its time, ability id, target
# ((name, key) or None), END_CAST time (None until read) and flags
CAST_TIME, CAST_ABILITY, CAST_TARGET, CAST_END, CAST_FLAGS = range(5)
INTERRUPTED = 1  # a flag: the cast's END_CAST says INTERRUPTED
# What a BEGIN_CAST writes for a cast aimed at no other unit: '*' its
# caster, '0' none
_NO_TARGET = frozenset({"*", "0"})


def line_time(line: str) -> int:
    """A log line's time, its first field, in ms since BEGIN_LOG. The
    parser gives a BEGIN_CAST entry the timestamp 0, which other readers
    rely on (an encounter a cast opens starts at 0), so the cast's own time
    is read from its line; 0 when it has none."""
    head = (line or "").split(",", 1)[0]
    return int(head) if head.isdigit() else 0


def kind_of(ability_id: str) -> str | None:
    """The extras kind of a cast, None for any other."""
    return next((kind for kind, ids in EXTRA_KINDS if ability_id in ids), None)


def same_skill(slot_id: str, slot_name: str, cast_id: str, cast_name: str) -> bool:
    """Whether a cast is of the skill a bar slot holds: the same id, the
    same name, or one family of SKILL_FAMILIES. A werewolf morph's form
    effect, cast beside the ultimate under the ultimate's name, is not."""
    if cast_id == slot_id:
        return True
    if slot_name and cast_name == slot_name and cast_id not in werewolf.FORM_EFFECTS:
        return True
    family = _FAMILY_OF.get(slot_id)
    return family is not None and cast_id in family


class CastRecorder:
    """Each player's casts over a BEGIN_LOG session, one per castTrackId,
    until a fight's entry is built from them. Keyed by the player's record
    id in the encounter (CombatEncounter.player_of). See the module on a
    track id written again after its END_CAST: a synergy taken again, or a
    proc. Each cast keeps the unit it was aimed at and its END_CAST's time
    as well, for the Events tab's actions (fight_casts, issue #214)."""

    def __init__(self):
        # Each caster's casts in the order begun: [time, ability id,
        # target, END_CAST time, flags] (CAST_* above): the target the
        # (name, key) note_cast's target_of gave as the cast was noted, or
        # None; the END_CAST's time None until one is read
        self._casts: dict[str, list[list]] = defaultdict(list)
        # Each caster's tracks: track id -> (the last ability written under
        # it, that line's time); the track ids any caster holds; and each
        # of those tracks' last END_CAST time (the line names no caster)
        self._tracks: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
        self._held: set[str] = set()
        self._ended: dict[str, int] = {}
        # The cast each held track last began, until its END_CAST
        self._open: dict[str, list] = {}
        # Each caster's procs, for the session (see the module)
        self._procs: dict[str, set[str]] = defaultdict(set)

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart."""
        self._casts.clear()
        self._tracks.clear()
        self._held.clear()
        self._ended.clear()
        self._open.clear()
        self._procs.clear()

    def note_end(self, track_id: str, timestamp: int, reason: str = "") -> None:
        """An END_CAST (the line names the track, not the caster), kept
        for a track a caster here holds: the time the cast the track last
        began ended, and whether the line says it was INTERRUPTED. The
        parser rejects a PLAYER_CANCELLED one: that cast has no end."""
        if track_id in self._held:
            self._ended[track_id] = timestamp
            cast = self._open.pop(track_id, None)
            if cast is not None:
                cast[CAST_END] = timestamp
                if reason == "INTERRUPTED":
                    cast[CAST_FLAGS] |= INTERRUPTED

    def note_cast(self, key: str, track_id: str, ability_id: str, timestamp: int,
                  target_id: str = "", caster_id: str = "",
                  target_of: Callable[[str], tuple[str, str] | None] | None = None) -> None:
        """A BEGIN_CAST by the player. A second line under the same
        castTrackId is the same cast, unless it comes at a later
        millisecond after the track's END_CAST: then a synergy is taken
        again, a new cast, and the same ability again is a proc (never an
        extra: a light or heavy attack, a dodge, a potion is a press).
        *target_id* is the unit the line says the cast was aimed at ('*',
        '0' or the caster's own *caster_id* for none), which *target_of*
        names for a new cast only, as the engine resolves it then (unit ids
        are handed out again later): (name, key), or None for a unit it
        does not know; without *target_of* no target is kept."""
        tracks = self._tracks[key]
        held = tracks.get(track_id)
        tracks[track_id] = (ability_id, timestamp)
        if held is None:
            self._held.add(track_id)
            self._add(key, track_id, ability_id, timestamp, target_id, caster_id, target_of)
            return
        last_ability, last_at = held
        ended = self._ended.get(track_id)
        if ended is None or not last_at <= ended < timestamp:
            return  # a later line of the same cast
        if ability_id in SYNERGIES:
            self._add(key, track_id, ability_id, timestamp, target_id, caster_id, target_of)
        elif ability_id == last_ability and ability_id not in _EXTRA_IDS:
            self._procs[key].add(ability_id)

    def _add(self, key: str, track_id: str, ability_id: str, timestamp: int,
             target_id: str, caster_id: str, target_of) -> None:
        target = None
        if (target_of is not None and target_id and target_id not in _NO_TARGET
                and target_id != caster_id):
            target = target_of(target_id)
            if target is not None and target[1] == key:
                target = None  # the caster, back on another unit id
        cast = [timestamp, ability_id, target, None, 0]
        self._casts[key].append(cast)
        self._open[track_id] = cast

    def procs_of(self, key: str) -> frozenset:
        """The ability ids found to be the caster's procs this session."""
        return frozenset(self._procs.get(key, ()))

    def cast_records(self, key: str, start: int, end: int, slotted=()) -> list[list]:
        """Every cast begun from *start* to *end*, in the order cast, as
        the recorder keeps it ([time, ability id, target, END_CAST time,
        flags]), less the caster's procs that are not among the ability
        ids *slotted*, those of a skill on their bars (on_bars). The
        fight's counts are of these, and so are the casts its entry keeps
        (fight_casts)."""
        procs = self._procs.get(key)
        if procs:
            procs = procs - set(slotted)
        return [cast for cast in self._casts.get(key, ())
                if start <= cast[0] <= end and not (procs and cast[1] in procs)]

    def casts_between(self, key: str, start: int, end: int,
                      slotted=()) -> list[tuple[int, str]]:
        """(time, ability id) of every cast begun from *start* to *end*, in
        the order cast, procs left out as in cast_records. A death recap's
        casts are these (issue #214)."""
        return [(cast[0], cast[1]) for cast in self.cast_records(key, start, end, slotted)]

    def fight_counts(self, key: str, start: int, end: int, slotted=()) -> Counter:
        """Casts per ability id begun from *start* to *end*, procs left out
        as in casts_between."""
        return Counter(ability_id for _timestamp, ability_id
                       in self.casts_between(key, start, end, slotted))

    def fight_times(self, key: str, start: int, end: int, ability_ids,
                    slotted=()) -> list[tuple[int, str]]:
        """(time, ability id) of each cast of one of *ability_ids* begun
        from *start* to *end*, in the order cast (procs left out as in
        casts_between)."""
        return [(timestamp, ability_id) for timestamp, ability_id
                in self.casts_between(key, start, end, slotted) if ability_id in ability_ids]

    def prune_before(self, timestamp: int) -> None:
        """Forget the casts begun before *timestamp*, and the tracks last
        written before it. A track still written after it stays, so that a
        banner pressed in one fight and ticking on into the next is not
        cast again there. The procs found stay for the session."""
        for key in list(self._casts):
            kept = [cast for cast in self._casts[key] if cast[0] >= timestamp]
            if kept:
                self._casts[key] = kept
            else:
                del self._casts[key]
        for key in list(self._tracks):
            tracks = {track_id: held for track_id, held in self._tracks[key].items()
                      if held[1] >= timestamp}
            if tracks:
                self._tracks[key] = tracks
            else:
                del self._tracks[key]
        self._held = {track_id for tracks in self._tracks.values() for track_id in tracks}
        self._ended = {track_id: at for track_id, at in self._ended.items()
                       if track_id in self._held}
        self._open = {track_id: cast for track_id, cast in self._open.items()
                      if track_id in self._held}


def slot_holds(slot: dict, name_of: Callable[[str], str]) -> Callable[[str, str], bool]:
    """Whether a cast (id, name) is of the skill bar *slot* holds
    (same_skill), by any name the slot goes by: its own, its id's, or a
    stand-in's (a Rampage shown as its morph)."""
    slot_id = str(slot.get("id", ""))
    slot_names = {str(slot.get("name") or ""), name_of(slot_id) or "",
                  str(slot.get("stand_in") or "")} - {""}
    return lambda cast_id, cast_name: any(
        same_skill(slot_id, name, cast_id, cast_name) for name in slot_names or {""})


def mark_slot_casts(counts: Counter, bars: Iterable[list], name_of: Callable[[str], str]) -> None:
    """Set 'casts' on each slot dict of *bars* (front, back, werewolf) to
    the fight's casts of its skill (same_skill). A slot that is a stand-in
    (a Rampage shown as its morph) counts the casts of what the log listed
    as well."""
    names = {ability_id: name_of(ability_id) or "" for ability_id in counts}
    for bar in bars:
        for slot in bar or []:
            holds = slot_holds(slot, name_of)
            slot["casts"] = sum(n for cast_id, n in counts.items() if holds(cast_id, names[cast_id]))


def on_bars(ability_ids: Iterable[str], bars: Iterable[list],
            name_of: Callable[[str], str]) -> set:
    """The ids of *ability_ids* that are casts of a skill a slot of *bars*
    holds, as mark_slot_casts matches them (same_skill): a proc found on
    such an id is a press written again, which stays counted (Chakram of
    Destiny, slotted as 186207, is pressed as 194237 and pressed again on
    the same track)."""
    names = {ability_id: name_of(ability_id) or "" for ability_id in ability_ids}
    found = set()
    if not names:
        return found
    for bar in bars:
        for slot in bar or []:
            holds = slot_holds(slot, name_of)
            found.update(cast_id for cast_id, cast_name in names.items()
                         if holds(cast_id, cast_name))
    return found


def cast_summary(counts: Counter, duration_s: float, present_pct: float | None = None,
                 kinds: tuple[tuple[str, frozenset], ...] = EXTRA_KINDS) -> dict:
    """The fight entry's 'casts' for a player: 'total', 'cpm' (casts per
    minute over the fight, or the share of it a player who left was there
    for) and a count per extras kind of *kinds* (a companion's are
    COMPANION_EXTRA_KINDS)."""
    total = sum(counts.values())
    minutes = duration_s / 60.0
    if present_pct is not None:
        minutes *= max(0.0, min(100.0, float(present_pct))) / 100.0
    summary = {"total": total, "cpm": total / minutes if minutes > 0 else 0.0}
    for kind, ids in kinds:
        summary[kind] = sum(n for ability_id, n in counts.items() if ability_id in ids)
    return summary
