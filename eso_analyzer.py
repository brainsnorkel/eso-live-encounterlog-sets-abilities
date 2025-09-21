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

class CombatEncounter:
    """Represents a single combat encounter."""

    def __init__(self):
        self.start_time: int = 0
        self.end_time: int = 0
        self.players: Dict[str, PlayerInfo] = {}  # Keyed by short unit ID
        self.abilities_used: Dict[str, Set[str]] = defaultdict(set)
        self.in_combat = False

    def add_player(self, unit_id: str, name: str, handle: str):
        """Add a player to this encounter."""
        self.players[unit_id] = PlayerInfo(unit_id, name, handle)

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

class ESOLogAnalyzer:
    """Main analyzer class for processing ESO encounter logs."""

    def __init__(self):
        self.current_encounter: Optional[CombatEncounter] = None
        self.ability_cache: Dict[str, str] = {}  # ability_id -> ability_name
        self.gear_cache: Dict[str, str] = {}  # gear_item_id -> gear_set_name
        self.current_zone: Optional[str] = None  # Track current zone name
        self.subclass_analyzer = ESOSubclassAnalyzer()
        self.set_database = ESOSetDatabase()
        
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


    def _handle_unit_added(self, entry: ESOLogEntry):
        """Handle UNIT_ADDED events to track players."""
        # UNIT_ADDED format: unit_id, PLAYER, F/T, unknown, unknown, F/T, unknown, unknown, "name", "@handle", ...
        if len(entry.fields) >= 10 and entry.fields[1] == "PLAYER":
            unit_id = entry.fields[0]
            name = entry.fields[8] if len(entry.fields) > 8 else ""
            handle = entry.fields[9] if len(entry.fields) > 9 else ""

            # Only add players if we have a current encounter (zone has been set)
            if self.current_encounter:
                # Clean up name and handle (remove quotes if present)
                clean_name = name.strip('"') if name else ""
                clean_handle = handle.strip('"') if handle else ""

                self.current_encounter.add_player(unit_id, clean_name, clean_handle)

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
            
            # Reset all tracking - create new encounter for this zone
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

    def _handle_begin_combat_event(self, entry: ESOLogEntry):
        """Handle BEGIN_COMBAT events to start combat tracking."""
        # BEGIN_COMBAT format: timestamp,BEGIN_COMBAT (no additional data)
        
        # Ensure we have an encounter to work with
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
        
        # Mark combat as active and set start time
        self.current_encounter.in_combat = True
        if not self.current_encounter.start_time:
            self.current_encounter.start_time = entry.timestamp

    def _handle_end_combat_event(self, entry: ESOLogEntry):
        """Handle END_COMBAT events to print player reports."""
        # END_COMBAT format: timestamp,END_COMBAT (no additional data)
        
        # Show combat reports if there are any players
        if self.current_encounter and self.current_encounter.players:
            # End current encounter if active and display results
            if self.current_encounter.players:
                self.current_encounter.end_time = entry.timestamp
                self._display_encounter_summary(self.current_zone)
        
        # Reset combat tracking but keep players for next encounter
        if self.current_encounter:
            self.current_encounter.in_combat = False

    def _handle_begin_cast(self, entry: ESOLogEntry):
        """Handle BEGIN_CAST events."""
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

        if not self.current_encounter.in_combat:
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

            # Only track GAINED effects to avoid spam, and only from valid source units
            if (effect_type == "GAINED" and source_unit_id != "0" and
                ability_id in self.ability_cache):
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(source_unit_id, ability_name)

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

        # Update the combat ended header with duration and players info
        if zone_name:
            print(f"{Fore.RED}=== COMBAT ENDED ({zone_name}) | Duration: {duration:.1f}s | Players: {players_count} ==={Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}=== COMBAT ENDED | Duration: {duration:.1f}s | Players: {players_count} ==={Style.RESET_ALL}")

        for player in self.current_encounter.players.values():
            # Use equipped abilities from PLAYER_INFO
            abilities_to_analyze = player.equipped_abilities
            
            # Analyze subclass and build first to create the title line
            analysis = None
            if abilities_to_analyze:
                analysis = self.subclass_analyzer.analyze_subclass(abilities_to_analyze)
            
            # Create the title line: @playername Skill Lines
            title_parts = [player.get_display_name()]
            if analysis and analysis['confidence'] > 0.1:
                if analysis['skill_lines']:
                    # Extract first word of each skill line
                    first_words = [skill_line.split()[0] for skill_line in analysis['skill_lines']]
                    skill_lines_str = '/'.join(first_words)
                    title_parts.append(skill_lines_str)
                else:
                    title_parts.append("unknown")
            else:
                title_parts.append("unknown")
            
            print(f"\n{Fore.GREEN}{' '.join(title_parts)}{Style.RESET_ALL}")
            
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
                    # Count gear pieces by set
                    set_counts = {}
                    for slot, gear_item in player.gear.items():
                        if len(gear_item) > 6:  # Make sure we have enough elements
                            set_id = str(gear_item[6])  # Set ID is at position 6
                            set_name = gear_set_db.get_set_name_by_set_id(set_id)
                            if set_name:
                                set_counts[set_name] = set_counts.get(set_name, 0) + 1
                    
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
                    print(f"  Equipment: {', '.join(equipment_parts)}")
                elif player.gear:
                    print(f"  Equipment: {len(player.gear)} items (sets unknown)")
                else:
                    print(f"  Equipment: No data")
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