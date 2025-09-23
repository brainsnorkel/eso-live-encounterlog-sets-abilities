# Changelog

All notable changes to the ESO Live Encounter Log Sets & Abilities Analyzer will be documented in this file.

## [0.1.17] - 2025-01-22

### Fixed
- **Major Slayer Tracking**: Added support for both ability IDs (93120 and 931200) to properly track Major Slayer buff
- **Windows Build Error**: Fixed `ModuleNotFoundError: No module named gear_set_database_optimised` by updating PyInstaller spec file
- **Nunatak Monster Set**: Added comprehensive Nunatak variations to prevent incorrect red highlighting as incomplete 5-piece set

### Changed
- Updated PyInstaller spec file to include `gear_set_database_optimized` in hidden imports
- Updated GitHub Actions workflow to use spec file instead of command-line PyInstaller
- Added gear set data files to PyInstaller datas configuration

## [0.1.14] - 2025-01-22

### Enhanced
- **CLI Consistency**: Renamed `--scan-all-then-stop` to `--read-all-then-stop` for consistency with `--read-all-then-tail`
- **Help Text**: Updated help descriptions to use "Read mode" instead of "Scan mode" for clarity

### Fixed
- **File Position Tracking**: Resolved `OSError: telling position disabled by next() call` in `--read-all-then-tail` mode
- **File Monitoring**: Improved file position tracking compatibility with watchdog file monitoring system

### Technical
- **File I/O**: Changed from `for line in f:` loop to `while True:` with `f.readline()` for proper position tracking
- **EOF Handling**: Added proper end-of-file detection for robust file processing

## [0.1.13] - 2025-01-22

### Enhanced
- **Taunt Ability Highlighting**: Added purple highlighting for taunt abilities to easily identify tanking abilities
- **Health Thresholds**: Updated health highlighting thresholds from 19k-50k to 18.5k-44.5k for better health pool identification
- **DPS Display**: Changed DPS percentage format from `(3.1%)` to `D:3.1%` for consistency with resource indicators
- **Resource Highlighting**: Bold and underline each player's highest max resource type (health, stamina, or magicka)
- **Visual Improvements**: Changed encounter summary line color from red to dark orange for better visual distinction

### Fixed
- **Color Bleeding**: Fixed purple taunt highlighting that was affecting following text color
- **Variable Scope**: Resolved UnboundLocalError for `dps_str` variable when players had no damage data
- **Error Handling**: Improved robustness for edge cases in player data processing

### Technical
- **Taunt Detection**: Comprehensive lookup for 35+ taunt abilities across all classes and weapon lines
- **ANSI Colors**: Implemented dark orange color using `\033[38;5;208m` for encounter summaries
- **Resource Styling**: Applied bold and underline styling using ANSI escape codes for highest resources

## [Unreleased] - 2025-01-22

### Major Optimization
- **Gear Set Database**: Implemented pre-build data generation system for optimal performance
- **Startup Speed**: ~10x faster startup by eliminating Excel parsing at runtime
- **Installer Size**: ~1.8MB smaller installers by removing XLSM file dependencies
- **Reliability**: Eliminated Excel file corruption and missing file issues
- **Build Process**: Added `generate_gear_data.py` pre-build step to extract gear set data

### Enhanced
- **Build Documentation**: Updated BUILD_WINDOWS.md with gear data generation requirements
- **README**: Added comprehensive build instructions and gear set update process
- **GitHub Actions**: Updated workflow to include gear data generation step
- **File Cleanup**: Removed unused LibSets_SetData.xlsx file from repository

### Technical
- **Data Generation**: `generate_gear_data.py` extracts 704 gear sets from XLSM to optimized Python structures
- **Optimized Database**: `gear_set_database_optimized.py` provides same API with pre-generated data
- **Generated Module**: `gear_set_data.py` contains optimized dictionaries for fast lookups
- **Build Integration**: All platforms now generate gear data before building executables
- **Dependency Reduction**: Removed pandas/Excel runtime dependencies from installers

## [0.1.12] - 2025-01-22

### Enhanced
- **Documentation**: Updated README with real output examples from actual encounter logs
- **Accuracy**: Fixed installer names to match actual release artifacts (.zip files)
- **Platform Support**: Added Linux support to cross-platform description
- **Output Format**: Corrected output components to reflect actual implementation

### Fixed
- **Installer Names**: Updated from fictional .exe/.dmg to actual .zip installer names
- **Output Examples**: Replaced fictional examples with real data from Coral Aerie, Selene's Web, and Vateshran Hollows
- **Feature Descriptions**: Ensured all documented features match actual implementation

### Technical
- Comprehensive documentation review and consistency verification
- Real encounter log analysis for accurate example generation
- Updated output format documentation to match current code behavior

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
