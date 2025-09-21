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
        'Assassination': ['Surprise Attack', 'Killer\'s Blade', 'Death Stroke', 'Mark Target', 'Teleport Strike', 'Blade of Woe', 'Merciless Resolve', 'Incapacitating Strike', 'Assassin\'s Blade', 'Blur'],
        'Shadow': ['Mirage', 'Dark Cloak', 'Shadow Image', 'Shadowy Disguise', 'Summon Shade', 'Path of Darkness', 'Quick Cloak', 'Shadow Cloak', 'Veiled Strike'],
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
        'Living Death': ['Life amid Death', 'Render Flesh', 'Restoring Tether', 'Braided Tether', 'Renewing Undeath', 'Spirit Mender', 'Echoing Vigor', 'Expunge', 'Spirit Guardian', 'Soul Shred'],
        
        # Arcanist Skill Lines
        'Herald of the Tome': ['Runeblades', 'Fatecarver', 'Pragmatic Fatecarver', 'Abyssal Impact', 'Tentacular Dread', 'Inspired Scholarship', 'Cephaliarch\'s Flail', 'Exhausting Fatecarver', 'The Unblinking Eye', 'Fulminating Rune', 'Recuperative Treatise'],
        'Curative Runeforms': ['Chakram of Destiny', 'Healing Tether', 'Reconstructive Domain', 'Runemend', 'Curative Surge', 'Remedy Cascade', 'Vitalizing Glyphic', 'Runic Defense'],
        'Soldier of Apocrypha': ['Beacon of Protection', 'Impervious Runeward', 'Runeguard of Freedom', 'Apocryphal Gate', 'The Unfathomable Darkness', 'Rune of Eldritch Horror', 'Rune of Displacement']
    }

    # Weapon and guild abilities
    WEAPON_ABILITIES = {
        'Two Handed': ['Uppercut', 'Cleave', 'Carve', 'Wrecking Blow', 'Dizzying Swing'],
        'One Hand and Shield': ['Shield Bash', 'Puncture', 'Shield Wall', 'Shield Charge', 'Power Bash'],
        'Dual Wield': ['Twin Slashes', 'Flurry', 'Whirlwind', 'Blood Craze', 'Rending Slashes', 'Dual Wield Expert', 'Controlled Fury', 'Twin Blade and Blunt'],
        'Bow': ['Snipe', 'Volley', 'Poison Arrow', 'Lethal Arrow', 'Focused Aim'],
        'Destruction Staff': ['Impulse', 'Wall of Elements', 'Destructive Touch', 'Force Pulse', 'Elemental Blockade', 'Blockade of Frost'],
        'Restoration Staff': ['Grand Healing', 'Healing Springs', 'Regeneration', 'Blessing of Protection']
    }

    GUILD_ABILITIES = {
        'Fighters Guild': ['Silver Bolts', 'Circle of Protection', 'Trap Beast', 'Barbed Trap', 'Silver Shards'],
        'Mages Guild': ['Magelight', 'Entropy', 'Fire Rune', 'Meteor', 'Shooting Star'],
        'Undaunted': ['Inner Fire', 'Blood Altar', 'Bone Shield', 'Necrotic Orb', 'Energy Orb'],
        'Thieves Guild': ['Foul Play', 'Clemency'],
        'Dark Brotherhood': ['Blade of Woe', 'Mark Target'],
        'Psijic Order': ['Time Stop', 'Undo', 'Borrowed Time', 'Channeled Acceleration']
    }

    def analyze_subclass(self, abilities: Set[str]) -> Dict[str, any]:
        """Analyze abilities to infer skill lines, role, and build type."""
        if not abilities:
            return {'skill_lines': [], 'role': 'Unknown', 'build_type': 'Unknown', 'confidence': 0.0}

        # Clean ability names for better matching
        clean_abilities = {self._clean_ability_name(ability) for ability in abilities}

        # Score each skill line
        skill_line_scores = {}
        for skill_line, skill_abilities in self.SKILL_LINE_ABILITIES.items():
            score = sum(1 for ability in skill_abilities 
                       if any(self._ability_matches(ability, clean_ability) 
                            for clean_ability in clean_abilities))
            if score > 0:
                skill_line_scores[skill_line] = score

        # Apply priority rules for key abilities
        priority_skill_lines = set()
        
        # If Blazing Spear is present, prioritize Aedric Spear
        if any(self._ability_matches('Blazing Spear', clean_ability) for clean_ability in clean_abilities):
            if 'Aedric Spear' in skill_line_scores:
                priority_skill_lines.add('Aedric Spear')
        
        # Sort skill lines by score (highest first) and take top 3
        # Use skill line name as tie-breaker to ensure consistent ordering
        sorted_skill_lines = sorted(skill_line_scores.items(), key=lambda x: (-x[1], x[0]))
        
        # Build final skill lines list with priorities first, then top scorers
        top_skill_lines = []
        
        # Add priority skill lines first
        for skill_line in priority_skill_lines:
            if skill_line not in top_skill_lines and len(top_skill_lines) < 3:
                top_skill_lines.append(skill_line)
        
        # Add remaining skill lines by score
        for skill_line, score in sorted_skill_lines:
            if skill_line not in top_skill_lines and len(top_skill_lines) < 3:
                top_skill_lines.append(skill_line)

        # Analyze weapons and guilds
        weapon_info = self._analyze_weapons(clean_abilities)
        guild_info = self._analyze_guilds(clean_abilities)

        # Calculate confidence based on number of matching abilities
        total_abilities = len(clean_abilities)
        total_matches = sum(score for _, score in sorted_skill_lines[:3])
        confidence = min(total_matches / max(total_abilities, 1), 1.0) if total_matches > 0 else 0.0

        return {
            'skill_lines': top_skill_lines,
            'weapons': weapon_info,
            'guilds': guild_info,
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

    def _analyze_weapons(self, abilities: Set[str]) -> List[str]:
        """Identify weapons being used based on abilities."""
        weapons = []
        for weapon, weapon_abilities in self.WEAPON_ABILITIES.items():
            if any(self._ability_matches(ability, clean_ability) for ability in weapon_abilities for clean_ability in abilities):
                weapons.append(weapon)
        return weapons

    def _analyze_guilds(self, abilities: Set[str]) -> List[str]:
        """Identify guild skill lines being used."""
        guilds = []
        for guild, guild_abilities in self.GUILD_ABILITIES.items():
            if any(self._ability_matches(ability, clean_ability) for ability in guild_abilities for clean_ability in abilities):
                guilds.append(guild)
        return guilds



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