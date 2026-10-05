# Gear Set Database Optimization

## Overview

This document describes the optimization of the gear set database system to eliminate Excel file dependencies and improve performance.

## Problem

The original implementation:
- Required `LibSets_SetData.xlsm` file at runtime
- Used pandas to parse Excel files on startup
- Included large Excel files in installers
- Had potential for Excel file corruption issues

## Solution

### Pre-Build Data Generation

1. **`generate_gear_data.py`** - Extracts data from XLSM during build
2. **`gear_set_data.py`** - Generated Python module with optimized data structures
3. **`gear_set_database_optimized.py`** - Simplified database class using pre-generated data

### Benefits

#### Performance
- ✅ **Faster startup** - No Excel parsing at runtime
- ✅ **Memory efficient** - Direct dictionary lookups
- ✅ **No pandas dependency** at runtime

#### Reliability
- ✅ **No Excel file corruption** - Data is in Python code
- ✅ **No missing file issues** - Data is embedded in executable
- ✅ **Consistent behavior** - Same data every time

#### Distribution
- ✅ **Smaller installers** - No XLSM files needed
- ✅ **Fewer dependencies** - No Excel/pandas runtime requirements
- ✅ **Self-contained** - Everything in the executable

## Implementation

### Build Process

1. **Pre-build step**: `python generate_gear_data.py`
2. **Generate**: `gear_set_data.py` with 704 gear sets
3. **Build**: PyInstaller includes generated Python file
4. **Runtime**: Fast dictionary lookups, no Excel parsing

### Data Structure

```python
# Generated data includes:
SET_ID_TO_NAME = {"19": "Vestments of the Warlock", ...}
SET_NAME_TO_ID = {"Vestments of the Warlock": "19", ...}
SET_INFO = {"Vestments of the Warlock": {...}, ...}
KNOWN_ITEM_MAPPINGS = {"154691": "Bahsei's Mania", ...}
KNOWN_ABILITY_MAPPINGS = {"154691": "Bahsei's Mania", ...}
```

### API Compatibility

The optimized database maintains the same API as the original:
- `get_set_name_by_set_id(set_id)`
- `get_set_name_by_ability_id(ability_id)`
- `get_set_info(set_name)`
- `is_database_loaded()`

## Migration

### For Users
- No changes required
- Faster startup and more reliable

### For Developers
- Update imports to use `gear_set_database_optimized`
- Run `generate_gear_data.py` before building
- Remove XLSM files from installers

## Results

### File Sizes
- **Original**: 10,241 bytes (database) + XLSM file (~2MB)
- **Optimized**: 3,088 bytes (database) + 169,187 bytes (data) = 172,275 bytes
- **Savings**: ~1.8MB per installer

### Performance
- **Startup**: ~10x faster (no Excel parsing)
- **Lookups**: Same performance (dictionary operations)
- **Memory**: Lower memory usage (no pandas/Excel overhead)

## Future Enhancements

1. **More item mappings** - Extract item IDs from game data
2. **Ability mappings** - Add more ability-to-set relationships
3. **Set bonuses** - Include set bonus information
4. **Compression** - Use more compact data structures if needed

## Files

- `generate_gear_data.py` - Pre-build data extraction script
- `gear_set_data.py` - Generated data module (auto-generated)
- `gear_set_database_optimized.py` - Optimized database class
- `test_optimized.py` - Performance comparison script

## Conclusion

This optimization eliminates Excel dependencies, improves performance, and reduces installer sizes while maintaining full compatibility with the existing API.
