# Testing Guide

This document explains how to run the automated test cases for the ESO Live Sets Abilities tool.

## Test Suite Overview

The project uses a conventional test structure with unit and integration tests:

### Unit Tests (`tests/unit/`)
1. **`test_analyzer.py`** - Tests individual analyzer components and functionality
2. **`test_log_parser.py`** - Tests the robust log parser with real example data
3. **`test_optimized.py`** - Tests the optimized gear set database performance
4. **`test_damage_attribution.py`** - Tests damage attribution to players and pets
5. **`test_end_log_inclusion.py`** - Tests END_LOG inclusion in split log files
6. **`test_file_naming_conflicts.py`** - Tests file naming conflict resolution with content-based deduplication
7. **`test_report_splitting.py`** - Tests zone-specific report generation and isolation
8. **`test_report_saving.py`** - Tests report file saving functionality
9. **`test_timestamp_format.py`** - Tests timestamp format consistency and edge cases

### Integration Tests (`tests/integration/`)
1. **`test_full_workflow.py`** - Tests complete analyzer workflows and multi-component interactions
2. **`test_log_splitting_integration.py`** - Tests log splitting functionality with real file operations

### Test Infrastructure
- **`conftest.py`** - Pytest configuration and shared fixtures
- **`test_runner.py`** - Comprehensive test runner with options
- **`fixtures/`** - Shared test data and fixtures
- **`data/`** - Test data files and sample logs

## Current Test Status

**✅ All Tests Passing: 101/101**

The test suite is comprehensive and all tests are currently passing, validating:

- **File Naming Conflicts**: Content-based deduplication with MD5 hashing
- **END_LOG Inclusion**: Proper log structure in split files
- **Report Buffer Management**: Zone-specific report isolation
- **Timestamp Format**: Consistent timestamp handling and edge cases
- **Report Splitting**: Zone-based report generation and content isolation
- **Integration Workflows**: Complete end-to-end functionality

### Test Categories
- **Unit Tests**: 89 tests covering individual components
- **Integration Tests**: 12 tests covering complete workflows
- **File Operations**: Tests for split logs, reports, and conflict resolution
- **Data Integrity**: Tests for proper data handling and edge cases

## Running Tests

### Quick Test Run
```bash
# Run all tests using the test runner
python3 tests/test_runner.py

# Run only unit tests
python3 tests/test_runner.py --unit

# Run only integration tests
python3 tests/test_runner.py --integration

# Run with verbose output
python3 tests/test_runner.py --verbose
```

### Individual Test Files
```bash
# Run specific unit tests
python3 -m unittest tests.unit.test_analyzer
python3 -m unittest tests.unit.test_log_parser
python3 -m unittest tests.unit.test_optimized
python3 -m unittest tests.unit.test_damage_attribution

# Run integration tests
python3 -m unittest tests.integration.test_full_workflow

# Run with pytest (if installed)
pytest tests/unit/
pytest tests/integration/
pytest tests/
```

### Detailed Test Output
```bash
# Run with verbose output
python3 tests/test_runner.py --verbose

# Run specific test methods
python3 -m unittest tests.unit.test_log_parser.TestESOLogParser.test_player_info_parsing
python3 -m unittest tests.unit.test_analyzer.TestESOLogEntry.test_unit_added_parsing
```

## Test Coverage

### Unit Tests

#### Analyzer Tests (`test_analyzer.py`)
- **Log Entry Parsing**: Tests UNIT_ADDED, ABILITY_INFO, BEGIN_CAST parsing
- **Subclass Analysis**: Tests Templar healer and Sorcerer magicka DPS detection
- **Set Database**: Tests gear set identification and role-based suggestions
- **Full Integration**: Tests complete analyzer workflow

#### Log Parser Tests (`test_log_parser.py`)
- **Basic Parsing**: Tests BEGIN_LOG, ZONE_CHANGED, MAP_CHANGED
- **Unit Added**: Tests player and anonymous player detection
- **Ability Info**: Tests ability caching and name mapping
- **Begin Cast**: Tests combat event parsing with stats
- **Effect Changed**: Tests GAINED, FADED, UPDATED effect parsing
- **Player Info**: Tests complex PLAYER_INFO parsing with gear arrays
- **Equipped Abilities**: Tests ability extraction from PLAYER_INFO
- **Invalid Entries**: Tests error handling for malformed data
- **Edge Cases**: Tests special characters and empty strings

#### Damage Attribution Tests (`test_damage_attribution.py`)
- **Basic Attribution**: Tests direct damage attribution to players
- **Pet Attribution**: Tests damage from pets attributed to their owners
- **Unit ID Matching**: Tests short/long unit ID matching for players
- **Combat Event Parsing**: Tests damage parsing from COMBAT_EVENT entries
- **Multiple Players**: Tests damage attribution with multiple players
- **Edge Cases**: Tests unknown units and orphaned pets
- **Real Log Data**: Tests with actual ESO encounter log entries

#### Optimized Database Tests (`test_optimized.py`)
- **Performance**: Tests database lookup performance
- **Accuracy**: Tests database accuracy and completeness
- **Compatibility**: Tests compatibility with existing code

#### Log Splitting Tests (`test_log_splitting.py`)
- **File Creation**: Tests automatic creation of split files
- **Zone Detection**: Tests zone-based file naming
- **File Naming**: Tests naming conventions for different zones and difficulties
- **File Operations**: Tests writing, closing, and reopening files
- **Multiple Encounters**: Tests handling multiple encounters
- **Cleanup**: Tests proper cleanup of file handles and state

#### Report Saving Tests (`test_report_saving.py`)
- **File Creation**: Tests automatic creation of report files
- **Zone-based Naming**: Tests report file naming with zone information
- **Buffer Management**: Tests report buffer handling and clearing
- **Directory Handling**: Tests automatic directory creation and permissions
- **Multiple Reports**: Tests saving multiple reports with unique timestamps
- **Error Handling**: Tests permission errors and edge cases

### Integration Tests

#### Full Workflow Tests (`test_full_workflow.py`)
- **Complete Encounters**: Tests processing full encounters from start to finish
- **Multi-Encounter**: Tests handling multiple encounters in sequence
- **Error Recovery**: Tests recovery from malformed data and errors
- **Resource Tracking**: Tests resource tracking across different event types
- **Damage Attribution**: Tests damage attribution in full encounter context
- **Configuration**: Tests different analyzer configurations and modes

#### Log Splitting Integration Tests (`test_log_splitting_integration.py`)
- **Complete Workflow**: Tests full encounter processing with both splitting and report saving
- **Multiple Encounters**: Tests multiple encounters with log splitting
- **Zone Detection**: Tests encounter processing when zone information is missing
- **File Handling**: Tests file handling edge cases in integration
- **Concurrent Operations**: Tests concurrent file operations between splitter and analyzer

## Test Data

### Real Example Data
All tests use actual ESO encounter log data from `data/example_logs/Encounter.log`:
- **48MB sample log** with real combat encounters
- **Multiple players** including named and anonymous
- **Complex gear data** with all 13 available gear slots
- **Various ability types** including class skills, passives, and consumables

### Sample Test Entries
The tests include real log entries such as:
```csv
5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T
2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T
40604,PLAYER_INFO,1,[142210,142079,84731,...],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,...]]
```

## Gear Set Database Testing

### Testing Optimized Database
The `test_optimized.py` script compares the original and optimized gear set databases:

```bash
# Run performance comparison
python3 tests/test_optimized.py
```

**Expected Output:**
- Both databases return identical results
- Performance benchmarks show similar lookup speeds
- File size comparison shows optimization benefits

### Testing Gear Data Generation
```bash
# Generate gear data from XLSM
python3 scripts/generate_gear_data.py

# Verify generated data
python3 -c "import sys; sys.path.append('src'); from gear_set_data import get_stats; print(get_stats())"
```

**Expected Results:**
- 704 gear sets extracted from LibSets database
- Generated `gear_set_data.py` file (~169KB)
- All set ID and name mappings working correctly

### When to Regenerate Gear Data
**Regenerate whenever:**
- New gear sets are added to ESO
- LibSets spreadsheet is updated
- Building from source with latest data

## Expected Results

### All Tests Should Pass
```bash
$ python3 test_analyzer.py
Running ESO Analyzer Tests
✓ UNIT_ADDED parsing works
✓ ABILITY_INFO parsing works  
✓ BEGIN_CAST parsing works
✓ Templar healer detection works
✓ Sorcerer magicka DPS detection works
✓ Set identification works
✓ Role-based set suggestions work
✓ Full analyzer integration works
🎉 All tests passed! ESO Analyzer is ready to use.

$ python3 test_log_parser.py
.........
----------------------------------------------------------------------
Ran 9 tests in 0.000s
OK
```

## Test Validation

### Gear Slot Validation
The log parser tests specifically validate:
- **Exactly 13 gear slots** are parsed (ESO log limitation)
- **All expected slot names** are present: HEAD, SHOULDERS, HAND, LEGS, CHEST, WAIST, FEET, NECK, RING1, RING2, MAIN_HAND, OFF_HAND, BACKUP_MAIN
- **Missing BACKUP_OFF slot** is handled gracefully

### Ability Mapping Validation
Tests verify:
- **Ability ID to name mapping** works correctly
- **Equipped abilities** are extracted from PLAYER_INFO
- **Ability cache** is properly maintained

### Error Handling Validation
Tests ensure:
- **Malformed entries** are handled gracefully
- **Empty lines** don't crash the parser
- **Incomplete data** is handled appropriately

## Debugging Failed Tests

### Common Issues
1. **Import Errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
2. **File Not Found**: Ensure `example-log/Encounter.log` exists
3. **Parsing Errors**: Check if log format has changed

### Verbose Output
```bash
# Get detailed test output
python3 -m unittest test_log_parser.TestESOLogParser.test_player_info_parsing -v
```

### Individual Test Debugging
```bash
# Test specific functionality
python3 -c "
from eso_log_parser import ESOLogParser
parser = ESOLogParser()
# Add debug code here
"
```

## Continuous Integration

### Pre-commit Testing
Before committing changes, run:
```bash
# Run all tests
python3 tests/test_runner.py

# Or run specific test suites
python3 tests/test_runner.py --unit && python3 tests/test_runner.py --integration
```

### Test Coverage
The test suites cover:
- ✅ All major log entry types
- ✅ Error handling scenarios  
- ✅ Real-world data parsing
- ✅ Integration workflows
- ✅ Edge cases and special characters

## Adding New Tests

### Test Structure
```python
def test_new_feature(self):
    """Test description."""
    # Arrange
    parser = ESOLogParser()
    
    # Act
    result = parser.parse_new_feature(test_data)
    
    # Assert
    self.assertIsNotNone(result)
    self.assertEqual(result.expected_field, expected_value)
```

### Test Data
- Use real ESO log entries when possible
- Include edge cases and error conditions
- Test both valid and invalid inputs

## Performance Testing

### Large Log Testing
```bash
# Test with full sample log
python3 src/esolog_tail.py --test-mode --replay-speed 1000
```

### Memory Usage
Monitor memory usage during large log processing to ensure efficient parsing.

## Tail Mode Testing

### Testing File Monitoring
The tail mode functionality can be tested using the log simulator:

```bash
# Test with low volume (50 lines every 2 seconds)
python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 50 2.0

# Test with high volume (10,000 lines every 1 second)  
python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 10000 1.0

# Test with very high volume (50,000 lines every 1 second)
python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 50000 1.0
```

### Testing Tail Mode with Diagnostic Output
```bash
# Run esolog_tail in diagnostic mode to monitor file changes
python3 src/esolog_tail.py --log-file test_output.log --diagnostic --no-wait
```

**Expected Diagnostic Output:**
```
[HH:MM:SS] DIAGNOSTIC: File system event detected - /path/to/test_output.log
[HH:MM:SS] DIAGNOSTIC: Event matches target file, processing new lines
[HH:MM:SS] DIAGNOSTIC: Reading new data from test_output.log (size: X, pos: Y)
[HH:MM:SS] DIAGNOSTIC: Read X lines from test_output.log
[HH:MM:SS] DIAGNOSTIC: FALLBACK - Detected file growth (size: X, pos: Y)
```

### Tail Mode Validation
The diagnostic mode should show:
- ✅ File system events being detected
- ✅ Path comparison working correctly  
- ✅ New data being read when files change
- ✅ Fallback polling mechanism working
- ✅ Proper handling of high-volume data streams

### Testing Standard Tail Comparison
```bash
# Compare with standard tail command
tail -f test_output.log &

# Run esolog_tail in another terminal
python3 src/esolog_tail.py --log-file test_output.log --diagnostic
```

Both should detect changes at the same time, confirming the file monitoring is working correctly.

## Test Maintenance

### Updating Tests
When adding new features:
1. Add corresponding test cases
2. Update test data if needed
3. Ensure all tests still pass
4. Update this documentation

### Test Data Updates
If ESO log format changes:
1. Update sample log entries in tests
2. Verify parser handles new format
3. Add tests for new log entry types
4. Update expected results

This testing framework ensures the ESO Live Sets Abilities tool maintains reliability and accuracy as it evolves.
