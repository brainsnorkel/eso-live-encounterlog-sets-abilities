# ESO Live Encounter Log Sets & Abilities Analyzer

A cross-platform CLI tool for monitoring Elder Scrolls Online encounter logs in real-time and analyzing combat encounters to extract player information, abilities, gear sets, and subclass builds.

## Features

- **Real-time Log Monitoring**: Continuously monitors ESO encounter logs using file system watchers
- **Comprehensive Player Analysis**: Extracts player names, abilities, and gear information
- **Skill Line Detection**: Analyzes equipped abilities to infer skill lines (e.g., "Herald/Assassination/Winter's")
- **Front/Back Bar Abilities**: Distinguishes between front bar and back bar equipped abilities
- **Gear Set Identification**: Identifies gear sets using LibSets database integration
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

## Usage

### Live Monitoring

**Auto-detect ESO log file:**
```bash
python3 eso_analyzer.py
```

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
Zone: Vateshran Hollows (VETERAN)

=== COMBAT ENDED (Vateshran Hollows) | Duration: 196.4s | Players: 1 ===

@brainsnorkel Herald/Assassination/Winter's
  Bar 1: Cephaliarch's Flail, Exhausting Fatecarver, Quick Cloak, Concealed Weapon, Merciless Resolve, Incapacitating Strike
  Bar 2: Blockade of Frost, Arctic Blast, Inspired Scholarship, Elemental Susceptibility, Echoing Vigor, Northern Storm
  Equipment: 1pc Slimecraw, 1pc Velothi Ur-Mage's Amulet, 3pc Perfected Bahsei's Mania, 2pc Bahsei's Mania, 1pc Perfected Crushing Wall
```

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

### Zone-based Reporting

- **Zone Changes**: Reports when entering new zones
- **Combat Events**: Tracks BEGIN_COMBAT and END_COMBAT events
- **Player Persistence**: Maintains player data across multiple combats within a zone

## Requirements

- Python 3.7+
- ESO encounter logging enabled in-game
- Dependencies listed in `requirements.txt`:
  - `watchdog` - File system monitoring
  - `click` - Command-line interface
  - `pandas` - Excel file processing
  - `openpyxl` - Excel file reading
  - `colorama` - Cross-platform colored terminal output

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
    └── LibSets_SetData.xlsx # LibSets gear set data
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

- **LibSets**: Gear set database by Baertram
- **UESP**: Elder Scrolls Online wiki for authoritative skill line information
- **ESO Community**: For encounter log format documentation