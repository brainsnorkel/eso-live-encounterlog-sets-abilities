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

    # Skill line abilities - organized by actual ESO skill lines
    SKILL_LINE_ABILITIES = {
        # Dragonknight Skill Lines
        'Ardent Flame': ['Flame Whip', 'Burning Embers', 'Engulfing Flames', 'Molten Whip', 'Power Lash', 'Flame Clench', 'Flames of Oblivion', 'Fiery Grip', 'Searing Strike', 'Fiery Breath'],
        'Draconic Power': ['Spike Armor', 'Hardened Armor', 'Magma Shell', 'Igneous Shield', 'Choking Talons', 'Dragon Leap', 'Dragonknight Standard', 'Spiked Armor', 'Dragon Blood', 'Reflective Scales'],
        'Earthen Heart': ['Stonefist', 'Stone Giant', 'Volatile Armor', 'Earthen Heart', 'Corrosive Armor', 'Obsidian Shield', 'Molten Weapons'],
        
        # Sorcerer Skill Lines
        'Dark Magic': ['Crystal Fragments', 'Dark Exchange', 'Dark Deal', 'Daedric Curse', 'Negate Magic', 'Encase', 'Crystal Shard', 'Rune Prison'],
        'Daedric Summoning': ['Hardened Ward', 'Conjured Ward', 'Bound Armaments', 'Storm Atronach', 'Summon Winged Twilight', 'Summon Unstable Familiar', 'Bound Armor'],
        'Storm Calling': ['Streak', 'Lightning Form', 'Critical Surge', 'Hurricane', 'Lightning Splash', 'Overload', 'Mage\'s Fury'],
        
        # Nightblade Skill Lines
        'Assassination': ['Surprise Attack', 'Killer\'s Blade', 'Death Stroke', 'Mark Target', 'Teleport Strike', 'Blade of Woe', 'Merciless Resolve', 'Incapacitating Strike', 'Assassin\'s Blade', 'Blur',  'Veiled Strike'],
        'Shadow': ['Mirage', 'Dark Cloak', 'Shadow Image', 'Shadowy Disguise', 'Summon Shade', 'Path of Darkness', 'Shadow Cloak'],
        'Siphoning': ['Swallow Soul', 'Crippling Grasp', 'Debilitate', 'Sap Essence', 'Leeching Strikes', 'Relentless Focus', 'Strife', 'Agony', 'Soul Shred'],
        
        # Templar Skill Lines
        'Aedric Spear': ['Puncturing Sweeps', 'Biting Jabs', 'Binding Javelin', 'Power of the Light', 'Spear Shards', 'Radial Sweep', 'Puncturing Strikes', 'Piercing Javelin', 'Blazing Spear'],
        'Dawn\'s Wrath': ['Dark Flare', 'Vampire\'s Bane', 'Radiant Destruction', 'Sun Fire', 'Backlash', 'Solar Barrage', 'Solar Flare'],
        'Restoring Light': ['Breath of Life', 'Healing Ritual', 'Restoring Light', 'Honor the Dead', 'Healing Springs', 'Ritual of Retribution', 'Rushed Ceremony', 'Restoring Aura', 'Extended Ritual', 'Purifying Light'],
        
        # Warden Skill Lines
        'Animal Companions': ['Deep Fissure', 'Cutting Dive', 'Bird of Prey', 'Bull Netch', 'Falcon\'s Swiftness', 'Scorch', 'Dive', 'Swarm'],
        'Green Balance': ['Healing Seed', 'Living Seed', 'Enchanted Growth', 'Nature\'s Gift', 'Living Vines', 'Budding Seeds', 'Fungal Growth'],
        'Winter\'s Embrace': ['Arctic Blast', 'Crystallized Shield', 'Frozen Gate', 'Ice Fortress', 'Gripping Shards', 'Permafrost', 'Winter\'s Revenge', 'Northern Storm', 'Frost Cloak', 'Impaling Shards', 'Arctic Wind'],
        
        # Necromancer Skill Lines
        'Bone Tyrant': ['Bone Prison', 'Bone Armor', 'Beckoning Armor', 'Bitter Harvest', 'Pummeling Goliath', 'Renewing Undeath', 'Bone Goliath Transformation'],
        'Grave Lord': ['Flame Skull', 'Blastbones', 'Skeletal Arcanist', 'Skeletal Mage', 'Bone Goliath', 'Skeletal Colossus', 'Boneyard', 'Leashing Soul', 'Ruinous Scythe', 'Necrotic Potency'],
        'Living Death': ['Life amid Death', 'Render Flesh', 'Restoring Tether', 'Braided Tether', 'Renewing Undeath', 'Spirit Mender', 'Expunge', 'Spirit Guardian'],
        
        # Arcanist Skill Lines
        'Herald of the Tome': ['The Unblinking Eye', 'The Languid Eye', 'The Tide King\'s Gaze', 
                                'Runeblades', 'Writhing Runeblades', 'Escalating Runeblades', 
                                'Fatecarver', 'Pragmatic Fatecarver', 'Exhausting Fatecarver', 
                                'Abyssal Impact', 'Tentacular Dread', 'Cephaliarch\'s Flail', 
                                'Tome-Bearer\'s Inspiration', 'Inspired Scholarship', 'Recuperative Treatise',
                                'The Imperfect Ring', 'Rune of Displacement', 'Fulminating Rune'],
        'Curative Runeforms': ['Chakram of Destiny', 'Healing Tether', 'Reconstructive Domain', 'Runemend', 'Curative Surge', 'Remedy Cascade', 'Vitalizing Glyphic', 'Runic Defense'],
        'Soldier of Apocrypha': ['Gibbering Shield', 'Sanctum of the Abyssal Sea', 'Gibbering Shelter',
                                'Runic Jolt', 'Runic Sunder', 'Runic Embrace',
                                'Runespite Ward', 'Spiteward of the Lucid Mind', 'Impervious Runeward'
                                'Fatewoven Armor', 'Cruxweaver Armor', 'Unbreakable Fate',
                                'Runic Defense', 'Runeguard of Still Waters', 'Runeguard of Freedom',
                                'Rune of Eldritch Horror', 'Rune of Uncanny Adoration', 'Rune of the Colorless Pool']
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




class ESOSetDatabase:
    """Simple ESO set database for gear identification."""

    def __init__(self):
        # Basic set database - in a real implementation, this would be loaded from LibSets
        self.sets = {
            # Popular DPS sets
            'Mother\'s Sorrow': {
                'type': 'crafted',
                'bonuses': ['Spell Critical', 'Maximum Magicka', 'Spell Damage'],
                'role': 'magicka_dps'
            },
            'False God\'s Devotion': {
                'type': 'trial',
                'bonuses': ['Spell Damage', 'Maximum Magicka', 'Magicka Recovery'],
                'role': 'magicka_dps'
            },
            'Relequen': {
                'type': 'trial',
                'bonuses': ['Weapon Damage', 'Weapon Critical', 'Stamina'],
                'role': 'stamina_dps'
            },
            'Deadly Strike': {
                'type': 'overland',
                'bonuses': ['Weapon Damage', 'DoT Damage'],
                'role': 'dps'
            },

            # Tank sets
            'Ebon Armory': {
                'type': 'dungeon',
                'bonuses': ['Maximum Health', 'Health Recovery', 'Group Health'],
                'role': 'tank'
            },
            'Yolnahkriin': {
                'type': 'trial',
                'bonuses': ['Maximum Health', 'Spell Resistance', 'Group Minor Courage'],
                'role': 'tank'
            },

            # Healer sets
            'Spell Power Cure': {
                'type': 'dungeon',
                'bonuses': ['Spell Damage', 'Maximum Magicka', 'Group Spell Damage'],
                'role': 'healer'
            },
            'Olorime': {
                'type': 'trial',
                'bonuses': ['Spell Damage', 'Spell Critical', 'Group Major Courage'],
                'role': 'healer'
            },

            # Monster sets
            'Zaan': {
                'type': 'monster',
                'bonuses': ['Spell Damage', 'Flame Damage'],
                'role': 'magicka_dps'
            },
            'Stormfist': {
                'type': 'monster',
                'bonuses': ['Weapon Damage', 'Shock Damage'],
                'role': 'stamina_dps'
            },
            'Lord Warden': {
                'type': 'monster',
                'bonuses': ['Maximum Health', 'Damage Shield'],
                'role': 'tank'
            }
        }

    def identify_sets_from_abilities(self, abilities: Set[str], role: str) -> List[Dict[str, any]]:
        """Attempt to identify gear sets based on abilities and role."""
        # This is a simplified version - real implementation would need
        # to track gear changes from EFFECT_CHANGED events
        identified_sets = []

        # Look for set-specific ability names or effects
        for ability in abilities:
            ability_lower = ability.lower()

            # Check for known set proc names
            if 'mother\'s sorrow' in ability_lower or 'spell critical' in ability_lower:
                identified_sets.append({
                    'name': 'Mother\'s Sorrow',
                    'confidence': 0.7,
                    'source': 'ability_name'
                })
            elif 'false god' in ability_lower or 'perfected false god' in ability_lower:
                identified_sets.append({
                    'name': 'False God\'s Devotion',
                    'confidence': 0.8,
                    'source': 'ability_name'
                })
            elif 'relequen' in ability_lower or 'poisonous serpent' in ability_lower:
                identified_sets.append({
                    'name': 'Relequen',
                    'confidence': 0.8,
                    'source': 'ability_name'
                })

        # If no specific sets identified, suggest common sets for the role
        if not identified_sets:
            role_sets = self._get_common_sets_for_role(role)
            for set_name in role_sets[:2]:  # Top 2 suggestions
                identified_sets.append({
                    'name': set_name,
                    'confidence': 0.3,
                    'source': 'role_suggestion'
                })

        return identified_sets

    def _get_common_sets_for_role(self, role: str) -> List[str]:
        """Get common sets for a given role."""
        role_mapping = {
            'magicka_dps': ['Mother\'s Sorrow', 'False God\'s Devotion', 'Zaan'],
            'stamina_dps': ['Relequen', 'Deadly Strike', 'Stormfist'],
            'tank': ['Ebon Armory', 'Yolnahkriin', 'Lord Warden'],
            'healer': ['Spell Power Cure', 'Olorime']
        }
        return role_mapping.get(role, [])