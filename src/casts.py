"""
Cast counts and casts per minute (engine side, no Qt). Issue #94.

Design: every player's BEGIN_CAST lines are in the log, the group's as well
as the logging player's. One cast can write two of them under one
castTrackId: a channelled heavy attack writes one at the press and one for
the channel (11 of 11 for a Lightning staff in the Tideborn Taleria fight
of 2026-10-27), and a synergy can write two ability ids (Healing
Combustion, 63507 then 95042, on the same timestamp). A cast is therefore
one castTrackId per caster, whatever the lines under it.

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
    "63507", "95042", "39301",   # Healing Combustion, Combustion (Necrotic Orb)
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
    id in the encounter (CombatEncounter.player_of)."""

    def __init__(self):
        self._casts: dict[str, list[tuple[int, str]]] = defaultdict(list)
        self._tracks: dict[str, set[str]] = defaultdict(set)

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart."""
        self._casts.clear()
        self._tracks.clear()

    def note_cast(self, key: str, track_id: str, ability_id: str, timestamp: int) -> None:
        """A BEGIN_CAST by the player; a second line under the same
        castTrackId is the same cast."""
        tracks = self._tracks[key]
        if track_id in tracks:
            return
        tracks.add(track_id)
        self._casts[key].append((timestamp, ability_id))

    def fight_counts(self, key: str, start: int, end: int) -> Counter:
        """Casts per ability id begun from *start* to *end*."""
        return Counter(ability_id for timestamp, ability_id in self._casts.get(key, ())
                       if start <= timestamp <= end)

    def fight_times(self, key: str, start: int, end: int, ability_ids) -> list[tuple[int, str]]:
        """(time, ability id) of each cast of one of *ability_ids* begun
        from *start* to *end*, in the order cast."""
        return [(timestamp, ability_id) for timestamp, ability_id in self._casts.get(key, ())
                if start <= timestamp <= end and ability_id in ability_ids]

    def prune_before(self, timestamp: int) -> None:
        """Forget the casts begun before *timestamp* (and the track ids,
        which only ever matter within a cast)."""
        for key in list(self._casts):
            kept = [cast for cast in self._casts[key] if cast[0] >= timestamp]
            if kept:
                self._casts[key] = kept
            else:
                del self._casts[key]
        self._tracks.clear()


def mark_slot_casts(counts: Counter, bars: Iterable[list], name_of: Callable[[str], str]) -> None:
    """Set 'casts' on each slot dict of *bars* (front, back, werewolf) to
    the fight's casts of its skill (same_skill). A slot that is a stand-in
    (a Rampage shown as its morph) counts the casts of what the log listed
    as well."""
    names = {ability_id: name_of(ability_id) or "" for ability_id in counts}
    for bar in bars:
        for slot in bar or []:
            slot_id = str(slot.get("id", ""))
            slot_names = {str(slot.get("name") or ""), name_of(slot_id) or "",
                          str(slot.get("stand_in") or "")} - {""}
            slot["casts"] = sum(n for cast_id, n in counts.items()
                                if any(same_skill(slot_id, name, cast_id, names[cast_id])
                                       for name in slot_names or {""}))


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
