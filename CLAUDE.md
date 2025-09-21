# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ESO (Elder Scrolls Online) encounter log analyzer CLI tool that:
- Tails ESO encounter logs in real-time
- Analyzes combat encounters after each combat ends
- Extracts character information, gear setups, and abilities
- Provides gear set identification and subclass inference

## Project Architecture

### Core Components
- **Log Parser**: Processes ESO encounter log format (comma-separated values with timestamps)
- **Combat Tracker**: Identifies combat start/end boundaries from log events
- **Character Analyzer**: Extracts player handles, abilities, and gear from combat data
- **Set Database Integration**: Uses LibSets data for gear set identification
- **Output Formatter**: Displays character analysis summaries

### Data Sources
- **ESO Encounter Logs**: Real-time combat logs from the game client
- **LibSets Database**: Community-maintained database of gear sets (https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets/Data)
- **Log Format Reference**: ESO log parsing documentation (https://github.com/sheumais/logs/blob/master/parser/README.md)

### Log Format Structure
ESO encounter logs use comma-separated format with:
- Timestamp (milliseconds)
- Event type (COMBAT_EVENT, UNIT_ADDED, ABILITY_INFO, etc.)
- Player/unit states (health, magicka, stamina)
- Ability and equipment tracking
- Character handles and anonymization flags

## Development Commands

### Testing with Sample Data
```bash
# Use example log for testing
tail -f example-log/Encounter.log

# Simulate live logging by self-tailing (as mentioned in description.md)
# This mode should replay the log to simulate real-time logging
```

### Key Implementation Areas

#### Log Parsing
- Handle comma-separated log format with varying field counts
- Parse timestamps for combat timing
- Extract UNIT_ADDED events for player information
- Track ABILITY_INFO and equipment changes

#### Combat Detection
- Identify combat start/end boundaries from log events
- Group related combat events into encounters
- Handle multiple players in group combat scenarios

#### Character Analysis
- Extract character handles (with anonymization support)
- Infer subclass from ability usage patterns
- Parse gear equipped during combat
- Identify set bonuses from equipped items

#### Set Database Integration
- Parse LibSets Lua data files for set information
- Match equipped items to known gear sets
- Calculate set bonuses based on equipped pieces

## Testing Strategy

### Sample Data
- `example-log/Encounter.log`: Real ESO encounter log (48MB) for comprehensive testing
- Contains various combat scenarios, player interactions, and gear changes

### Simulation Mode
Implement a self-tailing mode that replays the sample log to simulate live logging conditions for development and testing.

## Platform Considerations

Target platforms: macOS/Windows
- Cross-platform file tailing implementation
- Handle different log file locations per platform
- Consider real-time file monitoring approaches (inotify/kqueue)

## Output Requirements

For each completed combat encounter, display:
- Character handles (or "anon" if anonymized)
- Inferred subclass setup based on abilities used
- Bar abilities observed during combat
- Summary of equipped gear and identified sets