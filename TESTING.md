# Testing Guide

This document explains how to run the automated test cases for the ESO Live Sets Abilities tool.

## Test Suite Overview

The project includes two comprehensive test suites:

1. **`test_analyzer.py`** - Tests the main analyzer functionality
2. **`test_log_parser.py`** - Tests the robust log parser with real example data

## Running Tests

### Quick Test Run
```bash
# Run all analyzer tests
python3 test_analyzer.py

# Run all log parser tests  
python3 test_log_parser.py
```

### Detailed Test Output
```bash
# Run with verbose output
python3 test_analyzer.py -v

# Run specific test methods
python3 -m unittest test_log_parser.TestESOLogParser.test_player_info_parsing
```

## Test Coverage

### Analyzer Tests (`test_analyzer.py`)
- **Log Entry Parsing**: Tests UNIT_ADDED, ABILITY_INFO, BEGIN_CAST parsing
- **Subclass Analysis**: Tests Templar healer and Sorcerer magicka DPS detection
- **Set Database**: Tests gear set identification and role-based suggestions
- **Full Integration**: Tests complete analyzer workflow

### Log Parser Tests (`test_log_parser.py`)
- **Basic Parsing**: Tests BEGIN_LOG, ZONE_CHANGED, MAP_CHANGED
- **Unit Added**: Tests player and anonymous player detection
- **Ability Info**: Tests ability caching and name mapping
- **Begin Cast**: Tests combat event parsing with stats
- **Effect Changed**: Tests GAINED, FADED, UPDATED effect parsing
- **Player Info**: Tests complex PLAYER_INFO parsing with gear arrays
- **Equipped Abilities**: Tests ability extraction from PLAYER_INFO
- **Invalid Entries**: Tests error handling for malformed data
- **Edge Cases**: Tests special characters and empty strings

## Test Data

### Real Example Data
All tests use actual ESO encounter log data from `example-log/Encounter.log`:
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
python3 test_analyzer.py && python3 test_log_parser.py
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

## GUI Testing

### Manual GUI Testing Procedures

1. **Launch GUI Mode**
   ```bash
   python3 eso_analyzer.py --gui
   ```

2. **Test Directory Selection**
   - Verify auto-detection works on startup
   - Test manual directory browsing
   - Test with invalid directories

3. **Test Log File Detection**
   - Click "Auto-detect" button
   - Verify Encounter.log is found
   - Test with missing log files

4. **Test Monitoring**
   - Click "Start Monitoring"
   - Verify status changes to "Monitoring..."
   - Test "Stop Monitoring" functionality

5. **Test Output Display**
   - Use "Test Mode" to generate sample output
   - Verify output appears in scrollable text area
   - Test "Clear Output" functionality

6. **Test User Guide**
   - Click "User Guide" button
   - Verify guide opens in new window
   - Test guide content loading

### GUI Error Handling Tests
- Test with missing log files
- Test with corrupted log files
- Test with invalid directory paths
- Test GUI responsiveness during monitoring

## Performance Testing

### Large Log Testing
```bash
# Test CLI with full sample log
python3 eso_analyzer.py --test-mode --replay-speed 1000

# Test GUI with sample data
python3 eso_analyzer.py --gui
# Then click "Test Mode" button
```

### Memory Usage
Monitor memory usage during large log processing to ensure efficient parsing.

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
