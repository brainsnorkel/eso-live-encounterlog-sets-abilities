"""
ESO Encounter Log Entry Structures

This module defines data structures for all ESO encounter log entry types with symbolic field names.
Based on examples from actual encounter logs and the ESO log format documentation.

Reference: https://github.com/sheumais/logs/blob/1331c1360486fdc07682fa2e36f502b6a8291bd4/parser/README.md

Each structure includes:
- Symbolic field names for better code readability
- Field types and descriptions
- Real examples from encounter logs
- Parsing methods for converting raw CSV fields to structured data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
import csv
import io


class EventType(Enum):
    """ESO log event types"""
    BEGIN_LOG = "BEGIN_LOG"
    ZONE_CHANGED = "ZONE_CHANGED"
    UNIT_ADDED = "UNIT_ADDED"
    UNIT_CHANGED = "UNIT_CHANGED"
    UNIT_REMOVED = "UNIT_REMOVED"  # Missing from current parser
    ABILITY_INFO = "ABILITY_INFO"
    MAP_CHANGED = "MAP_CHANGED"
    BEGIN_CAST = "BEGIN_CAST"
    END_CAST = "END_CAST"
    EFFECT_INFO = "EFFECT_INFO"
    EFFECT_CHANGED = "EFFECT_CHANGED"
    COMBAT_EVENT = "COMBAT_EVENT"
    BEGIN_COMBAT = "BEGIN_COMBAT"
    END_COMBAT = "END_COMBAT"
    PLAYER_INFO = "PLAYER_INFO"
    # Trial events (missing from current parser)
    TRIAL_INIT = "TRIAL_INIT"
    BEGIN_TRIAL = "BEGIN_TRIAL"
    END_TRIAL = "END_TRIAL"
    # Endless dungeon events (missing from current parser)
    ENDLESS_DUNGEON_START = "ENDLESS_DUNGEON_START"
    ENDLESS_DUNGEON_END = "ENDLESS_DUNGEON_END"


class UnitType(Enum):
    """Unit types in ESO logs"""
    PLAYER = "PLAYER"
    MONSTER = "MONSTER"
    NPC = "NPC"


class EffectType(Enum):
    """Effect types"""
    BUFF = "BUFF"
    DEBUFF = "DEBUFF"


class EffectChangeType(Enum):
    """Effect change types"""
    GAINED = "GAINED"
    FADED = "FADED"
    UPDATED = "UPDATED"


class CastResult(Enum):
    """Cast completion results"""
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class CombatEventType(Enum):
    """Combat event types"""
    POWER_ENERGIZE = "POWER_ENERGIZE"
    QUEUED = "QUEUED"
    DAMAGE = "DAMAGE"
    HEAL = "HEAL"


class Difficulty(Enum):
    """Zone difficulty levels"""
    NORMAL = "NORMAL"
    VETERAN = "VETERAN"
    NONE = "NONE"


@dataclass
class UnitStats:
    """Unit statistics (health, magicka, stamina, etc.)"""
    current_health: int
    max_health: int
    current_magicka: int
    max_magicka: int
    current_stamina: int
    max_stamina: int
    current_ultimate: int
    max_ultimate: int
    werewolf_ultimate: int
    magicka_regen: float
    stamina_regen: float
    ultimate_regen: float
    forward_camps: int = 0

    @classmethod
    def from_string(cls, stats_str: str) -> 'UnitStats':
        """Parse unit stats from string format like '22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492'"""
        parts = stats_str.split(',')
        if len(parts) < 9:
            # Fallback for incomplete stats
            return cls(0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
        
        health = parts[0].split('/')
        magicka = parts[1].split('/')
        stamina = parts[2].split('/')
        ultimate = parts[3].split('/')
        werewolf = parts[4].split('/')
        
        return cls(
            current_health=int(health[0]),
            max_health=int(health[1]),
            current_magicka=int(magicka[0]),
            max_magicka=int(magicka[1]),
            current_stamina=int(stamina[0]),
            max_stamina=int(stamina[1]),
            current_ultimate=int(ultimate[0]),
            max_ultimate=int(ultimate[1]),
            werewolf_ultimate=int(werewolf[0]) if len(werewolf) > 0 else 0,
            magicka_regen=float(parts[6]),
            stamina_regen=float(parts[7]),
            ultimate_regen=float(parts[8]),
            forward_camps=int(parts[9]) if len(parts) > 9 else 0
        )


@dataclass
class GearItem:
    """Individual gear item structure"""
    slot: str  # HEAD, CHEST, MAIN_HAND, etc.
    item_id: int
    bind_type: str  # T/F for bind on pickup
    level: int
    trait: str  # ARMOR_DIVINES, WEAPON_CHARGED, etc.
    quality: str  # LEGENDARY, ARTIFACT, etc.
    set_id: int
    enchant: str  # MAGICKA, INCREASE_SPELL_DAMAGE, etc.
    enchant_bind_type: str
    enchant_level: int
    enchant_quality: str

    @classmethod
    def from_list(cls, gear_data: List[str]) -> 'GearItem':
        """Parse gear item from list format"""
        if len(gear_data) < 11:
            # Fallback for incomplete gear data
            return cls("UNKNOWN", 0, "F", 0, "NONE", "NORMAL", 0, "NONE", "F", 0, "NORMAL")
        
        return cls(
            slot=gear_data[0],
            item_id=int(gear_data[1]),
            bind_type=gear_data[2],
            level=int(gear_data[3]),
            trait=gear_data[4],
            quality=gear_data[5],
            set_id=int(gear_data[6]),
            enchant=gear_data[7],
            enchant_bind_type=gear_data[8],
            enchant_level=int(gear_data[9]),
            enchant_quality=gear_data[10]
        )


# ============================================================================
# LOG ENTRY STRUCTURES
# ============================================================================

@dataclass
class BeginLogEntry:
    """
    BEGIN_LOG event - starts a new log session
    
    Example: 5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"
    """
    line_number: int
    unix_timestamp: int  # Unix timestamp in milliseconds
    session_id: int
    server_name: str
    language: str
    game_version: str

    @classmethod
    def parse(cls, line: str) -> Optional['BeginLogEntry']:
        """Parse BEGIN_LOG entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 7 or fields[1] != "BEGIN_LOG":
                return None
                
            return cls(
                line_number=int(fields[0]),
                unix_timestamp=int(fields[2]),
                session_id=int(fields[3]),
                server_name=fields[4].strip('"'),
                language=fields[5].strip('"'),
                game_version=fields[6].strip('"')
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class ZoneChangedEntry:
    """
    ZONE_CHANGED event - entering/leaving zones
    
    Example: 5,ZONE_CHANGED,1301,"Coral Aerie",VETERAN
    """
    line_number: int
    zone_id: int
    zone_name: str
    difficulty: Difficulty

    @classmethod
    def parse(cls, line: str) -> Optional['ZoneChangedEntry']:
        """Parse ZONE_CHANGED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 5 or fields[1] != "ZONE_CHANGED":
                return None
                
            return cls(
                line_number=int(fields[0]),
                zone_id=int(fields[2]),
                zone_name=fields[3].strip('"'),
                difficulty=Difficulty(fields[4]) if fields[4] in [d.value for d in Difficulty] else Difficulty.NONE
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class UnitAddedEntry:
    """
    UNIT_ADDED event - when units (players/enemies) are added to the encounter
    
    Format: UNIT_ADDED, unitId, unitType, isLocalPlayer, playerPerSessionId, monsterId, isBoss, classId, raceId, name, displayName, characterId, level, championPoints, ownerUnitId, reaction, isGroupedWithLocalPlayer
    
    Example: 5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T
    """
    line_number: int
    unit_id: str
    unit_type: UnitType
    is_local_player: bool  # T/F
    player_per_session_id: int
    monster_id: int
    is_boss: bool  # F/T
    class_id: int  # For players: 1=DK, 2=Sorc, 3=NB, 4=Templar, 5=Warden, 6=Necro, 7=Arcanist
    race_id: int
    name: str
    display_name: str  # Player handle (e.g., @brainsnorkel)
    character_id: int  # Long player ID
    level: int
    champion_points: int
    owner_unit_id: int
    reaction: str  # PLAYER_ALLY, HOSTILE, etc.
    is_grouped_with_local_player: bool

    @classmethod
    def parse(cls, line: str) -> Optional['UnitAddedEntry']:
        """Parse UNIT_ADDED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)

            if len(fields) < 18 or fields[1] != "UNIT_ADDED":
                return None
                
            return cls(
                line_number=int(fields[0]),
                unit_id=fields[2],
                unit_type=UnitType(fields[3]),
                is_local_player=fields[4] == "T",
                player_per_session_id=int(fields[5]),
                monster_id=int(fields[6]),
                is_boss=fields[7] == "T",
                class_id=int(fields[8]),
                race_id=int(fields[9]),
                name=fields[10].strip('"'),
                display_name=fields[11].strip('"'),
                character_id=int(fields[12]) if fields[12].isdigit() else 0,
                level=int(fields[13]),
                champion_points=int(fields[14]),
                owner_unit_id=int(fields[15]),
                reaction=fields[16],
                is_grouped_with_local_player=fields[17] == "T"
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class UnitChangedEntry:
    """
    UNIT_CHANGED event - when unit properties change
    
    Format: UNIT_CHANGED, unitId, classId, raceId, name, displayName, characterId, level, championPoints, ownerUnitId, reaction, isGroupedWithLocalPlayer
    
    Example: 83373,UNIT_CHANGED,125,0,0,"Coral Crab","",0,50,160,0,HOSTILE,F
    """
    line_number: int
    unit_id: str
    class_id: int
    race_id: int
    name: str
    display_name: str
    character_id: int
    level: int
    champion_points: int
    owner_unit_id: int
    reaction: str
    is_grouped_with_local_player: bool

    @classmethod
    def parse(cls, line: str) -> Optional['UnitChangedEntry']:
        """Parse UNIT_CHANGED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 13 or fields[1] != "UNIT_CHANGED":
                return None
                
            return cls(
                line_number=int(fields[0]),
                unit_id=fields[2],
                class_id=int(fields[3]),
                race_id=int(fields[4]),
                name=fields[5].strip('"'),
                display_name=fields[6].strip('"'),
                character_id=int(fields[7]) if fields[7].isdigit() else 0,
                level=int(fields[8]),
                champion_points=int(fields[9]),
                owner_unit_id=int(fields[10]),
                reaction=fields[11],
                is_grouped_with_local_player=fields[12] == "T"
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class AbilityInfoEntry:
    """
    ABILITY_INFO event - ability definitions
    
    Example: 2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T
    """
    line_number: int
    ability_id: int
    ability_name: str
    icon_path: str
    is_passive: bool  # T/F
    is_ultimate: bool  # T/F

    @classmethod
    def parse(cls, line: str) -> Optional['AbilityInfoEntry']:
        """Parse ABILITY_INFO entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 7 or fields[1] != "ABILITY_INFO":
                return None
                
            return cls(
                line_number=int(fields[0]),
                ability_id=int(fields[2]),
                ability_name=fields[3].strip('"'),
                icon_path=fields[4].strip('"'),
                is_passive=fields[5] == "T",
                is_ultimate=fields[6] == "T"
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class MapChangedEntry:
    """
    MAP_CHANGED event - map transitions within zones
    
    Example: 2928,MAP_CHANGED,2110,"Brackish Cove","summerset/CoralAerie_Beach_001"
    """
    line_number: int
    map_id: int
    map_name: str
    map_path: str

    @classmethod
    def parse(cls, line: str) -> Optional['MapChangedEntry']:
        """Parse MAP_CHANGED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 5 or fields[1] != "MAP_CHANGED":
                return None
                
            return cls(
                line_number=int(fields[0]),
                map_id=int(fields[2]),
                map_name=fields[3].strip('"'),
                map_path=fields[4].strip('"')
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class BeginCastEntry:
    """
    BEGIN_CAST event - when abilities start casting
    
    Example: 2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000
    """
    line_number: int
    channel_id: int
    is_channeled: bool  # F/T
    caster_unit_id: int
    ability_id: int
    target_unit_id: int
    caster_stats: UnitStats
    target_stats: Optional[UnitStats] = None

    @classmethod
    def parse(cls, line: str) -> Optional['BeginCastEntry']:
        """Parse BEGIN_CAST entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 16 or fields[1] != "BEGIN_CAST":
                return None
            
            # Parse caster stats (fields 7-15)
            caster_stats_str = ",".join(fields[7:16])
            caster_stats = UnitStats.from_string(caster_stats_str)
            
            # Parse target stats if present (fields 17+)
            target_stats = None
            if len(fields) > 17 and fields[16] != "0":
                target_stats_str = ",".join(fields[17:26]) if len(fields) >= 26 else ""
                if target_stats_str:
                    target_stats = UnitStats.from_string(target_stats_str)
                
            return cls(
                line_number=int(fields[0]),
                channel_id=int(fields[2]),
                is_channeled=fields[3] == "T",
                caster_unit_id=int(fields[4]),
                ability_id=int(fields[5]),
                target_unit_id=int(fields[6]),
                caster_stats=caster_stats,
                target_stats=target_stats
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EndCastEntry:
    """
    END_CAST event - when abilities finish casting
    
    Example: 2928,END_CAST,COMPLETED,4021667,84734
    """
    line_number: int
    result: CastResult
    caster_unit_id: int
    ability_id: int

    @classmethod
    def parse(cls, line: str) -> Optional['EndCastEntry']:
        """Parse END_CAST entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 5 or fields[1] != "END_CAST":
                return None
                
            return cls(
                line_number=int(fields[0]),
                result=CastResult(fields[2]),
                caster_unit_id=int(fields[3]),
                ability_id=int(fields[4])
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EffectInfoEntry:
    """
    EFFECT_INFO event - effect definitions
    
    Example: 2928,EFFECT_INFO,84734,BUFF,NONE,NEVER
    """
    line_number: int
    effect_id: int
    effect_type: EffectType
    stack_rule: str  # NONE, STACK, etc.
    duration_type: str  # NEVER, DEFAULT, TIMED, etc.

    @classmethod
    def parse(cls, line: str) -> Optional['EffectInfoEntry']:
        """Parse EFFECT_INFO entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 6 or fields[1] != "EFFECT_INFO":
                return None
                
            return cls(
                line_number=int(fields[0]),
                effect_id=int(fields[2]),
                effect_type=EffectType(fields[3]),
                stack_rule=fields[4],
                duration_type=fields[5]
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EffectChangedEntry:
    """
    EFFECT_CHANGED event - when effects are gained/faded/updated
    
    Example: 2928,EFFECT_CHANGED,GAINED,1,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,*
    """
    line_number: int
    change_type: EffectChangeType
    target_unit_id: int
    source_unit_id: int
    effect_id: int
    stack_count: int
    target_stats: UnitStats
    additional_targets: List[int] = field(default_factory=list)  # Multiple targets possible

    @classmethod
    def parse(cls, line: str) -> Optional['EffectChangedEntry']:
        """Parse EFFECT_CHANGED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 16 or fields[1] != "EFFECT_CHANGED":
                return None
            
            # Parse target stats (fields 7-15)
            target_stats_str = ",".join(fields[7:16])
            target_stats = UnitStats.from_string(target_stats_str)
            
            # Parse additional targets if present
            additional_targets = []
            if len(fields) > 16 and fields[16] != "*":
                # Additional target data follows
                additional_targets.append(int(fields[16]))
                
            return cls(
                line_number=int(fields[0]),
                change_type=EffectChangeType(fields[2]),
                target_unit_id=int(fields[3]),
                source_unit_id=int(fields[4]),
                effect_id=int(fields[5]),
                stack_count=int(fields[6]),
                target_stats=target_stats,
                additional_targets=additional_targets
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class CombatEventEntry:
    """
    COMBAT_EVENT event - combat actions (damage, healing, etc.)
    
    Example: 20147,COMBAT_EVENT,POWER_ENERGIZE,GENERIC,4,625,0,4021356,118117,1,21896/21896,27034/29628,11388/13021,500/500,1000/1000,0,0.3121,0.5651,5.1608,*
    """
    line_number: int
    event_type: str  # POWER_ENERGIZE, QUEUED, DAMAGE, HEAL, etc.
    damage_type: str  # GENERIC, PHYSICAL, MAGIC, etc.
    hit_value: int
    amount: int
    mitigation: int
    source_unit_id: int
    ability_id: int
    target_unit_id: int
    target_stats: UnitStats

    @classmethod
    def parse(cls, line: str) -> Optional['CombatEventEntry']:
        """Parse COMBAT_EVENT entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 19 or fields[1] != "COMBAT_EVENT":
                return None
            
            # Parse target stats (fields 10-18)
            target_stats_str = ",".join(fields[10:19])
            target_stats = UnitStats.from_string(target_stats_str)
                
            return cls(
                line_number=int(fields[0]),
                event_type=fields[2],
                damage_type=fields[3],
                hit_value=int(fields[4]),
                amount=int(fields[5]),
                mitigation=int(fields[6]),
                source_unit_id=int(fields[7]),
                ability_id=int(fields[8]),
                target_unit_id=int(fields[9]),
                target_stats=target_stats
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class BeginCombatEntry:
    """
    BEGIN_COMBAT event - combat starts
    
    Example: 40603,BEGIN_COMBAT
    """
    line_number: int

    @classmethod
    def parse(cls, line: str) -> Optional['BeginCombatEntry']:
        """Parse BEGIN_COMBAT entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 2 or fields[1] != "BEGIN_COMBAT":
                return None
                
            return cls(line_number=int(fields[0]))
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EndCombatEntry:
    """
    END_COMBAT event - combat ends
    
    Example: 49372,END_COMBAT
    """
    line_number: int

    @classmethod
    def parse(cls, line: str) -> Optional['EndCombatEntry']:
        """Parse END_COMBAT entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 2 or fields[1] != "END_COMBAT":
                return None
                
            return cls(line_number=int(fields[0]))
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class UnitRemovedEntry:
    """
    UNIT_REMOVED event - when units are removed from the encounter
    
    Example: 50000,UNIT_REMOVED,125
    """
    line_number: int
    unit_id: str

    @classmethod
    def parse(cls, line: str) -> Optional['UnitRemovedEntry']:
        """Parse UNIT_REMOVED entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 3 or fields[1] != "UNIT_REMOVED":
                return None
                
            return cls(
                line_number=int(fields[0]),
                unit_id=fields[2]
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class TrialInitEntry:
    """
    TRIAL_INIT event - trial initialization
    
    Example: 5,TRIAL_INIT,18,F,F,0,0,F,0
    """
    line_number: int
    trial_id: int
    in_progress: bool
    completed: bool
    start_time_ms: int
    duration_ms: int
    success: bool
    final_score: int

    @classmethod
    def parse(cls, line: str) -> Optional['TrialInitEntry']:
        """Parse TRIAL_INIT entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 9 or fields[1] != "TRIAL_INIT":
                return None
                
            return cls(
                line_number=int(fields[0]),
                trial_id=int(fields[2]),
                in_progress=fields[3] == 'T',
                completed=fields[4] == 'T',
                start_time_ms=int(fields[5]),
                duration_ms=int(fields[6]),
                success=fields[7] == 'T',
                final_score=int(fields[8])
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class BeginTrialEntry:
    """
    BEGIN_TRIAL event - trial starts
    
    Example: 2000,BEGIN_TRIAL,1234,1757807878937
    """
    line_number: int
    trial_id: int
    start_time_ms: int

    @classmethod
    def parse(cls, line: str) -> Optional['BeginTrialEntry']:
        """Parse BEGIN_TRIAL entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 4 or fields[1] != "BEGIN_TRIAL":
                return None
                
            return cls(
                line_number=int(fields[0]),
                trial_id=int(fields[2]),
                start_time_ms=int(fields[3])
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EndTrialEntry:
    """
    END_TRIAL event - trial ends
    
    Example: 30000,END_TRIAL,1234,5260938,T,54193,0
    """
    line_number: int
    trial_id: int
    duration_ms: int
    success: bool
    final_score: int
    vitality_bonus: int

    @classmethod
    def parse(cls, line: str) -> Optional['EndTrialEntry']:
        """Parse END_TRIAL entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 7 or fields[1] != "END_TRIAL":
                return None
                
            return cls(
                line_number=int(fields[0]),
                trial_id=int(fields[2]),
                duration_ms=int(fields[3]),
                success=fields[4] == 'T',
                final_score=int(fields[5]),
                vitality_bonus=int(fields[6])
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EndlessDungeonStartEntry:
    """
    ENDLESS_DUNGEON_START event - endless dungeon begins
    
    Example: 1000,ENDLESS_DUNGEON_START,5678,"Maelstrom Arena",VETERAN
    """
    line_number: int
    dungeon_id: int
    dungeon_name: str
    difficulty: Difficulty

    @classmethod
    def parse(cls, line: str) -> Optional['EndlessDungeonStartEntry']:
        """Parse ENDLESS_DUNGEON_START entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 5 or fields[1] != "ENDLESS_DUNGEON_START":
                return None
                
            return cls(
                line_number=int(fields[0]),
                dungeon_id=int(fields[2]),
                dungeon_name=fields[3].strip('"'),
                difficulty=Difficulty(fields[4]) if fields[4] in [d.value for d in Difficulty] else Difficulty.NONE
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class EndlessDungeonEndEntry:
    """
    ENDLESS_DUNGEON_END event - endless dungeon ends
    
    Example: 50000,ENDLESS_DUNGEON_END,5678,COMPLETED,15
    """
    line_number: int
    dungeon_id: int
    result: str  # COMPLETED, FAILED, etc.
    rounds_completed: int

    @classmethod
    def parse(cls, line: str) -> Optional['EndlessDungeonEndEntry']:
        """Parse ENDLESS_DUNGEON_END entry from CSV line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 5 or fields[1] != "ENDLESS_DUNGEON_END":
                return None
                
            return cls(
                line_number=int(fields[0]),
                dungeon_id=int(fields[2]),
                result=fields[3],
                rounds_completed=int(fields[4])
            )
        except (ValueError, IndexError, StopIteration):
            return None


@dataclass
class PlayerInfoEntry:
    """
    PLAYER_INFO event - player equipment and abilities
    
    Example: 40604,PLAYER_INFO,1,[142210,142079,84731,...],[1,1,1,...],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY],...],[183006,183122,38901,25267,217699,113105],[39028,86169,86156,185842,217699,86113]
    """
    line_number: int
    unit_id: int
    ability_ids: List[int]
    ability_levels: List[int]
    gear_items: List[GearItem]
    front_bar_abilities: List[int]
    back_bar_abilities: List[int]

    @classmethod
    def parse(cls, line: str) -> Optional['PlayerInfoEntry']:
        """Parse PLAYER_INFO entry from CSV line (complex regex parsing required)"""
        import re
        
        # PLAYER_INFO has complex nested arrays that break standard CSV parsing
        pattern = r'(\d+),PLAYER_INFO,(\d+),\[([^\]]+)\],\[([^\]]+)\],(\[.*\]),(\[.*\]),(\[.*\])'
        match = re.search(pattern, line)
        
        if not match:
            return None
            
        unit_id = int(match.group(2))
            
        try:
            line_number = int(match.group(1))
            unit_id = int(match.group(2))
            
            
            # Parse ability IDs
            ability_ids_str = match.group(3)
            ability_ids = [int(x.strip()) for x in ability_ids_str.split(',')]
            
            # Parse ability levels  
            ability_levels_str = match.group(4)
            ability_levels = [int(x.strip()) for x in ability_levels_str.split(',')]
            
            # Parse gear data (complex nested structure)
            gear_data_str = match.group(5)
            gear_items = cls._parse_gear_data(gear_data_str)
            
            # Parse front bar abilities
            front_bar_str = match.group(6).strip('[]')
            front_bar_abilities = [int(x.strip()) for x in front_bar_str.split(',') if x.strip()]
            
            # Parse back bar abilities
            back_bar_str = match.group(7).strip('[]')
            back_bar_abilities = [int(x.strip()) for x in back_bar_str.split(',') if x.strip()]
            
            result = cls(
                line_number=line_number,
                unit_id=unit_id,
                ability_ids=ability_ids,
                ability_levels=ability_levels,
                gear_items=gear_items,
                front_bar_abilities=front_bar_abilities,
                back_bar_abilities=back_bar_abilities
            )
            
            
            return result
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_gear_data(gear_data_str: str) -> List[GearItem]:
        """
        Parse complex gear data structure with proper nested bracket handling
        
        Handles complex configurations that break simple regex parsing:
        - Nested brackets within gear items
        - Quoted strings containing commas
        - Variable-length gear item data
        """
        gear_items = []
        
        # Remove outer brackets if present
        if gear_data_str.startswith('[[') and gear_data_str.endswith(']]'):
            gear_data_str = gear_data_str[1:-1]  # Remove one level of brackets
        
        # Use a more robust approach to handle nested brackets
        bracket_count = 0
        current_item = ""
        items = []
        
        for char in gear_data_str:
            if char == '[':
                bracket_count += 1
                current_item += char
            elif char == ']':
                bracket_count -= 1
                current_item += char
                if bracket_count == 0:
                    # Complete gear item found
                    items.append(current_item.strip())
                    current_item = ""
            elif bracket_count == 0 and char == ',':
                # Skip commas between items (when not inside brackets)
                continue
            else:
                current_item += char
        
        # Parse each gear item
        for item_str in items:
            if item_str.startswith('[') and item_str.endswith(']'):
                # Remove brackets and parse CSV-style data
                item_content = item_str[1:-1]
                
                # Use CSV reader to handle quoted strings properly
                try:
                    reader = csv.reader(io.StringIO(item_content))
                    gear_parts = next(reader)
                    
                    if len(gear_parts) >= 11:
                        gear_item = GearItem.from_list(gear_parts)
                        gear_items.append(gear_item)
                except (ValueError, IndexError, StopIteration):
                    # Skip malformed gear items
                    continue
        
        return gear_items


# ============================================================================
# PARSER CLASS
# ============================================================================

class ESOLogStructureParser:
    """
    Parser for converting raw ESO log lines into structured data types
    """
    
    PARSERS = {
        EventType.BEGIN_LOG: BeginLogEntry.parse,
        EventType.ZONE_CHANGED: ZoneChangedEntry.parse,
        EventType.UNIT_ADDED: UnitAddedEntry.parse,
        EventType.UNIT_CHANGED: UnitChangedEntry.parse,
        EventType.UNIT_REMOVED: UnitRemovedEntry.parse,
        EventType.ABILITY_INFO: AbilityInfoEntry.parse,
        EventType.MAP_CHANGED: MapChangedEntry.parse,
        EventType.BEGIN_CAST: BeginCastEntry.parse,
        EventType.END_CAST: EndCastEntry.parse,
        EventType.EFFECT_INFO: EffectInfoEntry.parse,
        EventType.EFFECT_CHANGED: EffectChangedEntry.parse,
        EventType.COMBAT_EVENT: CombatEventEntry.parse,
        EventType.BEGIN_COMBAT: BeginCombatEntry.parse,
        EventType.END_COMBAT: EndCombatEntry.parse,
        EventType.PLAYER_INFO: PlayerInfoEntry.parse,
        # New event types
        EventType.TRIAL_INIT: TrialInitEntry.parse,
        EventType.BEGIN_TRIAL: BeginTrialEntry.parse,
        EventType.END_TRIAL: EndTrialEntry.parse,
        EventType.ENDLESS_DUNGEON_START: EndlessDungeonStartEntry.parse,
        EventType.ENDLESS_DUNGEON_END: EndlessDungeonEndEntry.parse,
    }
    
    def parse_line(self, line: str) -> Optional[Any]:
        """Parse a single log line into the appropriate structured type"""
        if not line or not line.strip():
            return None
            
        try:
            # Extract event type from line
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 2:
                return None
                
            event_type_str = fields[1]
            
            # Find matching parser
            for event_type in EventType:
                if event_type.value == event_type_str:
                    parser = self.PARSERS.get(event_type)
                    if parser:
                        return parser(line)
                    break
                    
            return None
        except (ValueError, IndexError, StopIteration):
            return None

    def get_event_type(self, line: str) -> Optional[EventType]:
        """Get the event type from a log line"""
        try:
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)
            
            if len(fields) < 2:
                return None
                
            event_type_str = fields[1]
            
            for event_type in EventType:
                if event_type.value == event_type_str:
                    return event_type
                    
            return None
        except (ValueError, IndexError, StopIteration):
            return None


# ============================================================================
# HYBRID PARSER FOR GRADUAL MIGRATION
# ============================================================================

class HybridESOLogParser:
    """
    Hybrid parser that combines structured parsing with legacy parsing
    for gradual migration from the existing ESOLogParser
    """
    
    def __init__(self):
        self.structured_parser = ESOLogStructureParser()
        self.legacy_parser = None  # Will be set to existing ESOLogParser instance
        
    def set_legacy_parser(self, legacy_parser):
        """Set the legacy parser for fallback"""
        self.legacy_parser = legacy_parser
    
    def parse_line(self, line: str) -> Optional[Any]:
        """
        Parse a log line using structured parser first, fallback to legacy
        
        This allows gradual migration:
        1. New event types use structured parser
        2. Critical paths can be migrated individually
        3. Legacy parser handles remaining events
        """
        if not line or not line.strip():
            return None
        
        # Try structured parser first
        structured_result = self.structured_parser.parse_line(line)
        if structured_result is not None:
            return structured_result
        
        # Fallback to legacy parser if available
        if self.legacy_parser:
            return self.legacy_parser.parse_line(line)
        
        return None
    
    def parse_player_info(self, line: str) -> Optional[PlayerInfoEntry]:
        """
        Enhanced PLAYER_INFO parsing with better error handling
        
        This addresses the critical PLAYER_INFO parsing issues mentioned
        in the terminal selection
        """
        # Use structured parser for PLAYER_INFO
        result = self.structured_parser.parse_line(line)
        if isinstance(result, PlayerInfoEntry):
            return result
        
        # Fallback to legacy parser if structured parsing fails
        if self.legacy_parser:
            legacy_result = self.legacy_parser.parse_player_info(
                self.structured_parser._create_legacy_entry(line)
            )
            if legacy_result:
                # Convert legacy result to structured format
                return self._convert_legacy_player_info(legacy_result)
        
        return None
    
    def _create_legacy_entry(self, line: str):
        """Create a legacy ESOLogEntry for compatibility"""
        from eso_log_parser import ESOLogEntry
        return ESOLogEntry.parse(line)
    
    def _convert_legacy_player_info(self, legacy_result):
        """Convert legacy PlayerInfoEntry to structured format"""
        # This would convert the legacy format to the new structured format
        # Implementation depends on the legacy structure
        pass


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    """
    Example usage of the structured log parser
    """
    
    # Example log lines from actual encounter logs
    example_lines = [
        '5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"',
        '5,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
        '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
        '2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T',
        '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
        '40603,BEGIN_COMBAT',
        '49372,END_COMBAT',
    ]
    
    parser = ESOLogStructureParser()
    
    for line in example_lines:
        parsed = parser.parse_line(line)
        if parsed:
            print(f"Parsed {type(parsed).__name__}: {parsed}")
        else:
            print(f"Failed to parse: {line}")
