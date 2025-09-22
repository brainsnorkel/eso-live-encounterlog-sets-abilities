# Changelog

All notable changes to the ESO Live Encounter Log Sets & Abilities Analyzer will be documented in this file.

## [0.1.11] - 2025-01-22

### Fixed
- **GitHub Actions**: Fixed automated release creation by enabling proper repository permissions
- **Release Automation**: GitHub Actions now automatically creates releases with installer artifacts
- **Workflow Reliability**: Improved workflow stability and error handling

### Technical
- Enabled "Read and write permissions" for GitHub Actions workflows
- Automated release creation now works without manual intervention
- All platform installers are automatically attached to releases

## [0.1.10] - 2025-01-22

### Fixed
- **Default Behavior**: Changed default behavior to wait for log file instead of exiting immediately
- **User Experience**: Tool now waits for encounter log file to appear by default with status updates every minute
- **Command Line Options**: Replaced `--wait-for-file` with `--no-wait` flag (inverted logic for better UX)

### Enhanced
- **Intuitive Behavior**: Users no longer need to remember special flags to wait for log files
- **Better Defaults**: More user-friendly default behavior for new users
- **Clearer Options**: Simplified command line interface with more intuitive flag names

### Technical
- Inverted wait-for-file logic to make waiting the default behavior
- Updated all documentation to reflect new default behavior
- Improved error messages and user guidance

## [0.1.9] - 2025-01-22

### Added
- **Wait for File Option**: `--wait-for-file` flag to wait for log file to appear if it doesn't exist
- **Read All Then Tail Option**: `--read-all-then-tail` flag to read entire log file from beginning then continue tailing
- **Status Updates**: Print status updates every minute while waiting for log file to appear
- **Enhanced Log File Handling**: Improved file monitoring with better error handling and user guidance

### Enhanced
- **Command Line Options**: More flexible monitoring options for different use cases
- **User Experience**: Better status messages and progress indicators
- **Documentation**: Updated README with usage examples for new options
- **Troubleshooting**: Added guidance for common file not found scenarios

### Technical
- Added `_wait_for_file()` helper function with periodic status updates
- Enhanced `LogFileHandler` class with `read_all_then_tail` parameter
- Added `_process_entire_file()` method for reading complete log files
- Improved file position tracking for seamless tailing after full read
- Updated command line interface with new flags and help text

## [0.1.8] - 2025-01-22

### Added
- **Resource Tracking**: Real-time monitoring of player maximum health, magicka, and stamina values
- **Resource Display**: Shows resource values in player build information (e.g., "M:25k S:30k H:20k")
- **Health Anomaly Detection**: Highlights unusual health values (below 19k or above 50k) in red
- **Resource Reset**: Automatic resource tracking reset between encounters for accurate per-encounter analysis

### Enhanced
- **Player Information**: More comprehensive player statistics including resource pools
- **Visual Indicators**: Color-coded health values for quick identification of unusual builds
- **Combat Analysis**: Better understanding of player builds through resource distribution

### Technical
- Added `update_resources()` and `reset_resources()` methods to PlayerInfo class
- Enhanced BEGIN_CAST event parsing to extract resource information from sourceUnitState
- Added `_parse_and_update_player_resources()` for resource data processing
- Improved resource display formatting with rounded values (e.g., "25.5k" instead of "25500")

## [0.1.7] - 2025-01-22

### Enhanced
- **Improved Log Processing**: Enhanced log file parsing and analysis capabilities
- **Better Error Handling**: Improved error handling and edge case management
- **Code Quality**: Refactored and improved code structure for better maintainability

### Technical
- Significant code improvements across multiple modules
- Enhanced database integration and set detection
- Improved analyzer performance and reliability

## [0.1.6] - 2025-01-22

### Added
- **Intelligent Auto-Detection**: Automatically detects most likely ESO log directory based on host OS (Windows, macOS, Linux)
- **Enhanced Status Messages**: Clear, informative messages about what the tool is doing and where it's looking
- **Directory Creation**: Automatically creates log directories if they don't exist
- **Easy Stalking Integration**: Comprehensive documentation and references to Easy Stalking addon for automatic logging
- **Improved User Experience**: Better guidance for users on enabling encounter logging
- **Zone Rewind Functionality**: Automatically detects and handles scenarios where the tool starts after a zone change

### Enhanced
- **Cross-Platform Detection**: Smart detection of ESO installation paths for Windows, macOS (native/Wine), and Linux (Wine)
- **Status Reporting**: Real-time feedback on log file detection and monitoring status
- **Error Handling**: Better error messages and guidance when log files aren't found
- **Documentation**: Added troubleshooting section with common issues and solutions
- **Zone Context Recovery**: Automatically recovers zone context when starting monitoring after zone changes

### Removed
- **Resource Categorization**: Removed magicka/health/stamina resource type categorization from player build displays
- **Individual Major Courage Uptime**: Removed redundant individual Major Courage uptime calculations after player reports

### Technical
- Added `_get_most_likely_log_directory()` for OS-specific path detection
- Added `_get_host_type_description()` for user-friendly OS identification
- Enhanced main function with detailed status reporting
- Improved directory and file existence checking with automatic directory creation
- Added zone history tracking with `_add_zone_to_history()` and `_rewind_to_last_zone()`
- Enhanced LogFileHandler with `_initialize_zone_history()` for startup zone detection
- Added `_process_log_file_from_position()` for efficient log file scanning
- Removed resource tracking fields and methods from PlayerInfo class
- Simplified player build display format by removing resource type categorization
- Removed individual Major Courage uptime display code from player report section

## [0.1.5] - 2025-01-22

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
