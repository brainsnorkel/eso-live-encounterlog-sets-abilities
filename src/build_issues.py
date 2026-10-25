"""
Possible build issues: what a player's logged build and their fights say
about likely mistakes, shown behind an (i) on their row of the fight pane
and repeated in the build window (engine side, no Qt). Issue #16.

Design: a finding is something the log proves about the build the player
pulled with, and every finding carries the rule it comes from in plain
words, so the reader learns the rule from the finding. The rules are the
maintainer's (decided 2026-10-24), checked against 83 split logs of
September and October 2026 (1,615 fights, 13,998 player-fights, 393
characters); with them, 17% of the characters seen would carry a note. Per
rule, player-fights / distinct characters in that survey:

- **Nirnhoned on an off-hand weapon** (429 / 17, every one a DPS; the
  classic form is a Precise main hand beside a Nirnhoned off hand). The
  trait raises the damage of the weapon it is on, and UESP's Dual Wield
  page gives Dual Wield Expert as Weapon and Spell Damage equal to 6% of
  the off-hand weapon's damage, so an off-hand Nirnhoned is worth about a
  sixteenth of a main-hand one. A shield's Nirnhoned (ARMOR_NIRNHONED, 4
  tank fights) is the armor trait and is not reported.
- **The same glyph on both weapons of a bar** (421 / 22: Absorb Stamina,
  Berserker, Poisoned, Weakening, Absorb Health), whatever the glyph.
  Identical glyphs share one cooldown: measured on every dual-wield front
  bar of those logs, the same glyph from one player never fired twice
  within 4.0 s whether the bar carried it once or twice, and the proc rate
  was the same (Absorb Stamina 6.0 against 6.5 per minute, Poisoned 6.2
  against 7.2, Berserker 9 s gaps either way), so the second glyph never
  fires. The same glyph on both bars (112 / 7: a tank's Hardening or
  Crusher on both bars, Berserker on both bars of a DPS) is not reported:
  with a cooldown twice the buff's duration, a copy on the other bar fills
  the gap after a swap.
- **Two or more heavy armor pieces on a damage dealer** (218 / 9; five or
  more 103 / 4). Heavy Armor's passives add nothing to damage. One heavy
  piece is the usual Undaunted Mettle split (618 of 8,766 DPS
  player-fights) and is not reported. The role is the app's heuristic
  (infer_player_role), which reads the dominant resource, so a
  health-stacked DPS reads as a tank and a stamina-heavy fake tank as a
  DPS: 363 "tank" player-fights wore no heavy at all. The rule therefore
  asks for the DPS role and that the player has not taunted this session.
- **A weapon skill on a bar holding another weapon** (235 / 14 with the
  bar in use; Stampede left on a staff back bar is the commonest). The
  skill's line comes from the bundled weapon_skill_lines.json (UESP's
  player skill table, scripts/generate_weapon_skill_lines.py), or from the
  grimoire a scribed skill's icon names; the bar's line from the weapon
  types of its two slots. The back bar under Oakensoul Ring (set 658; 55
  more player-fights) is skipped, since the ring forbids swapping, and a
  bar whose weapon the bundled table does not know is not judged.
- **Elemental Drain** (124 / 5: tanks 69, healers 50, DPS 5, all in
  trials), per player, the maintainer's decision. The finding states both
  morphs: Drain (ids 39095, 41559, 41563, 41567) applies Major Breach and
  Minor Magickasteal; Elemental Susceptibility applies Major Breach and
  the Burning, Chilled and Concussion status effects every 7.5 seconds.
- **A proc set that never fires** (Roar of Alkosh 12 / 3 and Roaring
  Opportunist 19 / 8 at the 60 s floor). Judged per logging session, not
  per fight: in fights of 90 s or more Alkosh fired for 112 of 117
  wearer-fights, yet 30 of 219 wearer-fights under 30 s had no proc though
  the set worked. So the tracker counts, per player and set, the fights of
  a minute or more the set was worn in, and whether the set's effect was
  ever sourced by the player in any fight of the session; one fire clears
  the finding for the session. In those logs Alkosh wearers sourced Roar
  of Alkosh as 76667 and 75751, Roaring Opportunist wearers Major Slayer as
  93109 and 135923 (the other Major Slayer ids, 93120, 93442 and 177886,
  came from other sets). The one wearer who never fired Alkosh never used a
  synergy through a whole Halls of Fabrication run, 240 s fight included.
- **A group buff set complete on one bar only** (80 / 3), for Pearlescent
  Ward, Xoryn's Masterpiece and Lucent Echoes, whose five-piece bonus is a
  buff for the whole group that holds only while five pieces are active.
  The rule cannot be general: 38% of all five-piece wearings in the survey
  were one-bar, which is normal for proc sets and front-bar damage sets.
  Piece counts per bar come from player_build.piece_counts (a two-hander
  counts as two). A build without a back-bar weapon, or wearing Oakensoul
  Ring, is not reported.
- **A tank with no taunt or pull** (95 / 3 with the gates below; added the
  same day at the maintainer's request). The health pool alone is not a
  tank: of 3,154 health-dominant player-fights in the same logs, 762 had
  neither a taunt nor a pull on their bars and never taunted, but 519 of
  those wore at most one heavy piece and were damage dealers or healers
  whose health happened to be their largest pool, and 40 more taunted
  through the Tormentor set's charges and chains. Real tanks (a taunt
  slotted and taunting) dealt a median 0.10 of an equal share of the
  group's damage, 0.22 at the 90th percentile and 0.27 at the 95th. So
  besides the role, the bars and the session's taunts the rule asks for
  tank gear (a shield, an ice staff or five heavy pieces), at most half an
  equal share of the damage, and no healer sign (a restoration staff on a
  bar, or more healing to others than damage dealt: a heavy-armor healer in
  Sunspire would otherwise be flagged). Taunt and pull ids are UESP's for
  every rank plus the ids the bars carried in the logs; names count too,
  since the game now calls the chains Chains of Flame, Dominance and
  Devastation and the Arcanist's rank ids differ from UESP's. A scribed
  skill taunts or pulls by its focus script, Taunt or Pull, which names it
  Goading or Leashing. Destructive Clench taunts only with an ice staff in
  hand, when it is cast as Frost Clench.

The lists a later rules text could lift out (the maintainer's separate
issue) are module data: GROUP_SETS, PROC_SETS, ELEMENTAL_DRAIN_IDS,
OAKENSOUL_SET_ID, the taunt and pull tables, the weapon lines table. The
checks themselves are code.
"""

import json
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from ability_icons import bundle_root
from player_build import (
    ARMOR_SLOTS,
    NO_VALUE,
    armor_weight,
    enchant_label,
    piece_counts,
    weapon_type,
    weapon_type_label,
)
from scribing import GRIMOIRE_ICON_PREFIX, GRIMOIRES

WEAPON_LINES = ("Two Handed", "One Hand and Shield", "Dual Wield", "Bow",
                "Destruction Staff", "Restoration Staff")
# The two bars: (name, main-hand slot, off-hand slot)
BARS = (("front", "MAIN_HAND", "OFF_HAND"), ("back", "BACKUP_MAIN", "BACKUP_OFF"))
_TWO_HANDED_TYPES = frozenset({"greatsword", "battle_axe", "maul"})
_ONE_HANDED_TYPES = frozenset({"axe", "mace", "sword", "dagger"})
_STAFF_LINES = {"inferno_staff": "Destruction Staff", "ice_staff": "Destruction Staff",
                "lightning_staff": "Destruction Staff", "restoration_staff": "Restoration Staff"}
# The weapon line of each grimoire whose skills need a weapon (scribing.GRIMOIRES)
GRIMOIRE_LINES = {
    "Shield Throw": "One Hand and Shield", "Smash": "Two Handed", "Vault": "Bow",
    "Traveling Knife": "Dual Wield", "Elemental Explosion": "Destruction Staff",
    "Mender's Bond": "Restoration Staff",
}
NIRNHONED_WEAPON_TRAIT = "WEAPON_NIRNHONED"
# Elemental Drain at ranks I to IV (UESP playerSkills)
ELEMENTAL_DRAIN_IDS = frozenset({"39095", "41559", "41563", "41567"})
OAKENSOUL_SET_ID = "658"
HEAVY_PIECES_FLAGGED = 2  # the maintainer's threshold; one piece is the Undaunted Mettle norm
LONG_FIGHT_S = 60.0  # a fight long enough for a proc set to have had its chance
# The group buff sets that must be active on both bars, by set id
GROUP_SETS = {
    "648": "Pearlescent Ward", "651": "Perfected Pearlescent Ward",
    "768": "Lucent Echoes", "771": "Perfected Lucent Echoes",
    "769": "Xoryn's Masterpiece", "770": "Perfected Xoryn's Masterpiece",
}

# Taunts and pulls, by the ids a bar can carry (UESP playerSkills for every
# rank, plus the ids the bars held in the September and October 2026 logs)
# and by name, for a rank id neither list has
TAUNT_SKILL_IDS = frozenset({
    "28306", "41473", "41475", "41477",  # Puncture
    "38256", "41479", "41483", "41487",  # Ransack
    "38250", "41491", "41494", "41497",  # Pierce Armor
    "39475", "43353", "43358", "43363",  # Inner Fire
    "42056", "43368", "43373", "43378",  # Inner Rage
    "42060", "43383", "43388", "43393",  # Inner Beast
    "183165", "178447",                  # Runic Jolt
    "183430", "187741", "187742",        # Runic Sunder
    "186531",                            # Runic Embrace
})
TAUNT_SKILL_NAMES = frozenset({
    "Puncture", "Ransack", "Pierce Armor", "Inner Fire", "Inner Rage", "Inner Beast",
    "Runic Jolt", "Runic Sunder", "Runic Embrace",
})
# Destructive Clench taunts with an ice staff in hand (it is cast as Frost
# Clench then), and does nothing of the kind with another staff
CLENCH_SKILL_IDS = frozenset({"38984", "40977", "40995", "41006"})
CLENCH_SKILL_NAMES = frozenset({"Destructive Clench"})
PULL_SKILL_IDS = frozenset({
    "20492", "23736", "23740", "23744", "29446",  # Chains of Flame
    "20496", "23770", "23774", "23778",           # Chains of Dominance
    "20499", "32215", "32222", "32229",           # Chains of Devastation
    "40336", "42677", "42687", "42696", "40340",  # Silver Leash
    "86175", "86176", "86177", "86178",           # Frozen Gate
    "86179", "86180", "86181", "86182",           # Frozen Device
    "86183", "86184", "86185", "86186",           # Frozen Retreat
})
PULL_SKILL_NAMES = frozenset({
    "Chains of Flame", "Chains of Dominance", "Chains of Devastation",
    "Fiery Grip", "Unrelenting Grip", "Empowering Chains",  # the chains' older names
    "Silver Leash", "Frozen Gate", "Frozen Device", "Frozen Retreat",
})
# A scribed skill taunts or pulls by its focus script, which names it
TAUNT_FOCUS, TAUNT_PREFIX = "Taunt", "Goading "
PULL_FOCUS, PULL_PREFIX = "Pull", "Leashing "
TANK_HEAVY_PIECES = 5  # heavy pieces that read as a tank's armor
TANK_DAMAGE_RATIO = 0.5  # of an equal share of the group's damage; real tanks sit near 0.1


class ProcSet(NamedTuple):
    name: str
    effect_ids: frozenset  # the effect ids the wearer sources when the set fires
    effect: str  # the effect's name, for the finding
    trigger: str  # what makes the set fire, for the finding


_ALKOSH_EFFECTS = frozenset({"76667", "75751", "75752", "120018"})
_SLAYER_EFFECTS = frozenset({"93109", "135923"})
# The proc sets judged over the session, by set id
PROC_SETS = {
    "232": ProcSet("Roar of Alkosh", _ALKOSH_EFFECTS, "Roar of Alkosh",
                   "the wearer activates a synergy"),
    "496": ProcSet("Roaring Opportunist", _SLAYER_EFFECTS, "Major Slayer",
                   "the wearer completes a fully charged heavy attack"),
    "497": ProcSet("Perfected Roaring Opportunist", _SLAYER_EFFECTS, "Major Slayer",
                   "the wearer completes a fully charged heavy attack"),
}
PROC_EFFECT_IDS = frozenset().union(*(proc.effect_ids for proc in PROC_SETS.values()))

# The rule behind each finding, as the finding states it
NIRNHONED_DETAIL = (
    "Nirnhoned raises the damage of the weapon it is on, and the Dual Wield Expert passive "
    "counts only 6% of an off-hand weapon's damage, so the trait gives about a sixteenth "
    "there of what it gives a main-hand weapon. Precise, Charged or Infused serve an off "
    "hand better.")
GLYPH_DETAIL = (
    "Two identical weapon glyphs on one bar share one cooldown, so the second never fires. "
    "A different glyph on the other weapon would add a proc of its own.")
HEAVY_DETAIL = (
    "Heavy Armor's passives add health, resistance and sustain, nothing to damage. One heavy "
    "piece is the usual Undaunted Mettle split; every further one replaces a medium or light "
    "piece whose passives add damage, critical chance or penetration.")
WRONG_WEAPON_DETAIL = (
    "{skill} is a {line} skill and the {bar} bar holds {held}. A weapon skill works only "
    "with its own weapon type in hand, so the slot does nothing until the skill or the "
    "weapon changes.")
DRAIN_DETAIL = (
    "Elemental Drain applies Major Breach and Minor Magickasteal. The other morph, Elemental "
    "Susceptibility, applies Major Breach and the Burning, Chilled and Concussion status "
    "effects every 7.5 seconds; unless the group needs the magicka, Susceptibility is the "
    "morph to run.")
ONE_BAR_DETAIL = (
    "{set}'s five-piece bonus is a buff for the whole group that holds only while five "
    "pieces are active, so the group loses it every time this player swaps to the other "
    "bar. Five body pieces, or three with the two weapons of each bar, keep it on both.")
PROC_DETAIL = (
    "{set}'s five-piece bonus fires when {trigger}; this player's {effect} never appeared "
    "this session, so the set is dead weight until that changes.")
TANK_TITLE = "Tank with no taunt or pull on either bar"
TANK_DETAIL = (
    "This player reads as a tank: health is the largest pool, they hold {gear}, and they "
    "dealt {share} of an equal share of the group's damage. Yet neither bar holds a taunt "
    "(Puncture, Inner Fire or Runic Jolt and their morphs, Destructive Clench on an ice "
    "staff, a scribed skill with the Taunt focus) or a pull (Chains of Flame and its morphs, "
    "Silver Leash, Frozen Gate and its morphs, a scribed skill with the Pull focus), and no "
    "taunt of theirs was logged this session, so nothing holds the boss on them.")


def _finding(rule: str, title: str, detail: str, set_name: str = "", skill: str = "") -> dict:
    """One finding: the rule's id, what was found, the rule behind it, and
    the set or skill it is about (for a link), '' when none."""
    return {"rule": rule, "title": title, "detail": detail, "set": set_name, "skill": skill}


def _an(label: str) -> str:
    """'an Inferno Staff', 'a Dagger'."""
    return f"an {label}" if label[:1].lower() in "aeiou" else f"a {label}"


@lru_cache(maxsize=1)
def _bundled_weapon_skills() -> Dict[str, dict]:
    """Ability id -> {'line', 'name'} for every weapon-line skill in the
    bundled table; {} when the table is absent."""
    try:
        data = json.loads(bundle_root().joinpath("data", "skills", "weapon_skill_lines.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    skills = data.get("skills") if isinstance(data, dict) else None
    return {str(k): v for k, v in (skills or {}).items() if isinstance(v, dict)}


def skill_line_of_slot(slot: dict, table: Optional[Dict[str, dict]] = None) -> str:
    """The weapon skill line a bar slot's skill belongs to ('Two Handed'),
    '' for a skill of no weapon line or one the table does not know. A
    scribed skill whose id the table lacks is known by its grimoire's icon.
    *table* overrides the bundled one; tests use it."""
    known = _bundled_weapon_skills() if table is None else table
    entry = known.get(str(slot.get("id", "")))
    if entry:
        return str(entry.get("line") or "")
    icon = str(slot.get("icon") or "")
    if icon.startswith(GRIMOIRE_ICON_PREFIX):
        return GRIMOIRE_LINES.get(GRIMOIRES.get(icon, ""), "")
    return ""


def bar_weapon_line(gear: Dict[str, List[str]], main_slot: str, off_slot: str,
                    types: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """(weapon line, what the bar holds) for a bar: ('Destruction Staff',
    'an Inferno Staff'), ('Dual Wield', 'two Daggers'), ('One Hand and
    Shield', 'a Sword and a Shield'). ('', '') when the bar is empty, the
    main hand is not in the bundled weapon table, or a one-hander has no
    partner the rule can read."""
    main = gear.get(main_slot)
    if not main or len(main) < 2:
        return "", ""
    main_type = weapon_type(main[1], types)
    if not main_type:
        return "", ""
    main_label = weapon_type_label(main_type) or "weapon"
    if main_type in _TWO_HANDED_TYPES:
        return "Two Handed", _an(main_label)
    if main_type == "bow":
        return "Bow", _an(main_label)
    if main_type in _STAFF_LINES:
        return _STAFF_LINES[main_type], _an(main_label)
    if main_type not in _ONE_HANDED_TYPES:
        return "", ""
    off = gear.get(off_slot)
    off_type = weapon_type(off[1], types) if off and len(off) > 1 else ""
    if off and not off_type and len(off) > 4 and str(off[4]).startswith("ARMOR_"):
        off_type = "shield"  # a shield from a set newer than the table
    if off_type == "shield":
        return "One Hand and Shield", f"{_an(main_label)} and a Shield"
    if off_type in _ONE_HANDED_TYPES:
        off_label = weapon_type_label(off_type)
        held = (f"two {main_label}s" if off_type == main_type
                else f"{_an(main_label)} and {_an(off_label)}")
        return "Dual Wield", held
    return "", ""


def heavy_pieces(gear: Dict[str, List[str]], weights: Optional[Dict[str, str]] = None) -> int:
    """How many of the seven armor slots hold a heavy piece the bundled
    weight table knows."""
    return sum(1 for slot in ARMOR_SLOTS
               if slot in gear and len(gear[slot]) > 1
               and armor_weight(gear[slot][1], weights) == "heavy")


def wears_oakensoul(gear: Dict[str, List[str]]) -> bool:
    return any(len(item) > 6 and str(item[6]) == OAKENSOUL_SET_ID for item in gear.values())


def _slot_is(slot: dict, names: frozenset, ids: frozenset, focus: str, prefix: str) -> bool:
    """Whether a bar slot is one of the skills *ids* or *names*, or a
    scribed skill whose focus script is *focus* (which gives it a name
    starting with *prefix*); a scribed skill with several possible lines
    counts when any of them has that focus."""
    name = str(slot.get("name") or "")
    if str(slot.get("id", "")) in ids or name in names or name.startswith(prefix):
        return True
    scripts = slot.get("scripts") or []
    if scripts and str(scripts[0]) == focus:
        return True
    return any(len(option) > 1 and str(option[1]) == focus
               for option in slot.get("script_options") or [])


def taunts_and_pulls(gear: Dict[str, List[str]], front_slots: Optional[List[dict]],
                     back_slots: Optional[List[dict]],
                     types: Optional[Dict[str, str]] = None) -> Set[str]:
    """{'taunt', 'pull'}, those of the two the bars hold: a taunt skill, a
    Destructive Clench on a bar whose main hand is an ice staff, a pull skill,
    or a scribed skill with the Taunt or Pull focus."""
    found: Set[str] = set()
    for (_bar, main_slot, _off_slot), slots in zip(BARS, (front_slots, back_slots)):
        main = gear.get(main_slot)
        ice = bool(main) and len(main) > 1 and weapon_type(main[1], types) == "ice_staff"
        for slot in slots or []:
            clench = (str(slot.get("id", "")) in CLENCH_SKILL_IDS
                      or str(slot.get("name") or "") in CLENCH_SKILL_NAMES)
            if (_slot_is(slot, TAUNT_SKILL_NAMES, TAUNT_SKILL_IDS, TAUNT_FOCUS, TAUNT_PREFIX)
                    or (ice and clench)):
                found.add("taunt")
            elif _slot_is(slot, PULL_SKILL_NAMES, PULL_SKILL_IDS, PULL_FOCUS, PULL_PREFIX):
                found.add("pull")
    return found


def tank_gear(gear: Dict[str, List[str]], weights: Optional[Dict[str, str]] = None,
              types: Optional[Dict[str, str]] = None) -> str:
    """What makes the gear a tank's, for the finding: 'a shield', 'an ice
    staff' or '5 heavy pieces'; '' when nothing does."""
    for _bar, _main_slot, off_slot in BARS:
        off = gear.get(off_slot)
        if off and len(off) > 4 and (weapon_type(off[1], types) == "shield"
                                     or str(off[4]).startswith("ARMOR_")):
            return "a shield"
    for _bar, main_slot, _off_slot in BARS:
        main = gear.get(main_slot)
        if main and len(main) > 1 and weapon_type(main[1], types) == "ice_staff":
            return "an ice staff"
    heavy = heavy_pieces(gear, weights)
    return f"{heavy} heavy pieces" if heavy >= TANK_HEAVY_PIECES else ""


def _has_restoration_staff(gear: Dict[str, List[str]],
                           types: Optional[Dict[str, str]] = None) -> bool:
    return any(len(gear.get(main_slot, ())) > 1
               and weapon_type(gear[main_slot][1], types) == "restoration_staff"
               for _bar, main_slot, _off_slot in BARS)


def worn_proc_sets(gear: Dict[str, List[str]]) -> Set[str]:
    """The proc sets (PROC_SETS ids) this build has at five pieces on
    either bar."""
    counts = piece_counts(gear or {})
    return {set_id for set_id, (front, back) in counts.items()
            if set_id in PROC_SETS and (front >= 5 or (back or 0) >= 5)}


def fired_proc_sets(worn: Iterable[str], sourced_effect_ids: Iterable[str]) -> Set[str]:
    """Of the proc sets *worn*, those whose effect the player sourced
    (*sourced_effect_ids*, the ids they were the source of in the fight)."""
    sourced = {str(i) for i in sourced_effect_ids}
    return {set_id for set_id in worn
            if set_id in PROC_SETS and PROC_SETS[set_id].effect_ids & sourced}


def structural_findings(gear: Dict[str, List[str]], front_slots: Optional[List[dict]],
                        back_slots: Optional[List[dict]], role: str, taunted: bool = False,
                        set_name_of: Optional[Callable[[str], Optional[str]]] = None,
                        weights: Optional[Dict[str, str]] = None,
                        types: Optional[Dict[str, str]] = None,
                        skills: Optional[Dict[str, dict]] = None,
                        damage_ratio: Optional[float] = None,
                        out_heals: bool = False) -> List[dict]:
    """The per-fight rules on one build: Nirnhoned off hand, duplicate
    glyph, heavy armor on a DPS who has not taunted, a tank with no taunt
    or pull, weapon skill on the wrong bar, Elemental Drain, a group set on
    one bar; in that order.

    *gear* is slot -> the item's eleven log fields, the bar slots the
    engine's {'id', 'name', 'icon'} dicts, *role* the app's 'T', 'H' or
    'D', *taunted* whether the player taunted this session, *damage_ratio*
    the player's damage this fight over an equal share of the group's (1.0
    is an equal share; None when the fight had no damage), *out_heals*
    whether they healed others for more than they dealt. *set_name_of*
    names a set id (the bundled set data by default); *weights*, *types*
    and *skills* override the bundled tables for tests.
    """
    gear = gear or {}
    findings: List[dict] = []
    oakensoul = wears_oakensoul(gear)

    for bar, _main_slot, off_slot in BARS:
        off = gear.get(off_slot)
        if off and len(off) > 4 and str(off[4]) == NIRNHONED_WEAPON_TRAIT:
            weapon = weapon_type_label(weapon_type(off[1], types)) or "weapon"
            findings.append(_finding(
                "nirnhoned-off-hand", f"Nirnhoned on the off-hand {weapon} ({bar} bar)",
                NIRNHONED_DETAIL))

    for bar, main_slot, off_slot in BARS:
        main, off = gear.get(main_slot), gear.get(off_slot)
        if not (main and off and len(main) > 7 and len(off) > 7):
            continue
        if str(off[4]).startswith("ARMOR_"):
            continue  # a shield's glyph is an armor glyph
        glyph = str(main[7])
        if glyph == str(off[7]) and glyph not in NO_VALUE:
            label = enchant_label(glyph) or glyph
            findings.append(_finding(
                "duplicate-glyph", f"Two {label} glyphs on the {bar} bar", GLYPH_DETAIL))

    if role == "D" and not taunted:
        heavy = heavy_pieces(gear, weights)
        if heavy >= HEAVY_PIECES_FLAGGED:
            findings.append(_finding(
                "heavy-armor", f"{heavy} heavy armor pieces on a damage dealer", HEAVY_DETAIL))

    # A tank with nothing to hold the boss. The role's health pool alone is
    # not a tank (see the module notes), so tank gear, a small share of the
    # damage and no healer sign are asked for as well
    gear_sign = tank_gear(gear, weights, types) if role == "T" and not taunted else ""
    if (gear_sign and (front_slots or back_slots)
            and damage_ratio is not None and damage_ratio <= TANK_DAMAGE_RATIO
            and not out_heals and not _has_restoration_staff(gear, types)
            and not taunts_and_pulls(gear, front_slots, back_slots, types)):
        findings.append(_finding(
            "tank-no-taunt", TANK_TITLE,
            TANK_DETAIL.format(gear=gear_sign, share=f"{damage_ratio:.0%}")))

    for (bar, main_slot, off_slot), slots in zip(BARS, (front_slots, back_slots)):
        if bar == "back" and oakensoul:
            continue
        line, held = bar_weapon_line(gear, main_slot, off_slot, types)
        if not line:
            continue
        for slot in slots or []:
            skill_line = skill_line_of_slot(slot, skills)
            if skill_line and skill_line != line:
                name = str(slot.get("name") or f"Ability {slot.get('id', '')}")
                findings.append(_finding(
                    "wrong-weapon", f"{name} cannot be cast from the {bar} bar",
                    WRONG_WEAPON_DETAIL.format(skill=name, line=skill_line, bar=bar, held=held),
                    skill=name))

    for (bar, _main_slot, _off_slot), slots in zip(BARS, (front_slots, back_slots)):
        if any(str(slot.get("id", "")) in ELEMENTAL_DRAIN_IDS for slot in slots or []):
            findings.append(_finding(
                "elemental-drain", f"Elemental Drain slotted ({bar} bar)", DRAIN_DETAIL,
                skill="Elemental Drain"))

    if not oakensoul:
        for set_id, (front, back) in sorted(piece_counts(gear).items()):
            if set_id not in GROUP_SETS or back is None or (front >= 5) == (back >= 5):
                continue
            name = (set_name_of(set_id) if set_name_of else None) or GROUP_SETS[set_id]
            bar = "front" if front >= 5 else "back"
            findings.append(_finding(
                "set-on-one-bar",
                f"{name} is complete only on the {bar} bar ({front}/{back} pieces)",
                ONE_BAR_DETAIL.format(set=name), set_name=name))
    return findings


class BuildIssueTracker:
    """The rules judged over a logging session rather than a fight: the
    proc sets that never fire, and who has taunted (the heavy-armor rule's
    guard). Keyed by the engine's per-session player key; a fight is keyed
    by its start, so a fight the game cut in two and republished replaces
    its own record instead of counting twice. reset() at BEGIN_LOG."""

    def __init__(self):
        # (player key, set id) -> {fight start ms: (long enough, fired)}
        self._fights: Dict[Tuple[str, str], Dict[int, Tuple[bool, bool]]] = {}
        self._taunters: Set[str] = set()

    def reset(self) -> None:
        self._fights.clear()
        self._taunters.clear()

    def note_taunt(self, player_key: str) -> None:
        self._taunters.add(player_key)

    def has_taunted(self, player_key: str) -> bool:
        return player_key in self._taunters

    def note_fight(self, player_key: str, fight_start_ms: int, duration_s: float,
                   worn: Iterable[str], fired: Iterable[str]) -> None:
        """A fight ended: the proc sets *worn* at five pieces, and those of
        them that *fired* (the player sourced the set's effect)."""
        fired = set(fired)
        for set_id in worn:
            records = self._fights.setdefault((player_key, str(set_id)), {})
            records[int(fight_start_ms)] = (float(duration_s) >= LONG_FIGHT_S, set_id in fired)

    def long_fights(self, player_key: str, set_id: str) -> Tuple[int, bool]:
        """(fights of a minute or more the set was worn in, whether it ever
        fired) this session."""
        records = self._fights.get((player_key, str(set_id)), {})
        return (sum(1 for long, _fired in records.values() if long),
                any(fired for _long, fired in records.values()))

    def findings(self, player_key: str, worn: Iterable[str]) -> List[dict]:
        """The never-fired findings for the proc sets *worn* in this fight,
        in PROC_SETS order."""
        out = []
        worn = {str(set_id) for set_id in worn}
        for set_id, proc in PROC_SETS.items():
            if set_id not in worn:
                continue
            long, fired = self.long_fights(player_key, set_id)
            if long < 1 or fired:
                continue
            plural = "" if long == 1 else "s"
            out.append(_finding(
                "set-never-fired",
                f"{proc.name} never fired in {long} fight{plural} of a minute or more",
                PROC_DETAIL.format(set=proc.name, trigger=proc.trigger, effect=proc.effect),
                set_name=proc.name))
        return out
