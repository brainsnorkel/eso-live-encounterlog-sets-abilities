#!/usr/bin/env python3
"""
ESO Encounter Log Analyzer
A CLI tool that continuously monitors ESO encounter logs and analyzes combat encounters.
"""

# Quick version check before any imports
import sys
if len(sys.argv) > 1 and sys.argv[1] in ['-v', '--version']:
    try:
        from version import __version__
        print(f"ESO Live Encounter Log Sets & Abilities Analyzer v{__version__}")
        print(f"Repository: https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities")
        print(f"License: MIT")
        sys.exit(0)
    except ImportError:
        pass

import os
import sys
import time
import csv
import io
import threading
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
import click
import requests
from colorama import init, Fore, Style
from gear_set_database_optimized import gear_set_db

# Add keyboard detection and clipboard functionality
try:
    import pynput
    from pynput import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# Initialize colorama for cross-platform colored output
init()

from version import __version__

# Taunt abilities lookup for highlighting
TAUNT_ABILITIES = {
    'puncture', 'ransack', 'pierce armor', 'inner fire', 'inner rage', 
    'inner beast', 'frost clench', 'runic jolt', 'runic sunder', 'runic embrace',
    'focused charge', 'explosive charge', 'toppling charge', 'goading throw', 'goading vault'
}

def highlight_taunt_abilities(ability_list):
    """Highlight taunt abilities in purple and return formatted list."""
    highlighted_abilities = []
    for ability in ability_list:
        ability_lower = ability.lower()
        if any(taunt in ability_lower for taunt in TAUNT_ABILITIES):
            highlighted_abilities.append(f"{Fore.MAGENTA}{ability}{Style.RESET_ALL}")
        else:
            highlighted_abilities.append(ability)
    return highlighted_abilities

# Import our ESO analysis modules
from eso_sets import ESOSubclassAnalyzer, ESOSetDatabase

# Known mythic item sets (these typically have only 1 piece and unique bonuses)
MYTHIC_SETS = {
    "Velothi Ur-Mage's Amulet",
    "Kilt",  # Harpooner's Wading Kilt
    "Ring of the Pale Order",
    "Snow Treaders",
    "Gaze of Sithis",
    "Thrassian Stranglers",
    "Antiquarian's Eye",
    "Malacath's Band of Brutality",
    "Spaulder of Ruin",
    "Markyn Ring of Majesty",
    "Dov-rha Sabatons",
    "Lefthander's Aegis Belt",
    "Mora's Whispers",
    "Oakensoul Ring",
    "Pearls of Ehlnofey",
    "Sea-Serpent's Coil",
    "Shapeshifter's Chain",
    "Tarnished Nightmare",
    "Torc of Tonal Constancy",
}

# Set types that typically only have 1-2 piece bonuses (no 5pc bonus)
NO_FIVE_PIECE_SET_TYPES = {
    "LIBSETS_SETTYPE_MYTHIC",      # 1 piece only
    "LIBSETS_SETTYPE_MONSTER",     # 2 pieces only
    "LIBSETS_SETTYPE_ARENA",       # Usually 2 pieces (weapon sets)
}

# Cache for set types to avoid repeatedly reading Excel file
_set_type_cache = {}

def has_five_piece_bonus(set_name: str) -> bool:
    """Check if a set has a 5-piece bonus using the gear set database."""
    # Remove "Perfected " prefix for lookup
    clean_name = set_name
    if clean_name.startswith('Perfected '):
        clean_name = clean_name[10:]

    # Check cache first
    if clean_name in _set_type_cache:
        set_type = _set_type_cache[clean_name]
        return set_type not in NO_FIVE_PIECE_SET_TYPES

    # Load set types into cache if not already done
    if not _set_type_cache:
        try:
            import pandas as pd
            excel_file = pd.ExcelFile('/Users/christophergentle/2025-development/eso/live-sets-abilities/setsdb/LibSets_SetData.xlsm')
            df = pd.read_excel(excel_file, sheet_name='Sets data', header=1)

            # Build cache of set name -> set type
            for _, row in df.iterrows():
                name = row.get('Name EN', '')
                set_type = row.get('Set Type', '')
                if name and set_type:
                    _set_type_cache[name] = set_type
        except Exception:
            pass  # If we can't load the database, fall back to defaults

    # Check if set is in cache now
    if clean_name in _set_type_cache:
        set_type = _set_type_cache[clean_name]
        return set_type not in NO_FIVE_PIECE_SET_TYPES

    # If not in database, make an educated guess based on name patterns
    # Most sets have 5pc bonuses except mythics, monster sets, and weapon sets
    mythic_keywords = ['ring', 'amulet', 'kilt', 'treaders', 'gaze', 'stranglers', 'eye', 'band', 'spaulder', 'sabatons', 'belt', 'whispers', 'oakensoul', 'pearls', 'coil', 'chain', 'nightmare', 'torc']
    if any(keyword in clean_name.lower() for keyword in mythic_keywords):
        return False

    # Known 2-piece sets from LibSets database (monster sets + arena weapon sets)
    two_piece_sets = [
        # Monster sets (2-piece)
        "spawn of mephala", "blood spawn", "lord warden", "scourge harvester", "engine guardian", "nightflame",
        "nerien'eth", "valkyn skoria", "maw of the infernal", "molag kena", "mighty chudan", "velidreth",
        "giant spider", "shadowrend", "kra'gh", "swarm mother", "sentinel of rkugamz", "chokethorn",
        "slimecraw", "sellistrix", "infernal guardian", "ilambris", "iceheart", "stormfist", "tremorscale",
        "pirate skeleton", "the troll king", "selene", "grothdarr", "earthgore", "domihaus", "thurvokun",
        "zaan", "balorgh", "vykosa", "stonekeeper", "symphony of blades", "grundwulf", "maarselok",
        "mother ciannait", "kjalnar's nightmare", "stone husk", "lady thorn", "encrati's behemoth",
        "baron zaudrus", "prior thierric", "magma incarnate", "kargaeda", "nazaray", "archdruid devyric",
        "euphotic gatekeeper", "roksa the warped", "ozezan the inferno", "anthelmir's construct",
        "the blind", "squall of retribution", "orpheon the tactician", "nunatak", "nunatak's blessing",
        # Arena weapon sets (2-piece)
        "archer's mind", "footman's fortune", "healer's habit", "robes of destruction mastery", "permafrost",
        "glorious defender", "para bellum", "elemental succession", "hunt leader", "winterborn",
        "titanic cleave", "puncturing remedy", "stinging slashes", "caustic arrow", "destructive impact",
        "grand rejuvenation", "merciless charge", "rampaging slash", "cruel flurry", "thunderous volley",
        "crushing wall", "precise regeneration", "gallant charge", "radial uppercut", "spectral cloak",
        "virulent shot", "wild impulse", "mender's ward", "perfect gallant charge", "perfect radial uppercut",
        "perfect spectral cloak", "perfect virulent shot", "perfect wild impulse", "perfect mender's ward",
        "perfected merciless charge", "perfected rampaging slash", "perfected cruel flurry", "perfected thunderous volley",
        "perfected crushing wall", "perfected precise regeneration", "perfected titanic cleave", "perfected puncturing remedy",
        "perfected stinging slashes", "perfected caustic arrow", "perfected destructive impact", "perfected grand rejuvenation",
        "executioner's blade", "void bash", "frenzied momentum", "point-blank snipe", "wrath of elements",
        "force overflow", "perfected executioner's blade", "perfected void bash", "perfected frenzied momentum",
        "perfected point-blank snipe", "perfected wrath of elements", "perfected force overflow"
    ]
    if any(keyword in clean_name.lower() for keyword in two_piece_sets):
        return False

    # Default: assume it has 5pc bonus unless proven otherwise
    return True

class ESOLogEntry:
    """Represents a single log entry from the ESO encounter log."""

    def __init__(self, timestamp: int, event_type: str, fields: List[str], original_line: str = ""):
        self.timestamp = timestamp
        self.event_type = event_type
        self.fields = fields
        self.original_line = original_line

    @classmethod
    def parse(cls, line: str) -> Optional['ESOLogEntry']:
        """Parse a single log line into an ESOLogEntry."""
        try:
            # Split on comma, handle potential quoting
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)

            if len(fields) < 2:
                return None

            event_type = fields[1]
            
            # Check if the third field is a timestamp (numeric)
            if len(fields) >= 3:
                try:
                    timestamp = int(fields[2])
                    # For certain events, the third field is not a timestamp
                    if event_type in ["UNIT_ADDED", "UNIT_CHANGED", "COMBAT_EVENT", "EFFECT_CHANGED", "BEGIN_CAST", "END_CAST"]:
                        # These events don't have timestamps, use line number as timestamp
                        line_number = int(fields[0]) if fields[0].isdigit() else 0
                        return cls(line_number, event_type, fields[2:], line)
                    else:
                        # These events have timestamps
                        return cls(timestamp, event_type, fields[3:], line)
                except ValueError:
                    # Third field is not a timestamp, treat as data field
                    return cls(0, event_type, fields[2:], line)
            else:
                # No timestamp field, use line number as relative timestamp
                line_number = int(fields[0]) if fields[0].isdigit() else 0
                return cls(line_number, event_type, fields[2:], line)
        except (ValueError, IndexError, StopIteration):
            return None

class PlayerInfo:
    """Stores information about a player character."""

    def __init__(self, unit_id: str, name: str, handle: str, class_id: str = None):
        self.unit_id = unit_id  # Short unit ID from UNIT_ADDED
        self.name = name
        self.handle = handle
        self.class_id = class_id
        self.equipped_abilities: Set[str] = set()
        self.front_bar_abilities: List[str] = []
        self.back_bar_abilities: List[str] = []
        self.gear: Dict[str, List[str]] = {}
        self.last_seen = 0
        self.long_unit_ids: Set[str] = set()

        # Resource tracking (maximum values seen)
        self.max_health: int = 0
        self.max_magicka: int = 0
        self.max_stamina: int = 0

    def update_resources(self, health: int = None, magicka: int = None, stamina: int = None):
        """Update maximum resource values."""
        if health is not None and health > self.max_health:
            self.max_health = health
        if magicka is not None and magicka > self.max_magicka:
            self.max_magicka = magicka
        if stamina is not None and stamina > self.max_stamina:
            self.max_stamina = stamina

    def reset_resources(self):
        """Reset resource tracking."""
        self.max_health = 0
        self.max_magicka = 0
        self.max_stamina = 0

    def get_class_name(self) -> str:
        class_mapping = {
            "1": "Dragonknight",
            "2": "Sorcerer", 
            "3": "Nightblade",
            "4": "Warden",
            "5": "Necromancer",
            "6": "Templar",
            "117": "Arcanist"
        }
        return class_mapping.get(self.class_id, "Unknown")
    
    def get_class_skill_lines(self) -> List[str]:
        class_skill_lines = {
            "1": ["Ardent Flame", "Draconic Power", "Earthen Heart"],  # Dragonknight
            "2": ["Dark Magic", "Daedric Summoning", "Storm Calling"],  # Sorcerer
            "3": ["Assassination", "Shadow", "Siphoning"],  # Nightblade
            "4": ["Animal Companions", "Green Balance", "Winter's Embrace"],  # Warden
            "5": ["Bone", "Grave Lord", "Living Death"],  # Necromancer
            "6": ["Aedric Spear", "Dawn's Wrath", "Restoring Light"],  # Templar
            "117": ["Herald of the Tome", "Soldier of Apocrypha", "Curative Runeforms"]  # Arcanist
        }
        return class_skill_lines.get(self.class_id, [])


    def set_equipped_abilities(self, ability_names: Set[str]):
        """Set the equipped abilities from PLAYER_INFO."""
        self.equipped_abilities = ability_names

    def set_front_back_bar_abilities(self, front_bar: List[str], back_bar: List[str]):
        """Set the front and back bar abilities from PLAYER_INFO."""
        self.front_bar_abilities = front_bar
        self.back_bar_abilities = back_bar

    def set_gear(self, gear_data: List[List[str]]):
        """Set the gear data from PLAYER_INFO."""
        self.gear = {}
        for gear_item in gear_data:
            if len(gear_item) >= 2:
                slot = gear_item[0]
                self.gear[slot] = gear_item

    def add_long_unit_id(self, long_unit_id: str):
        """Add a long unit ID that maps to this player."""
        self.long_unit_ids.add(long_unit_id)


    def has_unit_id(self, unit_id: str) -> bool:
        """Check if this unit ID (short or long) belongs to this player."""
        return unit_id == self.unit_id or unit_id in self.long_unit_ids

    def get_display_name(self) -> str:
        """Get the display name for this player (handle or 'anon')."""
        if self.handle and self.handle not in ['""', '', '0']:
            return self.handle
        elif self.name and self.name not in ['""', '', '0']:
            return self.name
        else:
            return "anon"

class EnemyInfo:
    """Stores information about an enemy unit."""

    def __init__(self, unit_id: str, name: str, unit_type: str):
        self.unit_id = unit_id
        self.name = name
        self.unit_type = unit_type
        self.max_health: int = 0
        self.current_health: int = 0
        self.is_hostile: bool = False

class CombatEncounter:
    """Represents a single combat encounter."""

    def __init__(self):
        self.start_time: int = 0
        self.end_time: int = 0
        self.players: Dict[str, PlayerInfo] = {}  # Keyed by short unit ID
        self.enemies: Dict[str, EnemyInfo] = {}  # Track enemy units
        self.abilities_used: Dict[str, Set[str]] = defaultdict(set)
        self.total_damage: int = 0  # Track total damage dealt
        self.player_damage: Dict[str, int] = {}  # Track damage per player (including pets)
        self.enemy_damage: Dict[str, int] = {}  # Track damage dealt to each enemy
        self.total_health_damaged: int = 0  # Track total health of all damaged enemies
        self.player_deaths: int = 0  # Track player deaths
        self.in_combat = False
        self.finalized = False  # Track if encounter has been finalized (ended)
        
        # Buff tracking
        self.player_buffs: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))  # player_id -> buff_name -> [(start_time, end_time)]
        self.active_buffs: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # player_id -> buff_name -> start_time
        
        # Pet ownership tracking
        self.pet_ownership: Dict[str, str] = {}
        
        # Track combat end time
        self.combat_ended_at: Optional[int] = None
        
        # Grace period logic removed - encounters are finalized immediately on END_COMBAT
        
        # Track highest health hostile monster in this fight
        self.highest_health_hostile: Optional[EnemyInfo] = None
        self.most_damaged_hostile: Optional[EnemyInfo] = None

    def add_player(self, unit_id: str, name: str, handle: str, class_id: str = None):
        """Add a player to this encounter."""
        # Skip offline players
        if name == "Offline":
            return
        self.players[unit_id] = PlayerInfo(unit_id, name, handle, class_id)

    def add_enemy(self, unit_id: str, name: str, unit_type: str):
        """Add an enemy to this encounter."""
        self.enemies[unit_id] = EnemyInfo(unit_id, name, unit_type)

    def track_pet_ownership(self, pet_unit_id: str, owner_unit_id: str):
        """Track that a pet belongs to a specific player."""
        self.pet_ownership[pet_unit_id] = owner_unit_id

    def is_friendly_unit(self, unit_id: str) -> bool:
        """Check if a unit ID belongs to a friendly player or their pet."""
        # Check if it's a known player
        if self.find_player_by_unit_id(unit_id):
            return True
        
        # Check if it's a known pet of a friendly player
        if unit_id in self.pet_ownership:
            owner_id = self.pet_ownership[unit_id]
            return self.find_player_by_unit_id(owner_id) is not None
        
        # Note: Removed overly broad 1-50 fallback as it was filtering out legitimate hostile enemies
            
        return False
    
    def update_highest_health_hostile(self, enemy: EnemyInfo):
        """Update the highest health hostile monster if this enemy has more health."""
        # Only consider HOSTILE monsters (not players or pets)
        if (not self.is_friendly_unit(enemy.unit_id) and 
            enemy.max_health > 0 and 
            hasattr(enemy, 'is_hostile') and enemy.is_hostile):
            if (self.highest_health_hostile is None or 
                enemy.max_health > self.highest_health_hostile.max_health or
                (enemy.max_health == self.highest_health_hostile.max_health and "Stormreeve" in enemy.name)):
                self.highest_health_hostile = enemy
    
    def update_most_damaged_hostile(self, unit_id: str):
        """Update the most damaged hostile monster based on player damage."""
        if unit_id in self.enemies:
            enemy = self.enemies[unit_id]
            if (hasattr(enemy, 'is_hostile') and enemy.is_hostile and 
                unit_id in self.enemy_damage):
                damage = self.enemy_damage[unit_id]
                if (self.most_damaged_hostile is None or 
                    damage > self.enemy_damage.get(self.most_damaged_hostile.unit_id, 0)):
                    self.most_damaged_hostile = enemy
    
    def update_enemy_health(self, unit_id: str, current_health: int, max_health: int):
        """Update an enemy's health values and check if it's now the highest health hostile."""
        if unit_id in self.enemies:
            enemy = self.enemies[unit_id]
            # Update health values
            enemy.current_health = current_health
            enemy.max_health = max_health
            
            # Update highest health hostile if this is a hostile monster
            self.update_highest_health_hostile(enemy)

    def _is_valid_enemy(self, enemy: EnemyInfo) -> bool:
        """Check if an enemy represents a valid combat target."""
        # First check if this unit is a friendly (player or pet)
        if self.is_friendly_unit(enemy.unit_id):
            return False
        
        # Fallback: exclude known environmental hazards and generic terms
        excluded_names = {
            # Environmental hazards and mechanics
            'water', 'fire', 'lava', 'poison', 'ice', 'lightning', 'void',
            'trap', 'spike', 'flame', 'steam', 'gas', 'cloud', 'mist',
            'beam', 'laser', 'ray', 'orb', 'crystal', 'shard', 'fragment',
            'portal', 'gate', 'door', 'barrier', 'wall', 'shield',
            
            # Generic environmental terms
            'element', 'energy', 'force', 'field', 'aura', 'zone', 'area',
            'mechanism', 'device', 'construct', 'apparatus'
        }
        
        enemy_name_lower = enemy.name.lower()
        return not any(excluded_name in enemy_name_lower for excluded_name in excluded_names)

    def get_highest_health_enemy(self) -> Optional[EnemyInfo]:
        """Get the enemy with the highest health, excluding pets, corpses, and environmental hazards."""
        if not self.enemies:
            return None
        
        max_health = 0
        highest_health_enemy = None
        
        for enemy in self.enemies.values():
            # Skip if not a valid enemy target
            if not self._is_valid_enemy(enemy):
                continue
                
            if enemy.max_health > max_health:
                max_health = enemy.max_health
                highest_health_enemy = enemy
                
        return highest_health_enemy

    def get_most_damaged_enemy(self) -> Optional[EnemyInfo]:
        """Get the enemy that took the most damage, excluding pets, corpses, and environmental hazards."""
        if not self.enemies or not self.enemy_damage:
            return None
        
        max_damage = 0
        most_damaged_enemy = None
        
        for unit_id, damage in self.enemy_damage.items():
            enemy = self.enemies.get(unit_id)
            if enemy:
                # Skip if not a valid enemy target
                if not self._is_valid_enemy(enemy):
                    continue
                    
                if damage > max_damage:
                    max_damage = damage
                    most_damaged_enemy = enemy
                    
        return most_damaged_enemy

    def add_ability_use(self, unit_id: str, ability_name: str):
        """Record an ability use by a player (for tracking purposes only)."""
        player = self.find_player_by_unit_id(unit_id)
        if player:
            self.abilities_used[player.unit_id].add(ability_name)

    def find_player_by_unit_id(self, unit_id: str) -> Optional[PlayerInfo]:
        """Find a player by either short or long unit ID."""
        for player in self.players.values():
            if player.has_unit_id(unit_id):
                return player
        return None

    def associate_long_unit_id(self, short_unit_id: str, long_unit_id: str):
        """Associate a long unit ID with a player's short unit ID."""
        if short_unit_id in self.players:
            self.players[short_unit_id].add_long_unit_id(long_unit_id)

    def add_damage_to_player(self, unit_id: str, damage: int):
        """Add damage to a specific player's total (players and their pets)."""
        # Find the player this unit belongs to
        player = self.find_player_by_unit_id(unit_id)
        if player:
            if player.unit_id not in self.player_damage:
                self.player_damage[player.unit_id] = 0
            self.player_damage[player.unit_id] += damage
        else:
            # Check if this is a pet of a player
            if unit_id in self.pet_ownership:
                owner_id = self.pet_ownership[unit_id]
                owner_player = self.find_player_by_unit_id(owner_id)
                if owner_player:
                    if owner_player.unit_id not in self.player_damage:
                        self.player_damage[owner_player.unit_id] = 0
                    self.player_damage[owner_player.unit_id] += damage

    def track_buff(self, player_unit_id: str, buff_name: str, effect_type: str, timestamp: int):
        """Track buff applications and removals for uptime calculation."""
        if effect_type == "GAINED":
            # Start tracking this buff
            self.active_buffs[player_unit_id][buff_name] = timestamp
        elif effect_type == "FADED":
            # End tracking this buff and record the duration
            if buff_name in self.active_buffs[player_unit_id]:
                start_time = self.active_buffs[player_unit_id][buff_name]
                self.player_buffs[player_unit_id][buff_name].append((start_time, timestamp))
                del self.active_buffs[player_unit_id][buff_name]

    def get_buff_uptime(self, player_unit_id: str, buff_name: str) -> float:
        """Calculate uptime percentage for a specific buff on a player."""
        if not self.player_buffs[player_unit_id][buff_name]:
            return 0.0
        
        total_uptime = 0
        for start_time, end_time in self.player_buffs[player_unit_id][buff_name]:
            total_uptime += (end_time - start_time)
        
        # Add any currently active buff time
        if buff_name in self.active_buffs[player_unit_id]:
            current_time = self.end_time if self.end_time > 0 else self.start_time
            total_uptime += (current_time - self.active_buffs[player_unit_id][buff_name])
        
        if self.end_time > self.start_time:
            duration = self.end_time - self.start_time
            return (total_uptime / duration) * 100.0
        return 0.0

    def finalize_buff_tracking(self):
        """Finalize buff tracking by ending any active buffs at encounter end."""
        for player_id, active_buffs in self.active_buffs.items():
            for buff_name, start_time in active_buffs.items():
                end_time = self.end_time if self.end_time > 0 else self.start_time
                self.player_buffs[player_id][buff_name].append((start_time, end_time))
        self.active_buffs.clear()

    def get_combat_start_time_formatted(self, log_file_path: str = None, log_start_unix: int = None) -> str:
        """Get the combat start time formatted as local date/time."""
        if not self.start_time:
            return "Unknown Time"
        
        import datetime
        
        # Use Unix timestamp from BEGIN_LOG event if available (most accurate)
        if log_start_unix:
            try:
                log_start_dt = datetime.datetime.fromtimestamp(log_start_unix / 1000.0)
                combat_start_dt = log_start_dt + datetime.timedelta(milliseconds=self.start_time)
                return combat_start_dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass
        
        # Fallback: Use file modification time
        if log_file_path:
            import os
            try:
                if os.path.exists(log_file_path):
                    file_mtime = os.path.getmtime(log_file_path)
                    file_time = datetime.datetime.fromtimestamp(file_mtime)
                    combat_start_time = file_time - datetime.timedelta(seconds=(self.end_time - self.start_time) / 1000.0)
                    return combat_start_time.strftime("%Y-%m-%d %H:%M:%S")
            except (OSError, ValueError):
                pass
        
        # Final fallback: Use current time minus the relative timestamp
        current_time = datetime.datetime.now()
        base_time = current_time - datetime.timedelta(seconds=self.start_time / 1000.0)
        
        return base_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_group_buff_uptime(self, buff_name: str) -> float:
        """Calculate uptime percentage for a group buff (active on any player)."""
        # Collect all time intervals when the buff was active on any player
        active_intervals = []
        
        # Check all players for this buff
        for player_id in self.players.keys():
            # Add completed buff periods
            if buff_name in self.player_buffs[player_id]:
                for start_time, end_time in self.player_buffs[player_id][buff_name]:
                    # Clamp intervals to encounter bounds
                    start_clamped = max(start_time, self.start_time)
                    end_clamped = min(end_time, self.end_time) if self.end_time > 0 else end_time
                    if start_clamped < end_clamped:
                        active_intervals.append((start_clamped, end_clamped))
            
            # Add currently active buff
            if buff_name in self.active_buffs[player_id]:
                start_time = self.active_buffs[player_id][buff_name]
                end_time = self.end_time if self.end_time > 0 else self.start_time
                # Clamp to encounter bounds
                start_clamped = max(start_time, self.start_time)
                end_clamped = min(end_time, self.end_time) if self.end_time > 0 else end_time
                if start_clamped < end_clamped:
                    active_intervals.append((start_clamped, end_clamped))
        
        if not active_intervals:
            return 0.0
        
        # Merge overlapping intervals and calculate total active time
        active_intervals.sort()  # Sort by start time
        merged_intervals = []
        
        for start, end in active_intervals:
            if not merged_intervals or merged_intervals[-1][1] < start:
                # No overlap, add new interval
                merged_intervals.append((start, end))
            else:
                # Overlap exists, extend the last interval
                merged_intervals[-1] = (merged_intervals[-1][0], max(merged_intervals[-1][1], end))
        
        # Calculate total active time
        total_active_time = sum(end - start for start, end in merged_intervals)
        
        # Calculate uptime percentage
        encounter_duration = self.end_time - self.start_time if self.end_time > self.start_time else 0
        if encounter_duration > 0:
            uptime_percentage = (total_active_time / encounter_duration) * 100.0
            # Cap at 100% to prevent display issues
            return min(uptime_percentage, 100.0)
        return 0.0

    def get_group_buff_analysis(self) -> Dict[str, bool]:
        """Analyze which group buffs are present across all players."""
        group_buffs = ['Major Courage', 'Major Force', 'Major Slayer']
        buff_analysis = {}
        
        for buff_name in group_buffs:
            # Check if any player had this buff during the encounter
            has_buff = False
            for player_id in self.players.keys():
                if buff_name in self.player_buffs[player_id] and self.player_buffs[player_id][buff_name]:
                    has_buff = True
                    break
                # Also check if buff is currently active
                if buff_name in self.active_buffs[player_id]:
                    has_buff = True
                    break
            buff_analysis[buff_name] = has_buff
        
        return buff_analysis

class ESOLogAnalyzer:
    """Main analyzer class for processing ESO encounter logs."""

    def __init__(self, list_hostiles: bool = False, diagnostic: bool = False, save_reports: bool = False, reports_dir: Optional[Path] = None):
        self.current_encounter: Optional[CombatEncounter] = None
        self.ability_cache: Dict[str, str] = {}  # ability_id -> ability_name
        self.gear_cache: Dict[str, str] = {}  # gear_item_id -> gear_set_name
        self.current_zone: Optional[str] = None  # Track current zone name
        self.current_difficulty: Optional[str] = None  # Track current difficulty
        self.zone_deaths: int = 0  # Track total deaths since entering current zone
        self.subclass_analyzer = ESOSubclassAnalyzer()
        self.set_database = ESOSetDatabase()
        self.current_log_file: Optional[str] = None  # Track current log file path
        self.log_start_unix_timestamp: Optional[int] = None  # Unix timestamp from BEGIN_LOG event
        
        # Testing flag for listing hostile monsters
        self.list_hostiles = list_hostiles
        self.hostile_monsters: List[Tuple[str, str, str]] = []  # (unit_id, name, unit_type)
        self.engaged_monsters: Set[str] = set()  # Track monsters that appear in combat events
        
        # Diagnostic mode for debugging data flow and timing
        self.diagnostic = diagnostic
        
        # Report saving functionality
        self.save_reports = save_reports
        self.reports_dir = reports_dir
        self.report_buffer = []  # Buffer to collect report output lines
        
        # Zone history tracking for rewind functionality
        self.zone_history: List[Tuple[int, str]] = []  # (timestamp, zone_name)
        self.max_zone_history = 10  # Keep last 10 zone changes
        
        # Add Discord markdown functionality
        self.last_encounter_report = None
        self.keyboard_listener = None
        self.discord_copy_enabled = True
        
        # Group buff ability IDs - updated with correct IDs from user
        self.major_courage_ids = {
            '61665',  # Major Courage - Increases Weapon and Spell Damage by 430
        }
        
        # Group buff IDs for tracking in encounters with 3+ players
        self.group_buff_ids = {
            'Major Courage': self.major_courage_ids,
            'Major Force': {'40225'},  # Increases Critical Damage by 20%
            'Major Slayer': {'93120', '931200'},  # Increases damage done to Dungeon, Trial, and Arena monsters by 10%
        }
        
        # Session tracking for players going offline/online
        self.player_sessions: Dict[str, Dict] = {}  # handle+name -> {unit_id, name, equipped_abilities, gear_data, last_seen}
        self.unit_id_to_handle: Dict[str, str] = {}  # unit_id -> handle
        
        # Initialize the robust log parser
        from eso_log_parser import ESOLogParser
        self.log_parser = ESOLogParser()
        
        # Initialize gear set mapping database
        self._initialize_gear_database()

    def _add_zone_to_history(self, timestamp: int, zone_name: str):
        """Add a zone change to the history for rewind functionality."""
        self.zone_history.append((timestamp, zone_name))
        # Keep only the most recent zone changes
        if len(self.zone_history) > self.max_zone_history:
            self.zone_history.pop(0)

    def _rewind_to_last_zone(self) -> bool:
        """Rewind to the last known zone when combat events are encountered without current zone."""
        if not self.zone_history:
            return False
        
        # Get the most recent zone
        last_timestamp, last_zone = self.zone_history[-1]
        
        print(f"{Fore.YELLOW}No current zone detected. Rewinding to last zone: {last_zone}{Style.RESET_ALL}")
        
        # Set the current zone to the last known zone
        self.current_zone = last_zone
        
        # Create a new encounter for this zone
        self.current_encounter = CombatEncounter()
        self.current_encounter.start_time = last_timestamp
        
        return True

    def _process_log_file_from_position(self, log_file: Path, start_position: int = 0, end_position: Optional[int] = None) -> List[ESOLogEntry]:
        """Process a portion of the log file to find zone changes and combat events."""
        entries = []
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                if start_position > 0:
                    f.seek(start_position)
                
                for line in f:
                    if end_position and f.tell() > end_position:
                        break
                        
                    line = line.strip()
                    if line:
                        entry = ESOLogEntry.parse(line)
                        if entry:
                            entries.append(entry)
        except (IOError, UnicodeDecodeError) as e:
            print(f"{Fore.RED}Error reading log file for rewind: {e}{Style.RESET_ALL}")
        
        return entries

    def _initialize_gear_database(self):
        """Initialize gear item ID to gear set name mapping."""
        # Use the gear set database instead of hardcoded data
        self.gear_cache = gear_set_db.item_to_set
        self.gear_set_abilities = gear_set_db.ability_to_set

    def _is_two_handed_weapon(self, gear_item: List[str], player_gear: Dict[str, List[str]]) -> bool:
        """
        Check if a gear item is a 2-handed weapon (staff, bow, 2H axe, 2H mace, 2H sword).

        Args:
            gear_item: List containing gear item data [slot, item_id, ...]
            player_gear: Complete gear dictionary for the player

        Returns:
            True if the item is a 2-handed weapon, False otherwise
        """
        if len(gear_item) < 2:
            return False

        slot = gear_item[0]

        # Only check MAIN_HAND and BACKUP_MAIN slots
        if slot not in ['MAIN_HAND', 'BACKUP_MAIN']:
            return False

        # Check for known 2-handed weapon item IDs first (staffs, bows, 2H weapons)
        item_id = gear_item[1] if len(gear_item) > 1 else ""

        # Known 2-handed weapon item IDs - these are definitively 2-handed
        # TODO: This list should be expanded with more known 2H weapon IDs
        known_two_handed_items = {
            # Add known staff, bow, and 2H weapon item IDs here
            # Example: '87874': 'Staff', # Perfected Slivers Lightning Staff
        }

        if item_id in known_two_handed_items:
            return True

        # Check if there's a corresponding OFF_HAND weapon
        off_hand_key = 'OFF_HAND'
        backup_off_key = 'BACKUP_OFF'

        if slot == 'BACKUP_MAIN':
            # For backup weapons, check if there's a BACKUP_OFF
            if backup_off_key in player_gear and player_gear[backup_off_key]:
                backup_off_item = player_gear[backup_off_key]
                if len(backup_off_item) > 1:
                    backup_off_item_id = backup_off_item[1]
                    # If both weapons have the same item ID, they're dual-wielding (1-handed)
                    if backup_off_item_id == item_id:
                        return False
                    # If off-hand has valid item ID and isn't empty, main hand is 1-handed
                    if backup_off_item_id != "0" and backup_off_item_id != "":
                        return False
                    # If off-hand has armor trait, it's a shield - main hand is 1-handed
                    if len(backup_off_item) > 4 and "ARMOR" in backup_off_item[4]:
                        return False
            # If no backup off-hand equipped, assume 2-handed (staff, bow, 2H weapon)
            return True

        # For main hand, check if there's an off-hand weapon
        if off_hand_key in player_gear and player_gear[off_hand_key]:
            off_hand_item = player_gear[off_hand_key]
            if len(off_hand_item) > 1:
                off_hand_item_id = off_hand_item[1]
                # If both weapons have the same item ID, they're dual-wielding (1-handed)
                if off_hand_item_id == item_id:
                    return False
                # If off-hand has valid item ID and isn't empty, main hand is 1-handed
                if off_hand_item_id != "0" and off_hand_item_id != "":
                    return False
                # If off-hand has armor trait, it's a shield - main hand is 1-handed
                if len(off_hand_item) > 4 and "ARMOR" in off_hand_item[4]:
                    return False

        # If no off-hand weapon equipped, assume 2-handed (staff, bow, 2H weapon)
        return True

    def process_log_entry(self, entry: ESOLogEntry):
        """Process a single log entry."""
        # Check grace period before processing any events
        # Grace period logic removed - encounters are finalized immediately on END_COMBAT
        
        if self.diagnostic and entry.event_type in ["ZONE_CHANGED", "UNIT_ADDED", "BEGIN_COMBAT", "END_COMBAT"]:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Processing {entry.event_type} at {entry.timestamp}{Style.RESET_ALL}")
        
        if entry.event_type == "UNIT_ADDED":
            self._handle_unit_added(entry)
        elif entry.event_type == "UNIT_CHANGED":
            self._handle_unit_changed(entry)
        elif entry.event_type == "ABILITY_INFO":
            self._handle_ability_info(entry)
        elif entry.event_type == "PLAYER_INFO":
            self._handle_player_info(entry)
        elif entry.event_type == "ZONE_CHANGED":
            self._handle_zone_changed(entry)
        elif entry.event_type == "BEGIN_CAST":
            self._handle_begin_cast(entry)
        elif entry.event_type == "EFFECT_CHANGED":
            self._handle_effect_changed(entry)
        elif entry.event_type == "COMBAT_EVENT":
            self._handle_combat_event(entry)
        elif entry.event_type == "BEGIN_COMBAT":
            self._handle_begin_combat_event(entry)
        elif entry.event_type == "END_COMBAT":
            self._handle_end_combat_event(entry)
        elif entry.event_type == "BEGIN_LOG":
            self._handle_begin_log_event(entry)
        elif entry.event_type == "ZONE_CHANGED":
            self._handle_zone_changed(entry)

    def _check_pending_encounter_display(self):
        """Check if we have an encounter that ended but hasn't been displayed yet."""
        if (self.current_encounter and 
            self.current_encounter.combat_ended_at and 
            not self.current_encounter.finalized and 
            self.current_encounter.players):
            
            # Display the encounter if it's been ended
            self.current_encounter.finalized = True
            self._display_encounter_summary(self.current_zone)

    def _handle_unit_added(self, entry: ESOLogEntry):
        """Handle UNIT_ADDED events to track players and enemies."""
        # UNIT_ADDED format: timestamp,UNIT_ADDED,unit_id,unit_type,F/T,unknown,unknown,F/T,unknown,unknown,"name","@handle",...
        # After parsing, fields[0] = unit_id, fields[1] = unit_type, etc.
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: _handle_unit_added called with {len(entry.fields)} fields{Style.RESET_ALL}")
        
        if len(entry.fields) >= 10:
            unit_id = entry.fields[0]
            unit_type = entry.fields[1]
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: UNIT_ADDED unit_id={unit_id}, unit_type={unit_type}{Style.RESET_ALL}")
            
            # Handle player units
            if unit_type == "PLAYER":
                name = entry.fields[8] if len(entry.fields) > 8 else ""
                handle = entry.fields[9] if len(entry.fields) > 9 else ""
                long_unit_id = entry.fields[10] if len(entry.fields) > 10 else ""
                class_id = entry.fields[6] if len(entry.fields) > 6 else ""  # Class ID is in field 7 (index 6)

                # Only add players if we have a current encounter (zone has been set)
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: UNIT_ADDED player {unit_id}, encounter exists: {self.current_encounter is not None}{Style.RESET_ALL}")
                
                if self.current_encounter:
                    # Clean up name and handle (remove quotes if present)
                    clean_name = name.strip('"') if name else ""
                    clean_handle = handle.strip('"') if handle else ""
                    
                    if self.diagnostic:
                        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                        print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Adding player {unit_id} ({clean_name}) to encounter{Style.RESET_ALL}")

                    # Check if this is a returning player from session data
                    session_key = f"{clean_handle}+{clean_name}"
                    if session_key in self.player_sessions:
                        # Restore player from session data
                        self._restore_player_from_session(unit_id, clean_name, clean_handle)
                    else:
                        # New player - add normally with class ID
                        self.current_encounter.add_player(unit_id, clean_name, clean_handle, class_id)
                    
                    # Update session data
                    self._update_player_session(unit_id, clean_name, clean_handle, class_id=class_id)
                    
                    # Associate the long unit ID with the player
                    if long_unit_id and long_unit_id != "0":
                        self.current_encounter.associate_long_unit_id(unit_id, long_unit_id)
            
            # Handle enemy units (MONSTER, NPC, etc.)
            elif unit_type in ["MONSTER", "NPC"]:
                name = entry.fields[8] if len(entry.fields) > 8 else ""
                health = 0
                is_hostile = False
                
                # Extract health from field [4] if available (105634 in the example)
                if len(entry.fields) > 4 and entry.fields[4].isdigit():
                    health = int(entry.fields[4])
                
                # Check if this is a HOSTILE monster (field [14] in the example)
                if len(entry.fields) > 14 and entry.fields[14] == "HOSTILE":
                    is_hostile = True
                
                # Add ALL monsters (including FRIENDLY) so they can be updated later via UNIT_CHANGED
                if self.current_encounter and name and name != '0':
                    clean_name = name.strip('"') if name else ""
                    
                    enemy = EnemyInfo(unit_id, clean_name, unit_type)
                    enemy.max_health = health
                    enemy.current_health = health
                    enemy.is_hostile = is_hostile
                    
                    self.current_encounter.enemies[unit_id] = enemy
                    
                    # Update highest health hostile monster (only if currently hostile)
                    if is_hostile:
                        self.current_encounter.update_highest_health_hostile(enemy)
                        
                        # Track hostile monsters for testing flag
                        if self.list_hostiles:
                            self.hostile_monsters.append((unit_id, clean_name, unit_type))

    def _handle_unit_changed(self, entry: ESOLogEntry):
        """Handle UNIT_CHANGED events to track when monsters become hostile."""
        # UNIT_CHANGED format: timestamp,UNIT_CHANGED,unit_id,unknown,unknown,"name","",unknown,unknown,unknown,unknown,new_state,unknown
        # After parsing: fields[0]=unit_id, fields[3]=name, fields[9]=new_state
        if self.current_encounter and len(entry.fields) >= 10:
            unit_id = entry.fields[0]
            name = entry.fields[3] if len(entry.fields) > 3 else ""
            new_state = entry.fields[9] if len(entry.fields) > 9 else ""
            
            # Only process if this is a known enemy and it's becoming HOSTILE
            if (unit_id in self.current_encounter.enemies and 
                new_state == "HOSTILE" and name and name != '0'):
                
                enemy = self.current_encounter.enemies[unit_id]
                enemy.is_hostile = True
                
                # Update highest health hostile monster now that this enemy is hostile
                self.current_encounter.update_highest_health_hostile(enemy)
                
                # Track hostile monsters for testing flag
                if self.list_hostiles:
                    clean_name = name.strip('"') if name else ""
                    self.hostile_monsters.append((unit_id, clean_name, enemy.unit_type))

    def _handle_ability_info(self, entry: ESOLogEntry):
        """Handle ABILITY_INFO events to cache ability names and gear sets."""
        # Check if entry is already a AbilityInfoEntry
        if hasattr(entry, 'ability_id') and hasattr(entry, 'ability_name'):
            # Entry is already parsed as AbilityInfoEntry
            parsed = entry
        else:
            # Entry needs to be parsed
            parsed = self.log_parser.parse_ability_info(entry)
            
        if parsed:
            # Update both caches with the parsed ability info
            self.ability_cache[parsed.ability_id] = parsed.ability_name
            self.log_parser.ability_cache[parsed.ability_id] = parsed.ability_name
            
            # Check if this ability is actually a gear set (some gear sets appear as abilities)
            ability_name_lower = parsed.ability_name.lower()
            if any(set_name in ability_name_lower for set_name in ['bahsei', 'mother', 'sorrow', 'relequen', 'spell power', 'false god', 'deadly strike']):
                # This is a gear set ability - we can use it for gear set identification
                # Debug output removed for clean operation
                pass

    def _handle_player_info(self, entry: ESOLogEntry):
        """Handle PLAYER_INFO events to get equipped abilities and gear."""
        # Use the shared robust parser to handle the complex PLAYER_INFO format
        # Ensure caches are synchronized (both directions)
        self.log_parser.ability_cache = self.ability_cache  # Sync analyzer -> parser
        self.ability_cache.update(self.log_parser.ability_cache)  # Sync parser -> analyzer
        
        # Check if entry is already a PlayerInfoEntry
        if hasattr(entry, 'unit_id') and hasattr(entry, 'ability_ids'):
            # Entry is already parsed as PlayerInfoEntry
            player_info = entry
        else:
            # Entry needs to be parsed
            player_info = self.log_parser.parse_player_info(entry)
            
        if player_info:
            # Get equipped ability names (all abilities)
            equipped_ability_names = self.log_parser.get_equipped_abilities(player_info)
            # Get front and back bar abilities separately
            front_bar_abilities = self.log_parser.get_front_bar_abilities(player_info)
            back_bar_abilities = self.log_parser.get_back_bar_abilities(player_info)
            
            # Find the player and set their equipped abilities and gear
            if self.current_encounter and player_info.unit_id in self.current_encounter.players:
                player = self.current_encounter.players[player_info.unit_id]
                player.set_equipped_abilities(equipped_ability_names)
                player.set_front_back_bar_abilities(front_bar_abilities, back_bar_abilities)
                player.set_gear(player_info.gear_data)
                # Store equipped ability IDs for gear set detection (both bars)
                player._equipped_ability_ids = set(player_info.champion_points + player_info.additional_data)
                
                # Update session data with new player info
                self._update_player_session(
                    player_info.unit_id, 
                    player.name, 
                    player.handle, 
                    equipped_ability_names, 
                    player_info.gear_data
                )
                

    def _handle_zone_changed(self, entry: ESOLogEntry):
        """Handle ZONE_CHANGED events to reset all known players."""
        # ZONE_CHANGED format: zone_id, zone_name, difficulty
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: _handle_zone_changed called{Style.RESET_ALL}")
        
        if len(entry.fields) >= 2:
            zone_name = entry.fields[0].strip('"')
            difficulty = entry.fields[1].strip('"')
            
            # Store previous zone name before updating
            previous_zone = self.current_zone if self.current_zone else "Unknown"
            
            print(f"\n{Fore.YELLOW}=== ZONE CHANGED ==={Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Zone: {zone_name} ({difficulty}){Style.RESET_ALL}")
            print(f"{Fore.CYAN}ESO Live Encounter Log Sets & Abilities Analyzer v{__version__}{Style.RESET_ALL}")
            
            # If there's an active encounter when zone changes, display it if it ended but wasn't shown
            if (self.current_encounter and self.current_encounter.combat_ended_at and 
                not self.current_encounter.finalized and self.current_encounter.players):
                self.current_encounter.finalized = True
                self._display_encounter_summary(self.current_zone)
            
            # Reset any existing encounter
            if self.current_encounter:
                self.current_encounter = None
            
            # Update current zone and difficulty after processing previous zone's combat
            self.current_zone = zone_name
            self.current_difficulty = difficulty
            
            # Add this zone change to history for rewind functionality
            self._add_zone_to_history(entry.timestamp, zone_name)
            
            # Clean up offline players
            self._cleanup_offline_players()
            
            # Reset death counter for new zone
            self.zone_deaths = 0
            
            # Reset all tracking - create new encounter for this zone
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: ZONE_CHANGED created new encounter at {entry.timestamp}{Style.RESET_ALL}")

    def _handle_begin_combat_event(self, entry: ESOLogEntry):
        """Handle BEGIN_COMBAT events to start combat tracking."""
        # BEGIN_COMBAT format: timestamp,BEGIN_COMBAT (no additional data)
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_COMBAT at {entry.timestamp}, encounter exists: {self.current_encounter is not None}, players: {len(self.current_encounter.players) if self.current_encounter else 0}{Style.RESET_ALL}")
        
        # Check if we need to rewind to a previous zone
        if not self.current_zone and self.zone_history:
            self._rewind_to_last_zone()
        
        # Grace period logic removed - encounters are finalized immediately on END_COMBAT
        
        # If we have a previous encounter that ended but wasn't displayed, display it now
        if (self.current_encounter and self.current_encounter.combat_ended_at and 
            not self.current_encounter.finalized and self.current_encounter.players):
            self.current_encounter.finalized = True
            self._display_encounter_summary(self.current_zone)
            # Don't reset to None - we'll reuse the encounter and preserve players
        
        # Create a new encounter if we don't have one or if the previous one was finalized
        if not self.current_encounter or self.current_encounter.finalized:
            # Create new encounter but preserve players and enemies from previous encounter in same zone
            old_players = {}
            old_enemies = {}
            if self.current_encounter:
                if self.current_encounter.players:
                    old_players = self.current_encounter.players.copy()
                if self.current_encounter.enemies:
                    old_enemies = self.current_encounter.enemies.copy()
            
            self.current_encounter = CombatEncounter()

            # Restore players and enemies from previous encounter (they persist across combats in same zone)
            self.current_encounter.players = old_players
            self.current_encounter.enemies = old_enemies

            # Reset resource tracking for all players for the new encounter
            for player in self.current_encounter.players.values():
                player.reset_resources()
        
        # Mark combat as active and set start time to BEGIN_COMBAT timestamp
        self.current_encounter.in_combat = True
        self.current_encounter.start_time = entry.timestamp
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: After BEGIN_COMBAT, players: {len(self.current_encounter.players)}{Style.RESET_ALL}")

    def _handle_end_combat_event(self, entry: ESOLogEntry):
        """Handle END_COMBAT events to start grace period for combat tracking."""
        # END_COMBAT format: timestamp,END_COMBAT (no additional data)
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_COMBAT at {entry.timestamp}, encounter exists: {self.current_encounter is not None}, players: {len(self.current_encounter.players) if self.current_encounter else 0}{Style.RESET_ALL}")
        
        # Immediately finalize encounter if there are any players
        if self.current_encounter and self.current_encounter.players:
            self.current_encounter.end_time = entry.timestamp
            self.current_encounter.combat_ended_at = entry.timestamp
            self.current_encounter.in_combat = False
            # Finalize buff tracking
            self.current_encounter.finalize_buff_tracking()
            # Immediately display summary and finalize encounter
            self.current_encounter.finalized = True
            self._display_encounter_summary(self.current_zone)

    # Grace period logic removed - encounters are finalized immediately on END_COMBAT


    def _handle_begin_log_event(self, entry: ESOLogEntry):
        """Handle BEGIN_LOG events to extract Unix timestamp."""
        # BEGIN_LOG format: timestamp,BEGIN_LOG,unix_timestamp,version,"server","language","build"
        if len(entry.fields) >= 1:
            try:
                unix_timestamp = int(entry.fields[0])
                self.log_start_unix_timestamp = unix_timestamp
            except (ValueError, IndexError):
                pass  # Skip invalid timestamps

    def _handle_begin_cast(self, entry: ESOLogEntry):
        """Handle BEGIN_CAST events."""
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()

        # Only set combat start time if we're not already in combat and not finalized
        # This prevents BEGIN_CAST from overriding BEGIN_COMBAT timestamps or finalized encounters
        if not self.current_encounter.in_combat and not self.current_encounter.finalized:
            self.current_encounter.in_combat = True
            self.current_encounter.start_time = entry.timestamp

        # BEGIN_CAST format: durationMS, channeled, castTrackId, abilityId, <sourceUnitState>, <targetUnitState>
        # sourceUnitState: unitId, health/max, magicka/max, stamina/max, ultimate/max, werewolf/max, shield, x, y, heading
        if len(entry.fields) >= 7:
            ability_id = entry.fields[3]  # abilityId
            caster_unit_id = entry.fields[4]  # sourceUnitState.unitId

            if ability_id in self.ability_cache:
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(caster_unit_id, ability_name)

            # Parse resource information: health/max, magicka/max, stamina/max in fields 5, 6, 7
            if len(entry.fields) >= 8:
                self._parse_and_update_player_resources(caster_unit_id, entry.fields[5:8])
                # Also update enemy health if the caster is an enemy
                self._parse_and_update_enemy_health(caster_unit_id, entry.fields[5:8])

    def _parse_and_update_enemy_health(self, unit_id: str, resource_fields: List[str]):
        """Parse health information and update the corresponding enemy's maximum health."""
        if not self.current_encounter:
            return

        # Check if this unit is an enemy
        enemy = self.current_encounter.enemies.get(unit_id)
        if not enemy:
            return

        # Parse health field: "current/max" - we want the max (second number)
        try:
            if len(resource_fields) >= 1 and "/" in resource_fields[0]:
                current_health, max_health = resource_fields[0].split("/")
                max_health = int(max_health)
                if max_health > 0 and max_health > enemy.max_health:
                    enemy.max_health = max_health
                    enemy.current_health = int(current_health)
                    # Update highest health hostile if this enemy is hostile
                    if enemy.is_hostile:
                        self.current_encounter.update_highest_health_hostile(enemy)
        except (ValueError, IndexError):
            pass  # Skip invalid health data

    def _parse_and_update_player_resources(self, unit_id: str, resource_fields: List[str]):
        """Parse resource information and update the corresponding player's maximum values."""
        if not self.current_encounter:
            return

        # Find the player by unit ID (handles both short and long unit IDs)
        player = self.current_encounter.find_player_by_unit_id(unit_id)

        if not player:
            return

        # Parse resource fields: [health_current/health_max, magicka_current/magicka_max, stamina_current/stamina_max]
        try:
            if len(resource_fields) >= 1 and "/" in resource_fields[0]:
                # Health format: "current/max" - we want the max (second number)
                current_health, max_health = resource_fields[0].split("/")
                max_health = int(max_health)
                player.update_resources(health=max_health)

            if len(resource_fields) >= 2 and "/" in resource_fields[1]:
                # Magicka format: "current/max" - we want the max (second number)
                current_magicka, max_magicka = resource_fields[1].split("/")
                max_magicka = int(max_magicka)
                player.update_resources(magicka=max_magicka)

            if len(resource_fields) >= 3 and "/" in resource_fields[2]:
                # Stamina format: "current/max" - we want the max (second number)
                current_stamina, max_stamina = resource_fields[2].split("/")
                max_stamina = int(max_stamina)
                player.update_resources(stamina=max_stamina)

        except (ValueError, IndexError):
            pass  # Skip invalid resource data

    def _handle_combat_event(self, entry: ESOLogEntry):
        """Handle COMBAT_EVENT events."""
        
        # Check if we need to rewind to a previous zone
        if not self.current_zone and self.zone_history:
            self._rewind_to_last_zone()
        
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

        if not self.current_encounter.in_combat:
            self.current_encounter.in_combat = True
            self.current_encounter.start_time = entry.timestamp

        # Track damage events for DPS calculation (only friendly damage)
        # COMBAT_EVENT format: timestamp,COMBAT_EVENT,event_type,damage_type,source_unit_id,damage_value,...
        if len(entry.fields) >= 4:
            combat_event_type = entry.fields[0]  # DAMAGE/CRITICAL_DAMAGE is at index 0
            
            # Track any monster that appears in combat events as "engaged"
            if self.list_hostiles and self.current_encounter:
                # COMBAT_EVENT format: timestamp,COMBAT_EVENT,actionResult,damageType,powerType,hitValue,overflow,castTrackId,abilityId,sourceUnitState,targetUnitState
                # After parsing: fields[0]=actionResult, fields[1]=damageType, ..., fields[8]=sourceUnitId, fields[17]=targetUnitId
                if combat_event_type in ['DAMAGE', 'CRITICAL_DAMAGE']:
                    if len(entry.fields) > 17:
                        source_unit_id = entry.fields[7]  # Source unit (dealing damage)
                        target_unit_id = entry.fields[17]  # Target unit (receiving damage)
                        
                        # Track when players damage hostile monsters
                        if (target_unit_id and target_unit_id in self.current_encounter.enemies):
                            enemy = self.current_encounter.enemies[target_unit_id]
                            if enemy.is_hostile:
                                # Check if source is a player or player's pet
                                if (self.current_encounter.find_player_by_unit_id(source_unit_id) or 
                                    source_unit_id in self.current_encounter.pet_ownership):
                                    self.engaged_monsters.add(target_unit_id)
            
            if combat_event_type in ['DAMAGE', 'CRITICAL_DAMAGE']:
                pass  # Damage events are handled in the elif block below
            
            # Track death events
            if combat_event_type == 'DIED_XP':
                # Check if it's a player death by looking up the dying unit ID in known players
                # DIED_XP format: timestamp,COMBAT_EVENT,DIED_XP,damageType,powerType,hitValue,overflow,castTrackId,abilityId,sourceUnitState,targetUnitState
                # After parsing: fields[0]=DIED_XP, fields[1]=damageType, ..., fields[7]=sourceUnitId, fields[17]=dyingUnitId
                dying_unit_id = entry.fields[17] if len(entry.fields) > 17 else ""
                if (self.current_encounter and 
                    self.current_encounter.find_player_by_unit_id(dying_unit_id)):
                    self.zone_deaths += 1
                
                # If it's a hostile enemy death, mark it as damaged by players
                elif (self.current_encounter and 
                      dying_unit_id in self.current_encounter.enemies):
                    enemy = self.current_encounter.enemies[dying_unit_id]
                    # Only track deaths of hostile monsters, not friendly pets or NPCs
                    if enemy.is_hostile:
                        # Mark this enemy as damaged (even if we didn't track individual damage events)
                        if dying_unit_id not in self.current_encounter.enemy_damage:
                            self.current_encounter.enemy_damage[dying_unit_id] = 0
                            # Add enemy's max health to total when first damaged
                            if enemy.max_health > 0:
                                self.current_encounter.total_health_damaged += enemy.max_health
                        # Set a minimum damage amount to indicate it was killed
                        if self.current_encounter.enemy_damage[dying_unit_id] == 0:
                            self.current_encounter.enemy_damage[dying_unit_id] = 1
                        # Update the most damaged hostile monster
                        self.current_encounter.update_most_damaged_hostile(dying_unit_id)
            
            
            # Track damage events
            elif combat_event_type in ['DAMAGE', 'CRITICAL_DAMAGE']:
                try:
                    # COMBAT_EVENT format: timestamp,COMBAT_EVENT,actionResult,damageType,powerType,hitValue,overflow,castTrackId,abilityId,sourceUnitState,targetUnitState
                    # After parsing: fields[0]=actionResult, fields[1]=damageType, fields[3]=hitValue, fields[7]=sourceUnitId, fields[17]=targetUnitId
                    hit_value = int(entry.fields[3])  # hitValue is at index 3
                    source_unit_id = entry.fields[7] if len(entry.fields) > 7 else ""  # source unit ID
                    target_unit_id = entry.fields[17] if len(entry.fields) > 17 else ""  # target unit ID
                    
                    # Track damage dealt by players to hostile monsters
                    if hit_value > 0 and self.current_encounter:
                        if target_unit_id and target_unit_id in self.current_encounter.enemies:
                            enemy = self.current_encounter.enemies[target_unit_id]
                            if enemy.is_hostile:
                                # Check if source is a player or player's pet
                                if (self.current_encounter.find_player_by_unit_id(source_unit_id) or 
                                    source_unit_id in self.current_encounter.pet_ownership):
                                    if target_unit_id not in self.current_encounter.enemy_damage:
                                        self.current_encounter.enemy_damage[target_unit_id] = 0
                                        # Add enemy's max health to total when first damaged
                                        if target_unit_id in self.current_encounter.enemies:
                                            enemy = self.current_encounter.enemies[target_unit_id]
                                            if enemy.max_health > 0:
                                                self.current_encounter.total_health_damaged += enemy.max_health
                                    self.current_encounter.enemy_damage[target_unit_id] += hit_value
                                    # Update total group damage
                                    self.current_encounter.total_damage += hit_value
                                    
                                    # Track individual player damage
                                    self.current_encounter.add_damage_to_player(source_unit_id, hit_value)
                                    
                                    # Update the most damaged hostile monster
                                    self.current_encounter.update_most_damaged_hostile(target_unit_id)
                except (ValueError, IndexError):
                    pass  # Skip invalid damage values
            
            # Parse health information from COMBAT_EVENT (similar to EFFECT_CHANGED)
            # COMBAT_EVENT format can include health info in various positions depending on event type
            if len(entry.fields) > 17:  # Check if we have enough fields for health info
                # Look for health info in the format "current_health/max_health"
                for i, field in enumerate(entry.fields):
                    if "/" in field and field.count("/") == 1:
                        try:
                            current_health, max_health = field.split("/")
                            current_health = int(current_health)
                            max_health = int(max_health)
                            
                            # If this looks like valid health data (reasonable values)
                            if 1000 <= max_health <= 100000000:  # Reasonable health range
                                # Try to find the target unit ID - it's usually a few fields before health
                                target_unit_id = None
                                for j in range(max(0, i-5), i):
                                    if entry.fields[j].isdigit() and len(entry.fields[j]) > 3:  # Unit IDs are usually longer
                                        target_unit_id = entry.fields[j]
                                        break
                                
                                # Update enemy health if this is a known enemy
                                if (target_unit_id and self.current_encounter and 
                                    target_unit_id in self.current_encounter.enemies):
                                    self.current_encounter.update_enemy_health(target_unit_id, current_health, max_health)
                                    
                        except (ValueError, IndexError):
                            pass  # Skip invalid health data

    def _handle_effect_changed(self, entry: ESOLogEntry):
        """Handle EFFECT_CHANGED events for buffs/debuffs."""
        # EFFECT_CHANGED format: GAINED/FADED/UPDATED, target_unit_id, source_unit_id, ability_id, stacks, ...
        if self.current_encounter and len(entry.fields) >= 4:
            effect_type = entry.fields[0]
            target_unit_id = entry.fields[1]  # Short unit ID
            source_unit_id = entry.fields[2]  # Long unit ID
            ability_id = entry.fields[3]

            # Associate long unit ID with target player if we can find the target
            if target_unit_id in self.current_encounter.players:
                self.current_encounter.associate_long_unit_id(target_unit_id, source_unit_id)
            
            # Track pet ownership: if source is a player and target is not a player, target might be a pet
            if (source_unit_id in self.current_encounter.players and 
                target_unit_id not in self.current_encounter.players):
                # Check if target is likely a pet (not a known enemy)
                if target_unit_id not in self.current_encounter.enemies:
                    self.current_encounter.track_pet_ownership(target_unit_id, source_unit_id)

            # Track group buffs
            for buff_name, buff_ids in self.group_buff_ids.items():
                if ability_id in buff_ids and target_unit_id in self.current_encounter.players:
                    self.current_encounter.track_buff(target_unit_id, buff_name, effect_type, entry.timestamp)

            # Parse health information for enemies from EFFECT_CHANGED events
            # EFFECT_CHANGED format: GAINED/FADED/UPDATED,stacks,source_unit_id,ability_id,target_unit_id,source_health/max,source_magicka/max,source_stamina/max,source_ultimate/max,source_werewolf/max,source_shield,source_x,source_y,source_heading,target_unit_id,target_health/max,target_magicka/max,target_stamina/max,target_ultimate/max,target_werewolf/max,target_shield,target_x,target_y,target_heading
            # Look for the second target_unit_id (field 15) and its corresponding health (field 16)
            if len(entry.fields) >= 16:
                second_target_unit_id = str(entry.fields[14])  # Field 15 (0-indexed)
                target_health_info = str(entry.fields[15])     # Field 16 (0-indexed)
                
                if "/" in target_health_info and second_target_unit_id in self.current_encounter.enemies:
                    try:
                        current_health, max_health = target_health_info.split("/")
                        current_health = int(current_health)
                        max_health = int(max_health)
                        
                        if max_health > 0 and max_health > 100:  # Filter out small health values
                            self.current_encounter.update_enemy_health(second_target_unit_id, current_health, max_health)
                            
                    except (ValueError, IndexError):
                        pass  # Skip invalid health data
            
            # Also check the first target_unit_id (original logic for backward compatibility)
            if len(entry.fields) >= 6:
                first_target_health_info = str(entry.fields[5])  # Field 6 (0-indexed)
                if "/" in first_target_health_info and target_unit_id in self.current_encounter.enemies:
                    try:
                        current_health, max_health = first_target_health_info.split("/")
                        current_health = int(current_health)
                        max_health = int(max_health)
                        
                        if max_health > 0 and max_health > 100:  # Filter out small health values
                            self.current_encounter.update_enemy_health(target_unit_id, current_health, max_health)
                            
                    except (ValueError, IndexError):
                        pass  # Skip invalid health data

            # Only track GAINED effects to avoid spam, and only from valid source units
            if (effect_type == "GAINED" and source_unit_id != "0" and
                ability_id in self.ability_cache):
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(source_unit_id, ability_name)

            # Check if this is a health-related effect (field [7] contains health info)
            if len(entry.fields) >= 8:
                health_info = entry.fields[7] if len(entry.fields) > 7 else ""
                
                # Look for health information in format "current/max"
                if '/' in health_info and target_unit_id:
                    try:
                        current_health, max_health = health_info.split('/')
                        current_health = int(current_health)
                        max_health = int(max_health)
                        
                        # Update enemy health if this is an enemy unit
                        enemy = self.current_encounter.enemies.get(target_unit_id)
                        if enemy and max_health > 0:
                            # Update with the highest max health we've seen
                            if max_health > enemy.max_health:
                                enemy.max_health = max_health
                                enemy.current_health = current_health
                    except (ValueError, IndexError):
                        pass  # Skip invalid health data

            # Only mark combat activity if we're already in combat (after BEGIN_COMBAT)
            # Don't start combat from EFFECT_CHANGED events alone

    def _end_combat(self, end_time: int):
        """End the current combat encounter and display results."""
        # Display results if there are any players
        if self.current_encounter and self.current_encounter.players:
            self.current_encounter.end_time = end_time
            self._display_encounter_summary()

        self.current_encounter = None

    def _end_combat_with_zone(self, end_time: int, zone_name: str):
        """End the current combat encounter and display results with zone name."""
        # Display results if there are any players
        if self.current_encounter and self.current_encounter.players:
            self.current_encounter.end_time = end_time
            self._display_encounter_summary(zone_name)

        self.current_encounter = None

    def _display_encounter_summary(self, zone_name: str = None):
        """Display a summary of the completed encounter."""
        if not self.current_encounter:
            return

        # Use grace period end time if available, otherwise use end_time
        end_time = self.current_encounter.end_time
        duration = (end_time - self.current_encounter.start_time) / 1000.0
        players_count = len(self.current_encounter.players)
        
        # Calculate estimated group DPS
        estimated_dps = 0
        if duration > 0 and self.current_encounter.total_damage > 0:
            estimated_dps = self.current_encounter.total_damage / duration


        # Death counter (total deaths since entering zone)
        deaths_info = ""
        if self.zone_deaths > 0:
            deaths_info = f" | Deaths: {self.zone_deaths}"
        
        # Most damaged hostile monster info (primary target)
        hostile_info = ""
        if (self.current_encounter and self.current_encounter.most_damaged_hostile):
            hostile = self.current_encounter.most_damaged_hostile
            hostile_info = f" | Target: {hostile.name} (HP: {hostile.max_health:,})"
        
        # Highest HP hostile monster info - only consider enemies that were actually engaged by players
        highest_hp_info = ""
        if self.current_encounter:
            # Find the highest health hostile among enemies that were actually engaged by players
            # Use the same logic as the hostile monsters display
            engaged_hostiles = []
            all_engaged_monsters = set()
            
            # Add monsters from hostile_monsters list
            for unit_id, name, unit_type in self.hostile_monsters:
                if unit_id in self.engaged_monsters or unit_id in self.current_encounter.enemy_damage:
                    all_engaged_monsters.add(unit_id)
            
            # Add monsters that appeared in combat events but weren't in hostile_monsters list
            for unit_id in self.engaged_monsters:
                if unit_id in self.current_encounter.enemies:
                    enemy = self.current_encounter.enemies[unit_id]
                    if enemy.is_hostile:
                        all_engaged_monsters.add(unit_id)
            
            # Build list of engaged hostiles with health info
            for unit_id in all_engaged_monsters:
                if unit_id in self.current_encounter.enemies:
                    enemy = self.current_encounter.enemies[unit_id]
                    if hasattr(enemy, 'is_hostile') and enemy.is_hostile and enemy.max_health > 0:
                        engaged_hostiles.append(enemy)
            
            if engaged_hostiles:
                # Sort by max health (highest first), then prefer Stormreeve Neidir for equal health
                engaged_hostiles.sort(key=lambda e: (-e.max_health, 0 if "Stormreeve" in e.name else 1))
                highest_engaged = engaged_hostiles[0]
                highest_hp_info = f" | Highest HP: {highest_engaged.name} ({highest_engaged.max_health:,} HP)"
        
        # Total health of all damaged enemies
        total_health_info = ""
        if (self.current_encounter and self.current_encounter.total_health_damaged > 0):
            total_health_info = f" | Total Health Pool: {self.current_encounter.total_health_damaged:,} HP"

        # Get formatted combat start time
        combat_start_time = self.current_encounter.get_combat_start_time_formatted(self.current_log_file, self.log_start_unix_timestamp)
        
        # Update the combat ended header with start time, duration, players info, DPS, deaths, and enemy info
        dark_orange = "\033[38;5;208m"  # Dark orange color
        if zone_name:
            if estimated_dps > 0:
                self._print_and_buffer(f"{dark_orange}{combat_start_time} ({zone_name}) | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{hostile_info}{Style.RESET_ALL}")
            else:
                self._print_and_buffer(f"{dark_orange}{combat_start_time} ({zone_name}) | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{hostile_info}{Style.RESET_ALL}")
        else:
            if estimated_dps > 0:
                self._print_and_buffer(f"{dark_orange}{combat_start_time} | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{hostile_info}{Style.RESET_ALL}")
            else:
                self._print_and_buffer(f"{dark_orange}{combat_start_time} | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{hostile_info}{Style.RESET_ALL}")
        
        # Show group buff analysis for encounters with 3+ players
        if players_count >= 3:
            buff_analysis = self.current_encounter.get_group_buff_analysis()
            buff_status = []
            for buff_name, is_present in buff_analysis.items():
                if is_present:
                    # Calculate group uptime (time buff was active on any player)
                    group_uptime = self.current_encounter.get_group_buff_uptime(buff_name)
                    status = f"✅ ({group_uptime:.1f}%)"
                else:
                    status = "❌"
                buff_status.append(f"{buff_name}: {status}")
            self._print_and_buffer(f"{Fore.CYAN}Group Buffs: {' | '.join(buff_status)}{Style.RESET_ALL}")
        # Sort players by damage contribution (descending)
        # Only include players with PLAYER_INFO data (equipped abilities)
        players_with_damage = []
        for player in self.current_encounter.players.values():
            # Skip players without PLAYER_INFO data (no equipped abilities)
            if not player.equipped_abilities:
                continue
            player_damage = self.current_encounter.player_damage.get(player.unit_id, 0)
            players_with_damage.append((player, player_damage))
        
        # Sort by damage (descending)
        players_with_damage.sort(key=lambda x: x[1], reverse=True)
        
        for player, player_damage in players_with_damage:
            # Calculate player DPS
            player_dps = 0
            if duration > 0 and player_damage > 0:
                player_dps = player_damage / duration
            
            # Use equipped abilities from PLAYER_INFO
            abilities_to_analyze = player.equipped_abilities
            
            # Analyze subclass and build first to create the title line
            analysis = None
            if abilities_to_analyze:
                analysis = self.subclass_analyzer.analyze_subclass(abilities_to_analyze)
            
            # Create the title line: @playername {character_name} skill_lines dominant_resource
            title_parts = [player.get_display_name()]
            
            # Add character name if available and different from handle
            character_name = player.name if player.name and player.name not in ['""', '', '0'] else ""
            if character_name and character_name != player.get_display_name():
                title_parts.append(character_name)
            
            if analysis and analysis['confidence'] > 0.1:
                if analysis['skill_lines']:
                    # Use skill line aliases if available, otherwise extract first word
                    skill_line_aliases = []
                    class_skill_lines = player.get_class_skill_lines()

                    for skill_line in analysis['skill_lines']:
                        # Check if we have an alias for this skill line (partial matching)
                        alias_found = False
                        for alias_key, alias_value in self.subclass_analyzer.SKILL_LINE_ALIASES.items():
                            if alias_key in skill_line:
                                # Check if this is a class skill line and underline it
                                if any(alias_value in class_skill for class_skill in class_skill_lines):
                                    skill_line_aliases.append(f"\033[4m{alias_value}\033[24m")  # Underline without resetting color
                                else:
                                    skill_line_aliases.append(alias_value)
                                alias_found = True
                                break
                        
                        if not alias_found:
                            # Fall back to first word
                            first_word = skill_line.split()[0]
                            # Check if this is a class skill line and underline it
                            if any(first_word in class_skill for class_skill in class_skill_lines):
                                skill_line_aliases.append(f"\033[4m{first_word}\033[24m")  # Underline without resetting color
                            else:
                                skill_line_aliases.append(first_word)
                    # Sort skill line aliases before joining
                    skill_line_aliases.sort()
                    skill_lines_str = '/'.join(skill_line_aliases)
                    # Add class name and resource information after skill lines
                    class_name = player.get_class_name()
                    if class_name and class_name != "Unknown":
                        # Format resources with health coloring
                        resource_str = ""
                        dps_str = ""  # Initialize dps_str at this scope to avoid UnboundLocalError
                        if player.max_health > 0 or player.max_magicka > 0 or player.max_stamina > 0:
                            # Round to nearest 0.5k (500)
                            def round_to_half_k(value):
                                if value == 0:
                                    return "0k"
                                rounded = round(value / 500) * 0.5
                                if rounded == int(rounded):
                                    return f"{int(rounded)}k"
                                else:
                                    return f"{rounded:.1f}k"

                            health_display = round_to_half_k(player.max_health)
                            magicka_display = round_to_half_k(player.max_magicka)
                            stamina_display = round_to_half_k(player.max_stamina)

                            # Color health red if below 18.5k or above 44.5k
                            if player.max_health > 0 and (player.max_health < 18500 or player.max_health > 44500):
                                health_display = f"{Fore.RED}{health_display}{Fore.GREEN}"  # Return to green after red

                            # Bold and underline the highest resource value
                            max_resource_value = max(player.max_health, player.max_magicka, player.max_stamina)
                            if max_resource_value > 0:
                                if player.max_health == max_resource_value:
                                    health_display = f"{Style.BRIGHT}\033[4m{health_display}\033[0m{Style.NORMAL}{Fore.GREEN}"
                                elif player.max_magicka == max_resource_value:
                                    magicka_display = f"{Style.BRIGHT}\033[4m{magicka_display}\033[0m{Style.NORMAL}{Fore.GREEN}"
                                elif player.max_stamina == max_resource_value:
                                    stamina_display = f"{Style.BRIGHT}\033[4m{stamina_display}\033[0m{Style.NORMAL}{Fore.GREEN}"

                            resource_str = f" M:{magicka_display} S:{stamina_display} H:{health_display}"
                            
                            # Add DPS information and damage percentage
                            dps_str = ""
                            if player_dps > 0:
                                # Calculate damage percentage of total group damage
                                damage_percentage = 0
                                if self.current_encounter.total_damage > 0:
                                    damage_percentage = (player_damage / self.current_encounter.total_damage) * 100
                                dps_str = f" D:{damage_percentage:.1f}%"

                        skill_lines_str += f" ({class_name}{resource_str}{dps_str})"
                    title_parts.append(skill_lines_str)
                else:
                    title_parts.append("unknown")
            else:
                title_parts.append("unknown")
            
            self._print_and_buffer(f"{Fore.GREEN}{' '.join(title_parts)}{Style.RESET_ALL}")
            
            if abilities_to_analyze:
                # Show front and back bar abilities in order if available
                if player.front_bar_abilities or player.back_bar_abilities:
                    if player.front_bar_abilities:
                        highlighted_front_bar = highlight_taunt_abilities(player.front_bar_abilities)
                        self._print_and_buffer(f"  {', '.join(highlighted_front_bar)}")
                    if player.back_bar_abilities:
                        highlighted_back_bar = highlight_taunt_abilities(player.back_bar_abilities)
                        self._print_and_buffer(f"  {', '.join(highlighted_back_bar)}")
                else:
                    abilities_list = sorted(list(abilities_to_analyze))[:10]  # Show top 10 abilities
                    highlighted_abilities = highlight_taunt_abilities(abilities_list)
                    self._print_and_buffer(f"  Equipped: {', '.join(highlighted_abilities)}")
                    if len(abilities_to_analyze) > 10:
                        self._print_and_buffer(f"  ... and {len(abilities_to_analyze) - 10} more")


                # Analyze gear sets (no role-based filtering)
                identified_sets = []
                
                # Also check for gear sets from equipped abilities
                gear_set_abilities_found = []
                # Get the equipped ability IDs from the player info
                if hasattr(player, '_equipped_ability_ids'):
                    for ability_id in player._equipped_ability_ids:
                        if ability_id in self.gear_set_abilities:
                            gear_set_abilities_found.append({
                                'name': self.gear_set_abilities[ability_id],
                                'confidence': 0.9,
                                'source': 'equipped_ability'
                            })
                
                # Combine identified sets with gear set abilities
                all_identified_sets = identified_sets + gear_set_abilities_found
                
                # Create equipment summary line
                equipment_parts = []
                if player.gear:
                    # Count gear pieces by set name
                    set_counts = {}
                    for slot, gear_item in player.gear.items():
                        if len(gear_item) > 6:  # Make sure we have set ID
                            set_id = str(gear_item[6])  # Set ID is at position 6

                            # Skip items with no set (set ID 0 or empty)
                            if set_id == "0" or set_id == "" or set_id == "nan":
                                continue

                            # Look up set name by set ID
                            set_name = gear_set_db.get_set_name_by_set_id(set_id)
                            if not set_name:
                                set_name = f"Unknown Set ({set_id})"

                            # Check if this is a 2-handed weapon or staff (count as 2 pieces)
                            piece_count = 1
                            if slot in ['MAIN_HAND', 'BACKUP_MAIN'] and self._is_two_handed_weapon(gear_item, player.gear):
                                piece_count = 2

                            set_counts[set_name] = set_counts.get(set_name, 0) + piece_count
                    
                    # Format equipment summary
                    for set_name, count in set_counts.items():
                        if count >= 5:
                            equipment_parts.append(f"{count}pc {set_name}")
                        elif count >= 2:
                            equipment_parts.append(f"{count}pc {set_name}")
                        else:
                            equipment_parts.append(f"{count}pc {set_name}")
                
                # Add inferred sets
                if all_identified_sets:
                    high_confidence_sets = [s for s in all_identified_sets if s['confidence'] > 0.5]
                    for set_info in high_confidence_sets:
                        if set_info['name'] not in [part.split('pc ')[1] for part in equipment_parts]:
                            equipment_parts.append(f"?pc {set_info['name']} (inferred)")
                
                # Show equipment summary
                if equipment_parts:
                    # Sort equipment by set name, ignoring "Perfected" prefix
                    def sort_key(item):
                        # Extract set name from "Xpc Set Name" format
                        if 'pc ' in item:
                            set_name = item.split('pc ', 1)[1]
                            # Remove "Perfected " prefix for sorting
                            if set_name.startswith('Perfected '):
                                set_name = set_name[10:]  # Remove "Perfected "
                            return set_name.lower()
                        return item.lower()

                    equipment_parts.sort(key=sort_key)

                    # Apply coloring to equipment parts
                    colored_parts = []
                    for part in equipment_parts:
                        if 'pc ' in part:
                            # Extract piece count and set name
                            pieces_str, set_name = part.split('pc ', 1)
                            piece_count = int(pieces_str) if pieces_str.isdigit() else 0

                            # Remove any trailing text like "(inferred)"
                            clean_set_name = set_name.split(' (')[0]

                            # Check if it's a mythic set (color gold and remove "1pc" prefix)
                            if clean_set_name in MYTHIC_SETS:
                                colored_part = f"{Fore.YELLOW}{set_name}{Style.RESET_ALL}"
                            # Check if it's an incomplete 5-piece set (color dark red) - but never highlight monster sets
                            elif has_five_piece_bonus(clean_set_name) and piece_count < 5:
                                # Explicitly exclude 2-piece sets (monster sets + arena weapon sets) from red highlighting
                                two_piece_set_keywords = [
                                    # Monster sets (2-piece)
                                    "spawn of mephala", "blood spawn", "lord warden", "scourge harvester", "engine guardian", "nightflame",
                                    "nerien'eth", "valkyn skoria", "maw of the infernal", "molag kena", "mighty chudan", "velidreth",
                                    "giant spider", "shadowrend", "kra'gh", "swarm mother", "sentinel of rkugamz", "chokethorn",
                                    "slimecraw", "sellistrix", "infernal guardian", "ilambris", "iceheart", "stormfist", "tremorscale",
                                    "pirate skeleton", "the troll king", "selene", "grothdarr", "earthgore", "domihaus", "thurvokun",
                                    "zaan", "balorgh", "vykosa", "stonekeeper", "symphony of blades", "grundwulf", "maarselok",
                                    "mother ciannait", "kjalnar's nightmare", "stone husk", "lady thorn", "encrati's behemoth",
                                    "baron zaudrus", "prior thierric", "magma incarnate", "kargaeda", "nazaray", "archdruid devyric",
                                    "euphotic gatekeeper", "roksa the warped", "ozezan the inferno", "anthelmir's construct",
                                    "the blind", "squall of retribution", "orpheon the tactician", "nunatak", "nunatak's blessing", "nunatak", "nunatak's blessing",
                                    # Arena weapon sets (2-piece)
                                    "archer's mind", "footman's fortune", "healer's habit", "robes of destruction mastery", "permafrost",
                                    "glorious defender", "para bellum", "elemental succession", "hunt leader", "winterborn",
                                    "titanic cleave", "puncturing remedy", "stinging slashes", "caustic arrow", "destructive impact",
                                    "grand rejuvenation", "merciless charge", "rampaging slash", "cruel flurry", "thunderous volley",
                                    "crushing wall", "precise regeneration", "gallant charge", "radial uppercut", "spectral cloak",
                                    "virulent shot", "wild impulse", "mender's ward", "perfect gallant charge", "perfect radial uppercut",
                                    "perfect spectral cloak", "perfect virulent shot", "perfect wild impulse", "perfect mender's ward",
                                    "perfected merciless charge", "perfected rampaging slash", "perfected cruel flurry", "perfected thunderous volley",
                                    "perfected crushing wall", "perfected precise regeneration", "perfected titanic cleave", "perfected puncturing remedy",
                                    "perfected stinging slashes", "perfected caustic arrow", "perfected destructive impact", "perfected grand rejuvenation",
                                    "executioner's blade", "void bash", "frenzied momentum", "point-blank snipe", "wrath of elements",
                                    "force overflow", "perfected executioner's blade", "perfected void bash", "perfected frenzied momentum",
                                    "perfected point-blank snipe", "perfected wrath of elements", "perfected force overflow"
                                ]
                                if not any(keyword in clean_set_name.lower() for keyword in two_piece_set_keywords):
                                    colored_part = f"{Fore.RED}{part}{Style.RESET_ALL}"
                                else:
                                    colored_part = part
                            else:
                                colored_part = part
                        else:
                            colored_part = part

                        colored_parts.append(colored_part)

                    self._print_and_buffer(f"  {', '.join(colored_parts)}")
                elif player.gear:
                    self._print_and_buffer(f"  {len(player.gear)} items (sets unknown)")
                else:
                    self._print_and_buffer(f"  No data")
                
            else:
                self._print_and_buffer(f"  Abilities: No PLAYER_INFO data")
                self._print_and_buffer(f"  No data")
        
        # Display hostile monsters if testing flag is enabled
        if self.list_hostiles and (self.hostile_monsters or self.engaged_monsters):
            self._print_and_buffer(f"\n{Fore.YELLOW}=== Hostile Monsters Engaged by Players ==={Style.RESET_ALL}")
            
            # Combine hostile monsters that were tracked and those that appeared in combat events
            all_engaged_monsters = set()
            
            # Add monsters from hostile_monsters list
            for unit_id, name, unit_type in self.hostile_monsters:
                if unit_id in self.engaged_monsters or unit_id in self.current_encounter.enemy_damage:
                    all_engaged_monsters.add((unit_id, name, unit_type))
            
            # Add monsters that appeared in combat events but weren't in hostile_monsters list
            for unit_id in self.engaged_monsters:
                if unit_id in self.current_encounter.enemies:
                    enemy = self.current_encounter.enemies[unit_id]
                    all_engaged_monsters.add((unit_id, enemy.name, enemy.unit_type))
            
            # Display all engaged monsters
            unique_hostiles = []
            seen = set()
            for unit_id, name, unit_type in all_engaged_monsters:
                key = (unit_id, name)
                if key not in seen:
                    seen.add(key)
                    damage = self.current_encounter.enemy_damage.get(unit_id, 0)
                    unique_hostiles.append((unit_id, name, unit_type, damage))
            
            # Sort by damage (highest first), then by name
            unique_hostiles.sort(key=lambda x: (x[3], x[1]), reverse=True)
            
            for unit_id, name, unit_type, damage in unique_hostiles:
                # Get health information from the enemy
                enemy = self.current_encounter.enemies.get(unit_id)
                health_info = f"HP: {enemy.max_health:,}" if enemy and enemy.max_health > 0 else "HP: Unknown"
                
                if damage > 0:
                    self._print_and_buffer(f"{Fore.RED}  {name} (ID: {unit_id}, Type: {unit_type}, {health_info}, Damage: {damage:,}){Style.RESET_ALL}")
                else:
                    self._print_and_buffer(f"{Fore.RED}  {name} (ID: {unit_id}, Type: {unit_type}, {health_info}, Engaged){Style.RESET_ALL}")
            
            self._print_and_buffer(f"{Fore.YELLOW}Total hostile monsters engaged: {len(unique_hostiles)}{Style.RESET_ALL}")
        
        # Clear the hostile monsters list and engaged monsters set for the next encounter
        self.hostile_monsters.clear()
        self.engaged_monsters.clear()
        
        # Store the Discord markdown version for copying
        if self.discord_copy_enabled:
            self.last_encounter_report = self._format_encounter_for_discord(zone_name)
        
        # Save report to file if enabled
        if self.save_reports:
            self._save_report_to_file()

    def _save_report_to_file(self):
        """Save the current report buffer to a timestamped file."""
        if not self.report_buffer or not self.current_encounter:
            return
            
        try:
            # Create reports directory if it doesn't exist
            if self.reports_dir:
                reports_path = Path(self.reports_dir)
            else:
                # Default to same directory as log file
                if self.current_log_file:
                    reports_path = Path(self.current_log_file).parent
                else:
                    reports_path = Path.cwd()
            
            # Check if directory exists and is writable, or if we can create it
            if not reports_path.exists():
                try:
                    reports_path.mkdir(parents=True, exist_ok=True)
                except (PermissionError, OSError) as e:
                    print(f"{Fore.RED}ERROR: Cannot create reports directory: {reports_path}{Style.RESET_ALL}")
                    print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
                    print(f"{Fore.RED}Please create the directory manually: mkdir -p {reports_path}{Style.RESET_ALL}")
                    sys.exit(1)
            elif not reports_path.is_dir():
                print(f"{Fore.RED}ERROR: Reports path exists but is not a directory: {reports_path}{Style.RESET_ALL}")
                sys.exit(1)
            elif not os.access(reports_path, os.W_OK):
                print(f"{Fore.RED}ERROR: Reports directory is not writable: {reports_path}{Style.RESET_ALL}")
                print(f"{Fore.RED}Please check directory permissions or create it manually: mkdir -p {reports_path}{Style.RESET_ALL}")
                sys.exit(1)
            
            # Generate zone-based filename similar to split files
            # Use the encounter start time for consistent naming
            encounter_start_time = self.current_encounter.start_time
            dt = datetime.fromtimestamp(encounter_start_time / 1000)  # Convert from milliseconds
            timestamp_str = dt.strftime("%y%m%d%H%M%S")
            
            # Use same naming logic as split files: YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}.txt
            difficulty_suffix = "-vet" if self.current_difficulty and self.current_difficulty.upper() == "VETERAN" else ""
            zone_suffix = self.current_zone.replace(" ", "-") if self.current_zone else "Unknown-Zone"
            
            filename = f"{timestamp_str}-{zone_suffix}{difficulty_suffix}-report.txt"
            report_file_path = reports_path / filename
            
            # Write report to file (strip ANSI color codes for clean text)
            with open(report_file_path, 'w', encoding='utf-8') as f:
                for line in self.report_buffer:
                    # Remove ANSI color codes for clean text output
                    clean_line = self._strip_ansi_codes(line)
                    f.write(clean_line + '\n')
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Saved report to {report_file_path}{Style.RESET_ALL}")
                
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to save report: {e}{Style.RESET_ALL}")
        finally:
            # Clear the buffer for the next report
            self.report_buffer.clear()

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes from text for clean file output."""
        import re
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _print_and_buffer(self, text: str):
        """Print text to stdout and buffer it for report saving."""
        print(text)
        if self.save_reports:
            self.report_buffer.append(text)

    def _format_encounter_for_discord(self, zone_name: str = None) -> str:
        """Format the current encounter as Discord markdown."""
        if not self.current_encounter:
            return "No encounter data available."

        # Use grace period end time if available, otherwise use end_time
        end_time = self.current_encounter.end_time
        duration = (end_time - self.current_encounter.start_time) / 1000.0
        players_count = len(self.current_encounter.players)
        
        # Calculate estimated group DPS
        estimated_dps = 0
        if duration > 0 and self.current_encounter.total_damage > 0:
            estimated_dps = self.current_encounter.total_damage / duration

        # Death counter (total deaths since entering zone)
        deaths_info = ""
        if self.zone_deaths > 0:
            deaths_info = f" | Deaths: {self.zone_deaths}"
        
        # Most damaged hostile monster info (primary target)
        hostile_info = ""
        if (self.current_encounter and self.current_encounter.most_damaged_hostile):
            hostile = self.current_encounter.most_damaged_hostile
            hostile_info = f" | Target: {hostile.name} (HP: {hostile.max_health:,})"

        # Get formatted combat start time
        combat_start_time = self.current_encounter.get_combat_start_time_formatted(self.current_log_file, self.log_start_unix_timestamp)
        
        # Create Discord markdown formatted report
        report_lines = []
        
        # Header with encounter summary
        if zone_name:
            if estimated_dps > 0:
                header = f"**{combat_start_time} ({zone_name})** | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{hostile_info}"
            else:
                header = f"**{combat_start_time} ({zone_name})** | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{hostile_info}"
        else:
            if estimated_dps > 0:
                header = f"**{combat_start_time}** | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{hostile_info}"
            else:
                header = f"**{combat_start_time}** | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{hostile_info}"
        
        report_lines.append(header)
        report_lines.append("")  # Empty line
        
        # Group buff analysis for encounters with 3+ players
        if players_count >= 3:
            buff_analysis = self.current_encounter.get_group_buff_analysis()
            buff_status = []
            for buff_name, is_present in buff_analysis.items():
                if is_present:
                    # Calculate group uptime (time buff was active on any player)
                    group_uptime = self.current_encounter.get_group_buff_uptime(buff_name)
                    status = f"✅ ({group_uptime:.1f}%)"
                else:
                    status = "❌"
                buff_status.append(f"**{buff_name}**: {status}")
            report_lines.append("**Group Buffs:** " + " | ".join(buff_status))
            report_lines.append("")  # Empty line
        
        # Sort players by damage contribution (descending)
        players_with_damage = []
        for player in self.current_encounter.players.values():
            # Skip players without PLAYER_INFO data (no equipped abilities)
            if not player.equipped_abilities:
                continue
            player_damage = self.current_encounter.player_damage.get(player.unit_id, 0)
            players_with_damage.append((player, player_damage))
        
        # Sort by damage (descending)
        players_with_damage.sort(key=lambda x: x[1], reverse=True)
        
        for player, player_damage in players_with_damage:
            # Calculate player DPS
            player_dps = 0
            if duration > 0 and player_damage > 0:
                player_dps = player_damage / duration
            
            # Use equipped abilities from PLAYER_INFO
            abilities_to_analyze = player.equipped_abilities
            
            # Analyze subclass and build first to create the title line
            analysis = None
            if abilities_to_analyze:
                analysis = self.subclass_analyzer.analyze_subclass(abilities_to_analyze)
            
            # Create the title line: @playername {character_name} skill_lines dominant_resource
            title_parts = [f"**{player.get_display_name()}**"]
            
            # Add character name if available and different from handle
            character_name = player.name if player.name and player.name not in ['""', '', '0'] else ""
            if character_name and character_name != player.get_display_name():
                title_parts.append(f"*{character_name}*")
            
            if analysis and analysis['confidence'] > 0.1:
                if analysis['skill_lines']:
                    # Use skill line aliases if available, otherwise extract first word
                    skill_line_aliases = []
                    class_skill_lines = player.get_class_skill_lines()

                    for skill_line in analysis['skill_lines']:
                        # Check if we have an alias for this skill line (partial matching)
                        alias_found = False
                        for alias_key, alias_value in self.subclass_analyzer.SKILL_LINE_ALIASES.items():
                            if alias_key in skill_line:
                                # Check if this is a class skill line and make it bold
                                if any(alias_value in class_skill for class_skill in class_skill_lines):
                                    skill_line_aliases.append(f"**{alias_value}**")
                                else:
                                    skill_line_aliases.append(alias_value)
                                alias_found = True
                                break
                        
                        if not alias_found:
                            # Fall back to first word
                            first_word = skill_line.split()[0]
                            # Check if this is a class skill line and make it bold
                            if any(first_word in class_skill for class_skill in class_skill_lines):
                                skill_line_aliases.append(f"**{first_word}**")
                            else:
                                skill_line_aliases.append(first_word)
                    
                    # Sort skill line aliases before joining
                    skill_line_aliases.sort()
                    skill_lines_str = '/'.join(skill_line_aliases)
                    
                    # Add class name and resource information after skill lines
                    class_name = player.get_class_name()
                    if class_name and class_name != "Unknown":
                        # Format resources
                        resource_str = ""
                        dps_str = ""
                        if player.max_health > 0 or player.max_magicka > 0 or player.max_stamina > 0:
                            # Round to nearest 0.5k (500)
                            def round_to_half_k(value):
                                if value == 0:
                                    return "0k"
                                rounded = round(value / 500) * 0.5
                                if rounded == int(rounded):
                                    return f"{int(rounded)}k"
                                else:
                                    return f"{rounded:.1f}k"

                            health_display = round_to_half_k(player.max_health)
                            magicka_display = round_to_half_k(player.max_magicka)
                            stamina_display = round_to_half_k(player.max_stamina)

                            # Bold the highest resource value
                            max_resource_value = max(player.max_health, player.max_magicka, player.max_stamina)
                            if max_resource_value > 0:
                                if player.max_health == max_resource_value:
                                    health_display = f"**{health_display}**"
                                elif player.max_magicka == max_resource_value:
                                    magicka_display = f"**{magicka_display}**"
                                elif player.max_stamina == max_resource_value:
                                    stamina_display = f"**{stamina_display}**"

                            resource_str = f" M:{magicka_display} S:{stamina_display} H:{health_display}"
                            
                            # Add DPS information and damage percentage
                            if player_dps > 0:
                                # Calculate damage percentage of total group damage
                                damage_percentage = 0
                                if self.current_encounter.total_damage > 0:
                                    damage_percentage = (player_damage / self.current_encounter.total_damage) * 100
                                dps_str = f" D:{damage_percentage:.1f}%"

                        skill_lines_str += f" ({class_name}{resource_str}{dps_str})"
                    title_parts.append(skill_lines_str)
                else:
                    title_parts.append("unknown")
            else:
                title_parts.append("unknown")
            
            report_lines.append(' '.join(title_parts))
            
            if abilities_to_analyze:
                # Show front and back bar abilities in order if available
                if player.front_bar_abilities or player.back_bar_abilities:
                    if player.front_bar_abilities:
                        highlighted_front_bar = highlight_taunt_abilities(player.front_bar_abilities)
                        # Convert to Discord markdown (bold taunt abilities)
                        discord_front_bar = []
                        for ability in highlighted_front_bar:
                            if ability.startswith(Fore.MAGENTA):  # Taunt ability
                                clean_ability = ability.replace(Fore.MAGENTA, '').replace(Style.RESET_ALL, '')
                                discord_front_bar.append(f"**{clean_ability}**")
                            else:
                                discord_front_bar.append(ability)
                        report_lines.append(f"  {', '.join(discord_front_bar)}")
                    if player.back_bar_abilities:
                        highlighted_back_bar = highlight_taunt_abilities(player.back_bar_abilities)
                        # Convert to Discord markdown (bold taunt abilities)
                        discord_back_bar = []
                        for ability in highlighted_back_bar:
                            if ability.startswith(Fore.MAGENTA):  # Taunt ability
                                clean_ability = ability.replace(Fore.MAGENTA, '').replace(Style.RESET_ALL, '')
                                discord_back_bar.append(f"**{clean_ability}**")
                            else:
                                discord_back_bar.append(ability)
                        report_lines.append(f"  {', '.join(discord_back_bar)}")
                else:
                    abilities_list = sorted(list(abilities_to_analyze))[:10]  # Show top 10 abilities
                    highlighted_abilities = highlight_taunt_abilities(abilities_list)
                    # Convert to Discord markdown (bold taunt abilities)
                    discord_abilities = []
                    for ability in highlighted_abilities:
                        if ability.startswith(Fore.MAGENTA):  # Taunt ability
                            clean_ability = ability.replace(Fore.MAGENTA, '').replace(Style.RESET_ALL, '')
                            discord_abilities.append(f"**{clean_ability}**")
                        else:
                            discord_abilities.append(ability)
                    report_lines.append(f"  **Equipped:** {', '.join(discord_abilities)}")
                    if len(abilities_to_analyze) > 10:
                        report_lines.append(f"  ... and {len(abilities_to_analyze) - 10} more")

                # Analyze gear sets (no role-based filtering)
                identified_sets = []
                
                # Also check for gear sets from equipped abilities
                gear_set_abilities_found = []
                # Get the equipped ability IDs from the player info
                if hasattr(player, '_equipped_ability_ids'):
                    for ability_id in player._equipped_ability_ids:
                        if ability_id in self.gear_set_abilities:
                            gear_set_abilities_found.append({
                                'name': self.gear_set_abilities[ability_id],
                                'confidence': 0.9,
                                'source': 'equipped_ability'
                            })
                
                # Combine identified sets with gear set abilities
                all_identified_sets = identified_sets + gear_set_abilities_found
                
                # Create equipment summary line
                equipment_parts = []
                if player.gear:
                    # Count gear pieces by set name
                    set_counts = {}
                    for slot, gear_item in player.gear.items():
                        if len(gear_item) > 6:  # Make sure we have set ID
                            set_id = str(gear_item[6])  # Set ID is at position 6

                            # Skip items with no set (set ID 0 or empty)
                            if set_id == "0" or set_id == "" or set_id == "nan":
                                continue

                            # Look up set name by set ID
                            set_name = gear_set_db.get_set_name_by_set_id(set_id)
                            if not set_name:
                                set_name = f"Unknown Set ({set_id})"

                            # Check if this is a 2-handed weapon or staff (count as 2 pieces)
                            piece_count = 1
                            if slot in ['MAIN_HAND', 'BACKUP_MAIN'] and self._is_two_handed_weapon(gear_item, player.gear):
                                piece_count = 2

                            set_counts[set_name] = set_counts.get(set_name, 0) + piece_count
                    
                    # Format equipment summary
                    for set_name, count in set_counts.items():
                        if count >= 5:
                            equipment_parts.append(f"{count}pc {set_name}")
                        elif count >= 2:
                            equipment_parts.append(f"{count}pc {set_name}")
                        else:
                            equipment_parts.append(f"{count}pc {set_name}")
                
                # Add inferred sets
                if all_identified_sets:
                    high_confidence_sets = [s for s in all_identified_sets if s['confidence'] > 0.5]
                    for set_info in high_confidence_sets:
                        if set_info['name'] not in [part.split('pc ')[1] for part in equipment_parts]:
                            equipment_parts.append(f"?pc {set_info['name']} (inferred)")
                
                # Show equipment summary
                if equipment_parts:
                    # Sort equipment by set name, ignoring "Perfected" prefix
                    def sort_key(item):
                        # Extract set name from "Xpc Set Name" format
                        if 'pc ' in item:
                            set_name = item.split('pc ', 1)[1]
                            # Remove "Perfected " prefix for sorting
                            if set_name.startswith('Perfected '):
                                set_name = set_name[10:]  # Remove "Perfected "
                            return set_name.lower()
                        return item.lower()

                    equipment_parts.sort(key=sort_key)

                    # Apply Discord markdown formatting to equipment parts
                    discord_equipment_parts = []
                    for part in equipment_parts:
                        if 'pc ' in part:
                            # Extract piece count and set name
                            pieces_str, set_name = part.split('pc ', 1)
                            piece_count = int(pieces_str) if pieces_str.isdigit() else 0

                            # Remove any trailing text like "(inferred)"
                            clean_set_name = set_name.split(' (')[0]

                            # Check if it's a mythic set (make it bold)
                            if clean_set_name in MYTHIC_SETS:
                                discord_equipment_parts.append(f"**{set_name}**")
                            # Check if it's an incomplete 5-piece set (make it bold red) - but never highlight monster sets
                            elif has_five_piece_bonus(clean_set_name) and piece_count < 5:
                                # Explicitly exclude 2-piece sets (monster sets + arena weapon sets) from highlighting
                                two_piece_set_keywords = [
                                    # Monster sets (2-piece)
                                    "spawn of mephala", "blood spawn", "lord warden", "scourge harvester", "engine guardian", "nightflame",
                                    "nerien'eth", "valkyn skoria", "maw of the infernal", "molag kena", "mighty chudan", "velidreth",
                                    "giant spider", "shadowrend", "kra'gh", "swarm mother", "sentinel of rkugamz", "chokethorn",
                                    "slimecraw", "sellistrix", "infernal guardian", "ilambris", "iceheart", "stormfist", "tremorscale",
                                    "pirate skeleton", "the troll king", "selene", "grothdarr", "earthgore", "domihaus", "thurvokun",
                                    "zaan", "balorgh", "vykosa", "stonekeeper", "symphony of blades", "grundwulf", "maarselok",
                                    "mother ciannait", "kjalnar's nightmare", "stone husk", "lady thorn", "encrati's behemoth",
                                    "baron zaudrus", "prior thierric", "magma incarnate", "kargaeda", "nazaray", "archdruid devyric",
                                    "euphotic gatekeeper", "roksa the warped", "ozezan the inferno", "anthelmir's construct",
                                    "the blind", "squall of retribution", "orpheon the tactician", "nunatak", "nunatak's blessing", "nunatak", "nunatak's blessing",
                                    # Arena weapon sets (2-piece)
                                    "archer's mind", "footman's fortune", "healer's habit", "robes of destruction mastery", "permafrost",
                                    "glorious defender", "para bellum", "elemental succession", "hunt leader", "winterborn",
                                    "titanic cleave", "puncturing remedy", "stinging slashes", "caustic arrow", "destructive impact",
                                    "grand rejuvenation", "merciless charge", "rampaging slash", "cruel flurry", "thunderous volley",
                                    "crushing wall", "precise regeneration", "gallant charge", "radial uppercut", "spectral cloak",
                                    "virulent shot", "wild impulse", "mender's ward", "perfect gallant charge", "perfect radial uppercut",
                                    "perfect spectral cloak", "perfect virulent shot", "perfect wild impulse", "perfect mender's ward",
                                    "perfected merciless charge", "perfected rampaging slash", "perfected cruel flurry", "perfected thunderous volley",
                                    "perfected crushing wall", "perfected precise regeneration", "perfected titanic cleave", "perfected puncturing remedy",
                                    "perfected stinging slashes", "perfected caustic arrow", "perfected destructive impact", "perfected grand rejuvenation",
                                    "executioner's blade", "void bash", "frenzied momentum", "point-blank snipe", "wrath of elements",
                                    "perfect executioner's blade", "perfect void bash", "perfect frenzied momentum", "perfect point-blank snipe", "perfect wrath of elements",
                                    "perfected executioner's blade", "perfected void bash", "perfected frenzied momentum", "perfected point-blank snipe", "perfected wrath of elements"
                                ]
                                if not any(keyword in clean_set_name.lower() for keyword in two_piece_set_keywords):
                                    discord_equipment_parts.append(f"**{set_name}** ⚠️")
                                else:
                                    discord_equipment_parts.append(set_name)
                            else:
                                discord_equipment_parts.append(set_name)
                        else:
                            discord_equipment_parts.append(part)
                    
                    report_lines.append(f"  **Equipment:** {', '.join(discord_equipment_parts)}")
            
            report_lines.append("")  # Empty line after each player

        # Show hostile monsters if any
        if self.current_encounter and self.current_encounter.enemies:
            unique_hostiles = []
            seen = set()
            for unit_id, enemy in self.current_encounter.enemies.items():
                if enemy.is_hostile:
                    key = (unit_id, enemy.name)
                    if key not in seen:
                        seen.add(key)
                        unique_hostiles.append((unit_id, enemy.name, enemy.unit_type, enemy.max_health))
            
            if unique_hostiles:
                # Sort by health (descending), then by name
                unique_hostiles.sort(key=lambda x: (x[3], x[1]), reverse=True)
                
                hostile_names = []
                for unit_id, name, unit_type, max_health in unique_hostiles:
                    if max_health > 0:
                        hostile_names.append(f"{name} ({max_health:,} HP)")
                    else:
                        hostile_names.append(name)
                
                if hostile_names:
                    report_lines.append(f"**Hostile Monsters:** {', '.join(hostile_names)}")
                    report_lines.append("")  # Empty line

        return '\n'.join(report_lines)

    def _copy_discord_report_to_clipboard(self):
        """Copy the last encounter report to clipboard in Discord markdown format."""
        if not CLIPBOARD_AVAILABLE:
            print(f"{Fore.RED}Error: pyperclip not available. Install with: pip install pyperclip{Style.RESET_ALL}")
            return False
        
        if not self.last_encounter_report:
            print(f"{Fore.YELLOW}No encounter report available to copy.{Style.RESET_ALL}")
            return False
        
        try:
            pyperclip.copy(self.last_encounter_report)
            print(f"{Fore.GREEN}Discord markdown report copied to clipboard!{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"{Fore.RED}Error copying to clipboard: {e}{Style.RESET_ALL}")
            return False

    def _start_keyboard_listener(self):
        """Start keyboard listener for 'c' key detection."""
        if not KEYBOARD_AVAILABLE:
            print(f"{Fore.YELLOW}Warning: pynput not available. Discord copy feature disabled.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Install with: pip install pynput{Style.RESET_ALL}")
            return False
        
        def on_press(key):
            try:
                if hasattr(key, 'char') and key.char == 'c':
                    # Only copy if we're not in the middle of typing something
                    # This is a simple check - in a real implementation you might want more sophisticated detection
                    self._copy_discord_report_to_clipboard()
            except AttributeError:
                pass  # Handle special keys that don't have a 'char' attribute
        
        try:
            self.keyboard_listener = keyboard.Listener(on_press=on_press)
            self.keyboard_listener.start()
            return True
        except Exception as e:
            print(f"{Fore.RED}Error starting keyboard listener: {e}{Style.RESET_ALL}")
            return False

    def _stop_keyboard_listener(self):
        """Stop keyboard listener."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

    def _update_player_session(self, unit_id: str, name: str, handle: str, equipped_abilities: List[str] = None, gear_data: List = None, class_id: str = None):
        """Update or create a player session with their current data."""
        if not handle or handle == "" or not name or name == "":
            return
            
        # Clean up handle and name (remove quotes if present)
        clean_handle = handle.strip('"') if handle else ""
        clean_name = name.strip('"') if name else ""
        if not clean_handle or not clean_name:
            return
            
        # Create composite key for character-specific sessions
        session_key = f"{clean_handle}+{clean_name}"
        
        # Update unit ID mapping
        self.unit_id_to_handle[unit_id] = clean_handle
        
        # Update or create session data
        if session_key not in self.player_sessions:
            self.player_sessions[session_key] = {
                'unit_id': unit_id,
                'name': clean_name,
                'class_id': class_id,
                'equipped_abilities': equipped_abilities or [],
                'gear_data': gear_data or [],
                'last_seen': 0
            }
        else:
            # Update existing session
            self.player_sessions[session_key]['unit_id'] = unit_id
            self.player_sessions[session_key]['name'] = clean_name
            if class_id:
                self.player_sessions[session_key]['class_id'] = class_id
            if equipped_abilities:
                self.player_sessions[session_key]['equipped_abilities'] = equipped_abilities
            if gear_data:
                self.player_sessions[session_key]['gear_data'] = gear_data
            self.player_sessions[session_key]['last_seen'] = 0

    def _get_player_from_session(self, unit_id: str, name: str, handle: str) -> Optional[PlayerInfo]:
        """Get player info from session data if available."""
        if not handle or not name:
            return None
            
        # Clean up handle and name (remove quotes if present)
        clean_handle = handle.strip('"') if handle else ""
        clean_name = name.strip('"') if name else ""
        if not clean_handle or not clean_name:
            return None
            
        # Create composite key for character-specific sessions
        session_key = f"{clean_handle}+{clean_name}"
        
        if session_key not in self.player_sessions:
            return None
            
        session_data = self.player_sessions[session_key]
        
        # Create PlayerInfo from session data
        player = PlayerInfo(unit_id, clean_name, clean_handle, session_data.get('class_id'))
        player.equipped_abilities = session_data['equipped_abilities']
        player.gear_data = session_data['gear_data']
        
        return player

    def _is_player_offline(self, unit_id: str) -> bool:
        """Check if a player is currently offline (not in current encounter)."""
        if not self.current_encounter:
            return True
        return unit_id not in self.current_encounter.players

    def _restore_player_from_session(self, unit_id: str, name: str, handle: str):
        """Restore a player from session data when they come back online."""
        if not self.current_encounter:
            return

        # Get session data
        player = self._get_player_from_session(unit_id, name, handle)
        if not player:
            return

        # Update session with current unit_id
        self._update_player_session(unit_id, name, handle, player.equipped_abilities, player.gear_data, player.class_id)

        # Add player to current encounter with session data
        self.current_encounter.players[unit_id] = player

        # Associate long unit ID if available
        if hasattr(self.current_encounter, 'unit_id_mapping') and unit_id in self.current_encounter.unit_id_mapping:
            long_unit_id = self.current_encounter.unit_id_mapping[unit_id]
            if hasattr(self.current_encounter, 'associate_long_unit_id'):
                self.current_encounter.associate_long_unit_id(unit_id, long_unit_id)

    def _cleanup_offline_players(self):
        """Clean up session data for players who are no longer in the current encounter."""
        if not self.current_encounter:
            return
            
        current_unit_ids = set(self.current_encounter.players.keys())
        
        # Find handles for players no longer in current encounter
        offline_handles = []
        for handle, session_data in self.player_sessions.items():
            if session_data['unit_id'] not in current_unit_ids:
                offline_handles.append(handle)
        
        # Remove offline players from unit_id mapping but keep session data
        for handle in offline_handles:
            if handle in self.player_sessions:
                old_unit_id = self.player_sessions[handle]['unit_id']
                if old_unit_id in self.unit_id_to_handle:
                    del self.unit_id_to_handle[old_unit_id]


class LogSplitter:
    """Handles automatic splitting of encounter logs into individual encounter files."""
    
    def __init__(self, log_file: Path, diagnostic: bool = False, split_dir: Optional[Path] = None):
        self.log_file = log_file
        self.diagnostic = diagnostic
        self.split_dir = split_dir or log_file.parent  # Use custom dir or same as log file
        self.current_split_file = None
        self.current_split_path = None
        self.current_encounter_info = None
        self.split_files = []  # Track all created split files
        self.file_handle = None  # File handle for current split file
        
        # Zone tracking for combat-based naming
        self.pending_begin_log = None  # Store BEGIN_LOG entry until combat starts
        self.current_zone = None  # Track current zone as we go through the log
        self.current_difficulty = None  # Track current difficulty
        self.combat_started = False  # Track if combat has started
        self.temp_file_path = None  # Temporary file path before rename
        self.final_file_path = None  # Final file path after rename
        
        # Ensure split directory exists
        self.split_dir.mkdir(parents=True, exist_ok=True)
        
    def start_encounter(self, begin_log_entry, zone_name: str = "", difficulty: str = ""):
        """Start a new encounter split file."""
        # Close any existing split file
        self.end_encounter()
        
        # Store BEGIN_LOG entry and initialize zone tracking
        self.pending_begin_log = begin_log_entry
        self.current_zone = zone_name if zone_name else ""
        self.current_difficulty = difficulty if difficulty else ""
        self.combat_started = False
        
        # Create temporary file immediately
        self._create_temp_file()
        
        # If we already have zone info, rename immediately
        if zone_name:
            self._rename_to_final()
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_LOG detected with zone: {zone_name}{Style.RESET_ALL}")
        else:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_LOG detected, waiting for first zone{Style.RESET_ALL}")
    
    def _create_temp_file(self):
        """Create a temporary file immediately for writing."""
        if not self.pending_begin_log:
            return
            
        # Create temporary filename based on BEGIN_LOG timestamp
        timestamp = self.pending_begin_log.timestamp
        dt = datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
        
        # Format: YYMMDDHHMMSS-temp.log
        time_str = dt.strftime("%y%m%d%H%M%S")
        temp_filename = f"{time_str}-temp.log"
        self.temp_file_path = self.split_dir / temp_filename
        
        try:
            # Open file for writing (create new file)
            self.file_handle = open(self.temp_file_path, 'w', encoding='utf-8')
            self.current_split_file = self.temp_file_path
            self.current_split_path = self.temp_file_path
            self.current_encounter_info = {
                'path': self.temp_file_path,
                'start_time': timestamp,
                'zone_name': self.current_zone,
                'difficulty': self.current_difficulty
            }
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp_str}] DIAGNOSTIC: Created temporary file: {self.temp_file_path}{Style.RESET_ALL}")
                
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to create temporary file {self.temp_file_path}: {e}{Style.RESET_ALL}")
            self.current_split_file = None
            self.current_split_path = None
            self.current_encounter_info = None
            self.file_handle = None
            self.temp_file_path = None
    
    def _rename_to_final(self):
        """Rename the temporary file to the final name based on combat zone."""
        if not self.temp_file_path or not self.file_handle:
            return
            
        # Close the file handle before renaming
        try:
            self.file_handle.close()
            self.file_handle = None
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close file before rename: {e}{Style.RESET_ALL}")
        
        # Create final filename based on BEGIN_LOG timestamp and combat zone
        timestamp = self.pending_begin_log.timestamp
        dt = datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
        
        # Format: YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}.log
        time_str = dt.strftime("%y%m%d%H%M%S")
        
        difficulty_suffix = "-vet" if self.current_difficulty.upper() == "VETERAN" else ""
        zone_suffix = self.current_zone.replace(" ", "-") if self.current_zone else "Unknown-Zone"
        
        final_filename = f"{time_str}-{zone_suffix}{difficulty_suffix}.log"
        self.final_file_path = self.split_dir / final_filename
        
        try:
            # Rename the file
            self.temp_file_path.rename(self.final_file_path)
            
            # Update tracking
            self.current_split_file = self.final_file_path
            self.current_split_path = self.final_file_path
            self.current_encounter_info['path'] = self.final_file_path
            self.split_files.append(self.final_file_path)
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp_str}] DIAGNOSTIC: Renamed to final file: {self.final_file_path}{Style.RESET_ALL}")
                
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to rename file to {self.final_file_path}: {e}{Style.RESET_ALL}")
            # Keep the temp file if rename fails
            self.current_split_file = self.temp_file_path
            self.current_split_path = self.temp_file_path
    
    def write_log_line(self, line: str):
        """Write a log line to the current split file."""
        if self.file_handle:
            try:
                self.file_handle.write(line + '\n')
                self.file_handle.flush()  # Ensure immediate write
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to write to split file: {e}{Style.RESET_ALL}")
    
    def start_combat(self):
        """Mark that combat has started - rename file to current zone."""
        if not self.combat_started:
            self.combat_started = True
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Combat started in zone: {self.current_zone} ({self.current_difficulty}){Style.RESET_ALL}")
            
            # Rename the file to reflect the current zone when combat started
            self._rename_to_final()
    
    def handle_zone_change(self, zone_name: str, difficulty: str):
        """Handle a zone change - update current zone tracking."""
        # Check if this is the first zone we've encountered
        first_zone = not self.current_zone
        
        # Update current zone information
        self.current_zone = zone_name
        self.current_difficulty = difficulty
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Zone changed to: {zone_name} ({difficulty}){Style.RESET_ALL}")
        
        # Don't rename here - wait for combat to start
        # The file will be renamed when combat begins
    
    def end_encounter(self):
        """End the current encounter and close the split file."""
        if self.file_handle:
            try:
                self.file_handle.close()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: Closed split file: {self.current_split_path}{Style.RESET_ALL}")
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close split file {self.current_split_path}: {e}{Style.RESET_ALL}")
            finally:
                self.file_handle = None
                self.current_split_file = None
                self.current_split_path = None
                self.current_encounter_info = None
                self.pending_begin_log = None
                self.current_zone = None
                self.current_difficulty = None
                self.combat_started = False
                self.temp_file_path = None
                self.final_file_path = None
    
    def close_for_waiting(self):
        """Close the current split file when waiting for new events to prevent data loss."""
        if self.file_handle:
            try:
                self.file_handle.close()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Closed split file for waiting: {self.current_split_path}{Style.RESET_ALL}")
                self.file_handle = None
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close split file for waiting: {e}{Style.RESET_ALL}")
    
    def reopen_for_append(self):
        """Reopen the current split file for appending when new events arrive."""
        if self.current_split_path and not self.file_handle:
            try:
                self.file_handle = open(self.current_split_path, 'a', encoding='utf-8')
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Reopened split file for append: {self.current_split_path}{Style.RESET_ALL}")
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to reopen split file for append: {e}{Style.RESET_ALL}")
                self.file_handle = None

    def cleanup(self):
        """Clean up all split files."""
        self.end_encounter()
        # Could add cleanup logic here if needed


class LogFileMonitor:
    """Simple file polling monitor for log file changes."""

    def __init__(self, analyzer: ESOLogAnalyzer, log_file: Path, read_all_then_tail: bool = False, tail_and_split: bool = False, split_dir: Optional[Path] = None):
        self.analyzer = analyzer
        self.log_file = log_file
        self.last_position = 0
        self.read_all_then_tail = read_all_then_tail
        self.tail_and_split = tail_and_split
        self.has_read_all = False
        self.diagnostic = analyzer.diagnostic
        self.file_lock = threading.Lock()  # Prevent concurrent file access
        self.running = False
        
        # Initialize log splitter if needed
        self.log_splitter = LogSplitter(log_file, diagnostic=self.diagnostic, split_dir=split_dir) if tail_and_split else None

        # Initialize position based on mode
        if self.log_file.exists():
            if read_all_then_tail:
                # Start from the beginning to read everything first
                print(f"{Fore.CYAN}Reading entire log file from the beginning...{Style.RESET_ALL}")
                self.last_position = 0
                self._process_entire_file()
                print(f"{Fore.GREEN}Finished reading existing log data. Now monitoring for new data...{Style.RESET_ALL}")
            else:
                # Look back through recent log entries to find zone changes
                self._initialize_zone_history()
                self.last_position = self.log_file.stat().st_size

    def _initialize_zone_history(self):
        """Look back through recent log entries to find zone changes."""
        if not self.log_file.exists():
            return
            
        file_size = self.log_file.stat().st_size
        # Look back through the last 50KB of the file for zone changes
        lookback_size = min(50000, file_size)
        start_position = max(0, file_size - lookback_size)
        
        print(f"{Fore.CYAN}Scanning recent log entries for zone changes...{Style.RESET_ALL}")
        
        entries = self.analyzer._process_log_file_from_position(self.log_file, start_position)
        zone_found = False
        
        # Process entries in chronological order to find the most recent zone change
        for entry in entries:
            if entry.event_type == "ZONE_CHANGED" and len(entry.fields) >= 3:
                zone_name = entry.fields[1].strip('"')
                self.analyzer._add_zone_to_history(entry.timestamp, zone_name)
                if not zone_found:
                    print(f"{Fore.GREEN}Found recent zone: {zone_name}{Style.RESET_ALL}")
                    zone_found = True
        
        if not zone_found:
            print(f"{Fore.YELLOW}No recent zone changes found in log{Style.RESET_ALL}")

    def _process_entire_file(self):
        """Process the entire log file from the beginning."""
        if not self.log_file.exists():
            return
        
        with self.file_lock:  # Prevent concurrent file access
            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Processing entire file {self.log_file.name} from beginning{Style.RESET_ALL}")
            
            line_count = 0
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                while True:
                    line = f.readline()
                    if not line:  # End of file
                        break
                        
                    line = line.strip()
                    if line:
                        entry = ESOLogEntry.parse(line)
                        if entry:
                            # Handle log splitting if enabled
                            if self.log_splitter:
                                self._handle_log_splitting(entry, line)
                            
                            self.analyzer.process_log_entry(entry)
                            line_count += 1
                    
                    # Update position to current position
                    self.last_position = f.tell()
            
            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Processed {line_count} lines from {self.log_file.name}, now tailing{Style.RESET_ALL}")
            
            # Close any open split files after processing entire file
            if self.log_splitter:
                self.log_splitter.end_encounter()
            
            self.has_read_all = True

    def check_for_changes(self):
        """Check for file changes and process new lines."""
        if not self.log_file.exists():
            return False
            
        with self.file_lock:
            current_size = self.log_file.stat().st_size
            if current_size > self.last_position:
                # Reopen split file for appending when new data arrives
                if self.log_splitter:
                    self.log_splitter.reopen_for_append()
                
                if self.diagnostic:
                    timestamp = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: File growth detected in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
                self._process_new_lines()
                return True
            else:
                # Close split file when waiting for new data
                if self.log_splitter:
                    self.log_splitter.close_for_waiting()
                
                if self.diagnostic:
                    timestamp = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.BLUE}[{timestamp}] DIAGNOSTIC: No changes in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
        return False

    def _process_new_lines(self):
        """Process new lines added to the log file."""
        if not self.log_file.exists():
            return

        with self.file_lock:  # Prevent concurrent file access
            current_size = self.log_file.stat().st_size
            if current_size <= self.last_position:
                if self.diagnostic:
                    timestamp = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.BLUE}[{timestamp}] DIAGNOSTIC: No new data in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
                return

            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Reading new data from {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")

            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()

            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Read {len(new_lines)} lines from {self.log_file.name}{Style.RESET_ALL}")

            for line in new_lines:
                line = line.strip()
                if line:
                    entry = ESOLogEntry.parse(line)
                    if entry:
                        # Handle log splitting if enabled
                        if self.log_splitter:
                            self._handle_log_splitting(entry, line)
                        
                        self.analyzer.process_log_entry(entry)
    
    def _handle_log_splitting(self, entry, line: str):
        """Handle log splitting logic based on log entry type."""
        if not self.log_splitter:
            return
            
        # Handle BEGIN_LOG - start new encounter
        if entry.event_type == "BEGIN_LOG":
            # Start encounter without zone info - will wait for first zone
            self.log_splitter.start_encounter(entry)
            # Write the BEGIN_LOG line
            self.log_splitter.write_log_line(line)
        
        # Handle ZONE_CHANGED - track current zone
        elif entry.event_type == "ZONE_CHANGED":
            # Extract zone name and difficulty from ZONE_CHANGED
            # Format: ZONE_CHANGED,zone_id,"Zone Name",difficulty
            if len(entry.fields) >= 2:
                zone_name = entry.fields[0].strip('"') if entry.fields[0] else ""
                difficulty = entry.fields[1].strip('"') if len(entry.fields) > 1 else ""
                
                # Update current zone tracking
                self.log_splitter.handle_zone_change(zone_name, difficulty)
                
                # Write the ZONE_CHANGED line
                self.log_splitter.write_log_line(line)
        
        # Handle BEGIN_COMBAT - rename file to current zone
        elif entry.event_type == "BEGIN_COMBAT":
            self.log_splitter.start_combat()
            # Write the BEGIN_COMBAT line
            self.log_splitter.write_log_line(line)
        
        # Handle END_LOG - end current encounter
        elif entry.event_type == "END_LOG":
            if self.log_splitter.pending_begin_log or self.log_splitter.current_split_file:
                self.log_splitter.write_log_line(line)
                self.log_splitter.end_encounter()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG detected, closing split file{Style.RESET_ALL}")
        
        # Write all other lines to current split file
        else:
            self.log_splitter.write_log_line(line)

@click.command()
@click.option('--log-file', '-f', type=click.Path(),
              help='Path to ESO encounter log file')
@click.option('--read-all-then-stop', '-s', is_flag=True,
              help='Read mode: replay the entire log file from the beginning at high speed, then exit')
@click.option('--read-all-then-tail', '-t', is_flag=True,
              help='Read the entire log file from the beginning, then continue tailing for new data')
@click.option('--no-wait', is_flag=True,
              help='Exit immediately if log file does not exist (default: wait for file to appear)')
@click.option('--replay-speed', '-r', default=100, type=int,
              help='Replay speed multiplier for read mode (default: 100x)')
@click.option('--version', '-v', is_flag=True,
              help='Show version information and exit')
@click.option('--list-hostiles', is_flag=True,
              help='Testing mode: List all hostile monsters added to fights with names and IDs')
@click.option('--diagnostic', is_flag=True,
              help='Diagnostic mode: Show detailed timing and data flow information for debugging')
@click.option('--tail-and-split', is_flag=True,
              help='Auto-split mode: Automatically create individual encounter files while tailing the main log')
@click.option('--split-dir', type=click.Path(), default=None,
              help='Directory for split files (default: same directory as source log file)')
@click.option('--save-reports', is_flag=True,
              help='Save encounter reports to files with timestamp-based naming')
@click.option('--reports-dir', type=click.Path(), default=None,
              help='Directory for saved reports (default: same directory as source log file)')
def main(log_file: Optional[str], read_all_then_stop: bool, read_all_then_tail: bool, no_wait: bool, replay_speed: int, version: bool, list_hostiles: bool, diagnostic: bool, tail_and_split: bool, split_dir: Optional[str], save_reports: bool, reports_dir: Optional[str]):
    """ESO Encounter Log Analyzer - Monitor and analyze ESO combat encounters."""
    
    # Handle version flag early (before any other processing)
    if version:
        print(f"ESO Live Encounter Log Sets & Abilities Analyzer v{__version__}")
        print(f"Repository: https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities")
        print(f"License: MIT")
        sys.exit(0)

    print(f"{Fore.CYAN}ESO Live Encounter Log Sets & Abilities Analyzer v{__version__}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Monitoring ESO encounter logs for combat analysis...{Style.RESET_ALL}")
    
    # Check if no arguments were provided and show default behavior explanation
    if not any([log_file, read_all_then_stop, read_all_then_tail, no_wait, list_hostiles, diagnostic, tail_and_split, save_reports]):
        print(f"{Fore.CYAN}No arguments provided - using default behavior:{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • Auto-detect ESO log file location based on your operating system{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • Wait patiently for Encounter.log to appear (if not found){Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • Read existing log data, then monitor for new encounters in real-time{Style.RESET_ALL}")
        print(f"{Fore.WHITE}  • Generate live combat analysis reports as fights happen{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Tip: Use --help to see all available options{Style.RESET_ALL}")
        print()
    
    # Show active options
    active_options = []
    if read_all_then_stop:
        active_options.append("read-all-then-stop")
    if read_all_then_tail:
        active_options.append("read-all-then-tail")
    if no_wait:
        active_options.append("no-wait")
    if list_hostiles:
        active_options.append("list-hostiles")
    if diagnostic:
        active_options.append("diagnostic")
    
    if active_options:
        print(f"{Fore.CYAN}Active options: {', '.join(active_options)}{Style.RESET_ALL}")
    print()

    # Set up reports directory and validate it early
    reports_path = None
    if save_reports:
        if reports_dir:
            reports_path = Path(reports_dir)
        elif log_path:
            reports_path = Path(log_path).parent
        else:
            reports_path = Path.cwd()
        
        # Validate reports directory early
        if not reports_path.exists():
            try:
                reports_path.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                print(f"{Fore.RED}ERROR: Cannot create reports directory: {reports_path}{Style.RESET_ALL}")
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
                print(f"{Fore.RED}Please create the directory manually: mkdir -p {reports_path}{Style.RESET_ALL}")
                sys.exit(1)
        elif not reports_path.is_dir():
            print(f"{Fore.RED}ERROR: Reports path exists but is not a directory: {reports_path}{Style.RESET_ALL}")
            sys.exit(1)
        elif not os.access(reports_path, os.W_OK):
            print(f"{Fore.RED}ERROR: Reports directory is not writable: {reports_path}{Style.RESET_ALL}")
            print(f"{Fore.RED}Please check directory permissions or create it manually: mkdir -p {reports_path}{Style.RESET_ALL}")
            sys.exit(1)
    
    analyzer = ESOLogAnalyzer(list_hostiles=list_hostiles, diagnostic=diagnostic, save_reports=save_reports, reports_dir=reports_path)

    if read_all_then_stop:
        # Determine which log file to use
        if log_file:
            read_log = Path(log_file)
        else:
            # Use auto-detected log file
            read_log = _find_eso_log_file(diagnostic=diagnostic)
            if not read_log:
                print(f"{Fore.RED}Error: No log file found and none specified{Style.RESET_ALL}")
                _provide_log_file_guidance()
                sys.exit(1)
        
        if not read_log.exists():
            print(f"{Fore.RED}Error: Read log file not found: {read_log}{Style.RESET_ALL}")
            sys.exit(1)

        print(f"{Fore.YELLOW}Read mode: Processing {read_log} from the beginning at full speed{Style.RESET_ALL}")
        analyzer.current_log_file = str(read_log)
        split_dir_path = Path(split_dir) if split_dir else None
        _replay_log_file(analyzer, read_log, replay_speed, tail_and_split, split_dir_path)
        return

    # Determine log file path
    if log_file:
        log_path = Path(log_file)
        print(f"{Fore.CYAN}Using specified log file: {log_path}{Style.RESET_ALL}")
    else:
        # Auto-detect based on host OS
        host_type = _get_host_type_description()
        print(f"{Fore.CYAN}Auto-detecting ESO log location for {host_type}...{Style.RESET_ALL}")
        
        # First try to find existing log file
        log_path = _find_eso_log_file(diagnostic=diagnostic)
        if log_path:
            print(f"{Fore.GREEN}Encounter.log found at {log_path}{Style.RESET_ALL}")
        else:
            # Use most likely directory based on host OS
            likely_directory = _get_most_likely_log_directory()
            log_path = likely_directory / "Encounter.log"
            print(f"{Fore.YELLOW}Encounter.log not found, will check in {likely_directory}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Tip: Use --no-wait to see detailed guidance on enabling encounter logging{Style.RESET_ALL}")

    # Check if the directory exists, create it if it doesn't (for monitoring)
    log_directory = log_path.parent
    if not log_directory.exists():
        try:
            log_directory.mkdir(parents=True, exist_ok=True)
            print(f"{Fore.YELLOW}Created log directory: {log_directory}{Style.RESET_ALL}")
        except OSError as e:
            print(f"{Fore.RED}Error: Cannot create log directory {log_directory}: {e}{Style.RESET_ALL}")
            sys.exit(1)

    # Handle file existence - wait by default, exit only if --no-wait is used
    if not log_path.exists():
        if no_wait:
            print(f"{Fore.YELLOW}Encounter.log not found at {log_path}{Style.RESET_ALL}")
            _provide_log_file_guidance()
            sys.exit(1)
        else:
            # Wait for file by default
            if not _wait_for_file(log_path, True):
                print(f"{Fore.RED}Error: Could not wait for log file{Style.RESET_ALL}")
                sys.exit(1)
    else:
        print(f"{Fore.GREEN}Encounter.log found at {log_path}{Style.RESET_ALL}")

    print(f"{Fore.GREEN}Monitoring: {log_path}{Style.RESET_ALL}")

    # Set the current log file path for timestamp calculations
    analyzer.current_log_file = str(log_path)

    # Set up file monitoring with simple polling
    split_dir_path = Path(split_dir) if split_dir else None
    file_monitor = LogFileMonitor(analyzer, log_path, read_all_then_tail, tail_and_split, split_dir_path)
    file_monitor.running = True

    # Start keyboard listener for Discord copy feature - ONLY during tailing/monitoring
    analyzer._start_keyboard_listener()

    try:
        print(f"{Fore.YELLOW}Press Ctrl+C to stop monitoring{Style.RESET_ALL}\n")
        poll_interval = 1.0  # Check for changes every second
        
        while file_monitor.running:
            file_monitor.check_for_changes()
            
            if analyzer.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp}] DIAGNOSTIC: Polling {log_path.name} for changes...{Style.RESET_ALL}")
            
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopping monitor...{Style.RESET_ALL}")
        file_monitor.running = False
        
        # Clean up log splitter if it exists
        if file_monitor.log_splitter:
            file_monitor.log_splitter.cleanup()
            if tail_and_split:
                print(f"{Fore.CYAN}Auto-split cleanup completed{Style.RESET_ALL}")
        
        # Stop keyboard listener
        analyzer._stop_keyboard_listener()

def _wait_for_file(log_path: Path, wait_for_file: bool = False) -> bool:
    """Wait for the log file to appear if it doesn't exist."""
    if log_path.exists():
        return True
    
    if not wait_for_file:
        return False
    
    print(f"{Fore.YELLOW}Waiting for {log_path.name} to appear...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Make sure encounter logging is enabled in ESO{Style.RESET_ALL}")
    
    last_status_time = time.time()
    status_interval = 60  # Print status every 60 seconds
    
    while not log_path.exists():
        current_time = time.time()
        
        # Print status every minute
        if current_time - last_status_time >= status_interval:
            elapsed_minutes = int((current_time - last_status_time) / 60)
            print(f"{Fore.YELLOW}[{elapsed_minutes}m] Still waiting for {log_path.name}...{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Tip: Enable encounter logging in ESO or use the Easy Stalking addon{Style.RESET_ALL}")
            last_status_time = current_time
        
        time.sleep(1)
    
    print(f"{Fore.GREEN}{log_path.name} found! Starting monitoring...{Style.RESET_ALL}")
    return True

def _find_eso_log_file_windows(diagnostic: bool = False) -> Optional[Path]:
    """Enhanced Windows-specific ESO log file detection with comprehensive search."""
    
    # Windows-specific search locations
    search_locations = [
        Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs",
        Path.home() / "OneDrive" / "Documents" / "Elder Scrolls Online" / "live" / "Logs",
    ]
    
    found_directories = []
    found_encounter_logs = []
    
    if diagnostic:
        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
        print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Searching Windows locations for ESO log directories{Style.RESET_ALL}")
    
    # Check each directory
    for directory in search_locations:
        if directory.exists():
            found_directories.append(directory)
            encounter_log = directory / "Encounter.log"
            
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Found directory: {directory}{Style.RESET_ALL}")
            
            # Check for Encounter.log in this directory
            if encounter_log.exists():
                try:
                    # Get file modification time
                    mod_time = encounter_log.stat().st_mtime
                    mod_datetime = datetime.fromtimestamp(mod_time)
                    mod_time_str = mod_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    
                    found_encounter_logs.append({
                        'path': encounter_log,
                        'directory': directory,
                        'mod_time': mod_time,
                        'mod_time_str': mod_time_str
                    })
                    
                    print(f"{Fore.GREEN}Encounter.log found: {encounter_log}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}Last modified: {mod_time_str} (local time){Style.RESET_ALL}")
                    
                except OSError as e:
                    if diagnostic:
                        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                        print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Error accessing {encounter_log}: {e}{Style.RESET_ALL}")
            else:
                if diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: No Encounter.log in {directory}{Style.RESET_ALL}")
        else:
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Directory not found: {directory}{Style.RESET_ALL}")
    
    # If no directories found, exit with summary
    if not found_directories:
        print(f"{Fore.YELLOW}No ESO log directories found on Windows.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Searched locations:{Style.RESET_ALL}")
        for location in search_locations:
            print(f"{Fore.WHITE}  - {location}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Please ensure ESO is installed and encounter logging is enabled.{Style.RESET_ALL}")
        return None
    
    # Print found directories
    print(f"{Fore.GREEN}Found {len(found_directories)} ESO log directory(ies):{Style.RESET_ALL}")
    for directory in found_directories:
        print(f"{Fore.WHITE}  - {directory}{Style.RESET_ALL}")
        
        # Find most recently updated file in directory
        try:
            most_recent_file = None
            most_recent_time = 0
            
            for file_path in directory.iterdir():
                if file_path.is_file():
                    try:
                        file_time = file_path.stat().st_mtime
                        if file_time > most_recent_time:
                            most_recent_time = file_time
                            most_recent_file = file_path
                    except OSError:
                        continue
            
            if most_recent_file:
                mod_datetime = datetime.fromtimestamp(most_recent_time)
                mod_time_str = mod_datetime.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{Fore.CYAN}    Most recent file: {most_recent_file.name} ({mod_time_str}){Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}    Directory is empty{Style.RESET_ALL}")
                
        except OSError as e:
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Error scanning {directory}: {e}{Style.RESET_ALL}")
    
    # If Encounter.log files found, pick the most recent one
    if found_encounter_logs:
        # Sort by modification time (most recent first)
        found_encounter_logs.sort(key=lambda x: x['mod_time'], reverse=True)
        
        most_recent_log = found_encounter_logs[0]
        
        if len(found_encounter_logs) > 1:
            print(f"{Fore.GREEN}Selected most recently updated Encounter.log:{Style.RESET_ALL}")
            print(f"{Fore.WHITE}  {most_recent_log['path']}{Style.RESET_ALL}")
            print(f"{Fore.WHITE}  Last modified: {most_recent_log['mod_time_str']}{Style.RESET_ALL}")
        
        return most_recent_log['path']
    
    # If directories found but no Encounter.log files, pick the directory with most recent activity
    if found_directories:
        best_directory = None
        best_time = 0
        
        for directory in found_directories:
            try:
                # Check directory modification time
                dir_time = directory.stat().st_mtime
                
                # Also check for most recent file in directory
                most_recent_file_time = 0
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        try:
                            file_time = file_path.stat().st_mtime
                            most_recent_file_time = max(most_recent_file_time, file_time)
                        except OSError:
                            continue
                
                # Use the more recent of directory time or most recent file time
                effective_time = max(dir_time, most_recent_file_time)
                
                if effective_time > best_time:
                    best_time = effective_time
                    best_directory = directory
                    
            except OSError:
                continue
        
        if best_directory:
            print(f"{Fore.YELLOW}No Encounter.log files found, but will monitor:{Style.RESET_ALL}")
            print(f"{Fore.WHITE}  {best_directory / 'Encounter.log'}{Style.RESET_ALL}")
            return best_directory / "Encounter.log"
    
    return None

def _find_eso_log_file(diagnostic: bool = False) -> Optional[Path]:
    """Try to find the ESO encounter log file in common locations with enhanced detection."""
    
    # Use Windows-specific detection for Windows
    if sys.platform == "win32":
        return _find_eso_log_file_windows(diagnostic)
    
    # Enhanced ESO log file locations with more comprehensive coverage for other platforms
    possible_paths = []
    
    if sys.platform == "darwin":
        # macOS - native and Wine installations
        possible_paths = [
            # Native macOS installations
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / "Documents" / "Elder Scrolls Online" / "Logs" / "Encounter.log",
            # Wine installations
            Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "users" / os.getenv("USER", "user") / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            # Alternative Wine paths
            Path.home() / ".wine" / "drive_c" / "Program Files" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
        ]
    else:
        # Linux - Wine and native installations
        possible_paths = [
            # Wine installations (most common on Linux)
            Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "users" / os.getenv("USER", "user") / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            # Alternative Wine paths
            Path.home() / ".wine" / "drive_c" / "Program Files" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "Program Files (x86)" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
            # Native Linux installations (if any)
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / "Documents" / "Elder Scrolls Online" / "Logs" / "Encounter.log",
            # Steam Deck/SteamOS paths
            Path.home() / ".steam" / "steam" / "steamapps" / "compatdata" / "306130" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
        ]

    # Show diagnostic information if requested
    if diagnostic:
        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
        print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Searching for Encounter.log in {len(possible_paths)} locations{Style.RESET_ALL}")
        for i, path in enumerate(possible_paths, 1):
            status = "✓ EXISTS" if path.exists() else "✗ not found"
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: {i:2d}. {path} - {status}{Style.RESET_ALL}")

    # Search for existing files
    found_paths = []
    for path in possible_paths:
        if path.exists():
            found_paths.append(path)
    
    # Return the first found path, or None if none found
    if found_paths:
        if diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Found {len(found_paths)} log file(s), using: {found_paths[0]}{Style.RESET_ALL}")
        return found_paths[0]
    
    return None

def _provide_log_file_guidance() -> None:
    """Provide helpful guidance when no ESO log file is found."""
    host_type = _get_host_type_description()
    
    print(f"{Fore.YELLOW}No ESO Encounter.log file found on {host_type}.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Here's how to enable encounter logging in ESO:{Style.RESET_ALL}")
    print()
    
    if sys.platform == "win32":
        print(f"{Fore.WHITE}1. Open ESO and go to Settings > Combat > Combat Logging{Style.RESET_ALL}")
        print(f"{Fore.WHITE}2. Enable 'Combat Logging' and 'Combat Logging to File'{Style.RESET_ALL}")
        print(f"{Fore.WHITE}3. The log file should appear at:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   %USERPROFILE%\\Documents\\Elder Scrolls Online\\live\\Logs\\Encounter.log{Style.RESET_ALL}")
    elif sys.platform == "darwin":
        print(f"{Fore.WHITE}1. Open ESO and go to Settings > Combat > Combat Logging{Style.RESET_ALL}")
        print(f"{Fore.WHITE}2. Enable 'Combat Logging' and 'Combat Logging to File'{Style.RESET_ALL}")
        print(f"{Fore.WHITE}3. The log file should appear at:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   ~/Documents/Elder Scrolls Online/live/Logs/Encounter.log{Style.RESET_ALL}")
        print(f"{Fore.WHITE}   or (if using Wine):{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   ~/.wine/drive_c/users/Public/Documents/Elder Scrolls Online/live/Logs/Encounter.log{Style.RESET_ALL}")
    else:
        print(f"{Fore.WHITE}1. Open ESO and go to Settings > Combat > Combat Logging{Style.RESET_ALL}")
        print(f"{Fore.WHITE}2. Enable 'Combat Logging' and 'Combat Logging to File'{Style.RESET_ALL}")
        print(f"{Fore.WHITE}3. The log file should appear at:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   ~/.wine/drive_c/users/Public/Documents/Elder Scrolls Online/live/Logs/Encounter.log{Style.RESET_ALL}")
        print(f"{Fore.WHITE}   or (if using Steam Deck):{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   ~/.steam/steam/steamapps/compatdata/306130/pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/Logs/Encounter.log{Style.RESET_ALL}")
    
    print()
    print(f"{Fore.CYAN}Alternative: Specify the log file path manually:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}  python3 src/esolog_tail.py --log-file /path/to/your/Encounter.log{Style.RESET_ALL}")
    print()
    print(f"{Fore.CYAN}Tip: You can also use --no-wait to exit immediately if the file doesn't exist.{Style.RESET_ALL}")

def _get_most_likely_log_directory() -> Path:
    """Get the most likely ESO log directory based on the host OS."""
    if sys.platform == "win32":
        # Windows - most common location
        return Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs"
    elif sys.platform == "darwin":
        # macOS - try native first, then Wine
        native_path = Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs"
        wine_path = Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs"
        if native_path.exists():
            return native_path
        else:
            return wine_path
    else:
        # Linux - Wine is most likely
        return Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs"

def _get_host_type_description() -> str:
    """Get a user-friendly description of the host OS."""
    if sys.platform == "win32":
        return "Windows"
    elif sys.platform == "darwin":
        return "macOS"
    elif sys.platform.startswith("linux"):
        return "Linux"
    else:
        return "Unknown"

def _handle_replay_log_splitting(log_splitter, entry, line: str):
    """Handle log splitting logic for replay mode."""
    # Handle BEGIN_LOG - start new encounter
    if entry.event_type == "BEGIN_LOG":
        # Start encounter without zone info - will wait for first zone
        log_splitter.start_encounter(entry)
        # Write the BEGIN_LOG line
        log_splitter.write_log_line(line)
    
    # Handle ZONE_CHANGED - track current zone
    elif entry.event_type == "ZONE_CHANGED":
        # Extract zone name and difficulty from ZONE_CHANGED
        # Format: ZONE_CHANGED,zone_id,"Zone Name",difficulty
        if len(entry.fields) >= 2:
            zone_name = entry.fields[0].strip('"') if entry.fields[0] else ""
            difficulty = entry.fields[1].strip('"') if len(entry.fields) > 1 else ""
            
            # Update current zone tracking
            log_splitter.handle_zone_change(zone_name, difficulty)
            
            # Write the ZONE_CHANGED line
            log_splitter.write_log_line(line)
    
    # Handle BEGIN_COMBAT - rename file to current zone
    elif entry.event_type == "BEGIN_COMBAT":
        log_splitter.start_combat()
        # Write the BEGIN_COMBAT line
        log_splitter.write_log_line(line)
    
    # Handle END_LOG - end current encounter
    elif entry.event_type == "END_LOG":
        if log_splitter.pending_begin_log or log_splitter.current_split_file:
            log_splitter.write_log_line(line)
            log_splitter.end_encounter()
            if log_splitter.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                print(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG detected, closing split file{Style.RESET_ALL}")
    
    # Write all other lines to current split file
    else:
        log_splitter.write_log_line(line)

def _replay_log_file(analyzer: ESOLogAnalyzer, log_file: Path, speed_multiplier: int, tail_and_split: bool = False, split_dir: Optional[Path] = None):
    """Replay a log file for testing purposes."""

    print(f"{Fore.YELLOW}Reading log file...{Style.RESET_ALL}")

    # Initialize log splitter if needed
    log_splitter = LogSplitter(log_file, diagnostic=analyzer.diagnostic, split_dir=split_dir) if tail_and_split else None

    entries = []
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                print(f"{Fore.YELLOW}Processed {line_num} lines...{Style.RESET_ALL}")

            line = line.strip()
            if line:
                entry = ESOLogEntry.parse(line)
                if entry:
                    entries.append(entry)
                    
                    # Handle log splitting if enabled
                    if log_splitter:
                        _handle_replay_log_splitting(log_splitter, entry, line)

    print(f"{Fore.GREEN}Loaded {len(entries)} log entries{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Starting replay at full speed...{Style.RESET_ALL}\n")

    if not entries:
        print(f"{Fore.RED}No valid log entries found{Style.RESET_ALL}")
        return

    # Process all entries at full speed without delays
    for entry in entries:
        analyzer.process_log_entry(entry)

    # Final check to ensure any remaining encounters are displayed
    analyzer._check_pending_encounter_display()

    print(f"\n{Fore.GREEN}Replay complete!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()