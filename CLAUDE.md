# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cross-platform CLI tool for analyzing Elder Scrolls Online (ESO) encounter logs in real-time. The tool monitors ESO encounter log files and analyzes combat data to extract player information, abilities, gear sets, and skill line builds.

## Key Commands

### Development & Testing
```bash
# Run the analyzer with auto-detection
python3 eso_analyzer.py

# Run with specific log file
python3 eso_analyzer.py --log-file "path/to/Encounter.log"

# Test mode with sample data
python3 eso_analyzer.py --test-mode

# Test mode with faster replay
python3 eso_analyzer.py --test-mode --replay-speed 1000

# Run test suites
python3 test_analyzer.py
python3 test_log_parser.py

# Install dependencies
pip install -r requirements.txt
```

### Building & Distribution
```bash
# Build standalone executables
python3 build_installers.py

# Build specific platform
python3 build_installers.py --platform windows
python3 build_installers.py --platform macos

# Create distributable packages
python3 setup.py sdist bdist_wheel
```

## Architecture Overview

### Core Components

1. **eso_analyzer.py** - Main CLI application with file watching and real-time analysis
2. **eso_log_parser.py** - Robust CSV parser for ESO encounter log format with comprehensive event handling
3. **eso_sets.py** - Skill line detection and subclass analysis engine with comprehensive ability mappings
4. **gear_set_database.py** - LibSets integration for gear set identification from Excel database

### Data Flow Architecture

```
ESO Game → Encounter.log → File Watcher → Log Parser → Analysis Engine → Console Output
                                            ↓
                           Gear Set Database ← LibSets Excel File
                                            ↓
                           Skill Line Analyzer ← Ability Mappings
```

### Key Design Patterns

- **Event-driven monitoring**: Uses watchdog for real-time file system monitoring
- **Modular parsing**: Separate parsers for different log entry types (UNIT_ADDED, ABILITY_INFO, PLAYER_INFO, etc.)
- **Cache-based analysis**: Ability ID to name mapping with persistent caching
- **Database integration**: Excel-based gear set database (LibSets) with pandas processing

## Critical Implementation Details

### Log File Format Handling
- ESO logs use complex CSV format with nested arrays and quoted fields
- Parser handles special characters, unicode names, and malformed entries gracefully
- Events are timestamped with Unix timestamps for precise combat timing

### Gear Set Detection
- Uses LibSets_SetData.xlsm Excel file for comprehensive gear set database (634+ sets)
- Maps item IDs to set names through Excel sheet parsing
- Handles all 13 ESO gear slots (missing BACKUP_OFF slot is a game limitation)

### Skill Line Analysis
- Comprehensive ability-to-skill-line mappings based on UESP data
- Supports all class skill lines (Herald, Assassination, Winter's Embrace, etc.)
- Detects weapon and guild skill lines for complete build analysis

### Real-time Combat Detection
- Uses BEGIN_COMBAT/END_COMBAT events (not timeout-based)
- Zone-based reporting with player data persistence across multiple combats
- Automatic zone detection and rewind capability for mid-zone startup

## Testing Framework

### Test Coverage
- **test_analyzer.py**: Integration tests for full analyzer workflow
- **test_log_parser.py**: Unit tests for robust log parsing with real ESO data
- Uses 48MB sample log file from example-log/Encounter.log

### Test Data Sources
- Real ESO encounter log data with multiple players and complex gear
- Sample covers various ability types, gear sets, and combat scenarios
- Includes edge cases like anonymous players and special characters

## Development Considerations

### Cross-platform Compatibility
- Auto-detects ESO log locations on Windows, macOS, and Linux (Wine)
- Handles different file path formats and Wine directory structures
- Uses colorama for cross-platform colored console output

### Performance Optimization
- Efficient file watching with debouncing for large log files
- Cached ability lookups to avoid repeated Excel parsing
- Streaming log processing for real-time analysis

### Error Handling
- Graceful handling of malformed log entries
- Fallback mechanisms for missing gear set data
- Auto-recovery from file access issues during monitoring

## Data Dependencies

### External Data Sources
- **setsdb/LibSets_SetData.xlsm**: Gear set database (634+ sets)
- **example-log/**: Sample ESO encounter logs for testing
- **ESO Game Logs**: Real-time encounter logs from %USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\

### Version Management
- Version info in version.py (__version__ = "0.1.6")
- Semantic versioning for releases
- Changelog tracking in CHANGELOG.md

## Build System

### PyInstaller Configuration
- Standalone executables for Windows and macOS
- Includes data files (setsdb/, example-log/) in distribution
- Icon support for branded executables
- Cross-platform installer creation

### Distribution Packages
- ZIP installers for each platform
- Includes run scripts (run.bat, run.sh) for convenience
- Self-contained with all dependencies bundled