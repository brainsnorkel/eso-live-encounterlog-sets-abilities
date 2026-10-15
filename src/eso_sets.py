#!/usr/bin/env python3
"""
Which class skill lines a player has (subclassing).

Design: since Update 46 a character can swap any of its three class skill
lines for another class's, so the class id in UNIT_ADDED no longer says
what a build is. Two things in the log do.

The passives. The first list on a player's PLAYER_INFO line is their
long-term effects, and among the mundus boon, food and set auras it carries
every class-line passive the character has learned, by ability id. A
character with Assassination, Herald of the Tome and Animal Companions
lists Hemorrhage, Executioner, Splintered Secrets, Advanced Species and so
on. Each passive belongs to one line, so the lines are read off the ids
with no guessing: skill_lines_of looks each id up in
data/skills/class_passives.json (UESP's player skill table cut down to the
203 class passives by scripts/generate_class_passives.py, masteries
included) and names a line for every passive found. The lookup is by id,
never by name or icon: the group's Combustion resource return, the Reusable
Parts ally effect and the Resolute Defense proc share a passive's name and
land in the same list, and a passive's icon does not tell it from an active
(Blessing at the Peak uses an ability_* icon). Both rank ids of a passive
are in the table; a character lists the rank they have.

The slotted abilities, as a filler. ESOSubclassAnalyzer matches the names
of the bar abilities (ABILITY_INFO) against SKILL_LINE_ABILITIES, every
class line's ultimate, actives and morphs as the game names them, exactly
(never by substring: "Carve" is Two Handed, not Fatecarver; "Swarming
Scion" is Vampire, not a Warden Swarm), and the lines with the most matches
win. It cannot see a line the player slotted nothing from, which is routine
for healers, tanks and Arcanist DPS, and the passives can miss a line whose
passives a mid-level character has not learned yet. So skill_lines_of takes
the passives' lines first and fills up to three from the slotted guess.
In 73 split logs of September and October 2026 (7,019 distinct builds) the
passives named exactly three lines for 98.5% of builds and never
contradicted the slotted guess, which had missed one or more lines in 56%
of them; 489 builds borrowed a line, and for 133 of those the lines shown
change, 18 of them borrowed purely for the passives (nothing slotted). A
character has at most three lines, since subclassing swaps lines and never
adds a fourth; a fourth line of passives, seen three times in the survey,
loses to the lines whose actives are slotted.

The fight view and build window show only the borrowed lines, each with a
plus sign before its first word ("NB +Herald" for a Nightblade who swapped
a line for Herald of the Tome), so a stock build shows just its class. A
player whose class is unknown shows every line found.

Class Mastery passives (five per class; only a character with all three of
its own lines can take them) take the same place beside the class, after a
colon ("NB: An Eye for Exploitation, Above and Beyond"), and are named on
the build window's mundus and food line too. Two sources name them,
because the PLAYER_INFO list holds only the passives whose effect is always
on: a mastery that works by a proc (Unbound Potential, Abyssal Emergence,
Wildfire Embers, Bright Harbinger...) is never in it. Such a mastery shows
in the log as an EFFECT_CHANGED the player is the source of, under one of
a few effect ids that carry its name; the table lists those 60 ids as
mastery_effects, and mastery_of_effect names the mastery of one. The
engine notes a mastery on its holder when such an effect fires, and keeps
it for the rest of the session, since a mastery does not change between
fights. In the 73 survey logs, 11,697 pure-class player rows: the list
alone named a mastery for 42% of them, the list plus the fight's own
effects for 79%, the list plus the session's effects for 90% (191 of 209
characters). Nine of the 35 masteries fire no effect of their own name;
for four of them the effect is named after the buff it grants and has an
id in the same block, sourced by one class alone in those logs: Lead from
the Front's Major Berserk and Major Protection (Dragonknights), Tundra's
Maw's Major Brittle and Bountiful Harvest's Major Heroism (Wardens), and
Cutthroat's Focus's Cutthroat's Mockery (Nightblades). The table carries
those as signature effects (scripts/generate_class_passives.py says how
each was pinned down), and mastery_of_effect checks the source's class for
them. The other five (Share the Spoils, Nocturnal Inspiration,
Conservation of Energy, Bastion of Light, Devout Guardian) work through
resources, ultimate or unnamed heals and shields and stay invisible.
"""

import json
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ability_icons import bundle_root


class ESOSubclassAnalyzer:
    """Analyzes abilities to infer player subclass/build."""

    # Complete ESO Class Skill Line Abilities - Updated for 2025
    SKILL_LINE_ABILITIES = {
        # Dragonknight Skill Lines
        'Ardent Flame': [
            # Ultimate
            'Dragonknight Standard', 'Shifting Standard', 'Standard of Might',
            # Active Skills
            'Lava Whip', 'Molten Whip', 'Flame Lash',
            'Searing Strike', 'Venomous Claw', 'Burning Embers',
            'Fiery Breath', 'Noxious Breath', 'Engulfing Flames',
            'Fiery Grip', 'Empowering Chains', 'Unrelenting Grip',
            'Inferno', 'Flames of Oblivion', 'Cauterize'
        ],
        
        'Draconic Power': [
            # Ultimate
            'Dragon Leap', 'Ferocious Leap', 'Take Flight',
            # Active Skills
            'Spiked Armor', 'Hardened Armor', 'Volatile Armor',
            'Dark Talons', 'Burning Talons', 'Choking Talons',
            'Dragon Blood', 'Green Dragon Blood', 'Coagulating Blood',
            'Reflective Scale', 'Dragon Fire Scale', 'Reflective Plate',
            'Inhale', 'Deep Breath', 'Draw Essence'
        ],
        
        'Earthen Heart': [
            # Ultimate
            'Magma Armor', 'Magma Shell', 'Corrosive Armor',
            # Active Skills
            'Stonefist', 'Stone Giant', 'Obsidian Shard',
            'Molten Weapons', 'Igneous Weapons', 'Molten Armaments',
            'Obsidian Shield', 'Igneous Shield', 'Fragmented Shield',
            'Petrify', 'Fossilize', 'Shattering Rocks',
            'Ash Cloud', 'Cinder Storm', 'Eruption'
        ],
        
        # Sorcerer Skill Lines
        'Dark Magic': [
            # Ultimate
            'Negate Magic', 'Suppression Field', 'Absorption Field',
            # Active Skills
            'Crystal Shard', 'Crystal Fragments', 'Crystal Weapon',
            'Encase', 'Shattering Prison', 'Restraining Prison',
            'Rune Prison', 'Rune Cage', 'Defensive Rune',
            'Dark Exchange', 'Dark Deal', 'Dark Conversion',
            'Daedric Mines', 'Daedric Tomb', 'Daedric Minefield'
        ],
        
        'Daedric Summoning': [
            # Ultimate
            'Summon Storm Atronach', 'Greater Storm Atronach', 'Summon Charged Atronach',
            # Active Skills
            'Summon Unstable Familiar', 'Summon Unstable Clannfear', 'Summon Volatile Familiar',
            'Daedric Curse', 'Daedric Prey', 'Haunting Curse',
            'Summon Winged Twilight', 'Summon Twilight Tormentor', 'Summon Twilight Matriarch',
            'Conjured Ward', 'Hardened Ward', 'Empowered Ward',
            'Bound Armor', 'Bound Armaments', 'Bound Aegis'
        ],
        
        'Storm Calling': [
            # Ultimate
            'Overload', 'Power Overload', 'Energy Overload',
            # Active Skills
            'Mages\' Fury', 'Mages\' Wrath', 'Endless Fury',
            'Lightning Form', 'Hurricane', 'Boundless Storm',
            'Lightning Splash', 'Liquid Lightning', 'Lightning Flood',
            'Surge', 'Power Surge', 'Critical Surge',
            'Bolt Escape', 'Streak', 'Ball of Lightning'
        ],
        
        # Nightblade Skill Lines
        'Assassination': [
            # Ultimate
            'Death Stroke', 'Incapacitating Strike', 'Soul Harvest',
            # Active Skills
            'Assassin\'s Blade', 'Killer\'s Blade', 'Impale',
            'Teleport Strike', 'Ambush', 'Lotus Fan',
            'Veiled Strike', 'Surprise Attack', 'Concealed Weapon',
            'Mark Target', 'Piercing Mark', 'Reaper\'s Mark',
            'Grim Focus', 'Relentless Focus', 'Merciless Resolve'
        ],
        
        'Shadow': [
            # Ultimate
            'Consuming Darkness', 'Bolstering Darkness', 'Veil of Blades',
            # Active Skills
            'Shadow Cloak', 'Shadowy Disguise', 'Dark Cloak',
            'Blur', 'Mirage', 'Phantasmal Escape',
            'Path of Darkness', 'Twisting Path', 'Refreshing Path',
            'Aspect of Terror', 'Mass Hysteria', 'Manifestation of Terror',
            'Summon Shade', 'Dark Shade', 'Shadow Image'
        ],
        
        'Siphoning': [
            # Ultimate
            'Soul Shred', 'Soul Siphon', 'Soul Tether',
            # Active Skills
            'Strife', 'Funnel Health', 'Swallow Soul',
            'Agony', 'Prolonged Suffering', 'Malefic Wreath',
            'Cripple', 'Debilitate', 'Crippling Grasp',
            'Siphoning Strikes', 'Leeching Strikes', 'Siphoning Attacks',
            'Drain Power', 'Power Extraction', 'Sap Essence'
        ],
        
        # Templar Skill Lines
        'Aedric Spear': [
            # Ultimate
            'Radial Sweep', 'Crescent Sweep', 'Everlasting Sweep',
            # Active Skills
            'Puncturing Strikes', 'Biting Jabs', 'Puncturing Sweep',
            'Piercing Javelin', 'Aurora Javelin', 'Binding Javelin',
            'Focused Charge', 'Explosive Charge', 'Toppling Charge',
            'Spear Shards', 'Luminous Shards', 'Blazing Spear',
            'Sun Shield', 'Radiant Ward', 'Blazing Shield'
        ],
        
        'Dawn\'s Wrath': [
            # Ultimate
            'Nova', 'Solar Prison', 'Solar Disturbance',
            # Active Skills
            'Sun Fire', 'Vampire\'s Bane', 'Reflective Light',
            'Solar Flare', 'Dark Flare', 'Solar Barrage',
            'Backlash', 'Purifying Light', 'Power of the Light',
            'Eclipse', 'Total Dark', 'Unstable Core',
            'Radiant Destruction', 'Radiant Glory', 'Radiant Oppression'
        ],
        
        'Restoring Light': [
            # Ultimate
            'Rite of Passage', 'Practiced Incantation', 'Remembrance',
            # Active Skills
            'Rushed Ceremony', 'Breath of Life', 'Honor the Dead',
            'Healing Ritual', 'Ritual of Rebirth', 'Hasty Prayer',
            'Restoring Aura', 'Radiant Aura', 'Repentance',
            'Cleansing Ritual', 'Purifying Ritual', 'Extended Ritual',
            'Rune Focus', 'Channeled Focus', 'Restoring Focus'
        ],
        
        # Warden Skill Lines
        'Animal Companions': [
            # Ultimate
            'Feral Guardian', 'Eternal Guardian', 'Wild Guardian',
            # Active Skills
            'Dive', 'Cutting Dive', 'Screaming Cliff Racer',
            'Scorch', 'Subterranean Assault', 'Deep Fissure',
            'Swarm', 'Fetcher Infection', 'Growing Swarm',
            'Betty Netch', 'Blue Betty', 'Bull Netch',
            'Falcon\'s Swiftness', 'Deceptive Predator', 'Bird of Prey'
        ],
        
        'Green Balance': [
            # Ultimate
            'Secluded Grove', 'Enchanted Forest', 'Healing Thicket',
            # Active Skills
            'Fungal Growth', 'Enchanted Growth', 'Soothing Spores',
            'Healing Seed', 'Budding Seeds', 'Corrupting Pollen',
            'Living Vines', 'Leeching Vines', 'Nature\'s Grasp',
            'Lotus Flower', 'Green Lotus', 'Lotus Blossom',
            'Nature\'s Gift', 'Nature\'s Embrace', 'Emerald Moss'
        ],
        
        'Winter\'s Embrace': [
            # Ultimate
            'Sleet Storm', 'Northern Storm', 'Permafrost',
            # Active Skills
            'Frost Cloak', 'Expansive Frost Cloak', 'Ice Cloak',
            'Impaling Shards', 'Gripping Shards', 'Winter\'s Revenge',
            'Arctic Wind', 'Arctic Blast', 'Polar Wind',
            'Crystallized Shield', 'Crystallized Slab', 'Shimmering Shield',
            'Frozen Gate', 'Frozen Device', 'Frozen Retreat'
        ],
        
        # Necromancer Skill Lines
        'Grave Lord': [
            # Ultimate
            'Frozen Colossus', 'Pestilent Colossus', 'Glacial Colossus',
            # Active Skills
            'Flame Skull', 'Ricochet Skull', 'Venom Skull',
            'Blastbones', 'Blighted Blastbones', 'Stalking Blastbones',
            'Boneyard', 'Unnerving Boneyard', 'Avid Boneyard',
            'Skeletal Mage', 'Skeletal Archer', 'Skeletal Arcanist',
            'Shocking Siphon', 'Detonating Siphon', 'Mystic Siphon'
        ],
        
        'Bone Tyrant': [
            # Ultimate
            'Bone Goliath Transformation', 'Pummeling Goliath', 'Ravenous Goliath',
            # Active Skills
            'Death Scythe', 'Ruinous Scythe', 'Hungry Scythe',
            'Bone Armor', 'Beckoning Armor', 'Summoner\'s Armor',
            'Bitter Harvest', 'Deaden Pain', 'Necrotic Potency',
            'Bone Totem', 'Remote Totem', 'Agony Totem',
            'Grave Grasp', 'Ghostly Embrace', 'Empowering Grasp'
        ],
        
        'Living Death': [
            # Ultimate
            'Reanimate', 'Renewing Animation', 'Animate Blastbones',
            # Active Skills
            'Render Flesh', 'Resistant Flesh', 'Blood Sacrifice',
            'Life amid Death', 'Enduring Undeath', 'Renewing Undeath',
            'Spirit Mender', 'Spirit Guardian', 'Intensive Mender',
            'Restoring Tether', 'Braided Tether', 'Mortal Coil',
            'Expunge', 'Expunge and Modify', 'Hexproof'
        ],
        
        # Arcanist Skill Lines
        'Herald of the Tome': [
            # Ultimate
            'The Tide King\'s Gaze', 'The Languid Eye', 'The Unblinking Eye',
            # Active Skills
            'Runeblades', 'Writhing Runeblades', 'Escalating Runeblades',
            'Fatecarver', 'Pragmatic Fatecarver', 'Exhausting Fatecarver',
            'Abyssal Impact', 'Tentacular Dread', 'Cephaliarch\'s Flail',
            'Tome-Bearer\'s Inspiration', 'Inspired Scholarship', 'Recuperative Treatise',
            'The Imperfect Ring', 'Rune of Displacement', 'Fulminating Rune'
        ],
        
        'Curative Runeforms': [
            # Ultimate
            'Vitalizing Glyphic', 'Glyphic of the Tides', 'Resonating Glyphic',
            # Active Skills
            'Runemend', 'Evolving Runemend', 'Audacious Runemend',
            'Remedy Cascade', 'Cascading Fortune', 'Curative Surge',
            'Chakram of Destiny', 'Chakram\'s Havoc', 'Kinetic Aegis',
            'Arcanist\'s Domain', 'Reconstructive Domain', 'Zenas\' Empowering Disc',
            'Apocryphal Gate', 'Fleet-footed Gate', 'Passage Between Worlds'
        ],
        
        'Soldier of Apocrypha': [
            # Ultimate
            'Gibbering Shield', 'Sanctum of the Abyssal Sea', 'Gibbering Shelter',
            # Active Skills
            'Runic Jolt', 'Runic Sunder', 'Runic Embrace',
            'Runespite Ward', 'Spiteward of the Lucid Mind', 'Impervious Runeward',
            'Fatewoven Armor', 'Cruxweaver Armor', 'Unbreakable Fate',
            'Runic Defense', 'Runeguard of Still Waters', 'Runeguard of Freedom',
            'Rune of Eldritch Horror', 'Rune of Uncanny Adoration', 'Rune of the Colorless Pool'
        ]
    }   
    MAX_SKILL_LINES = 3  # a character never has more class skill lines than this

    def analyze_subclass(self, abilities: Set[str]) -> Dict[str, any]:
        """The class skill lines behind a set of slotted ability names: the
        best-supported three, in table order (see the module docstring)."""
        if not abilities:
            return {'skill_lines': [], 'confidence': 0.0}

        # Clean ability names for better matching
        clean_abilities = {self._clean_ability_name(ability).lower() for ability in abilities}

        # Exact-name matches per skill line. Substring matching is wrong
        # here: "Carve" (Two Handed) is not a Fatecarver, "Swarming Scion"
        # (Vampire) is not a Warden Swarm.
        scored = []
        for order, (skill_line, skill_abilities) in enumerate(self.SKILL_LINE_ABILITIES.items()):
            hits = sum(1 for ability in skill_abilities if ability.lower() in clean_abilities)
            if hits:
                scored.append((hits, order, skill_line))

        # A character has at most three class skill lines (subclassing swaps
        # lines, it never adds a fourth): keep the best-supported three, in
        # table order
        best = sorted(scored, key=lambda item: (-item[0], item[1]))[:self.MAX_SKILL_LINES]
        top_skill_lines = [line for _hits, _order, line in sorted(best, key=lambda item: item[1])]

        # Simple confidence: 1.0 if we found skill lines, 0.0 if not
        confidence = 1.0 if top_skill_lines else 0.0

        return {
            'skill_lines': top_skill_lines,
            'confidence': confidence,
            'role': self._infer_role_from_skill_lines(top_skill_lines, abilities)
        }
    
    def _infer_role_from_skill_lines(self, skill_lines: List[str], abilities: Set[str]) -> str:
        """Infer role from detected skill lines and abilities."""
        # Role detection based on skill lines and abilities
        if not skill_lines:
            return 'unknown'
        
        # Check for healing abilities
        healing_abilities = {'Breath of Life', 'Honor the Dead', 'Healing Ritual', 'Combat Prayer', 'Rapid Regeneration'}
        if any(ability in abilities for ability in healing_abilities):
            return 'healer'
        
        # Check for tank abilities
        tank_abilities = {'Pierce Armor', 'Inner Rage', 'Heroic Slash', 'Defensive Posture', 'Absorb Magic'}
        if any(ability in abilities for ability in tank_abilities):
            return 'tank'
        
        # Check for DPS abilities
        dps_abilities = {'Crystal Fragments', 'Force Pulse', 'Wrecking Blow', 'Biting Jabs', 'Scorched Earth'}
        if any(ability in abilities for ability in dps_abilities):
            return 'dps'
        
        # Default role based on skill lines
        if 'Restoring Light' in skill_lines:
            return 'healer'
        elif 'Aedric Spear' in skill_lines or 'Dawn\'s Wrath' in skill_lines:
            return 'dps'
        else:
            return 'dps'  # Default to DPS

    def _clean_ability_name(self, ability: str) -> str:
        """Clean ability name for better matching."""
        # Remove common prefixes/suffixes
        cleaned = ability.replace('Heavy Attack', '').replace('Light Attack', '')
        cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)  # Remove parenthetical content
        return cleaned.strip()

    def _ability_matches(self, pattern: str, ability: str) -> bool:
        """Whether a logged ability name is the listed skill (exact, case-insensitive)."""
        return pattern.strip().lower() == ability.strip().lower()


# ---- skill lines from the passives PLAYER_INFO lists ----

MAX_SKILL_LINES = ESOSubclassAnalyzer.MAX_SKILL_LINES
# Display order of the lines, the table's: a class's three lines together
LINE_ORDER = {line: index for index, line in enumerate(ESOSubclassAnalyzer.SKILL_LINE_ABILITIES)}
MASTERY_LINE = "Class Mastery"


@lru_cache(maxsize=1)
def _class_passive_file() -> dict:
    """data/skills/class_passives.json as parsed; {} when absent or malformed."""
    try:
        data = json.loads(bundle_root().joinpath("data", "skills", "class_passives.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def class_passive_table() -> Dict[str, dict]:
    """The file's passives as {ability id: {'class', 'line', 'name',
    'rank'}}; {} when the file is absent or malformed."""
    passives = _class_passive_file().get("passives")
    return {str(ability_id): entry for ability_id, entry in (passives or {}).items()
            if isinstance(entry, dict) and entry.get("line")}


@lru_cache(maxsize=1)
def mastery_effect_table() -> Dict[str, Tuple[str, str]]:
    """{ability id: (mastery name, class)} for the effects the masteries fire
    and the mastery passives themselves (both show as EFFECT_CHANGED from
    the holder); {} when the file is absent or malformed."""
    effects = _class_passive_file().get("mastery_effects")
    table = {str(ability_id): (str(entry.get("name") or ""), str(entry.get("class") or ""))
             for ability_id, entry in (effects or {}).items()
             if isinstance(entry, dict) and entry.get("name")}
    for ability_id, entry in class_passive_table().items():
        if entry.get("line") == MASTERY_LINE and entry.get("name"):
            table[ability_id] = (str(entry["name"]), str(entry.get("class") or ""))
    return table


def mastery_of_effect(ability_id, class_name: Optional[str] = None,
                      table: Optional[Dict[str, Tuple[str, str]]] = None) -> str:
    """The Class Mastery an effect id belongs to, '' for any other id. With
    *class_name* (the source's class, as get_class_name says it) an effect
    of another class's mastery gives '' too: the buff-named signature
    effects are tied to a class by evidence, so the class is checked."""
    table = mastery_effect_table() if table is None else table
    name, owner = table.get(str(ability_id), ("", ""))
    if class_name and owner and class_name != owner:
        return ""
    return name


def lines_from_passives(effect_ids: Iterable[str],
                        table: Optional[Dict[str, dict]] = None) -> Tuple[Dict[str, int], List[str]]:
    """({line: passives found}, [mastery names]) from a player's long-term
    effect ids: the class lines whose passives the ids name, in table order,
    and the Class Mastery passives among them. An id the table does not know
    is skipped, so a same-named effect never counts."""
    table = class_passive_table() if table is None else table
    counts: Counter = Counter()
    masteries: List[str] = []
    for effect in effect_ids or []:
        entry = table.get(str(effect))
        if not entry:
            continue
        if entry["line"] == MASTERY_LINE:
            name = str(entry.get("name") or "")
            if name and name not in masteries:
                masteries.append(name)
        else:
            counts[entry["line"]] += 1
    ordered = {line: counts[line] for line in sorted(counts, key=lambda l: LINE_ORDER.get(l, len(LINE_ORDER)))}
    return ordered, masteries


def skill_lines_of(effect_ids: Iterable[str], slotted_abilities: Iterable[str],
                   table: Optional[Dict[str, dict]] = None) -> List[str]:
    """The player's class skill lines, at most MAX_SKILL_LINES, in table
    order: the lines their passives name, filled up from the lines their
    slotted abilities name (see the module docstring). A fourth line of
    passives loses to the lines with a slotted ability, then to the lines
    with more passives."""
    found, _masteries = lines_from_passives(effect_ids, table)
    slotted = set(slotted_abilities or [])
    guessed = (ESOSubclassAnalyzer().analyze_subclass(slotted)['skill_lines']
               if slotted else [])
    if len(found) > MAX_SKILL_LINES:
        ranked = sorted(found, key=lambda line: (line not in guessed, -found[line],
                                                 LINE_ORDER.get(line, len(LINE_ORDER))))
        lines = ranked[:MAX_SKILL_LINES]
    else:
        lines = list(found)
        for line in guessed:
            if len(lines) >= MAX_SKILL_LINES:
                break
            if line not in lines:
                lines.append(line)
    return sorted(lines, key=lambda line: LINE_ORDER.get(line, len(LINE_ORDER)))



