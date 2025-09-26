#!/usr/bin/env python3
"""
ESO Set Database and Analysis Module
Provides gear set identification and subclass inference functionality.
"""

import re
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, Counter

class ESOSubclassAnalyzer:
    """Analyzes abilities to infer player subclass/build."""

    SKILL_LINE_ALIASES = { 
        'Assassination': 'Ass',
        'Dawn\'s Wrath': 'Dawn',
        'Herald': 'Herald',
        'Bone': 'BoneTyrant',
        'Living': 'LivingDeath',
        'Winter\'s': 'Winter'
    }

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
    def analyze_subclass(self, abilities: Set[str]) -> Dict[str, any]:
        """Analyze abilities to infer skill lines."""
        if not abilities:
            return {'skill_lines': [], 'confidence': 0.0}

        # Clean ability names for better matching
        clean_abilities = {self._clean_ability_name(ability) for ability in abilities}

        # Find skill lines that have at least one matching ability
        detected_skill_lines = []
        for skill_line, skill_abilities in self.SKILL_LINE_ABILITIES.items():
            if any(self._ability_matches(ability, clean_ability) 
                   for ability in skill_abilities 
                   for clean_ability in clean_abilities):
                detected_skill_lines.append(skill_line)

        # Create a list of unique skill lines (preserving order)
        seen = set()
        unique_skill_lines = []
        for skill_line in detected_skill_lines:
            if skill_line not in seen:
                unique_skill_lines.append(skill_line)
                seen.add(skill_line)
        top_skill_lines = unique_skill_lines

        # Simple confidence: 1.0 if we found skill lines, 0.0 if not
        confidence = 1.0 if top_skill_lines else 0.0

        return {
            'skill_lines': top_skill_lines,
            'confidence': confidence
        }

    def _clean_ability_name(self, ability: str) -> str:
        """Clean ability name for better matching."""
        # Remove common prefixes/suffixes
        cleaned = ability.replace('Heavy Attack', '').replace('Light Attack', '')
        cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)  # Remove parenthetical content
        return cleaned.strip()

    def _ability_matches(self, pattern: str, ability: str) -> bool:
        """Check if an ability matches a pattern."""
        pattern_lower = pattern.lower()
        ability_lower = ability.lower()
        return pattern_lower in ability_lower or ability_lower in pattern_lower



