"""
Penetration and critical damage: where each player's and the group's come
from, against the caps (issue #37). Engine side, no Qt.

Design. Two stats decide how much of a hit reaches a trial boss: Offensive
Penetration, which cancels the target's resistance (18,200 on the bosses
and mobs of dungeons, trials and arenas, 9,100 overland; a point past the
cap does nothing), and Critical Damage, 50% to begin with and capped at
125% (155% with the Nightblade mastery Above and Beyond). Raid leads check
both with a spreadsheet of checkboxes (LunaCairu's PenCrit Calc, and the
calculators at hyperioxes.com that skinnycheeks.gg recommends): every
source has a fixed value and they add up. This module does the sum from
the log, in two parts.

The player's own part is read from PLAYER_INFO: the passives in the
long-term list by id (Concentration 939 per light piece, Dexterity 2% per
medium piece, Hemorrhage 10%, Piercing Spear 12%, Fated Fortune 12%,
Advanced Species 5% per Animal Companions ability on the bar, Splintered
Secrets 1,240 per Herald of the Tome ability, Dismember 3,271, Feline
Ambush 12%, Hunter's Eye 950, Twin Blade and Blunt 6% per axe and 1,487
per mace, Heavy Weapons 12% for a battle axe and 2,974 for a maul, Blessing
at the Peak 10%, Above and Beyond 25%; every value is the game's own text
on UESP's skill tree, and a lower rank's id carries that rank's value), the
mundus boon with the Divines pieces that scale it (the Lover 2,744 and the
Shadow 11%, each piece of gold Divines adding 9.085%, rounded down as the
spreadsheet rounds), the sets at their worn piece counts
(data/sets/offense.json, generated from UESP's set texts by
scripts/generate_set_offense.py: "Adds 1487 Offensive Penetration",
Velothi's 1,650, Order's Wrath's 8%, Malacath's -50%), a Sharpened weapon,
and the weapon kinds and armor weights from the bundled item tables. A
value that depends on the bar (weapons, slotted abilities, set pieces with
a two-handed weapon) is kept per bar, so a total reads "14,095 / 11,121"
when the bars differ. A conditional bonus (Sul-Xan's 12% after a soul,
Stuhn's 5,312 against Off Balance, Dismember's 3,271 while a Grave Lord
ability is active) is listed with its condition and never added. A set
that gives a buff at all times (Medusa's or Velothi's Minor Force) is
credited with that buff for the whole fight: the game writes neither a
GAINED line nor a PLAYER_INFO entry for a mythic's permanent buff (four
trial logs: Velothi's aura 193447 on 917 PLAYER_INFO rows, Minor Force
61746 on none), so measuring it would read the other Minor Force sources
alone. A set that gives a buff under a condition (Tzogvin's at ten stacks)
is named as a possible source, and the buff measured like any other.

The group's part is what was on the target and on the player during the
fight, valued as Combat Metrics values the same debuffs (its StatDebuffs
table in CombatMetrics.lua): Major Breach 5,948, Minor Breach 2,974,
Crusher 2,108 (1,622 for the gold glyph, times 1.3 Infused, times 1.45
Torug's Pact, read from the caster's weapon), Roar of Alkosh 6,000, Crimson
Oath's Rive 3,541, Runic Sunder 2,200, Crystal Weapon 1,000, Tremorscale
2,640; Minor Brittle 10%, Major Brittle 20%, each Elemental Weakness 5%;
Major Force 20%, Minor Force 10%, Lucent Echoes 11%, Fated Fortune's 7 s
proc 12%. Combat Metrics adds those to the player's stat at every hit and
buckets the damage by the result, then shows the damage-weighted average
with each hit capped, the maximum, and the share of damage dealt over the
cap. The log has every hit with its time and target and every effect's
span on every unit, so the same is done here per second: for each second
and each target hit, the debuffs on that target (a fraction of the second
counts as that fraction) and the buffs on the player, times the damage
dealt that second, kept as a histogram of (penetration value, status
effects on the target, damage), so a reader can add any static part and
any cap and get the capped average (the effective figure) and the share
over the cap. In a fight with a boss only the bosses are measured; in a
trash fight every hostile hit.

Not in the log, and the reason the renderer adds "assumed" rows from the
Settings rather than this module: the Champion Point stars that only change
a stat. Four trial logs (2,292 PLAYER_INFO rows) never list Piercing (700
penetration), Fighting Finesse (8%), Deadly Aim or Master-at-Arms, and show
Backstabber (10% while flanking) only as 35 self-applied GAINED lines;
stars that are effects (Exploiter, Bulwark, Reaving Blows) are listed, so
the game simply has no effect for a stat star. Force of Nature (660
penetration per unique status effect on the target in Combat Metrics'
table, the star it calls wrathCP) is the same, but the status effects on
the target are logged (9,522 GAINED lines in one Sunspire log), so when the
reader assumes the star its value is the measured count of effects times
660. The Settings toggles only change the rendering, so a change needs no
engine restart and a fight entry holds nothing but what the log said.

What else the survey showed: Divines is the trait on 13,620 armor pieces
and no weapon of 2,292 builds is Sharpened; every Crusher glyph (302
weapons) is gold at CP 160; Fated Fortune's proc fired 2,374 times, so its
real uptime is measured, not assumed; the trial dummy applies the trial's
own debuffs to itself (Crusher 120007, Alkosh 120018, Breach 120010 and
120019, Minor Brittle, Elemental Catalyst), which is how a parse at a
dummy is known to be against 18,200 resistance in a house zone whose
difficulty reads NONE. It applies them once, as it spawns, and keeps them,
so a session begun after the spawn has no line for them and the log alone
would read the player's own penetration against an overland cap; a fight
against a unit named "Target Iron Atronach, Trial" therefore credits them
for the whole fight (TRIAL_DUMMY_DEBUFFS), as Combat Metrics reads them
from the game at the pull. Checked against a Combat Metrics report of a
25 s parse (2026-10-24): own penetration 3,126 (one light piece, Aerie's
Cry's two pieces, Piercing) plus the dummy's 17,030 is its maximum of
20,156 exactly, damage and dps agreed within 0.5%, and the ability table
row for row.

Solo dungeons and the Armour row (issue #55). The solo dungeons of October
2026 are the group dungeons' layouts and bosses at a zone id of their own,
with the dungeon's name and difficulty NONE on the ZONE_CHANGED line (the
solo March of Sacrifices is zone 1592, the group dungeon 1055, logged on
2026-10-25 and 2026-09-22); nothing else in the log says solo, and the
run's Misfortunes, picked at the door, did not appear in that log. Read by
difficulty alone a solo dungeon is overland, 9,100, so SOLO_DUNGEON_ZONES
names the ids and zone_kind reads it first; the figures are the
hyperioxes.com Moon Hunter Keep guide's: trash 18,200 like any instance,
bosses 27,300, the final boss 36,400, and the game's cap of 25,000 on an
enemy's armour, above which penetration changes nothing until the debuffs
bring the armour under. Every boss is taken at 27,300 (the maintainer's
choice, 2026-10-26); the labels say the final boss has more. The buff
timeline's Armour row (armour_row) draws the target's armour less the
group's armour debuffs on it, second by second, from a series fight_fields
keeps on the target the group damaged most: spans of equal debuff sum and
names, the sum rather than the remainder so the Settings' cap override
can restate the estimate. The remainder is averaged over time for the
label, where the build window's effective figures weigh each second by
the damage dealt; the two are different questions (how long the armour
was down, and how much of the damage met it down).
"""

import math
from collections.abc import Callable, Iterable
from functools import lru_cache

from effect_rules import PLAYER_KINDS, EffectTracker, Rule, group_size_class
from player_build import (
    ARMOR_SLOTS,
    OFF_HAND_OF,
    _load_json,
    armor_weight,
    is_two_handed,
    piece_counts,
    trait_label,
    weapon_type,
    weapon_type_label,
)

PEN_CAP_INSTANCED = 18200
PEN_CAP_OVERLAND = 9100
# Solo dungeons (October 2026): the group dungeons' layouts and bosses at
# a zone id of their own, with the dungeon's name and difficulty NONE on
# the ZONE_CHANGED line, which is the log's only marker (the solo March of
# Sacrifices is 1592, the group dungeon 1055). The figures are the
# hyperioxes.com Moon Hunter Keep guide's (October 2026): trash 18,200
# like any instance, bosses 27,300, the final boss 36,400 (Balorgh, Vykosa
# the Ascendant), and the game caps an enemy's armour at 25,000 (50%
# damage reduction), so against a boss the first 2,300 of penetration
# changes nothing until the debuffs bring the armour under the cap. Every
# boss is taken at 27,300 (the maintainer's choice, 2026-10-26): no
# per-boss table, the labels say the final boss has more. Moon Hunter
# Keep's solo zone id is in no log yet: read it off the ZONE_CHANGED line
# of a solo run and add it here.
SOLO_DUNGEON_ZONES = {"1592": "March of Sacrifices"}
SOLO_BOSS_ARMOUR = 27300
SOLO_FINAL_BOSS_ARMOUR = 36400
ENEMY_ARMOUR_CAP = 25000
ZONE_KINDS = ("solo_dungeon", "instanced", "overland")
ARMOUR_ROW = "Armour"  # the buff timeline's row name
CRIT_BASE = 50
CRIT_CAP = 125
DIVINES_PER_PIECE = 0.09085  # gold Divines, the spreadsheet's factor
GOLD_CRUSHER = 1622  # the gold CP 160 Glyph of Crushing
INFUSED_FACTOR = 1.3
TORUGS_PACT_SET_ID = "75"
TORUGS_FACTOR = 1.45
FORCE_OF_NATURE_PER_EFFECT = 660  # Combat Metrics' value per unique status effect
FRONT, BACK = 0, 1
BAR_NAMES = ("front", "back")

# Champion Point stars the log cannot show (see the module docstring): the
# renderer adds them from the Settings. 'group_sizes' says in which group
# sizes a star is assumed (effect_rules.group_size_class): Fighting Finesse
# in solo and small-group fights, not in a trial's large group, where a
# damage dealer's Warfare slots usually go elsewhere (Chris's choice,
# 2026-10-24, after his own trial parse read without it).
ASSUMED_STARS = {
    "piercing": {"name": "Piercing", "source": "Champion Point passive", "pen": 700},
    "fighting_finesse": {"name": "Fighting Finesse", "source": "Champion Point slottable",
                         "crit": 8, "group_sizes": ("solo", "small")},
    "backstabber": {"name": "Backstabber", "source": "Champion Point slottable, while flanking",
                    "crit": 10},
}

# PLAYER_INFO passive ids (every rank the list can carry) and what each
# gives. 'per' says what the value is counted by: light or medium armor
# pieces worn; one-handed axes and maces on the bar (Twin Blade and Blunt),
# a two-handed battle axe or maul (Heavy Weapons); Herald of the Tome or
# Animal Companions abilities slotted on the bar. 'when' marks a bonus the
# game applies under a condition the log cannot follow; 'measured' names
# the effect id of a proc whose uptime the group part measures instead.
PASSIVES: dict[str, dict] = {
    "45562": {"name": "Concentration", "source": "Light Armor passive", "pen": 939, "per": "light"},
    "29667": {"name": "Concentration", "source": "Light Armor passive, rank 1", "pen": 469, "per": "light"},
    "45564": {"name": "Dexterity", "source": "Medium Armor passive", "crit": 2.0, "per": "medium"},
    "45563": {"name": "Dexterity", "source": "Medium Armor passive, rank 2", "crit": 1.0, "per": "medium"},
    "29743": {"name": "Dexterity", "source": "Medium Armor passive, rank 1", "crit": 0.5, "per": "medium"},
    "45060": {"name": "Hemorrhage", "source": "Assassination passive", "crit": 10},
    "36641": {"name": "Hemorrhage", "source": "Assassination passive, rank 1", "crit": 5},
    "44046": {"name": "Piercing Spear", "source": "Aedric Spear passive", "crit": 12},
    "31698": {"name": "Piercing Spear", "source": "Aedric Spear passive, rank 1", "crit": 6},
    "184847": {"name": "Fated Fortune", "source": "Herald of the Tome passive, 7 s after a Crux change",
               "crit": 12, "measured": "194875"},
    "184844": {"name": "Fated Fortune", "source": "Herald of the Tome passive, rank 1",
               "crit": 6, "measured": "194875"},
    "86069": {"name": "Advanced Species", "source": "Animal Companions passive", "crit": 5, "per": "animal"},
    "86068": {"name": "Advanced Species", "source": "Animal Companions passive, rank 1", "crit": 2, "per": "animal"},
    "116194": {"name": "Dismember", "source": "Grave Lord passive", "pen": 3271,
               "when": "while a Grave Lord ability is active"},
    "116192": {"name": "Dismember", "source": "Grave Lord passive, rank 1", "pen": 1635,
               "when": "while a Grave Lord ability is active"},
    "184887": {"name": "Splintered Secrets", "source": "Herald of the Tome passive", "pen": 1240, "per": "herald"},
    "184885": {"name": "Splintered Secrets", "source": "Herald of the Tome passive, rank 1", "pen": 620, "per": "herald"},
    "45301": {"name": "Feline Ambush", "source": "Khajiit passive", "crit": 12},
    "45299": {"name": "Feline Ambush", "source": "Khajiit passive, rank 2", "crit": 8},
    "36067": {"name": "Feline Ambush", "source": "Khajiit passive, rank 1", "crit": 4},
    "45296": {"name": "Hunter's Eye", "source": "Wood Elf passive", "pen": 950},
    "45295": {"name": "Hunter's Eye", "source": "Wood Elf passive, rank 2", "pen": 600},
    "45430": {"name": "Heavy Weapons", "source": "Two Handed passive", "crit": 12, "pen": 2974, "per": "two_handed"},
    "29375": {"name": "Heavy Weapons", "source": "Two Handed passive, rank 1", "crit": 6, "pen": 1487, "per": "two_handed"},
    "45482": {"name": "Twin Blade and Blunt", "source": "Dual Wield passive", "crit": 6, "pen": 1487, "per": "one_handed"},
    "30893": {"name": "Twin Blade and Blunt", "source": "Dual Wield passive, rank 1", "crit": 3, "pen": 743, "per": "one_handed"},
    "45001": {"name": "Blessing at the Peak", "source": "Earthen Heart passive", "crit": 10},
    "29473": {"name": "Blessing at the Peak", "source": "Earthen Heart passive, rank 1", "crit": 5},
    "263605": {"name": "Above and Beyond", "source": "Class Mastery", "crit": 25, "crit_cap": 30},
}
MUNDUS = {"13981": ("The Lover", "pen", 2744), "13984": ("The Shadow", "crit", 11)}
SHARPENED = {"one_handed": 819, "two_handed": 1638}  # the gold trait

# ---- what the fight put on the targets and on the players ----
# (name, ids, penetration, critical damage %): Combat Metrics' values. The
# ids are every one the logs carry under that name (a skill-specific id
# such as Elemental Susceptibility's 62775 beside the generic 61743), the
# trial dummy's own among them.
DEBUFFS: tuple[tuple[str, tuple[str, ...], int, int], ...] = (
    ("Major Breach", ("61743", "117818", "62775", "40254", "48946", "62485", "36980",
                      "53881", "62787", "120010"), 5948, 0),
    ("Minor Breach", ("61742", "190180", "148803", "185910", "230694", "146908", "120019"), 2974, 0),
    ("Crusher", ("17906", "120007"), 2108, 0),
    ("Roar of Alkosh", ("76667", "120018"), 6000, 0),
    ("Crimson Oath's Rive", ("159288", "159287"), 3541, 0),
    ("Runic Sunder", ("187742",), 2200, 0),
    ("Crystal Weapon", ("143808",), 1000, 0),
    ("Tremorscale", ("80866",), 2640, 0),
    ("Minor Brittle", ("145975", "146697", "184986", "148977"), 0, 10),
    ("Major Brittle", ("145977", "263825", "167681"), 0, 20),
    ("Flame Weakness", ("142610",), 0, 5),
    ("Frost Weakness", ("142652",), 0, 5),
    ("Shock Weakness", ("142653",), 0, 5),
    ("Elemental Catalyst", ("181606",), 0, 15),  # the trial dummy's own three weaknesses
)
BUFFS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("Major Force", ("61747", "40225", "154830"), 20),
    ("Minor Force", ("61746", "68632", "188427", "103712", "103521", "103708"), 10),
    ("Lucent Echoes", ("220015",), 11),
    ("Fated Fortune", ("194875",), 12),
)
# The eight status effects, for Force of Nature (Combat Metrics' StatusEffectIds)
STATUS_EFFECTS = {"178118": "Overcharged", "18084": "Burning", "95136": "Chilled",
                  "95134": "Concussion", "178123": "Sundered", "21929": "Poisoned",
                  "178127": "Diseased", "148801": "Hemorrhaging"}
# The debuffs a trial dummy puts on itself: a parse, against 18,200
DUMMY_IDS = frozenset({"120007", "120018", "120010", "120019", "120030", "120011"})
# The Trial dummy puts a trial group's debuffs on itself once, as it spawns,
# and keeps them (a Dreadsail Reef log's eight spawns each wrote Crusher
# 120007, Alkosh 120018, Major Breach 120010, Minor Breach 120019, Minor
# Brittle 145975 and 148977 and Elemental Catalyst 181606 once, and never a
# FADED). A session begun after the spawn has no line for them, so a fight
# against a unit of this name credits them for the whole fight, as Combat
# Metrics reads them from the game at the pull
TRIAL_DUMMY_NAME = "Target Iron Atronach, Trial"
TRIAL_DUMMY_DEBUFFS = ("Major Breach", "Minor Breach", "Crusher", "Roar of Alkosh",
                       "Minor Brittle", "Elemental Catalyst")
TRIAL_DUMMY_VIA = "the dummy's own"
STATUS_PREFIX = "status:"

PEN_DEBUFFS = tuple(name for name, _ids, pen, _crit in DEBUFFS if pen)
CRIT_DEBUFFS = tuple(name for name, _ids, _pen, crit in DEBUFFS if crit)
_DEBUFF_VALUE = {name: (pen, crit) for name, _ids, pen, crit in DEBUFFS}
_BUFF_VALUE = {name: crit for name, _ids, crit in BUFFS}


def tracker_rules() -> list[Rule]:
    """The fixed rules the engine's pen/crit tracker runs: every debuff on
    any hostile, every buff on any player, and the status effects."""
    rules = [Rule(name, frozenset(ids), "enemies") for name, ids, _pen, _crit in DEBUFFS]
    rules.extend(Rule(name, frozenset(ids), "group") for name, ids, _crit in BUFFS)
    rules.extend(Rule(STATUS_PREFIX + name, frozenset({ability_id}), "enemies")
                 for ability_id, name in STATUS_EFFECTS.items())
    return rules


def new_tracker() -> EffectTracker:
    return EffectTracker(tracker_rules())


def pen_cap(instanced: bool, setting=None) -> int:
    """The target's resistance: 18,200 in instanced content or at a trial
    dummy, 9,100 overland; a numeric *setting* overrides both."""
    if isinstance(setting, (int, float)) and not isinstance(setting, bool) and setting > 0:
        return int(setting)
    if isinstance(setting, str) and setting.strip().isdigit():
        return int(setting.strip())
    return PEN_CAP_INSTANCED if instanced else PEN_CAP_OVERLAND


def zone_kind(zone_id, difficulty, dummy: bool = False) -> str:
    """What the zone says of its enemies' armour: 'solo_dungeon' for a solo
    dungeon's zone id (SOLO_DUNGEON_ZONES), 'instanced' when the difficulty
    is NORMAL or VETERAN or a trial dummy's own debuffs were seen (*dummy*),
    else 'overland'."""
    if str(zone_id or "") in SOLO_DUNGEON_ZONES:
        return "solo_dungeon"
    if dummy or str(difficulty or "").upper() in ("NORMAL", "VETERAN"):
        return "instanced"
    return "overland"


def target_armour(kind: str, boss: bool) -> int:
    """The resistance a target is taken to have: a solo dungeon's boss
    27,300 and its trash 18,200, instanced 18,200, overland 9,100."""
    if kind == "solo_dungeon":
        return SOLO_BOSS_ARMOUR if boss else PEN_CAP_INSTANCED
    return PEN_CAP_INSTANCED if kind == "instanced" else PEN_CAP_OVERLAND


# ---- the player's own sources ----

@lru_cache(maxsize=1)
def _bundled_offense() -> dict[str, dict]:
    table = _load_json("sets", "offense.json").get("sets")
    return {str(k): v for k, v in table.items() if isinstance(v, dict)} if isinstance(table, dict) else {}


def set_offense_table() -> dict[str, dict]:
    """set id -> {'name', 'bonuses': [...]} (see scripts/generate_set_offense.py)."""
    return _bundled_offense()


def _divines(gear: dict[str, list[str]]) -> int:
    return sum(1 for slot in ARMOR_SLOTS
               if len(gear.get(slot) or []) > 4 and str(gear[slot][4]) == "ARMOR_DIVINES")


def _weights(gear: dict[str, list[str]], weight_of: Callable[[str], str]) -> dict[str, int]:
    counts = {"light": 0, "medium": 0, "heavy": 0}
    for slot in ARMOR_SLOTS:
        item = gear.get(slot) or []
        if len(item) > 1:
            weight = weight_of(str(item[1]))
            if weight in counts:
                counts[weight] += 1
    return counts


def _bar_weapons(gear: dict[str, list[str]], kind_of: Callable[[str], str]):
    """Per bar: [(slot, item, kind, two_handed), ...] for the weapons logged."""
    bars = {FRONT: [], BACK: []}
    for main, off in OFF_HAND_OF.items():
        bar = FRONT if main == "MAIN_HAND" else BACK
        for slot in (main, off):
            item = gear.get(slot) or []
            if len(item) > 1 and str(item[1]) not in ("0", ""):
                two = slot == main and is_two_handed(slot, str(item[1]), gear)
                bars[bar].append((slot, item, kind_of(str(item[1])), two))
    return bars


def _slotted(names: Iterable[str], line: str) -> int:
    """How many of the bar's ability *names* belong to the class skill *line*."""
    from eso_sets import ESOSubclassAnalyzer
    known = set(ESOSubclassAnalyzer.SKILL_LINE_ABILITIES.get(line, ()))
    return sum(1 for name in names or () if str(name) in known)


def _row(name: str, source: str, kind: str, pen=None, crit=None, note: str = "",
         when: str | None = None, measured: str | None = None) -> dict:
    """A source row. pen and crit are per-bar pairs [front, back], None when
    the row gives none of that stat."""
    return {"name": name, "source": source, "kind": kind,
            "pen": list(pen) if pen is not None else None,
            "crit": list(crit) if crit is not None else None,
            "note": note, "when": when, "measured": measured}


def _pair(value) -> list:
    return [value, value]


def player_rows(gear: dict[str, list[str]], effect_ids: Iterable[str],
                front_bar: Iterable[str], back_bar: Iterable[str],
                set_table: dict[str, dict] | None = None,
                weight_of: Callable[[str], str] | None = None,
                kind_of: Callable[[str], str] | None = None) -> dict:
    """What the player's own build gives, from their PLAYER_INFO line.

    Returns {'rows': [...], 'static_pen': [front, back], 'static_crit':
    [front, back], 'crit_cap': cap, 'divines': n, 'weights': {...},
    'gives': {buff name: the set that gives it at all times}}. The static
    sums leave out rows with a condition ('when') and rows measured as a
    buff ('measured'). The lookups default to the bundled tables; tests
    pass their own."""
    gear = gear or {}
    effect_ids = {str(e) for e in effect_ids or ()}
    table = set_offense_table() if set_table is None else set_table
    weight_of = weight_of or armor_weight
    kind_of = kind_of or weapon_type
    rows: list[dict] = []
    gives: dict[str, str] = {}
    crit_cap = CRIT_CAP
    weights = _weights(gear, weight_of)
    divines = _divines(gear)
    bars = _bar_weapons(gear, kind_of)
    bar_names = (list(front_bar or ()), list(back_bar or ()))

    # Passives, one row per name (the highest rank listed wins)
    seen: dict[str, dict] = {}
    for ability_id in sorted(effect_ids, key=lambda i: int(i) if i.isdigit() else 0):
        passive = PASSIVES.get(ability_id)
        if passive is None:
            continue
        held = seen.get(passive["name"])
        if held is None or (passive.get("pen", 0), passive.get("crit", 0)) > (held.get("pen", 0), held.get("crit", 0)):
            seen[passive["name"]] = passive
    for passive in seen.values():
        per = passive.get("per")
        pen = passive.get("pen")
        crit = passive.get("crit")
        note = ""
        if per in ("light", "medium"):
            count = weights[per]
            if count == 0:
                continue
            note = f"{count} {per} piece{'s' if count != 1 else ''}"
            pen_pair = _pair(pen * count) if pen else None
            crit_pair = _pair(crit * count) if crit else None
        elif per in ("herald", "animal"):
            line = "Herald of the Tome" if per == "herald" else "Animal Companions"
            counts = [_slotted(names, line) for names in bar_names]
            if not any(counts):
                continue
            note = f"{counts[FRONT]}/{counts[BACK]} {line} abilities on the bars"
            pen_pair = [pen * c for c in counts] if pen else None
            crit_pair = [crit * c for c in counts] if crit else None
        elif per in ("one_handed", "two_handed"):
            axes, maces = [0, 0], [0, 0]
            for bar in (FRONT, BACK):
                for _slot, _item, kind, two in bars[bar]:
                    if per == "one_handed" and not two:
                        axes[bar] += kind == "axe"
                        maces[bar] += kind == "mace"
                    elif per == "two_handed" and two:
                        axes[bar] += kind == "battle_axe"
                        maces[bar] += kind == "maul"
            if not any(axes) and not any(maces):
                continue
            parts = []
            if any(axes):
                parts.append(f"{axes[FRONT]}/{axes[BACK]} {'battle axe' if per == 'two_handed' else 'axes'}")
            if any(maces):
                parts.append(f"{maces[FRONT]}/{maces[BACK]} {'maul' if per == 'two_handed' else 'maces'}")
            note = ", ".join(parts) + " on the bars"
            pen_pair = [pen * m for m in maces] if any(maces) else None
            crit_pair = [crit * a for a in axes] if any(axes) else None
        else:
            pen_pair = _pair(pen) if pen else None
            crit_pair = _pair(crit) if crit else None
        if passive.get("crit_cap"):
            crit_cap = CRIT_CAP + int(passive["crit_cap"])
            note = f"raises the critical damage cap to {crit_cap}%"
        rows.append(_row(passive["name"], passive["source"], "passive", pen_pair, crit_pair, note,
                         passive.get("when"), passive.get("measured")))

    # The mundus boon, scaled by the Divines pieces as the spreadsheet does
    for ability_id, (name, stat, base) in MUNDUS.items():
        if ability_id not in effect_ids:
            continue
        value = base + math.floor(DIVINES_PER_PIECE * base * divines)
        note = f"{divines} Divines piece{'s' if divines != 1 else ''}" if divines else "no Divines"
        rows.append(_row(name, "Mundus boon", "mundus",
                         _pair(value) if stat == "pen" else None,
                         _pair(value) if stat == "crit" else None, note))

    # Sets at their worn piece counts, per bar
    counts = piece_counts(gear)
    for set_id, pieces in sorted(counts.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        entry = table.get(str(set_id))
        if not entry:
            continue
        front_n = pieces[FRONT] or 0
        back_n = pieces[BACK] if pieces[BACK] is not None else front_n
        for bonus in entry.get("bonuses") or []:
            need = int(bonus.get("pieces") or 0)
            active = [front_n >= need, back_n >= need]
            if not any(active):
                continue
            label = f"{entry['name']} {need} piece{'s' if need != 1 else ''}"
            if "pen" in bonus or "crit" in bonus:
                pen = bonus.get("pen")
                crit = bonus.get("crit")
                rows.append(_row(label, "Set bonus", "set",
                                 [pen if on else 0 for on in active] if pen else None,
                                 [crit if on else 0 for on in active] if crit else None,
                                 bonus.get("note", "")))
            if bonus.get("gives"):
                for buff in bonus["gives"]:
                    gives.setdefault(buff, entry["name"])
                rows.append(_row(label, "Set bonus", "set", None, [0, 0],
                                 "gives " + ", ".join(bonus["gives"]) + " at all times (counted below)"))
            if bonus.get("gives_when"):
                rows.append(_row(label, "Set bonus", "set", None, [0, 0],
                                 "may give " + ", ".join(bonus["gives_when"]) + " (measured below)",
                                 when=bonus.get("when") or "under a condition"))
            if "pen_up_to" in bonus or "crit_up_to" in bonus:
                rows.append(_row(label, "Set bonus", "set",
                                 _pair(bonus["pen_up_to"]) if "pen_up_to" in bonus else None,
                                 _pair(bonus["crit_up_to"]) if "crit_up_to" in bonus else None,
                                 "", when=bonus.get("when") or "under a condition"))

    # Sharpened weapons, per bar
    for bar in (FRONT, BACK):
        for slot, item, kind, two in bars[bar]:
            if len(item) > 4 and str(item[4]) == "WEAPON_SHARPENED":
                value = SHARPENED["two_handed" if two else "one_handed"]
                pen = [0, 0]
                pen[bar] = value
                rows.append(_row("Sharpened", f"Weapon trait, {weapon_type_label(kind) or 'weapon'} ({BAR_NAMES[bar]} bar)",
                                 "trait", pen, None, "gold trait value"))

    static_pen = [0, 0]
    static_crit = [0.0, 0.0]
    for row in rows:
        if row["when"] or row["measured"]:
            continue
        for bar in (FRONT, BACK):
            if row["pen"]:
                static_pen[bar] += row["pen"][bar]
            if row["crit"]:
                static_crit[bar] += row["crit"][bar]
    return {"rows": rows, "static_pen": static_pen,
            "static_crit": [round(c, 1) for c in static_crit],
            "crit_cap": crit_cap, "divines": divines, "weights": weights, "gives": gives}


def crusher_weapons(gear: dict[str, list[str]], kind_of: Callable[[str], str] | None = None) -> list[dict]:
    """The caster's Crushing glyphs: [{'bar', 'slot', 'kind', 'infused',
    'torugs', 'value', 'label'}], strongest first. The value is the gold
    glyph's 1,622, times 1.3 on an Infused weapon, times 1.45 with Torug's
    Pact's five pieces on that bar (every glyph in the survey was gold)."""
    gear = gear or {}
    kind_of = kind_of or weapon_type
    counts = piece_counts(gear).get(TORUGS_PACT_SET_ID) or [0, None]
    out = []
    for bar, weapons in _bar_weapons(gear, kind_of).items():
        for slot, item, kind, _two in weapons:
            if len(item) < 8 or str(item[7]) != "REDUCE_ARMOR":
                continue
            infused = str(item[4]) == "WEAPON_INFUSED"
            pieces = counts[bar] if counts[bar] is not None else (counts[FRONT] or 0)
            torugs = (pieces or 0) >= 5
            value = GOLD_CRUSHER
            if infused:
                value = int(value * INFUSED_FACTOR)
            if torugs:
                value = int(value * TORUGS_FACTOR)
            parts = ["Infused" if infused else trait_label(str(item[4])) or "", weapon_type_label(kind) or "weapon"]
            label = " ".join(p for p in parts if p) + f" ({BAR_NAMES[bar]} bar)"
            if torugs:
                label += ", Torug's Pact"
            out.append({"bar": bar, "slot": slot, "kind": kind, "infused": infused,
                        "torugs": torugs, "value": value, "label": label})
    out.sort(key=lambda w: -w["value"])
    return out


def caster_source(gear: dict[str, list[str]], debuff: str,
                  set_table: dict[str, dict] | None = None,
                  kind_of: Callable[[str], str] | None = None) -> tuple[str, int | None]:
    """How the caster's build applies *debuff*: ('Infused Inferno Staff (back
    bar)', 2108) for Crusher, ('Roar of Alkosh', None) for a set that
    provides it, ('', None) when the build does not say."""
    if debuff == "Crusher":
        glyphs = crusher_weapons(gear, kind_of)
        if glyphs:
            return glyphs[0]["label"], glyphs[0]["value"]
        return "", None
    table = set_offense_table() if set_table is None else set_table
    counts = piece_counts(gear or {})
    wanted = "Elemental Weakness" if debuff.endswith("Weakness") else debuff
    for set_id, pieces in counts.items():
        entry = table.get(str(set_id))
        if not entry:
            continue
        worn = max(pieces[FRONT] or 0, pieces[BACK] or 0)
        for bonus in entry.get("bonuses") or []:
            if wanted in (bonus.get("provides") or []) and worn >= int(bonus.get("pieces") or 0):
                return entry["name"], None
    return "", None


# ---- the fight's effects, per second, weighted by damage ----

def _union(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if end <= start:
            continue
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _coverage(spans: Iterable[tuple[int, int]]) -> dict[int, float]:
    """log second -> the fraction of it the union of *spans* covers."""
    cov: dict[int, float] = {}
    for start, end in _union(spans):
        first, last = start // 1000, (end - 1) // 1000
        for second in range(first, last + 1):
            lo, hi = second * 1000, second * 1000 + 1000
            cov[second] = min(1.0, cov.get(second, 0.0) + (min(end, hi) - max(start, lo)) / 1000.0)
    return cov


def _union_ms(spans: Iterable[tuple[int, int]]) -> int:
    return sum(end - start for start, end in _union(spans))


def _pct(ms: int, duration_ms: int) -> int:
    return round(100.0 * ms / duration_ms) if duration_ms > 0 else 0


def _histogram(keys_damage: dict[tuple, int]) -> list[list]:
    return [[*key, damage] for key, damage in sorted(keys_damage.items())]


def fight_fields(tracker: EffectTracker, start_ms: int, end_ms: int,
                 units: dict[str, tuple], group_target_buckets: dict[str, dict[int, int]],
                 player_target_buckets: dict[str, dict[str, dict[int, int]]],
                 name_of: Callable[[str], str], gear_of: Callable[[str], dict[str, list[str]]],
                 zone: str = "overland", dummy: bool = False,
                 set_table: dict[str, dict] | None = None,
                 kind_of: Callable[[str], str] | None = None,
                 always_on: dict[str, dict[str, str]] | None = None,
                 permanent_debuffs: dict[str, list[str]] | None = None) -> tuple[dict, dict[str, dict]]:
    """The fight's group-provided penetration and critical damage.

    *units* is the engine's fight_units(); *group_target_buckets* the group's
    damage per log second per target unit, *player_target_buckets* the same
    per player; *gear_of* a caster's gear for the Crusher value and the set
    behind a debuff; *zone* the zone's kind (zone_kind: 'solo_dungeon',
    'instanced' or 'overland'), *dummy* whether a trial dummy's own debuffs
    were seen (an instance whatever the zone says); *always_on* the buffs a
    player's sets give at all times, player id -> {buff name: set name}
    (player_rows' 'gives'), credited for the whole fight;
    *permanent_debuffs* the debuffs a target keeps on itself for good,
    target unit id -> [debuff names] (the Trial dummy's,
    TRIAL_DUMMY_DEBUFFS), credited at 100% whether or not the session saw
    them applied. Returns the entry's dict ('on': 'boss' or 'enemies',
    'kind', 'cap' (the target's armour, target_armour), 'instanced',
    'dummy', 'debuffs' rows with uptime and casters, 'pen_hist'
    [[penetration, status effects, damage], ...], 'crit_hist' [[crit %,
    damage], ...], 'damage', and 'armour', the timeline row's series on the
    most-damaged target: {'estimate', 'kind', 'target', 'boss',
    'final_boss_armour', 'game_cap', 'spans': [[start_ms, end_ms, armour
    debuffs' sum, 'Major Breach, Crusher'], ...]} fight-relative, one span
    per run of seconds with the same sum and debuffs, None without a
    target) and one dict per player ('buffs' rows, their own 'pen_hist' and
    'crit_hist' with their buffs folded in, 'damage')."""
    duration = max(0, end_ms - start_ms)
    index_of = {rule.name: i for i, rule in enumerate(tracker.rules)}
    bosses = [u for u, info in units.items() if info[0] == "boss"]
    targets = bosses or [u for u, info in units.items() if info[0] == "enemy"]
    target_set = set(targets)
    kind = "instanced" if dummy and zone != "solo_dungeon" else (zone or "overland")
    cap = target_armour(kind, bool(bosses))

    def spans_of(name: str, want_targets: set | None) -> list[tuple]:
        index = index_of.get(name)
        if index is None:
            return []
        return [span for span in tracker.spans_in(index, start_ms, end_ms)
                if want_targets is None or span[3] in want_targets]

    # Each debuff's weighted value per target per second, and its row
    pen_by_target: dict[str, dict[int, float]] = {t: {} for t in targets}
    crit_by_target: dict[str, dict[int, float]] = {t: {} for t in targets}
    status_by_target: dict[str, dict[int, float]] = {t: {} for t in targets}
    # The armour debuffs covering at least half of each second, for the
    # timeline row's hover text
    names_by_target: dict[str, dict[int, set]] = {t: {} for t in targets}
    debuff_rows: list[dict] = []
    crusher_value: dict[str, int] = {}
    permanent_debuffs = permanent_debuffs or {}
    perm_pen: dict[str, float] = {}  # a target's permanent debuffs, summed
    perm_crit: dict[str, float] = {}
    for name, _ids, pen, crit in DEBUFFS:
        # A debuff a target keeps for good counts in full there, and what
        # the log shows of it on that target (another player's refresh of
        # the same debuff) adds nothing
        permanent_on = [t for t in targets if name in permanent_debuffs.get(t, ())]
        spans = [s for s in spans_of(name, target_set) if s[3] not in permanent_on]
        if not spans and not permanent_on:
            continue
        for target in permanent_on:
            perm_pen[target] = perm_pen.get(target, 0.0) + pen
            perm_crit[target] = perm_crit.get(target, 0.0) + crit
        by_source: dict[str, list] = {}
        for span in spans:
            by_source.setdefault(str(span[5] or ""), []).append(span)
        casters = [{"name": name_of(t), "pct": 100, "via": TRIAL_DUMMY_VIA, "value": pen or None}
                   for t in permanent_on]
        for source, own in sorted(by_source.items(), key=lambda kv: -_union_ms((s[0], s[1]) for s in kv[1])):
            via, value = caster_source(gear_of(source) if source else {}, name, set_table, kind_of)
            if name == "Crusher" and value:
                crusher_value[source] = value
            casters.append({"name": name_of(source) if source else "unknown",
                            "pct": _pct(_union_ms((s[0], s[1]) for s in own), duration),
                            "via": via, "value": value})
        row_value = max(crusher_value.values()) if name == "Crusher" and crusher_value else pen
        for target in targets:
            own = [s for s in spans if s[3] == target]
            if not own:
                continue
            if name == "Crusher" and crusher_value:
                # One caster's glyph at a time: the strongest covering the second
                weighted: dict[int, float] = {}
                for source, source_spans in by_source.items():
                    value = crusher_value.get(source, pen)
                    for second, frac in _coverage((s[0], s[1]) for s in source_spans if s[3] == target).items():
                        weighted[second] = max(weighted.get(second, 0.0), value * frac)
                        if frac >= 0.5:
                            names_by_target[target].setdefault(second, set()).add(name)
                for second, value in weighted.items():
                    pen_by_target[target][second] = pen_by_target[target].get(second, 0.0) + value
                continue
            for second, frac in _coverage((s[0], s[1]) for s in own).items():
                if pen:
                    pen_by_target[target][second] = pen_by_target[target].get(second, 0.0) + pen * frac
                    if frac >= 0.5:
                        names_by_target[target].setdefault(second, set()).add(name)
                if crit:
                    crit_by_target[target][second] = crit_by_target[target].get(second, 0.0) + crit * frac
        debuff_rows.append({"name": name, "pen": row_value if pen else 0, "crit": crit,
                            "uptime_pct": (100 if permanent_on
                                           else _pct(_union_ms((s[0], s[1]) for s in spans), duration)),
                            "casters": casters})
    for status in STATUS_EFFECTS.values():
        for target in targets:
            own = [s for s in spans_of(STATUS_PREFIX + status, {target})]
            for second, frac in _coverage((s[0], s[1]) for s in own).items():
                status_by_target[target][second] = status_by_target[target].get(second, 0.0) + frac

    def histograms(buckets_by_target: dict[str, dict[int, int]],
                   player_crit: dict[int, float] | None,
                   permanent_crit: float = 0.0) -> tuple[list[list], list[list], int]:
        pen_keys: dict[tuple, int] = {}
        crit_keys: dict[tuple, int] = {}
        total = 0
        for target in targets:
            for second, damage in (buckets_by_target.get(target) or {}).items():
                if damage <= 0:
                    continue
                total += damage
                g_pen = round(pen_by_target[target].get(second, 0.0) + perm_pen.get(target, 0.0))
                status = round(status_by_target[target].get(second, 0.0), 1)
                g_crit = (crit_by_target[target].get(second, 0.0) + perm_crit.get(target, 0.0)
                          + permanent_crit)
                if player_crit:
                    g_crit += player_crit.get(second, 0.0)
                pen_keys[(g_pen, status)] = pen_keys.get((g_pen, status), 0) + damage
                key = (round(g_crit),)
                crit_keys[key] = crit_keys.get(key, 0) + damage
        return _histogram(pen_keys), _histogram(crit_keys), total

    pen_hist, crit_hist, total = histograms(group_target_buckets, None)
    # The fight's group size, for the Champion Point rows assumed per size
    group_size = group_size_class(sum(1 for info in units.values() if info[0] in PLAYER_KINDS))
    # The timeline row's series: the armour debuffs on the target the group
    # damaged most, second by second (issue #55)
    armour = None
    if targets:
        main = max(targets, key=lambda t: (sum((group_target_buckets.get(t) or {}).values()), t))
        permanent_names = [n for n in PEN_DEBUFFS if n in permanent_debuffs.get(main, ())]
        armour = {"estimate": cap, "kind": kind, "target": name_of(main), "boss": main in bosses,
                  "final_boss_armour": (SOLO_FINAL_BOSS_ARMOUR
                                        if kind == "solo_dungeon" and bosses else None),
                  "game_cap": ENEMY_ARMOUR_CAP,
                  "spans": _armour_spans(start_ms, end_ms, pen_by_target[main], names_by_target[main],
                                         perm_pen.get(main, 0.0), permanent_names)}
    entry = {"on": ("boss" if bosses else "enemies") if targets else "", "targets": len(targets),
             "kind": kind, "cap": cap, "instanced": kind != "overland", "dummy": bool(dummy),
             "group_size": group_size,
             "debuffs": debuff_rows, "pen_hist": pen_hist, "crit_hist": crit_hist, "damage": total,
             "armour": armour}

    players: dict[str, dict] = {}
    for player_id, buckets in player_target_buckets.items():
        buff_rows = []
        own_crit: dict[int, float] = {}
        permanent = (always_on or {}).get(player_id) or {}
        permanent_crit = 0.0
        for name, _ids, crit in BUFFS:
            if name in permanent:
                # A set gives it at all times: the whole fight, whatever
                # the log shows of other sources of the same buff
                permanent_crit += crit
                buff_rows.append({"name": name, "crit": crit, "uptime_pct": 100,
                                  "via": f"{permanent[name]} at all times"})
                continue
            spans = spans_of(name, {player_id})
            if not spans:
                continue
            for second, frac in _coverage((s[0], s[1]) for s in spans).items():
                own_crit[second] = own_crit.get(second, 0.0) + crit * frac
            buff_rows.append({"name": name, "crit": crit,
                              "uptime_pct": _pct(_union_ms((s[0], s[1]) for s in spans), duration)})
        p_pen, p_crit, p_total = histograms(buckets, own_crit, permanent_crit)
        players[player_id] = {"buffs": buff_rows, "pen_hist": p_pen, "crit_hist": p_crit, "damage": p_total}
    return entry, players


def _armour_spans(start_ms: int, end_ms: int, pen_by_second: dict[int, float],
                  names_by_second: dict[int, set], permanent: float,
                  permanent_names: list[str]) -> list[list]:
    """The armour debuffs on one target through the fight as spans
    [start_ms, end_ms, sum, 'Major Breach, Crusher'] (fight-relative ms, the
    sum rounded, the names in DEBUFFS order), one per run of seconds with
    the same sum and the same debuffs; a second with none is a span with 0
    and ''. The fight's first and last seconds are clipped to its window."""
    spans: list[list] = []
    if end_ms <= start_ms:
        return spans
    first, last = start_ms // 1000, (end_ms - 1) // 1000
    for second in range(first, last + 1):
        value = round(pen_by_second.get(second, 0.0) + permanent)
        present = names_by_second.get(second, ())
        names = ", ".join(n for n in PEN_DEBUFFS if n in present or n in permanent_names)
        s = max(start_ms, second * 1000) - start_ms
        e = min(end_ms, second * 1000 + 1000) - start_ms
        if e <= s:
            continue
        if spans and spans[-1][1] == s and spans[-1][2] == value and spans[-1][3] == names:
            spans[-1][1] = e
        else:
            spans.append([s, e, value, names])
    return spans


# ---- the timeline's Armour row ----

_ZONE_EXPLAIN = {
    "overland": "Overland enemies have 9,100 armour.",
    "instanced": "The bosses and mobs of dungeons, trials and arenas have 18,200 armour.",
    "dummy": "A trial dummy has a trial boss's 18,200 armour.",
    "solo_boss": ("A solo dungeon's bosses have 27,300 armour and its final boss 36,400, so "
                  "the estimate is low on the final boss; the game caps an enemy's armour at "
                  "25,000, and nothing above the line counts until the debuffs bring it under."),
    "solo_trash": "A solo dungeon's trash has 18,200 armour, like any instance's.",
}
_ROW_EXPLAIN = ("The bar is the armour left after the group's armour debuffs each second, "
                "averaged over time; the build window's effective figures weigh each second "
                "by the damage dealt instead.")


def armour_row(group: dict | None, options: dict | None = None) -> dict | None:
    """The buff timeline's Armour row for a fight entry's group part
    (fight_fields' 'armour'): the estimate (the fight's target armour, or
    the Settings' cap override when it is a number), a label 'Armour 18,200
    · 9,400 left' with the time-averaged remainder, the scope word
    ('boss' or 'mobs'), intervals shaped like a stacking rule's with
    'stacks' the armour left that second plus 'debuff_pen' and 'debuffs'
    for the hover, 'stacks_max' the estimate, 'game_cap' 25,000 when the
    estimate is above it (a line on the row), the summary figures
    ('average_left', 'lowest_left', 'no_debuff_pct') and 'explain', the
    reason for the estimate. None for an entry without the series."""
    group = group or {}
    data = group.get("armour")
    if not data or not data.get("spans"):
        return None
    options = options or {}
    setting = options.get("cap", "auto")
    overridden = setting not in (None, "", "auto")
    estimate = pen_cap(True, setting) if overridden else int(data.get("estimate") or 0)
    if estimate <= 0:
        return None
    intervals = []
    duration = 0
    left_ms = 0.0
    lowest = estimate
    no_debuff_ms = 0
    target = str(data.get("target") or "")
    for s, e, value, names in data["spans"]:
        s, e, value = int(s), int(e), int(value)
        remaining = max(0, estimate - value)
        intervals.append({"start_ms": s, "end_ms": e, "stacks": remaining, "debuff_pen": value,
                          "debuffs": str(names or ""), "target": target, "source": ""})
        duration = max(duration, e)
        left_ms += remaining * (e - s)
        lowest = min(lowest, remaining)
        if not value:
            no_debuff_ms += e - s
    average = round(left_ms / duration) if duration else estimate
    kind = str(data.get("kind") or ("instanced" if group.get("instanced") else "overland"))
    boss = bool(data.get("boss"))
    if overridden:
        reason = f"The estimate is the Settings' penetration cap, {estimate:,}."
    elif group.get("dummy"):
        reason = _ZONE_EXPLAIN["dummy"]
    elif kind == "solo_dungeon":
        reason = _ZONE_EXPLAIN["solo_boss" if boss else "solo_trash"]
    else:
        reason = _ZONE_EXPLAIN.get(kind, _ZONE_EXPLAIN["overland"])
    return {"name": ARMOUR_ROW, "estimate": estimate,
            # Short enough for the strip's label column: the hover and the
            # click say the figure is an estimate and why
            "label": f"{ARMOUR_ROW} {estimate:,} · {average:,} left",
            "scope": "boss" if boss else "mobs", "intervals": intervals, "stacks_max": estimate,
            "game_cap": ENEMY_ARMOUR_CAP if estimate > ENEMY_ARMOUR_CAP else None,
            "average_left": average, "lowest_left": lowest,
            "no_debuff_pct": round(100.0 * no_debuff_ms / duration) if duration else 100,
            "kind": kind, "target": target, "final_boss_armour": data.get("final_boss_armour"),
            "explain": f"{reason} {_ROW_EXPLAIN}"}


# ---- reading the histograms, with any static part and cap ----

def effective_pen(pen_hist: list[list], static: float, cap: int,
                  per_status: float = 0.0) -> dict:
    """Damage-weighted figures from a penetration histogram: 'effective'
    (each second capped), 'average' (uncapped), 'over_pct' (share of damage
    dealt over the cap), 'status' (mean status effects on the target),
    'damage'. Combat Metrics' row 5 and row 6."""
    total = capped = raw = over = status_sum = 0.0
    for g, status, damage in pen_hist:
        value = static + g + per_status * status
        total += damage
        capped += min(value, cap) * damage
        raw += value * damage
        status_sum += status * damage
        if value > cap:
            over += damage
    if total <= 0:
        return {"effective": None, "average": None, "over_pct": None, "status": 0.0, "damage": 0}
    return {"effective": capped / total, "average": raw / total,
            "over_pct": 100.0 * over / total, "status": status_sum / total, "damage": int(total)}


def effective_crit(crit_hist: list[list], static: float, cap: int) -> dict:
    """The same for critical damage, *static* being the base 50 plus the
    player's own rows."""
    total = capped = raw = over = 0.0
    for g, damage in crit_hist:
        value = static + g
        total += damage
        capped += min(value, cap) * damage
        raw += value * damage
        if value > cap:
            over += damage
    if total <= 0:
        return {"effective": None, "average": None, "over_pct": None, "damage": 0}
    return {"effective": capped / total, "average": raw / total,
            "over_pct": 100.0 * over / total, "damage": int(total)}


def player_totals(player_pc: dict | None, fight_pc: dict | None,
                  options: dict | None) -> dict | None:
    """A player's figures with the Settings applied, for any reader: the
    assumed Champion Point rows, the static sums per bar with them added,
    the caps, Force of Nature's per-effect value, and the effective figures
    over the player's damage ('pen' and 'crit', see effective_pen and
    effective_crit, computed on the front bar's static part). None when the
    entry carries no figures at all (one built before them)."""
    data = player_pc or {}
    group = fight_pc or {}
    if not data and not group:
        return None
    options = dict(options or {})
    instanced = bool(group.get("instanced"))
    cap_setting = options.get("cap", "auto")
    if cap_setting in (None, "", "auto"):
        # The fight's own figure (a solo dungeon's boss 27,300; every entry
        # carries it), the zone's when an entry predates it
        cap = int(group.get("cap") or pen_cap(instanced))
    else:
        cap = pen_cap(instanced, cap_setting)
    crit_cap = int(data.get("crit_cap") or CRIT_CAP)
    assumed = assumed_rows(options, instanced, group.get("group_size"))
    static_pen = [float(v) for v in (data.get("static_pen") or [0, 0])]
    static_crit = [float(v) for v in (data.get("static_crit") or [0, 0])]
    for row in assumed:
        for bar in (FRONT, BACK):
            static_pen[bar] += (row.get("pen") or [0, 0])[bar]
            static_crit[bar] += (row.get("crit") or [0, 0])[bar]
    per_status = (float(options.get("force_of_nature_per_effect") or FORCE_OF_NATURE_PER_EFFECT)
                  if options.get("force_of_nature") else 0.0)
    pen = effective_pen(data.get("pen_hist") or [], static_pen[FRONT], cap, per_status)
    crit = effective_crit(data.get("crit_hist") or [], CRIT_BASE + static_crit[FRONT], crit_cap)
    return {"assumed": assumed, "static_pen": static_pen, "static_crit": static_crit,
            "cap": cap, "crit_cap": crit_cap, "per_status": per_status, "instanced": instanced,
            "pen": pen, "crit": crit}


def cap_shares(player_pc: dict | None, fight_pc: dict | None, options: dict | None) -> dict | None:
    """The figures a player's row shows: how much of each cap their effective
    penetration and critical damage reached over this fight's damage, as
    whole percentages ('pen_pct', 'crit_pct', never above 100 since each
    second is capped), with the figures behind them ('pen', 'pen_cap',
    'pen_over_pct', 'crit', 'crit_cap', 'crit_over_pct'). None for a player
    with no damage to weigh, or an entry without the figures."""
    totals = player_totals(player_pc, fight_pc, options)
    if totals is None or not totals["pen"].get("damage"):
        return None
    pen, crit = totals["pen"], totals["crit"]
    return {"pen_pct": round(100.0 * pen["effective"] / totals["cap"]) if totals["cap"] else 0,
            "crit_pct": round(100.0 * crit["effective"] / totals["crit_cap"]),
            "pen": pen["effective"], "pen_cap": totals["cap"], "pen_over_pct": pen["over_pct"],
            "crit": crit["effective"], "crit_cap": totals["crit_cap"],
            "crit_over_pct": crit["over_pct"]}


def assumed_rows(options: dict | None, instanced: bool, group_size: str | None = None) -> list[dict]:
    """The Champion Point rows the Settings ask for, as source rows marked
    assumed; Force of Nature is handled by the reader from the histogram.
    *group_size* is the fight's ('solo', 'small', 'large' or None when
    unknown, which assumes): a star with 'group_sizes' is left out in the
    others. *instanced* is kept for a star that may one day need it."""
    options = options or {}
    rows = []
    for key, star in ASSUMED_STARS.items():
        if not options.get(key):
            continue
        sizes = star.get("group_sizes")
        if sizes and group_size is not None and group_size not in sizes:
            continue
        row = _row(star["name"], star["source"], "assumed",
                   _pair(star["pen"]) if star.get("pen") else None,
                   _pair(star["crit"]) if star.get("crit") else None, "assumed, not in the log")
        rows.append(row)
    return rows
