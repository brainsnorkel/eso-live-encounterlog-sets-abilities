# Changelog

All notable changes to the ESO Live Encounter Log Sets & Abilities Analyzer will be documented in this file.

## [0.2.4] - 2025-01-29

### Fixed
- **File Locking Removal**: Eliminated unnecessary file locking that could interfere with ESO's log writing process
- **Enhanced File Tailing**: Improved reliability for high-frequency log monitoring (tested up to 1ms intervals)
- **Gear Set Classification Fix**: Corrected "Tarnished Nightmare" from mythic to 5-piece set classification
- **Improved Temp File Cleanup**: Enhanced log splitting logic to prevent orphaned temporary files
- **High-Performance Monitoring**: Validated real-time processing of 48MB+ log files without data loss

### Technical Improvements
- **File Access Optimization**: Removed `threading.Lock()` from `LogFileMonitor` class for better ESO compatibility
- **Enhanced Cleanup Logic**: Improved `end_encounter()` method in `LogSplitter` to handle edge cases
- **Temp File Management**: Added conditions to delete orphaned temp files and files with minimal combat events
- **Performance Validation**: Successfully tested with simulator at 0.001-second intervals (1000Hz)

### Quality Assurance
- **High-Frequency Testing**: Validated tool performance with extreme data rates
- **Data Integrity**: Confirmed zero data loss during high-speed monitoring
- **ESO Compatibility**: Ensured tool doesn't interfere with ESO's log writing process
- **Real-World Validation**: Tested with actual encounter log data processing

## [0.2.3] - 2025-01-29

### Fixed
- **Report Buffer Management**: Fixed critical bug where all zone reports were starting with the same encounters
- **Zone-Specific Report Isolation**: Each zone report now contains only encounters from that specific zone
- **File Naming Conflicts**: Enhanced conflict resolution with content-based deduplication using MD5 hashing
- **END_LOG Inclusion**: Ensured split log files properly include END_LOG entries for complete log structure
- **Timestamp Format Consistency**: Fixed edge cases in timestamp conversion and zone start time handling

### Technical Improvements
- **Content-Based Deduplication**: Implemented MD5 hash comparison for file conflict resolution
- **Automatic Suffix Numbering**: Files with different content get automatic -1, -2, etc. suffixes
- **Report Buffer Clearing**: Proper buffer management prevents cross-zone contamination
- **Enhanced Test Coverage**: Added comprehensive tests for file naming conflicts, END_LOG inclusion, and report isolation
- **Simulator Enhancement**: Improved ESO logging simulator to better simulate real-world file I/O behavior

### Quality Assurance
- **Comprehensive Testing**: All 101 tests passing with robust validation of new features
- **Edge Case Handling**: Proper handling of zero timestamps, missing values, and file conflicts
- **Data Integrity**: Atomic file operations ensure data safety during concurrent access

## [0.2.2] - 2025-01-29

### Removed
- **Discord Copy Feature**: Removed keyboard 'c' press functionality for copying reports to clipboard with Discord formatting
- **Keyboard Input Handling**: Removed all keyboard input detection and terminal input handling
- **Clipboard Integration**: Removed pyperclip dependency and clipboard copy functionality
- **Discord Markdown Formatting**: Removed Discord-specific report formatting methods

### Technical Changes
- Removed `pynput>=1.7.6` and `pyperclip>=1.8.2` dependencies from requirements.txt
- Cleaned up Discord-related instance variables and imports
- Simplified codebase by removing unused keyboard and clipboard functionality
- Updated documentation to remove Discord copy feature references

## [0.2.1] - 2025-01-29

### Fixed
- **Timestamp Format Bug**: Fixed incorrect timestamp generation for report filenames that was causing fallback to current time
- **Zero Timestamp Handling**: Correctly handle zero timestamps (log start) in timestamp conversion
- **Zone Start Time Preservation**: Fixed bug where zone start time was being overwritten during report generation

### Technical Improvements
- Enhanced timestamp conversion logic to properly handle edge cases
- Improved file naming conflict resolution for split logs and reports
- Added comprehensive test coverage for timestamp format validation

## [0.2.0] - 2025-01-27

### Major Features
- **Combat-Based Zone Naming**: Split files and reports are now named after the zone where combat begins, not the initial zone
- **Zone-Based Report Consolidation**: Reports are consolidated per zone instead of per encounter for better organization
- **Enhanced Log File Detection**: Automatic detection of ESO log files in multiple Windows locations including OneDrive
- **Robust File Handling**: Atomic file operations with temporary files and proper cleanup for data safety

### Added
- **New Buff Tracking**: Added Lucent Echoes (LE) and Pearlescent Ward (PW) buff tracking
- **Report Saving**: Save encounter reports to files with zone-based naming
- **Auto-Split Logs**: Automatically split encounter logs into zone-specific files
- **Enhanced Diagnostics**: Comprehensive diagnostic output for troubleshooting
- **Default Behavior Explanation**: Clear explanation when no command-line arguments are provided

### Changed
- **Buff Display Format**: Removed ticks/crosses, parentheses, and pipe separators from buff status
- **Buff Labels**: Shortened to Mslayer, MForce, MCourage, PA, LE, PW
- **Duration Format**: Display fight durations in minutes:seconds format, rounded to nearest second
- **Fight Summary**: Removed "Duration:", changed "Est. DPS" to "GrpDPS", removed "Target:"
- **Discord Formatting**: Equipment display uses "5x" instead of "5pc" and "p" instead of "Perfected "
- **Vitality Display**: Always show vitality bonus without % or + symbols
- **Timestamp Handling**: Correct conversion from relative milliseconds to absolute Unix timestamps

### Fixed
- **Critical Parsing Issues**: Fixed timestamp extraction and field indexing in log entry parsing
- **Event Routing**: Added missing ZONE_CHANGED event routing to proper handlers
- **Field Indexing**: Corrected field access for UNIT_ADDED, ZONE_CHANGED, and other events
- **Combat Zone Detection**: Fixed logic to properly detect and name files after combat zone
- **File Handle Management**: Proper file closing and reopening for robust data handling
- **Race Conditions**: Added threading locks to prevent concurrent file access issues
- **Deadlock Prevention**: Fixed polling-based tailing deadlock issues

### Testing
- ✅ 76 comprehensive tests covering all functionality
- ✅ Log splitting with combat-based zone naming
- ✅ Report saving with zone-based consolidation
- ✅ Buff tracking and display formatting
- ✅ File operations and error handling
- ✅ Integration tests for complete workflows
- ✅ Regression tests for existing functionality

### Documentation
- ✅ Updated README.md with new command-line options and features
- ✅ Added comprehensive help output integration
- ✅ Updated TESTING.md with new test coverage
- ✅ Enhanced troubleshooting and usage examples

## [0.1.29] - 2025-01-26

### Added
- **Log Splitting Tests**: Comprehensive test suite for log splitting functionality (`test_log_splitting.py`)
- **Report Saving Tests**: Complete test coverage for report saving functionality (`test_report_saving.py`)
- **Integration Tests**: Full integration tests for log splitting and report saving (`test_log_splitting_integration.py`)

### Fixed
- **LogSplitter File Handling**: Fixed issue where file handles were not properly reopened after renaming
- **End Encounter Cleanup**: Fixed cleanup logic to always clear encounter state regardless of file handle status
- **Report Buffer Management**: Fixed report buffer clearing behavior in tests

### Testing
- ✅ 75 new tests covering log splitting and report saving functionality
- ✅ File operations: creation, naming, writing, closing, and cleanup
- ✅ Zone detection: zone-based file naming and difficulty handling
- ✅ Error handling: permission errors, directory creation, and edge cases
- ✅ Integration: complete workflows combining splitting and report saving
- ✅ All tests pass successfully

### Documentation
- ✅ Updated TESTING.md with new log splitting and report saving test documentation
- ✅ Added test coverage details and integration test scenarios

## [0.1.28] - 2025-01-26

### Verified
- **Damage Attribution**: Verified that damage attribution to players is working correctly
- **Pet Ownership Tracking**: Confirmed pet damage is properly attributed to their owners
- **Unit ID Matching**: Validated short/long unit ID matching for player identification
- **Combat Event Processing**: Verified damage parsing from COMBAT_EVENT entries

### Testing
- ✅ Added comprehensive damage attribution test suite (`test_damage_attribution.py`)
- ✅ Basic damage attribution to players
- ✅ Pet damage attribution to owners
- ✅ Unit ID matching between short and long formats
- ✅ Combat event damage parsing
- ✅ Multiple players damage attribution
- ✅ Edge cases: unknown units, orphaned pets
- ✅ Real log data processing validation

### Documentation
- Updated TESTING.md with damage attribution test documentation
- Added test coverage for damage attribution verification

## [0.1.27] - 2025-01-26

### Enhanced
- **Comprehensive Test Suite**: Added extensive testing for all new features and edge cases
- **Combat-Based Zone Naming**: Split files now correctly named after zone where combat begins
- **Zone-Based Report Naming**: Report files use consistent naming with split files
- **Robust Error Handling**: Improved error handling for missing zones and invalid directories
- **Edge Case Coverage**: Comprehensive testing of missing zones, invalid paths, and large files

### Technical Details
- Enhanced LogSplitter to wait for combat before renaming files
- Added current_difficulty tracking to ESOLogAnalyzer
- Implemented zone-based naming for both split files and reports
- Added comprehensive test scenarios covering all functionality
- Improved diagnostic output for better debugging

### Testing
- ✅ Combat-based zone naming for split files
- ✅ Zone-based report naming with difficulty suffixes
- ✅ Combined splitting + report saving functionality
- ✅ Regression tests on existing functionality
- ✅ Edge cases: missing zones, invalid directories, large files
- ✅ Error handling and graceful degradation

## [0.1.26] - 2025-01-26

### Enhanced
- **Zone-Based Report Naming**: Report files now use the same naming convention as split files
- **Consistent File Naming**: Reports are named `YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}-report.txt`
- **Difficulty Tracking**: Added difficulty tracking to ESOLogAnalyzer for accurate report naming
- **Improved Organization**: Report files are now organized by zone and difficulty, making them easier to identify

### Technical Details
- Added `current_difficulty` tracking to ESOLogAnalyzer class
- Modified `_save_report_to_file()` method to use zone-based naming logic
- Updated `_handle_zone_changed()` to track both zone name and difficulty
- Enhanced report filename generation to match split file naming convention

## [0.1.25] - 2025-01-25

### Added
- **Combat-Based Zone Naming**: Split files are now named after the first zone encountered during combat rather than the initial zone
- **Improved Split File Accuracy**: Enhanced log splitting logic to wait for combat events before determining zone names
- **Combat State Tracking**: Added tracking of combat start events to ensure accurate zone detection

### Enhanced
- **Smart Zone Detection**: Tool now waits for BEGIN_COMBAT event and uses the first subsequent ZONE_CHANGED for naming
- **Immediate File Creation**: Split files are created immediately as temporary files, then renamed when combat zone is determined
- **Robust Data Safety**: No data loss risk - files are written immediately and renamed atomically
- **Better Diagnostic Output**: Enhanced diagnostic messages for combat and zone detection events

### Technical Details
- Added combat_started flag to LogSplitter to track combat state
- Implemented immediate temporary file creation with atomic rename operation
- Modified both live tailing and replay modes to support combat-based zone detection
- Added start_combat(), handle_zone_change(), _create_temp_file(), and _rename_to_final() methods

## [0.1.24] - 2025-01-25

### Fixed
- **Critical Parsing Issue**: Fixed ESOLogEntry parsing for events without timestamps (BEGIN_COMBAT, END_COMBAT, UNIT_ADDED, etc.)
- **Missing Event Routing**: Added missing ZONE_CHANGED event routing in process_log_entry method
- **Field Indexing**: Corrected field indexing for ZONE_CHANGED events to properly extract zone name and difficulty
- **Encounter Detection**: Fixed encounter detection and player addition that was preventing report generation

### Enhanced
- **Robust Event Parsing**: Improved parsing logic to handle events with and without timestamps correctly
- **Better Error Handling**: Enhanced diagnostic output for debugging event processing issues
- **Report Generation**: Encounter reports now generate correctly in all modes

### Technical Details
- Modified ESOLogEntry.parse() to distinguish between events with timestamps and those using line numbers
- Added ZONE_CHANGED case to process_log_entry method routing
- Fixed field access for ZONE_CHANGED events (zone_name, difficulty)
- Added comprehensive debug output for event processing flow

## [0.1.23] - 2025-01-25

### Added
- **Report Saving Feature**: New `--save-reports` option to automatically save encounter reports to timestamped files
- **Custom Reports Directory**: New `--reports-dir` option to specify where report files are created
- **Timestamped Report Files**: Reports saved with format `YYMMDDHHMMSS-report.txt` based on encounter start time
- **Clean Text Output**: Report files contain clean text without ANSI color codes for easy reading

### Enhanced
- **Early Directory Validation**: Tool validates reports directory permissions before starting processing
- **Graceful Error Handling**: Clear error messages when directory creation fails, with instructions for manual creation
- **All Modes Support**: Report saving works in tail, read-all-then-stop, and read-all-then-tail modes

### Technical Details
- Added report buffering system to capture stdout output during encounter display
- Implemented ANSI color code stripping for clean text file output
- Added comprehensive directory validation with proper error handling
- Integrated report saving into existing encounter summary display system

## [0.1.22] - 2025-01-25

### Added
- **Auto-Split Logs Feature**: New `--tail-and-split` option to automatically create individual encounter files while tailing
- **Smart File Naming**: Split files named with format `YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}.log`
- **Zone Detection**: Automatically extracts zone name and difficulty from ZONE_CHANGED events
- **Robust File Handling**: Split files are closed when waiting and reopened for appending to prevent data loss
- **Custom Split Directory**: New `--split-dir` option to specify where split files are created

### Enhanced
- **All Modes Support**: Auto-split functionality works in tail, read-all-then-stop, and read-all-then-tail modes
- **Timestamp Accuracy**: Fixed ESOLogEntry parsing to use correct timestamps from log entries
- **Diagnostic Output**: Enhanced diagnostic mode shows split file creation and management details

### Technical Details
- Added `LogSplitter` class for managing split file creation, writing, and cleanup
- Fixed ESOLogEntry parsing to use `fields[2]` as timestamp instead of `fields[0]` (line number)
- Implemented robust file handling with `close_for_waiting()` and `reopen_for_append()` methods
- Added support for both LogFileMonitor and replay modes with auto-split functionality

## [0.1.19] - 2025-01-24

### Fixed
- **Critical Concurrency Issues**: Fixed race conditions in file monitoring that caused read-all-then-tail to fail
- **File Monitoring Reliability**: Replaced complex watchdog directory monitoring with simple, reliable file polling
- **Multiple File Confusion**: Eliminated issues where tool was monitoring multiple log files simultaneously
- **Thread Safety**: Added threading locks to prevent concurrent file access conflicts

### Changed
- **Simplified Architecture**: Replaced watchdog-based file monitoring with simple 1-second polling
- **Better Diagnostics**: Improved diagnostic output to clearly show file monitoring status
- **Removed Dependencies**: Eliminated watchdog library dependency for more reliable operation

### Technical Details
- Added `threading.Lock()` to prevent race conditions between `_process_entire_file()` and `_process_new_lines()`
- Replaced `LogFileHandler(FileSystemEventHandler)` with `LogFileMonitor` class
- Implemented `check_for_changes()` method for reliable file change detection
- Simplified main monitoring loop to use direct file polling instead of event-driven monitoring

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
