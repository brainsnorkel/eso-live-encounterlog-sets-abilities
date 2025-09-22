#!/usr/bin/env python3
"""
ESO Encounter Log Analyzer
A CLI tool that continuously monitors ESO encounter logs and analyzes combat encounters.
"""

import os
import sys
import time
import csv
import io
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set
import click
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
from colorama import init, Fore, Style
from gear_set_database import gear_set_db

# Initialize colorama for cross-platform colored output
init()

# Import our ESO analysis modules
from eso_sets import ESOSubclassAnalyzer, ESOSetDatabase

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

            timestamp = int(fields[0])
            event_type = fields[1]

            return cls(timestamp, event_type, fields[2:], line)
        except (ValueError, IndexError, StopIteration):
            return None

class PlayerInfo:
    """Stores information about a player character."""

    def __init__(self, unit_id: str, name: str, handle: str):
        self.unit_id = unit_id  # Short unit ID from UNIT_ADDED
        self.name = name
        self.handle = handle
        self.equipped_abilities: Set[str] = set()  # All abilities from PLAYER_INFO
        self.front_bar_abilities: List[str] = []  # Front bar abilities in order
        self.back_bar_abilities: List[str] = []  # Back bar abilities in order
        self.gear: Dict[str, List[str]] = {}  # gear_slot -> [item_id, trait, quality, enchant_value, enchant_type, ...]
        self.last_seen = 0
        self.long_unit_ids: Set[str] = set()  # Track long unit IDs used in combat events
        
        # Resource tracking
        self.health_current: int = 0
        self.health_max: int = 0
        self.magicka_current: int = 0
        self.magicka_max: int = 0
        self.stamina_current: int = 0
        self.stamina_max: int = 0


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

    def set_resources(self, health_curr: int, health_max: int, magicka_curr: int, magicka_max: int, stamina_curr: int, stamina_max: int):
        """Set the player's resource values."""
        self.health_current = health_curr
        self.health_max = health_max
        self.magicka_current = magicka_curr
        self.magicka_max = magicka_max
        self.stamina_current = stamina_curr
        self.stamina_max = stamina_max

    def get_highest_resource(self) -> Tuple[str, int]:
        """Get the highest resource type and its maximum value."""
        resources = {
            'Health': self.health_max,
            'Magicka': self.magicka_max,
            'Stamina': self.stamina_max
        }
        highest_resource = max(resources.items(), key=lambda x: x[1])
        return highest_resource

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
        self.player_deaths: int = 0  # Track player deaths
        self.in_combat = False
        self.finalized = False  # Track if encounter has been finalized (ended)
        
        # Buff tracking
        self.player_buffs: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))  # player_id -> buff_name -> [(start_time, end_time)]
        self.active_buffs: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # player_id -> buff_name -> start_time

    def add_player(self, unit_id: str, name: str, handle: str):
        """Add a player to this encounter."""
        self.players[unit_id] = PlayerInfo(unit_id, name, handle)

    def add_enemy(self, unit_id: str, name: str, unit_type: str):
        """Add an enemy to this encounter."""
        self.enemies[unit_id] = EnemyInfo(unit_id, name, unit_type)

    def _is_valid_enemy(self, enemy_name: str) -> bool:
        """Check if an enemy name represents a valid combat target."""
        # Exclude pet/corpse names, environmental hazards, and other non-combat entities
        excluded_names = {
            # Player pets and summons
            'necromantic corpse', 'skeletal mage', 'skeletal archer', 'skeletal warrior',
            'atronach', 'clannfear', 'daedroth', 'scamp', 'winged twilight',
            'storm atronach', 'flame atronach', 'frost atronach', 'flesh atronach',
            'bone colossus', 'goliath', 'skeletal dragon', 'bone goliath',
            'corpse', 'skeleton', 'bone', 'golem', 'familiar', 'pet',
            
            # Environmental hazards and mechanics
            'water', 'fire', 'lava', 'poison', 'ice', 'lightning', 'void',
            'trap', 'spike', 'flame', 'steam', 'gas', 'cloud', 'mist',
            'beam', 'laser', 'ray', 'orb', 'crystal', 'shard', 'fragment',
            'portal', 'gate', 'door', 'barrier', 'wall', 'shield',
            
            # Generic environmental terms
            'element', 'energy', 'force', 'field', 'aura', 'zone', 'area',
            'mechanism', 'device', 'construct', 'apparatus'
        }
        
        enemy_name_lower = enemy_name.lower()
        return not any(excluded_name in enemy_name_lower for excluded_name in excluded_names)

    def get_highest_health_enemy(self) -> Optional[EnemyInfo]:
        """Get the enemy with the highest health, excluding pets, corpses, and environmental hazards."""
        if not self.enemies:
            return None
        
        max_health = 0
        highest_health_enemy = None
        
        for enemy in self.enemies.values():
            # Skip if not a valid enemy target
            if not self._is_valid_enemy(enemy.name):
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
                if not self._is_valid_enemy(enemy.name):
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
        """Add damage to a specific player's total (including pets)."""
        # Find the player this unit belongs to
        player = self.find_player_by_unit_id(unit_id)
        if player:
            if player.unit_id not in self.player_damage:
                self.player_damage[player.unit_id] = 0
            self.player_damage[player.unit_id] += damage
        else:
            # If it's a pet (unit IDs 1-50), try to find the closest player
            # For now, we'll distribute pet damage evenly among all players
            if unit_id.isdigit() and 1 <= int(unit_id) <= 50 and self.players:
                # Distribute pet damage among all players (simple approach)
                damage_per_player = damage // len(self.players)
                for player_id in self.players.keys():
                    if player_id not in self.player_damage:
                        self.player_damage[player_id] = 0
                    self.player_damage[player_id] += damage_per_player

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

    def __init__(self):
        self.current_encounter: Optional[CombatEncounter] = None
        self.ability_cache: Dict[str, str] = {}  # ability_id -> ability_name
        self.gear_cache: Dict[str, str] = {}  # gear_item_id -> gear_set_name
        self.current_zone: Optional[str] = None  # Track current zone name
        self.zone_deaths: int = 0  # Track total deaths since entering current zone
        self.subclass_analyzer = ESOSubclassAnalyzer()
        self.set_database = ESOSetDatabase()
        self.current_log_file: Optional[str] = None  # Track current log file path
        self.log_start_unix_timestamp: Optional[int] = None  # Unix timestamp from BEGIN_LOG event
        
        # Group buff ability IDs - updated with correct IDs from user
        self.major_courage_ids = {
            '61665',  # Major Courage - Increases Weapon and Spell Damage by 430
        }
        
        # Group buff IDs for tracking in encounters with 3+ players
        self.group_buff_ids = {
            'Major Courage': self.major_courage_ids,
            'Major Force': {'40225'},  # Increases Critical Damage by 20%
            'Major Slayer': {'93120'},  # Increases damage done to Dungeon, Trial, and Arena monsters by 10%
        }
        
        # Initialize the robust log parser
        from eso_log_parser import ESOLogParser
        self.log_parser = ESOLogParser()
        
        # Initialize gear set mapping database
        self._initialize_gear_database()

    def _initialize_gear_database(self):
        """Initialize gear item ID to gear set name mapping."""
        # Use the gear set database instead of hardcoded data
        self.gear_cache = gear_set_db.item_to_set
        self.gear_set_abilities = gear_set_db.ability_to_set

    def process_log_entry(self, entry: ESOLogEntry):
        """Process a single log entry."""
        if entry.event_type == "UNIT_ADDED":
            self._handle_unit_added(entry)
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


    def _handle_unit_added(self, entry: ESOLogEntry):
        """Handle UNIT_ADDED events to track players and enemies."""
        # UNIT_ADDED format: timestamp,UNIT_ADDED,unit_id,unit_type,F/T,unknown,unknown,F/T,unknown,unknown,"name","@handle",...
        if len(entry.fields) >= 10:
            unit_id = entry.fields[0]
            unit_type = entry.fields[1]
            
            # Handle player units
            if unit_type == "PLAYER":
                name = entry.fields[8] if len(entry.fields) > 8 else ""
                handle = entry.fields[9] if len(entry.fields) > 9 else ""

                # Only add players if we have a current encounter (zone has been set)
                if self.current_encounter:
                    # Clean up name and handle (remove quotes if present)
                    clean_name = name.strip('"') if name else ""
                    clean_handle = handle.strip('"') if handle else ""

                    self.current_encounter.add_player(unit_id, clean_name, clean_handle)
            
            # Handle enemy units (MONSTER, NPC, etc.)
            elif unit_type in ["MONSTER", "NPC"]:
                name = entry.fields[8] if len(entry.fields) > 8 else ""
                health = 0
                
                # Extract health from field [4] if available (105634 in the raw line)
                if len(entry.fields) > 4 and entry.fields[4].isdigit():
                    health = int(entry.fields[4])
                
                # Only add enemies if we have a current encounter and valid name
                if self.current_encounter and name and name != '0':
                    clean_name = name.strip('"') if name else ""
                    
                    enemy = EnemyInfo(unit_id, clean_name, unit_type)
                    enemy.max_health = health
                    enemy.current_health = health
                    
                    self.current_encounter.enemies[unit_id] = enemy

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
                
                # Parse and set resource data
                if len(player_info.additional_data) >= 6:
                    try:
                        # ESO resource format: [health_curr, health_max, magicka_curr, magicka_max, stamina_curr, stamina_max]
                        health_curr = int(player_info.additional_data[0])
                        health_max = int(player_info.additional_data[1])
                        magicka_curr = int(player_info.additional_data[2])
                        magicka_max = int(player_info.additional_data[3])
                        stamina_curr = int(player_info.additional_data[4])
                        stamina_max = int(player_info.additional_data[5])
                        
                        player.set_resources(health_curr, health_max, magicka_curr, magicka_max, stamina_curr, stamina_max)
                    except (ValueError, IndexError):
                        pass  # Skip invalid resource data

    def _handle_zone_changed(self, entry: ESOLogEntry):
        """Handle ZONE_CHANGED events to reset all known players."""
        # ZONE_CHANGED format: zone_id, zone_name, difficulty
        if len(entry.fields) >= 3:
            zone_id = entry.fields[0]
            zone_name = entry.fields[1].strip('"')
            difficulty = entry.fields[2].strip('"')
            
            # Store previous zone name before updating
            previous_zone = self.current_zone if self.current_zone else "Unknown"
            
            print(f"\n{Fore.YELLOW}=== ZONE CHANGED ==={Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Zone: {zone_name} ({difficulty}){Style.RESET_ALL}")
            
            # End current encounter if active but don't display results on zone change
            # The previous zone's combat should have ended naturally, not forced by zone change
            if self.current_encounter and self.current_encounter.players:
                # Just reset the encounter without displaying results
                self.current_encounter = None
            
            # Update current zone after processing previous zone's combat
            self.current_zone = zone_name
            
            # Reset death counter for new zone
            self.zone_deaths = 0
            
            # Reset all tracking - create new encounter for this zone
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

    def _handle_begin_combat_event(self, entry: ESOLogEntry):
        """Handle BEGIN_COMBAT events to start combat tracking."""
        # BEGIN_COMBAT format: timestamp,BEGIN_COMBAT (no additional data)
        
        # Ensure we have an encounter to work with
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
        
        # Mark combat as active and ALWAYS set start time to BEGIN_COMBAT timestamp
        # This takes priority over any previous start time from BEGIN_CAST events
        self.current_encounter.in_combat = True
        self.current_encounter.start_time = entry.timestamp

    def _handle_end_combat_event(self, entry: ESOLogEntry):
        """Handle END_COMBAT events to print player reports."""
        # END_COMBAT format: timestamp,END_COMBAT (no additional data)
        
        # Show combat reports if there are any players
        if self.current_encounter and self.current_encounter.players:
            # End current encounter if active and display results
            if self.current_encounter.players:
                self.current_encounter.end_time = entry.timestamp
                # Finalize buff tracking before displaying summary
                self.current_encounter.finalize_buff_tracking()
                self._display_encounter_summary(self.current_zone)
        
        # Reset combat tracking but keep players for next encounter
        if self.current_encounter:
            self.current_encounter.in_combat = False
            self.current_encounter.finalized = True

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

        # BEGIN_CAST format: 0, F/T, unit_id, ability_id, target_unit_id, health/health, magicka/magicka, ...
        if len(entry.fields) >= 4:
            caster_unit_id = entry.fields[2]  # This is the long unit ID
            ability_id = entry.fields[3]

            if ability_id in self.ability_cache:
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(caster_unit_id, ability_name)

    def _handle_combat_event(self, entry: ESOLogEntry):
        """Handle COMBAT_EVENT events."""
        
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

        if not self.current_encounter.in_combat:
            self.current_encounter.in_combat = True
            self.current_encounter.start_time = entry.timestamp

        # Track damage events for DPS calculation (only friendly damage)
        # COMBAT_EVENT format: timestamp,COMBAT_EVENT,event_type,damage_type,source_unit_id,damage_value,...
        if len(entry.fields) >= 4:
            event_type = entry.fields[0]  # DAMAGE/CRITICAL_DAMAGE is at index 0
            
            # Track death events
            if event_type == 'DIED_XP':
                # Check if it's a player death by looking up the dying unit ID in known players
                # DIED_XP format: timestamp,COMBAT_EVENT,DIED_XP,damage_type,source_unit_id,...,dying_unit_id,...
                dying_unit_id = entry.fields[9] if len(entry.fields) > 9 else ""
                if (self.current_encounter and 
                    self.current_encounter.find_player_by_unit_id(dying_unit_id)):
                    self.zone_deaths += 1
            
            # Track damage events
            elif event_type in ['DAMAGE', 'CRITICAL_DAMAGE']:
                try:
                    source_unit_id = entry.fields[2]  # Source unit ID is at index 2
                    damage_value = int(entry.fields[3])  # Damage value is at index 3
                    target_unit_id = entry.fields[4] if len(entry.fields) > 4 else ""  # Target unit ID is at index 4
                    
                    # Count damage from friendly players and their pets (only if we have an encounter)
                    if damage_value > 0 and self.current_encounter:
                        # Check if it's a player or pet (unit IDs 1-50 are typically friendly)
                        if (self.current_encounter.find_player_by_unit_id(source_unit_id) or 
                            (source_unit_id.isdigit() and 1 <= int(source_unit_id) <= 50)):
                            self.current_encounter.total_damage += damage_value
                            # Track damage per player
                            self.current_encounter.add_damage_to_player(source_unit_id, damage_value)
                            
                            # Track damage dealt to enemies
                            if target_unit_id and target_unit_id in self.current_encounter.enemies:
                                if target_unit_id not in self.current_encounter.enemy_damage:
                                    self.current_encounter.enemy_damage[target_unit_id] = 0
                                self.current_encounter.enemy_damage[target_unit_id] += damage_value
                except (ValueError, IndexError):
                    pass  # Skip invalid damage values

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

            # Track group buffs
            for buff_name, buff_ids in self.group_buff_ids.items():
                if ability_id in buff_ids and target_unit_id in self.current_encounter.players:
                    self.current_encounter.track_buff(target_unit_id, buff_name, effect_type, entry.timestamp)

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

        duration = (self.current_encounter.end_time - self.current_encounter.start_time) / 1000.0
        players_count = len(self.current_encounter.players)
        
        # Calculate estimated group DPS
        estimated_dps = 0
        if duration > 0 and self.current_encounter.total_damage > 0:
            estimated_dps = self.current_encounter.total_damage / duration

        # Get enemy for display (primary target)
        # First try most damaged enemy, fallback to highest health enemy
        most_damaged_enemy = self.current_encounter.get_most_damaged_enemy()
        enemy_info = ""
        if most_damaged_enemy:
            enemy_info = f" | Target: {most_damaged_enemy.name}"
        else:
            # Fallback to highest health enemy if no damage tracking available
            highest_health_enemy = self.current_encounter.get_highest_health_enemy()
            if highest_health_enemy:
                enemy_info = f" | Target: {highest_health_enemy.name}"

        # Death counter (total deaths since entering zone)
        deaths_info = ""
        if self.zone_deaths > 0:
            deaths_info = f" | Deaths: {self.zone_deaths}"

        # Get formatted combat start time
        combat_start_time = self.current_encounter.get_combat_start_time_formatted(self.current_log_file, self.log_start_unix_timestamp)
        
        # Update the combat ended header with start time, duration, players info, DPS, deaths, and enemy info
        if zone_name:
            if estimated_dps > 0:
                print(f"{Fore.RED}{combat_start_time} ({zone_name}) | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{enemy_info}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}{combat_start_time} ({zone_name}) | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{enemy_info}{Style.RESET_ALL}")
        else:
            if estimated_dps > 0:
                print(f"{Fore.RED}{combat_start_time} | Duration: {duration:.1f}s | Players: {players_count} | Est. DPS: {estimated_dps:,.0f}{deaths_info}{enemy_info}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}{combat_start_time} | Duration: {duration:.1f}s | Players: {players_count}{deaths_info}{enemy_info}{Style.RESET_ALL}")
        
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
            print(f"{Fore.CYAN}Group Buffs: {' | '.join(buff_status)}{Style.RESET_ALL}")
        # Sort players by damage contribution (descending)
        players_with_damage = []
        for player in self.current_encounter.players.values():
            player_damage = self.current_encounter.player_damage.get(player.unit_id, 0)
            damage_percentage = (player_damage / self.current_encounter.total_damage * 100) if self.current_encounter.total_damage > 0 else 0
            players_with_damage.append((player, player_damage, damage_percentage))
        
        # Sort by damage (descending)
        players_with_damage.sort(key=lambda x: x[1], reverse=True)
        
        for player, player_damage, damage_percentage in players_with_damage:
            # Use equipped abilities from PLAYER_INFO
            abilities_to_analyze = player.equipped_abilities
            
            # Analyze subclass and build first to create the title line
            analysis = None
            if abilities_to_analyze:
                analysis = self.subclass_analyzer.analyze_subclass(abilities_to_analyze)
            
            # Create the title line: @playername {character_name} skill_lines dominant_resource ({damage_percentage:.1f}%)
            title_parts = [player.get_display_name()]
            
            # Add character name if available and different from handle
            character_name = player.name if player.name and player.name not in ['""', '', '0'] else ""
            if character_name and character_name != player.get_display_name():
                title_parts.append(character_name)
            
            if analysis and analysis['confidence'] > 0.1:
                if analysis['skill_lines']:
                    # Use skill line aliases if available, otherwise extract first word
                    skill_line_aliases = []
                    for skill_line in analysis['skill_lines']:
                        # Check if we have an alias for this skill line (partial matching)
                        alias_found = False
                        for alias_key, alias_value in self.subclass_analyzer.SKILL_LINE_ALIASES.items():
                            if alias_key in skill_line:
                                skill_line_aliases.append(alias_value)
                                alias_found = True
                                break
                        
                        if not alias_found:
                            # Fall back to first word
                            skill_line_aliases.append(skill_line.split()[0])
                    # Sort skill line aliases before joining
                    skill_line_aliases.sort()
                    skill_lines_str = '/'.join(skill_line_aliases)
                    title_parts.append(skill_lines_str)
                else:
                    title_parts.append("unknown")
            else:
                title_parts.append("unknown")
            
            # Add dominant resource between skill lines and damage percentage
            if player.health_max > 0 or player.magicka_max > 0 or player.stamina_max > 0:
                highest_resource_name, highest_resource_value = player.get_highest_resource()
                # Convert to short form: Magicka -> Mag, Stamina -> Stam, Health -> Health
                if highest_resource_name == "Magicka":
                    resource_short = "Mag"
                elif highest_resource_name == "Stamina":
                    resource_short = "Stam"
                else:
                    resource_short = "Health"
                title_parts.append(resource_short)
            
            # Add damage percentage
            title_parts.append(f"({damage_percentage:.1f}%)")
            
            print(f"{Fore.GREEN}{' '.join(title_parts)}{Style.RESET_ALL}")
            
            if abilities_to_analyze:
                # Show front and back bar abilities in order if available
                if player.front_bar_abilities or player.back_bar_abilities:
                    if player.front_bar_abilities:
                        print(f"  Bar 1: {', '.join(player.front_bar_abilities)}")
                    if player.back_bar_abilities:
                        print(f"  Bar 2: {', '.join(player.back_bar_abilities)}")
                else:
                    abilities_list = sorted(list(abilities_to_analyze))[:10]  # Show top 10 abilities
                    print(f"  Equipped: {', '.join(abilities_list)}")
                    if len(abilities_to_analyze) > 10:
                        print(f"  ... and {len(abilities_to_analyze) - 10} more")


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
                    # Count gear pieces by set ID
                    set_counts = {}
                    for slot, gear_item in player.gear.items():
                        if len(gear_item) > 6:  # Make sure we have enough elements
                            set_id = str(gear_item[6])  # Set ID is at position 6
                            set_counts[set_id] = set_counts.get(set_id, 0) + 1
                    
                    # Format equipment summary
                    for set_id, count in set_counts.items():
                        set_name = gear_set_db.get_set_name_by_set_id(set_id)
                        if set_name:
                            if count >= 5:
                                equipment_parts.append(f"{count}pc {set_name}")
                            elif count >= 2:
                                equipment_parts.append(f"{count}pc {set_name}")
                            else:
                                equipment_parts.append(f"{count}pc {set_name}")
                        else:
                            # Handle unknown sets
                            if count >= 5:
                                equipment_parts.append(f"{count}pc Unknown Set ({set_id})")
                            elif count >= 2:
                                equipment_parts.append(f"{count}pc Unknown Set ({set_id})")
                            else:
                                equipment_parts.append(f"{count}pc Unknown Set ({set_id})")
                
                # Add inferred sets
                if all_identified_sets:
                    high_confidence_sets = [s for s in all_identified_sets if s['confidence'] > 0.5]
                    for set_info in high_confidence_sets:
                        if set_info['name'] not in [part.split('pc ')[1] for part in equipment_parts]:
                            equipment_parts.append(f"?pc {set_info['name']} (inferred)")
                
                # Show equipment summary
                if equipment_parts:
                    print(f"  Equipment: {', '.join(equipment_parts)}")
                elif player.gear:
                    print(f"  Equipment: {len(player.gear)} items (sets unknown)")
                else:
                    print(f"  Equipment: No data")
                
                # Show Major Courage uptime
                major_courage_uptime = self.current_encounter.get_buff_uptime(player.unit_id, "Major Courage")
                if major_courage_uptime > 0:
                    print(f"  Major Courage Uptime: {major_courage_uptime:.1f}%")
            else:
                print(f"  Abilities: No PLAYER_INFO data")
                print(f"  Equipment: No data")


class LogFileHandler(FileSystemEventHandler):
    """File system event handler for monitoring log file changes."""

    def __init__(self, analyzer: ESOLogAnalyzer, log_file: Path):
        self.analyzer = analyzer
        self.log_file = log_file
        self.last_position = 0

        # Initialize position to end of file for live monitoring
        if self.log_file.exists():
            self.last_position = self.log_file.stat().st_size

    def on_modified(self, event):
        """Handle file modification events."""
        if event.src_path == str(self.log_file):
            self._process_new_lines()

    def _process_new_lines(self):
        """Process new lines added to the log file."""
        if not self.log_file.exists():
            return

        current_size = self.log_file.stat().st_size
        if current_size <= self.last_position:
            return

        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            self.last_position = f.tell()

        for line in new_lines:
            line = line.strip()
            if line:
                entry = ESOLogEntry.parse(line)
                if entry:
                    self.analyzer.process_log_entry(entry)

@click.command()
@click.option('--log-file', '-f', type=click.Path(exists=True),
              help='Path to ESO encounter log file')
@click.option('--test-mode', '-t', is_flag=True,
              help='Test mode: replay the sample log file')
@click.option('--replay-speed', '-s', default=100, type=int,
              help='Replay speed multiplier for test mode (default: 100x)')
def main(log_file: Optional[str], test_mode: bool, replay_speed: int):
    """ESO Encounter Log Analyzer - Monitor and analyze ESO combat encounters."""

    print(f"{Fore.CYAN}ESO Encounter Log Analyzer{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Monitoring ESO encounter logs for combat analysis...{Style.RESET_ALL}\n")

    analyzer = ESOLogAnalyzer()

    if test_mode:
        # Use the example log file for testing
        test_log = Path("example-log/Encounter.log")
        if not test_log.exists():
            print(f"{Fore.RED}Error: Test log file not found: {test_log}{Style.RESET_ALL}")
            sys.exit(1)

        print(f"{Fore.YELLOW}Test mode: Replaying {test_log} at {replay_speed}x speed{Style.RESET_ALL}")
        analyzer.current_log_file = str(test_log)
        _replay_log_file(analyzer, test_log, replay_speed)
        return

    # Determine log file path
    if log_file:
        log_path = Path(log_file)
    else:
        # Try to find ESO log file in common locations
        log_path = _find_eso_log_file()
        if not log_path:
            print(f"{Fore.RED}Error: Could not find ESO encounter log file.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Please specify the log file path with --log-file option.{Style.RESET_ALL}")
            sys.exit(1)

    if not log_path.exists():
        print(f"{Fore.RED}Error: Log file does not exist: {log_path}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}Monitoring: {log_path}{Style.RESET_ALL}")

    # Set the current log file path for timestamp calculations
    analyzer.current_log_file = str(log_path)

    # Set up file monitoring
    event_handler = LogFileHandler(analyzer, log_path)
    observer = Observer()
    observer.schedule(event_handler, str(log_path.parent), recursive=False)
    observer.start()

    try:
        print(f"{Fore.YELLOW}Press Ctrl+C to stop monitoring{Style.RESET_ALL}\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopping monitor...{Style.RESET_ALL}")
        observer.stop()

    observer.join()

def _find_eso_log_file() -> Optional[Path]:
    """Try to find the ESO encounter log file in common locations."""

    # Common ESO log file locations
    if sys.platform == "win32":
        # Windows
        possible_paths = [
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / "Documents" / "Elder Scrolls Online" / "Logs" / "Encounter.log",
        ]
    else:
        # macOS and Linux (through Wine or similar)
        possible_paths = [
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
        ]

    for path in possible_paths:
        if path.exists():
            return path

    return None

def _replay_log_file(analyzer: ESOLogAnalyzer, log_file: Path, speed_multiplier: int):
    """Replay a log file for testing purposes."""

    print(f"{Fore.YELLOW}Reading log file...{Style.RESET_ALL}")

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

    print(f"{Fore.GREEN}Loaded {len(entries)} log entries{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Starting replay...{Style.RESET_ALL}\n")

    if not entries:
        print(f"{Fore.RED}No valid log entries found{Style.RESET_ALL}")
        return

    start_time = entries[0].timestamp
    real_start = time.time()

    for entry in entries:
        # Calculate when this entry should be processed
        log_elapsed = (entry.timestamp - start_time) / 1000.0  # Convert to seconds
        real_elapsed = time.time() - real_start
        target_time = log_elapsed / speed_multiplier

        # Sleep if we're ahead of schedule
        if target_time > real_elapsed:
            time.sleep(target_time - real_elapsed)

        analyzer.process_log_entry(entry)

    print(f"\n{Fore.GREEN}Replay complete!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()