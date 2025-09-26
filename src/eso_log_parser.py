#!/usr/bin/env python3
"""
ESO Log Parser
A robust parser for ESO encounter log files with comprehensive support for all log entry types.

Phase 2 Migration: Integrating structured parser for critical paths (PLAYER_INFO, UNIT_ADDED)
while maintaining backward compatibility with existing functionality.
"""

import re
import csv
import io
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

# Import structured parser for Phase 2 migration
try:
    from eso_log_structures import (
        ESOLogStructureParser, 
        PlayerInfoEntry as StructuredPlayerInfoEntry,
        UnitAddedEntry as StructuredUnitAddedEntry,
        EventType
    )
    STRUCTURED_PARSER_AVAILABLE = True
except ImportError:
    STRUCTURED_PARSER_AVAILABLE = False


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

            if len(fields) < 3:
                return None

            # Format: line_number,event_type,timestamp,...
            # But some events don't have timestamps (like ABILITY_INFO)
            event_type = fields[1]
            
            # Check if the third field is a timestamp (numeric)
            if len(fields) >= 3:
                try:
                    timestamp = int(fields[2])
                    # For certain events, the third field is not a timestamp
                    if event_type in ["UNIT_ADDED", "UNIT_CHANGED", "COMBAT_EVENT", "EFFECT_CHANGED", "BEGIN_CAST", "END_CAST", "ABILITY_INFO"]:
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
    """Robust parser for ESO encounter log files with Phase 2 structured parser integration."""
    
    def __init__(self):
        self.ability_cache: Dict[str, str] = {}
        
        # Initialize structured parser for Phase 2 migration
        if STRUCTURED_PARSER_AVAILABLE:
            self.structured_parser = ESOLogStructureParser()
        else:
            self.structured_parser = None
        
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
        """
        Parse UNIT_ADDED entry with Phase 2 structured parser integration.
        
        This method now uses the structured parser for better field parsing
        and error handling while maintaining backward compatibility.
        """
        if entry.event_type != "UNIT_ADDED" or len(entry.fields) < 10:
            return None
        
        # Phase 2: Try structured parser first for better field parsing
        if self.structured_parser:
            try:
                structured_result = self.structured_parser.parse_line(entry.original_line)
                if isinstance(structured_result, StructuredUnitAddedEntry):
                    # Convert structured result to legacy format for backward compatibility
                    return self._convert_structured_to_legacy_unit_added(structured_result)
            except Exception as e:
                # Fall back to legacy parsing if structured parsing fails
                print(f"Structured UNIT_ADDED parsing failed, falling back to legacy: {e}")
        
        # Legacy parsing as fallback
        return self._parse_unit_added_legacy(entry)
    
    def _convert_structured_to_legacy_unit_added(self, structured: StructuredUnitAddedEntry) -> Optional[UnitAddedEntry]:
        """Convert structured UnitAddedEntry to legacy format for backward compatibility"""
        try:
            return UnitAddedEntry(
                timestamp=structured.line_number,
                unit_id=structured.unit_id,
                unit_type=structured.unit_type.value,
                flags=[
                    "T" if structured.is_local_player else "F",
                    str(structured.unknown_1),
                    str(structured.unknown_2),
                    "T" if structured.unknown_3 else "F",
                    str(structured.unknown_4),
                    str(structured.class_id)
                ],
                name=structured.name,
                handle=structured.handle,
                player_id=structured.player_id,
                level=structured.level,
                alliance=structured.alliance
            )
        except Exception as e:
            print(f"Failed to convert structured UnitAddedEntry: {e}")
            return None
    
    def _parse_unit_added_legacy(self, entry: ESOLogEntry) -> Optional[UnitAddedEntry]:
        """Legacy UNIT_ADDED parsing as fallback"""
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
        """
        Parse PLAYER_INFO entry with Phase 2 structured parser integration.
        
        This method now uses the structured parser for better error handling
        and robust parsing of complex nested bracket structures.
        """
        if entry.event_type != "PLAYER_INFO":
            return None
        
        # Phase 2: Try structured parser first for better error handling
        if self.structured_parser:
            try:
                structured_result = self.structured_parser.parse_line(entry.original_line)
                if isinstance(structured_result, StructuredPlayerInfoEntry):
                    # Convert structured result to legacy format for backward compatibility
                    return self._convert_structured_to_legacy_player_info(structured_result, entry.timestamp)
            except Exception as e:
                # Fall back to legacy parsing if structured parsing fails
                print(f"Structured PLAYER_INFO parsing failed, falling back to legacy: {e}")
        
        # Legacy parsing as fallback
        return self._parse_player_info_legacy(entry)
    
    def _convert_structured_to_legacy_player_info(self, structured: StructuredPlayerInfoEntry, timestamp: int) -> Optional[PlayerInfoEntry]:
        """Convert structured PlayerInfoEntry to legacy format for backward compatibility"""
        try:
            # Convert gear items to legacy format
            gear_data = []
            for gear_item in structured.gear_items:
                gear_data.append([
                    gear_item.slot,
                    str(gear_item.item_id),
                    gear_item.bind_type,
                    str(gear_item.level),
                    gear_item.trait,
                    gear_item.quality,
                    str(gear_item.set_id),
                    gear_item.enchant,
                    gear_item.enchant_bind_type,
                    str(gear_item.enchant_level),
                    gear_item.enchant_quality
                ])
            
            return PlayerInfoEntry(
                timestamp=timestamp,
                unit_id=structured.unit_id,
                ability_ids=structured.ability_ids,
                ability_levels=structured.ability_levels,
                gear_data=gear_data,
                champion_points=structured.front_bar_abilities,
                additional_data=structured.back_bar_abilities
            )
        except Exception as e:
            print(f"Failed to convert structured PlayerInfoEntry: {e}")
            return None
    
    def _parse_player_info_legacy(self, entry: ESOLogEntry) -> Optional[PlayerInfoEntry]:
        """Legacy PLAYER_INFO parsing as fallback"""
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
