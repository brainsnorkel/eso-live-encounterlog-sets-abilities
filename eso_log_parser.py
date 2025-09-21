#!/usr/bin/env python3
"""
ESO Log Parser
A robust parser for ESO encounter log files with comprehensive support for all log entry types.
"""

import re
import csv
import io
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field


@dataclass
class ESOLogEntry:
    """Represents a single log entry from the ESO encounter log."""
    timestamp: int
    event_type: str
    fields: List[str]
    original_line: str

    @classmethod
    def parse(cls, line: str) -> Optional['ESOLogEntry']:
        """Parse a single log line into an ESOLogEntry."""
        if not line or not line.strip():
            return None
            
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


@dataclass
class UnitAddedEntry:
    """Parsed UNIT_ADDED entry."""
    timestamp: int
    unit_id: str
    unit_type: str
    flags: List[str]
    name: str
    handle: str
    player_id: str
    level: int
    alliance: int


@dataclass
class AbilityInfoEntry:
    """Parsed ABILITY_INFO entry."""
    timestamp: int
    event_type: str = "ABILITY_INFO"
    ability_id: str = ""
    ability_name: str = ""
    icon_path: str = ""
    flags: List[str] = field(default_factory=list)


@dataclass
class PlayerInfoEntry:
    """Parsed PLAYER_INFO entry."""
    timestamp: int
    event_type: str = "PLAYER_INFO"
    unit_id: str = ""
    ability_ids: List[str] = field(default_factory=list)
    ability_levels: List[str] = field(default_factory=list)
    gear_data: List[List[str]] = field(default_factory=list)
    champion_points: List[str] = field(default_factory=list)
    additional_data: List[str] = field(default_factory=list)


@dataclass
class BeginCastEntry:
    """Parsed BEGIN_CAST entry."""
    timestamp: int
    unknown1: str
    unknown2: str
    caster_unit_id: str
    ability_id: str
    target_unit_id: str
    stats: List[str]


@dataclass
class EffectChangedEntry:
    """Parsed EFFECT_CHANGED entry."""
    timestamp: int
    effect_type: str  # GAINED, FADED, UPDATED
    target_unit_id: str
    source_unit_id: str
    ability_id: str
    stacks: str
    target_stats: List[str]
    additional_targets: List[List[str]]


class ESOLogParser:
    """Robust parser for ESO encounter log files."""
    
    def __init__(self):
        self.ability_cache: Dict[str, str] = {}
        
    def parse_line(self, line: str) -> Optional[ESOLogEntry]:
        """Parse a single log line."""
        # First try to parse as a generic entry
        entry = ESOLogEntry.parse(line)
        if not entry:
            return None
            
        # For specific event types, try specialized parsing
        if entry.event_type == "PLAYER_INFO":
            player_info = self.parse_player_info(entry)
            if player_info:
                return player_info
        elif entry.event_type == "ABILITY_INFO":
            ability_info = self.parse_ability_info(entry)
            if ability_info:
                return ability_info
                
        return entry
    
    def parse_unit_added(self, entry: ESOLogEntry) -> Optional[UnitAddedEntry]:
        """Parse UNIT_ADDED entry."""
        if entry.event_type != "UNIT_ADDED" or len(entry.fields) < 10:
            return None
            
        try:
            # UNIT_ADDED format: unit_id, unit_type, F/T, unknown, unknown, F/T, unknown, unknown, "name", "@handle", player_id, level, alliance, ...
            unit_id = entry.fields[0]
            unit_type = entry.fields[1]
            flags = entry.fields[2:8]
            name = entry.fields[8].strip('"') if len(entry.fields) > 8 else ""
            handle = entry.fields[9].strip('"') if len(entry.fields) > 9 else ""
            player_id = entry.fields[10] if len(entry.fields) > 10 else ""
            level = int(entry.fields[11]) if len(entry.fields) > 11 and entry.fields[11].isdigit() else 0
            alliance = int(entry.fields[12]) if len(entry.fields) > 12 and entry.fields[12].isdigit() else 0
            
            return UnitAddedEntry(
                timestamp=entry.timestamp,
                unit_id=unit_id,
                unit_type=unit_type,
                flags=flags,
                name=name,
                handle=handle,
                player_id=player_id,
                level=level,
                alliance=alliance
            )
        except (ValueError, IndexError):
            return None
    
    def parse_ability_info(self, entry: ESOLogEntry) -> Optional[AbilityInfoEntry]:
        """Parse ABILITY_INFO entry."""
        if entry.event_type != "ABILITY_INFO" or len(entry.fields) < 3:
            return None
            
        try:
            ability_id = entry.fields[0]
            ability_name = entry.fields[1].strip('"')
            icon_path = entry.fields[2].strip('"')
            flags = entry.fields[3:] if len(entry.fields) > 3 else []
            
            # Cache the ability for later use
            self.ability_cache[ability_id] = ability_name
            
            return AbilityInfoEntry(
                timestamp=entry.timestamp,
                ability_id=ability_id,
                ability_name=ability_name,
                icon_path=icon_path,
                flags=flags
            )
        except (ValueError, IndexError):
            return None
    
    def parse_player_info(self, entry: ESOLogEntry) -> Optional[PlayerInfoEntry]:
        """Parse PLAYER_INFO entry."""
        if entry.event_type != "PLAYER_INFO":
            return None
            
        # PLAYER_INFO has complex nested arrays that break CSV parsing
        # We need to parse it manually with regex
        import re
        
        # Pattern: timestamp,PLAYER_INFO,unit_id,[ability_ids],[ability_levels],[[gear_data]],champion_points,additional_data
        pattern = r'(\d+),PLAYER_INFO,(\d+),\[([^\]]+)\],\[([^\]]+)\],(\[.*\]),(\[.*\]),(\[.*\])'
        match = re.search(pattern, entry.original_line)
        
        if not match:
            return None
            
        try:
            timestamp = int(match.group(1))
            unit_id = match.group(2)
            ability_ids_str = match.group(3)
            ability_levels_str = match.group(4)
            gear_data_str = match.group(5)
            champion_points_str = match.group(6)
            additional_data_str = match.group(7)
            
            # Parse ability IDs
            ability_ids = [aid.strip() for aid in ability_ids_str.split(',') if aid.strip()]
            
            # Parse ability levels
            ability_levels = [level.strip() for level in ability_levels_str.split(',') if level.strip()]
            
            # Parse gear data (complex nested arrays)
            gear_data = self._parse_gear_data(gear_data_str)
            
            # Parse champion points
            champion_points = [cp.strip() for cp in champion_points_str.strip('[]').split(',') if cp.strip()]
            
            # Parse additional data
            additional_data = [data.strip() for data in additional_data_str.strip('[]').split(',') if data.strip()]
            
            return PlayerInfoEntry(
                timestamp=timestamp,
                unit_id=unit_id,
                ability_ids=ability_ids,
                ability_levels=ability_levels,
                gear_data=gear_data,
                champion_points=champion_points,
                additional_data=additional_data
            )
        except (ValueError, IndexError):
            return None
    
    def _parse_gear_data(self, gear_data_str: str) -> List[List[str]]:
        """Parse the complex gear data array."""
        # Gear data format: [[slot,item_id,flags...],[slot,item_id,flags...],...]
        gear_items = []
        
        # Remove outer brackets
        gear_data_str = gear_data_str.strip('[]')
        
        # Split on ],[ to separate gear items, but be careful about the first and last items
        # First, remove the leading [ from the first item and trailing ] from the last item
        if gear_data_str.startswith('['):
            gear_data_str = gear_data_str[1:]
        if gear_data_str.endswith(']'):
            gear_data_str = gear_data_str[:-1]
        
        # Now split on ],[ 
        gear_item_strings = gear_data_str.split('],[')
        
        for gear_item_str in gear_item_strings:
            gear_item = [item.strip() for item in gear_item_str.split(',')]
            gear_items.append(gear_item)
        
        return gear_items
    
    def parse_begin_cast(self, entry: ESOLogEntry) -> Optional[BeginCastEntry]:
        """Parse BEGIN_CAST entry."""
        if entry.event_type != "BEGIN_CAST" or len(entry.fields) < 5:
            return None
            
        try:
            unknown1 = entry.fields[0]
            unknown2 = entry.fields[1]
            caster_unit_id = entry.fields[2]
            ability_id = entry.fields[3]
            target_unit_id = entry.fields[4]
            stats = entry.fields[5:]
            
            return BeginCastEntry(
                timestamp=entry.timestamp,
                unknown1=unknown1,
                unknown2=unknown2,
                caster_unit_id=caster_unit_id,
                ability_id=ability_id,
                target_unit_id=target_unit_id,
                stats=stats
            )
        except (ValueError, IndexError):
            return None
    
    def parse_effect_changed(self, entry: ESOLogEntry) -> Optional[EffectChangedEntry]:
        """Parse EFFECT_CHANGED entry."""
        if entry.event_type != "EFFECT_CHANGED" or len(entry.fields) < 5:
            return None
            
        try:
            effect_type = entry.fields[0]
            target_unit_id = entry.fields[1]
            source_unit_id = entry.fields[2]
            ability_id = entry.fields[3]
            stacks = entry.fields[4]
            
            # The remaining fields are complex - target stats and potentially additional targets
            remaining_fields = entry.fields[5:]
            
            # Parse target stats (first set of stats)
            target_stats = []
            additional_targets = []
            
            # This is complex - the format can vary
            # For now, just collect all remaining fields as target stats
            target_stats = remaining_fields
            
            return EffectChangedEntry(
                timestamp=entry.timestamp,
                effect_type=effect_type,
                target_unit_id=target_unit_id,
                source_unit_id=source_unit_id,
                ability_id=ability_id,
                stacks=stacks,
                target_stats=target_stats,
                additional_targets=additional_targets
            )
        except (ValueError, IndexError):
            return None
    
    def get_ability_name(self, ability_id: str) -> Optional[str]:
        """Get ability name from ID using the cache."""
        return self.ability_cache.get(ability_id)
    
    def get_equipped_abilities(self, player_info: PlayerInfoEntry) -> Set[str]:
        """Get all equipped ability names for a player (front + back bar).
        
        The equipped bar abilities are split between:
        - champion_points array: Front bar abilities
        - additional_data array: Back bar abilities
        The main ability_ids array contains ALL abilities including passives, champion points, etc.
        """
        equipped_abilities = set()
        # Get front bar abilities (champion_points array)
        for ability_id in player_info.champion_points:
            ability_name = self.get_ability_name(ability_id)
            if ability_name:
                equipped_abilities.add(ability_name)
        # Get back bar abilities (additional_data array)
        for ability_id in player_info.additional_data:
            ability_name = self.get_ability_name(ability_id)
            if ability_name:
                equipped_abilities.add(ability_name)
        return equipped_abilities

    def get_front_bar_abilities(self, player_info: PlayerInfoEntry) -> List[str]:
        """Get front bar ability names in order."""
        front_bar_abilities = []
        for ability_id in player_info.champion_points:
            ability_name = self.get_ability_name(ability_id)
            if ability_name:
                front_bar_abilities.append(ability_name)
        return front_bar_abilities

    def get_back_bar_abilities(self, player_info: PlayerInfoEntry) -> List[str]:
        """Get back bar ability names in order."""
        back_bar_abilities = []
        for ability_id in player_info.additional_data:
            ability_name = self.get_ability_name(ability_id)
            if ability_name:
                back_bar_abilities.append(ability_name)
        return back_bar_abilities
