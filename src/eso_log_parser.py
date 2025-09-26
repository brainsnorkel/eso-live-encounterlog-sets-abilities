#!/usr/bin/env python3
"""
ESO Log Parser
A robust parser for ESO encounter log files with comprehensive support for all log entry types.

Phase 3 Migration: Complete replacement with structured parser while maintaining
backward compatibility with existing functionality.
"""

import re
import csv
import io
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

# Import structured parser for Phase 3 complete replacement
try:
    from eso_log_structures import (
        ESOLogStructureParser, 
        PlayerInfoEntry as StructuredPlayerInfoEntry,
        UnitAddedEntry as StructuredUnitAddedEntry,
        AbilityInfoEntry as StructuredAbilityInfoEntry,
        BeginCastEntry as StructuredBeginCastEntry,
        EndCastEntry as StructuredEndCastEntry,
        EffectChangedEntry as StructuredEffectChangedEntry,
        CombatEventEntry as StructuredCombatEventEntry,
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
    """Robust parser for ESO encounter log files with Phase 3 structured parser replacement."""
    
    def __init__(self):
        self.ability_cache: Dict[str, str] = {}
        
        # Initialize structured parser for Phase 3 complete replacement
        if STRUCTURED_PARSER_AVAILABLE:
            self.structured_parser = ESOLogStructureParser()
        else:
            raise ImportError("Structured parser not available. Please ensure eso_log_structures.py is present.")
        
    def parse_line(self, line: str) -> Optional[ESOLogEntry]:
        """
        Parse a single log line with Phase 3 structured parser replacement.
        
        This method maintains backward compatibility by always returning
        legacy ESOLogEntry objects, while using structured parsing internally
        for all event types.
        """
        # Use structured parser for all parsing
        structured_result = self.structured_parser.parse_line(line)
        if not structured_result:
            return None
            
        # Convert structured result to legacy ESOLogEntry for backward compatibility
        return self._convert_structured_to_legacy_entry(structured_result, line)
    
    def _convert_structured_to_legacy_entry(self, structured_result: Any, original_line: str) -> ESOLogEntry:
        """Convert structured parser result to legacy ESOLogEntry format."""
        # Extract timestamp based on event type
        timestamp = 0
        if hasattr(structured_result, '__class__'):
            class_name = structured_result.__class__.__name__
            # Use appropriate timestamp for each event type
            if class_name == 'BeginLogEntry' and hasattr(structured_result, 'unix_timestamp'):
                timestamp = structured_result.unix_timestamp
            elif class_name == 'ZoneChangedEntry' and hasattr(structured_result, 'zone_id'):
                timestamp = structured_result.zone_id
            elif class_name == 'MapChangedEntry' and hasattr(structured_result, 'map_id'):
                timestamp = structured_result.map_id
            elif class_name == 'UnitAddedEntry' and hasattr(structured_result, 'line_number'):
                timestamp = structured_result.line_number
            elif class_name == 'AbilityInfoEntry' and hasattr(structured_result, 'line_number'):
                timestamp = 0  # ABILITY_INFO doesn't have timestamps
            elif class_name == 'PlayerInfoEntry' and hasattr(structured_result, 'line_number'):
                timestamp = structured_result.line_number
            elif class_name == 'BeginCastEntry' and hasattr(structured_result, 'line_number'):
                timestamp = 0  # BEGIN_CAST doesn't have timestamps
            elif class_name == 'EndCastEntry' and hasattr(structured_result, 'line_number'):
                timestamp = 0  # END_CAST doesn't have timestamps
            elif class_name == 'EffectChangedEntry' and hasattr(structured_result, 'line_number'):
                timestamp = 0  # EFFECT_CHANGED doesn't have timestamps
            elif hasattr(structured_result, 'line_number'):
                timestamp = structured_result.line_number
        else:
            timestamp = 0
            
        if hasattr(structured_result, '__class__'):
            class_name = structured_result.__class__.__name__
            # Map class names to event types
            if class_name == 'BeginLogEntry':
                event_type = 'BEGIN_LOG'
            elif class_name == 'ZoneChangedEntry':
                event_type = 'ZONE_CHANGED'
            elif class_name == 'MapChangedEntry':
                event_type = 'MAP_CHANGED'
            elif class_name == 'UnitAddedEntry':
                event_type = 'UNIT_ADDED'
            elif class_name == 'AbilityInfoEntry':
                event_type = 'ABILITY_INFO'
            elif class_name == 'PlayerInfoEntry':
                event_type = 'PLAYER_INFO'
            elif class_name == 'BeginCastEntry':
                event_type = 'BEGIN_CAST'
            elif class_name == 'EndCastEntry':
                event_type = 'END_CAST'
            elif class_name == 'EffectChangedEntry':
                event_type = 'EFFECT_CHANGED'
            elif class_name == 'CombatEventEntry':
                event_type = 'COMBAT_EVENT'
            else:
                event_type = class_name.replace('Entry', '').upper()
        else:
            event_type = "UNKNOWN"
            
        # Parse the original line to get fields for backward compatibility
        try:
            reader = csv.reader(io.StringIO(original_line))
            fields = next(reader)
            # Remove line number and event type from fields
            if len(fields) >= 2:
                fields = fields[2:]
        except:
            fields = []
            
        # Create ESOLogEntry with proper fields
        return ESOLogEntry(
            timestamp=timestamp,
            event_type=event_type,
            fields=fields,
            original_line=original_line
        )
    
    def parse_unit_added(self, entry: ESOLogEntry) -> Optional[UnitAddedEntry]:
        """
        Parse UNIT_ADDED entry with Phase 3 structured parser replacement.
        
        This method now uses the structured parser exclusively for better field parsing
        and error handling while maintaining backward compatibility.
        """
        if not entry or entry.event_type != "UNIT_ADDED":
            return None
        
        # Use structured parser for all parsing
        try:
            structured_result = self.structured_parser.parse_line(entry.original_line)
            if isinstance(structured_result, StructuredUnitAddedEntry):
                # Convert structured result to legacy format for backward compatibility
                return self._convert_structured_to_legacy_unit_added(structured_result)
        except Exception as e:
            print(f"Structured UNIT_ADDED parsing failed: {e}")
            return None
        
        return None
    
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
    
    
    def parse_ability_info(self, entry: ESOLogEntry) -> Optional[AbilityInfoEntry]:
        """Parse ABILITY_INFO entry with Phase 3 structured parser replacement."""
        if entry.event_type != "ABILITY_INFO":
            return None
        
        # Use structured parser for all parsing
        try:
            structured_result = self.structured_parser.parse_line(entry.original_line)
            if isinstance(structured_result, StructuredAbilityInfoEntry):
                # Cache the ability for later use
                self.ability_cache[str(structured_result.ability_id)] = structured_result.ability_name
                
                # Convert structured result to legacy format for backward compatibility
                return self._convert_structured_to_legacy_ability_info(structured_result)
        except Exception as e:
            print(f"Structured ABILITY_INFO parsing failed: {e}")
            return None
        
        return None
    
    def _convert_structured_to_legacy_ability_info(self, structured: StructuredAbilityInfoEntry) -> Optional[AbilityInfoEntry]:
        """Convert structured AbilityInfoEntry to legacy format for backward compatibility"""
        try:
            return AbilityInfoEntry(
                timestamp=structured.line_number,
                ability_id=str(structured.ability_id),
                ability_name=structured.ability_name,
                icon_path=structured.icon_path,
                flags=["T" if structured.is_passive else "F", "T" if structured.is_ultimate else "F"]
            )
        except Exception as e:
            print(f"Failed to convert structured AbilityInfoEntry: {e}")
            return None
    
    def parse_player_info(self, entry: ESOLogEntry) -> Optional[PlayerInfoEntry]:
        """
        Parse PLAYER_INFO entry with Phase 3 structured parser replacement.
        
        This method now uses the structured parser exclusively for better error handling
        and robust parsing of complex nested bracket structures.
        """
        if entry.event_type != "PLAYER_INFO":
            return None
        
        # Use structured parser for all parsing
        try:
            structured_result = self.structured_parser.parse_line(entry.original_line)
            if isinstance(structured_result, StructuredPlayerInfoEntry):
                # Convert structured result to legacy format for backward compatibility
                return self._convert_structured_to_legacy_player_info(structured_result, entry.timestamp)
        except Exception as e:
            print(f"Structured PLAYER_INFO parsing failed: {e}")
            return None
        
        return None
    
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
                timestamp=structured.line_number,  # Use line_number from structured parser, not entry.timestamp
                unit_id=str(structured.unit_id),  # Convert to string to match legacy format
                ability_ids=[str(aid) for aid in structured.ability_ids],  # Convert to strings
                ability_levels=[str(al) for al in structured.ability_levels],  # Convert to strings
                gear_data=gear_data,
                champion_points=[str(cp) for cp in structured.front_bar_abilities],  # Convert to strings
                additional_data=[str(ad) for ad in structured.back_bar_abilities]  # Convert to strings
            )
        except Exception as e:
            print(f"Failed to convert structured PlayerInfoEntry: {e}")
            return None
    
    
    def parse_begin_cast(self, entry: ESOLogEntry) -> Optional[BeginCastEntry]:
        """Parse BEGIN_CAST entry with Phase 3 structured parser replacement."""
        if entry.event_type != "BEGIN_CAST":
            return None
        
        # Use structured parser for all parsing
        try:
            structured_result = self.structured_parser.parse_line(entry.original_line)
            if isinstance(structured_result, StructuredBeginCastEntry):
                # Convert structured result to legacy format for backward compatibility
                return self._convert_structured_to_legacy_begin_cast(structured_result, entry.original_line)
        except Exception as e:
            print(f"Structured BEGIN_CAST parsing failed: {e}")
            return None
        
        return None
    
    def _convert_structured_to_legacy_begin_cast(self, structured: StructuredBeginCastEntry, original_line: str) -> Optional[BeginCastEntry]:
        """Convert structured BeginCastEntry to legacy format for backward compatibility"""
        try:
            # Extract stats from the original line for backward compatibility
            stats = []
            try:
                reader = csv.reader(io.StringIO(original_line))
                fields = next(reader)
                if len(fields) > 7:  # Skip line_number, event_type, and first 5 fields
                    stats = fields[7:]
            except:
                pass
                
            return BeginCastEntry(
                timestamp=structured.line_number,
                unknown1=str(structured.channel_id),
                unknown2="T" if structured.is_channeled else "F",
                caster_unit_id=str(structured.caster_unit_id),
                ability_id=str(structured.ability_id),
                target_unit_id=str(structured.target_unit_id),
                stats=stats
            )
        except Exception as e:
            print(f"Failed to convert structured BeginCastEntry: {e}")
            return None
    
    def parse_effect_changed(self, entry: ESOLogEntry) -> Optional[EffectChangedEntry]:
        """Parse EFFECT_CHANGED entry with Phase 3 structured parser replacement."""
        if entry.event_type != "EFFECT_CHANGED":
            return None
        
        # Use structured parser for all parsing
        try:
            structured_result = self.structured_parser.parse_line(entry.original_line)
            if isinstance(structured_result, StructuredEffectChangedEntry):
                # Convert structured result to legacy format for backward compatibility
                return self._convert_structured_to_legacy_effect_changed(structured_result, entry.original_line)
        except Exception as e:
            print(f"Structured EFFECT_CHANGED parsing failed: {e}")
            return None
        
        return None
    
    def _convert_structured_to_legacy_effect_changed(self, structured: StructuredEffectChangedEntry, original_line: str) -> Optional[EffectChangedEntry]:
        """Convert structured EffectChangedEntry to legacy format for backward compatibility"""
        try:
            # Extract target_stats from the original line for backward compatibility
            target_stats = []
            try:
                reader = csv.reader(io.StringIO(original_line))
                fields = next(reader)
                if len(fields) > 7:  # Skip line_number, event_type, and first 5 fields
                    target_stats = fields[7:]
            except:
                pass
                
            return EffectChangedEntry(
                timestamp=0,  # EFFECT_CHANGED doesn't have timestamps
                effect_type=structured.change_type.value,
                target_unit_id=str(structured.target_unit_id),
                source_unit_id=str(structured.source_unit_id),
                ability_id=str(structured.effect_id),
                stacks=str(structured.stack_count),
                target_stats=target_stats,
                additional_targets=[[str(t)] for t in structured.additional_targets]
            )
        except Exception as e:
            print(f"Failed to convert structured EffectChangedEntry: {e}")
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
