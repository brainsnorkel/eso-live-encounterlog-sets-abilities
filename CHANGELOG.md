# Changelog

All notable changes to the ESO Live Encounter Log Sets & Abilities Analyzer will be documented in this file.

## [0.1.4] - 2025-01-22

### Added
- **Intelligent Auto-Detection**: Automatically detects most likely ESO log directory based on host OS (Windows, macOS, Linux)
- **Enhanced Status Messages**: Clear, informative messages about what the tool is doing and where it's looking
- **Directory Creation**: Automatically creates log directories if they don't exist
- **Easy Stalking Integration**: Comprehensive documentation and references to Easy Stalking addon for automatic logging
- **Improved User Experience**: Better guidance for users on enabling encounter logging

### Enhanced
- **Cross-Platform Detection**: Smart detection of ESO installation paths for Windows, macOS (native/Wine), and Linux (Wine)
- **Status Reporting**: Real-time feedback on log file detection and monitoring status
- **Error Handling**: Better error messages and guidance when log files aren't found
- **Documentation**: Added troubleshooting section with common issues and solutions

### Technical
- Added `_get_most_likely_log_directory()` for OS-specific path detection
- Added `_get_host_type_description()` for user-friendly OS identification
- Enhanced main function with detailed status reporting
- Improved directory and file existence checking with automatic directory creation

## [0.1.3] - 2025-01-22

### Added
- **Unix Timestamp Integration**: Accurate combat start times using Unix timestamps from BEGIN_LOG events
- **Group Buff Detection**: Monitors critical group buffs (Major Courage, Major Force, Major Slayer) with visual indicators
- **Individual Buff Uptime**: Tracks Major Courage uptime percentage for each player
- **Enhanced Visual Output**: Uses ✅/❌ emojis for prominent buff status display

### Enhanced
- **Combat Timing**: Fixed combat start time calculation to prioritize BEGIN_COMBAT events over BEGIN_CAST events
- **Timestamp Accuracy**: Replaced file modification time estimation with precise Unix timestamp calculations
- **Buff Tracking**: Comprehensive buff application and removal monitoring throughout encounters
- **Output Formatting**: Improved combat report layout with better visual hierarchy

### Technical
- Added `_handle_begin_log_event()` for Unix timestamp extraction
- Enhanced `get_combat_start_time_formatted()` with Unix timestamp support
- Implemented buff tracking system with uptime calculations
- Added encounter finalization protection against post-combat timestamp overrides

## [0.1.2] - 2025-01-XX

### Enhanced
- Updated skill line mappings and aliases for improved accuracy
- Enhanced skill line detection with better subclass analysis logic
- Improved readability of skill line abbreviations in combat reports

### Technical
- Refined skill line detection algorithms for better build identification
- Enhanced ability-to-skill-line mapping accuracy

## [0.1.1] - 2025-01-XX

### Fixed
- Fixed player death tracking to only count actual player deaths, not enemy deaths
- Enhanced enemy filtering to exclude environmental hazards like 'Water', 'Fire', 'Trap', etc.
- Improved target selection with better fallback logic from damage tracking to health-based selection
- Removed unnecessary blank lines in combat report output for cleaner formatting

### Enhanced
- Added comprehensive filtering for pets, corpses, and non-combat entities
- Updated gear set database to use LibSets_SetData.xlsm for more accurate set information
- Enhanced skill line detection and aliases
- Improved combat encounter tracking and reporting accuracy

### Technical
- Added cross-platform installers (Windows, macOS, Linux) via GitHub Actions
- Improved enemy tracking logic with better validation
- Enhanced error handling and edge case management

## [0.1.0] - 2025-01-XX

### Added
- Initial release of ESO Live Encounter Log Sets & Abilities Analyzer
- Real-time monitoring of ESO encounter logs
- Comprehensive player analysis with skill line detection
- Front/back bar ability tracking
- Gear set identification using LibSets database
- Zone-based reporting system
- Cross-platform support (Windows, macOS)
- Test mode with sample log replay
- Comprehensive skill line mappings based on UESP
- Support for 634+ gear sets from LibSets database

### Features
- **Player Analysis**: Extracts player names, abilities, and gear information
- **Skill Line Detection**: Analyzes equipped abilities to infer skill lines (e.g., "Herald/Assassination/Winter's")
- **Gear Set Identification**: Uses LibSets database for accurate set identification
- **Zone Tracking**: Reports zone changes and maintains player data across encounters
- **Combat Event Handling**: Proper BEGIN_COMBAT/END_COMBAT event processing
- **Real-time Monitoring**: File system watchers for live log analysis
- **Test Mode**: Replay sample logs at various speeds for testing

### Technical Improvements
- **Robust CSV Parsing**: Handles complex ESO log format with nested arrays
- **Ability Cache System**: Efficient ability ID to name mapping
- **Combat Timeout Removal**: Eliminated unreliable timeout-based combat detection
- **Explicit Event Handling**: Uses BEGIN_COMBAT/END_COMBAT events for accurate combat tracking
- **Enhanced Skill Line Detection**: Comprehensive ability-to-skill-line mappings
- **LibSets Integration**: Full gear set database integration
- **Improved Display Format**: Cleaner, more concise output format

### Dependencies
- Python 3.7+
- watchdog (file system monitoring)
- click (command-line interface)
- pandas (Excel file processing)
- openpyxl (Excel file reading)
- colorama (cross-platform colored terminal output)

### Supported Platforms
- Windows 10/11
- macOS 10.14+
- Linux (experimental)

### Known Limitations
- Ability cache dependency on ABILITY_INFO events
- Limited to sets available in LibSets database
- Cannot identify builds for anonymous players
- ESO logs track 13 gear slots (missing backup off-hand weapon slot)

### Future Enhancements
- Web interface for real-time monitoring
- Historical encounter database
- Damage/healing number parsing
- Advanced build analysis
- Integration with ESO addons

### Acknowledgments
This project builds upon excellent community resources:
- **[LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets)** by Baertram for gear set database
- **[ESO Log Tool](https://github.com/sheumais/logs)** by sheumais for log parsing insights
- **UESP** for authoritative skill line information
