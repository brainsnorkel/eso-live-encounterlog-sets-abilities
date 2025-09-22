# ESO Live Encounter Log Sets & Abilities Analyzer

A cross-platform CLI tool for monitoring Elder Scrolls Online encounter logs in real-time and analyzing combat encounters to extract player information, abilities, gear sets, and subclass builds.

## Features

- **Real-time Log Monitoring**: Continuously monitors ESO encounter logs using file system watchers
- **Comprehensive Player Analysis**: Extracts player names, abilities, and gear information
- **Skill Line Detection**: Analyzes equipped abilities to infer skill lines (e.g., "Herald/Assassination/Winter's")
- **Front/Back Bar Abilities**: Distinguishes between front bar and back bar equipped abilities
- **Gear Set Identification**: Identifies gear sets using LibSets database integration
- **Accurate Timestamps**: Uses Unix timestamps from log data for precise combat start times
- **Group Buff Detection**: Monitors critical group buffs (Major Courage, Major Force, Major Slayer)
- **Individual Buff Uptime**: Tracks Major Courage uptime for each player
- **Damage Analysis**: Shows damage percentages and sorts players by contribution
- **Resource Analysis**: Displays dominant resource (Magicka/Stamina/Health) for each player
- **Zone-based Reporting**: Generates reports for each combat encounter within zones
- **Cross-platform**: Works on macOS and Windows
- **Test Mode**: Replay sample logs for development and testing

## Installation

### Option 1: Standalone Installers (Recommended)

Download the latest release for your platform:
- **Windows**: `eso-analyzer-windows-installer.exe`
- **macOS**: `eso-analyzer-macos-installer.dmg`

### Option 2: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/christophergentle/eso-live-encounterlog-sets-abilities.git
   cd eso-live-encounterlog-sets-abilities
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make the script executable (macOS/Linux):**
   ```bash
   chmod +x eso_analyzer.py
   ```

### Enable ESO Encounter Logging

**Important**: ESO encounter logging must be enabled in-game for this tool to work.

#### Automatic Logging (Recommended)
Install the **[Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html)** addon to automatically start/stop encounter logging based on content type:
- Automatically logs in Dungeons, Trials, Arenas, Battlegrounds, etc.
- Visual on-screen indicator when logging is active
- Configurable for different content types
- `/ezlog` chat command for manual control

#### Manual Logging
Alternatively, you can manually enable encounter logging:
- In-game: `/encounterlog` (toggles logging on/off)
- Or enable in Settings → Combat → Combat Logging

## Usage

### Live Monitoring

**Auto-detect ESO log file (Recommended):**
```bash
python3 eso_analyzer.py
```
The tool automatically detects the most likely ESO log directory based on your operating system:
- **Windows**: `%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\`
- **macOS**: `~/Documents/Elder Scrolls Online/live/Logs/` or Wine location
- **Linux**: `~/.wine/drive_c/users/Public/Documents/Elder Scrolls Online/live/Logs/`

**Specify log file manually:**
```bash
python3 eso_analyzer.py --log-file "/path/to/ESO/Logs/Encounter.log"
```

### Test Mode

**Replay sample log file:**
```bash
python3 eso_analyzer.py --test-mode
```

**Replay at different speeds:**
```bash
python3 eso_analyzer.py --test-mode --replay-speed 1000  # 1000x speed
```

## Command Line Options

- `--log-file`, `-f`: Path to ESO encounter log file
- `--test-mode`, `-t`: Test mode using sample log file
- `--replay-speed`, `-s`: Replay speed multiplier for test mode (default: 100x)

## ESO Log File Locations

The tool automatically searches for ESO encounter logs in common locations:

**Windows:**
- `%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\Encounter.log`
- `%USERPROFILE%\Documents\Elder Scrolls Online\Logs\Encounter.log`

**macOS (via Wine):**
- `~/Documents/Elder Scrolls Online/live/Logs/Encounter.log`
- `~/.wine/drive_c/users/Public/Documents/Elder Scrolls Online/live/Logs/Encounter.log`

## Output Format

When a combat encounter ends, the tool displays:

```
=== ZONE CHANGED ===
Zone: Coral Aerie (VETERAN)

2025-08-21 08:42:06 (Coral Aerie) | Duration: 8.8s | Players: 4 | Est. DPS: 131,062 | Deaths: 0 | Target: Yaghra Spewer
Group Buffs: Major Courage: ✅ | Major Force: ❌ | Major Slayer: ✅

@brainsnorkel Beam Hal Herald/Ass/Winter Mag (87.2%)
  Bar 1: Cephaliarch's Flail, Exhausting Fatecarver, Quick Cloak, Concealed Weapon, Magical Banner, Incapacitating Strike
  Bar 2: Blockade of Frost, Winter's Revenge, Arctic Blast, Inspired Scholarship, Magical Banner, Northern Storm
  Equipment: 1pc Slimecraw, 1pc Velothi Ur-Mage's Amulet, 5pc Tide-Born Wildstalker, 3pc Perfected Bahsei's Mania, 2pc Bahsei's Mania, 1pc Perfected Crushing Wall
  Major Courage Uptime: 95.2%

anon Aedric/Ass/Herald Stam (4.3%)
  Bar 1: Pragmatic Fatecarver, Cephaliarch's Flail, Blazing Spear, Quick Cloak, Shocking Banner, Soul Harvest
  Bar 2: Barbed Trap, Merciless Resolve, Inspired Scholarship, Elemental Blockade, Shocking Banner, The Languid Eye
  Equipment: 1pc Slimecraw, 1pc Velothi Ur-Mage's Amulet, 6pc Order's Wrath, 5pc Tide-Born Wildstalker
```

### Output Components

- **Timestamp**: Accurate local date/time when combat started (using Unix timestamps from log data)
- **Zone & Duration**: Combat location and duration in seconds
- **Player Count & DPS**: Number of players and estimated group DPS
- **Death Counter**: Total deaths since entering the zone
- **Target**: Primary enemy that received the most damage events
- **Group Buffs**: Visual indicators (✅/❌) for critical group buffs in encounters with 3+ players
- **Player Info**: Character name, skill lines, dominant resource, and damage percentage
- **Ability Bars**: Front bar and back bar equipped abilities
- **Equipment**: Gear sets with piece counts and set names
- **Buff Uptime**: Major Courage uptime percentage for each player

## Analysis Features

### Skill Line Detection

The tool analyzes equipped abilities to determine skill lines using UESP as the authoritative source:
- **Class Skill Lines**: Herald of the Tome, Assassination, Winter's Embrace, etc.
- **Weapon Skill Lines**: Destruction Staff, Restoration Staff, Two Handed, etc.
- **Guild Skill Lines**: Fighters Guild, Mages Guild, Undaunted, etc.

### Gear Set Identification

The tool identifies gear sets by:
- **Set ID Mapping**: Uses LibSets database to map set IDs to set names
- **Comprehensive Database**: Includes 634+ gear sets from LibSets
- **Accurate Detection**: Shows actual equipped gear pieces with set names

### Buff Detection & Analysis

- **Group Buff Monitoring**: Tracks critical group buffs (Major Courage, Major Force, Major Slayer)
- **Visual Indicators**: Uses ✅/❌ emojis for clear buff status display
- **Individual Uptime**: Calculates Major Courage uptime percentage for each player
- **Buff Tracking**: Monitors buff applications and removals throughout encounters

### Damage & Resource Analysis

- **Damage Percentages**: Shows each player's contribution to total damage
- **Player Sorting**: Displays players in descending order by damage contribution
- **Resource Detection**: Identifies dominant resource (Magicka/Stamina/Health) for each player
- **DPS Calculation**: Estimates group DPS based on total damage and combat duration

### Zone-based Reporting

- **Zone Changes**: Reports when entering new zones
- **Combat Events**: Tracks BEGIN_COMBAT and END_COMBAT events with accurate timestamps
- **Player Persistence**: Maintains player data across multiple combats within a zone
- **Death Tracking**: Counts total deaths since entering each zone

## Requirements

- Python 3.7+
- ESO encounter logging enabled in-game
- Dependencies listed in `requirements.txt`:
  - `watchdog` - File system monitoring
  - `click` - Command-line interface
  - `pandas` - Excel file processing
  - `openpyxl` - Excel file reading
  - `colorama` - Cross-platform colored terminal output

## Troubleshooting

### Common Issues

#### "Encounter.log not found"
- Ensure ESO encounter logging is enabled in-game
- Use **[Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html)** addon for automatic logging
- Check that you're in the correct log directory
- Verify the log file exists and is accessible

#### "No combat encounters detected"
- Make sure you're actively fighting in ESO
- Check that the log file is being updated (file modification time)
- Try using Test Mode to verify the application is working

#### "Unknown" builds or abilities
- Some abilities may not be recognized if they're new or rare
- The analyzer requires ABILITY_INFO events before PLAYER_INFO for complete analysis
- Anonymous players (no abilities observed) will show as "unknown"

#### Tool started after zone change
- The analyzer automatically detects when you start monitoring after entering a zone
- It scans recent log entries to find the last zone change and rewinds to that zone
- Combat events will be properly associated with the correct zone
- Look for "Scanning recent log entries for zone changes..." message on startup

## Project Structure

```
eso-live-encounterlog-sets-abilities/
├── eso_analyzer.py          # Main CLI application
├── eso_log_parser.py        # Robust log parser with comprehensive CSV handling
├── eso_sets.py              # Skill line mappings and analysis
├── gear_set_database.py     # LibSets database integration
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── example-log/            # Sample ESO encounter log for testing
│   └── Encounter.log      # Sample log file
└── setsdb/                 # Gear set database
    └── LibSets_SetData.xlsm # LibSets gear set data
```

## Testing

The project includes comprehensive testing capabilities:

```bash
# Test with sample data
python3 eso_analyzer.py --test-mode

# Test at high speed
python3 eso_analyzer.py --test-mode --replay-speed 1000

# Test specific zones (Vateshran, Maelstrom, etc.)
python3 eso_analyzer.py --test-mode --replay-speed 1000 | grep -A 10 "Vateshran\|Maelstrom"
```

## Key Improvements

### Recent Updates

- **Combat Timeout Removal**: Eliminated unreliable timeout-based combat detection
- **Explicit Event Handling**: Uses BEGIN_COMBAT/END_COMBAT events for accurate combat tracking
- **Enhanced Skill Line Detection**: Comprehensive ability-to-skill-line mappings based on UESP
- **LibSets Integration**: Full gear set database with 634+ sets
- **Improved Display Format**: Cleaner, more concise output format
- **Zone-based Reporting**: Proper zone change handling and player data persistence

### Technical Features

- **Robust CSV Parsing**: Handles complex ESO log format with nested arrays
- **Ability Cache**: Efficient ability ID to name mapping
- **Gear Set Database**: Excel-based gear set identification
- **Cross-platform Compatibility**: Works on Windows and macOS
- **Real-time Processing**: File system monitoring for live log analysis

## Limitations

- **Ability Cache Dependency**: Requires ABILITY_INFO events before PLAYER_INFO for complete analysis
- **Set Database**: Limited to sets available in LibSets database
- **Anonymous Players**: Cannot identify builds for players with no observed abilities
- **Gear Slots**: ESO logs track 13 gear slots (missing backup off-hand weapon slot)

## Future Enhancements

- Web interface for real-time monitoring
- Historical encounter database
- Damage/healing number parsing
- Advanced build analysis
- Integration with ESO addons

## Contributing

Contributions are welcome! Areas of interest:
- Expanding skill line mappings
- Improving gear set detection
- Adding more sophisticated analysis
- Cross-platform testing and compatibility

## License

This project is for educational and research purposes. ESO game data belongs to ZeniMax Online Studios.

## Acknowledgments

This project builds upon and integrates several excellent community resources:

- **[LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets)**: Comprehensive gear set database by Baertram, providing the foundation for accurate gear set identification with 634+ sets
- **[ESO Log Tool](https://github.com/sheumais/logs)**: Desktop log file handler for TESO by sheumais, which provided valuable insights into ESO log format parsing and processing techniques
- **UESP**: Elder Scrolls Online wiki for authoritative skill line information and ability classifications
- **ESO Community**: For encounter log format documentation and testing feedback

Special thanks to the ESO community for their continued support and feedback in developing this tool.