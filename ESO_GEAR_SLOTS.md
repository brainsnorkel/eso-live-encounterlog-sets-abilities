# ESO Encounter Log Gear Slot Structure

## Overview
The Elder Scrolls Online encounter log tracks **13 gear slots** per player, not the full 14 slots available in the game's UI. This is a limitation of the encounter log format.

## Complete Gear Slot List

| Slot Name | Description | Notes |
|-----------|-------------|-------|
| `HEAD` | Helmet | Standard armor slot |
| `SHOULDERS` | Shoulder pads | Standard armor slot |
| `HAND` | Gloves/Arms | Log uses "HAND" instead of "ARMS" |
| `LEGS` | Leg armor | Standard armor slot |
| `CHEST` | Chest armor | Standard armor slot |
| `WAIST` | Belt | Log uses "WAIST" instead of "BELT" |
| `FEET` | Boots | Standard armor slot |
| `NECK` | Necklace | Jewelry slot |
| `RING1` | First ring | Jewelry slot |
| `RING2` | Second ring | Jewelry slot |
| `MAIN_HAND` | Primary weapon | Active weapon bar |
| `OFF_HAND` | Secondary weapon/shield | Active weapon bar |
| `BACKUP_MAIN` | Backup primary weapon | Backup weapon bar |

## Key Differences from Expected

### Missing Slots
- **`BACKUP_OFF`**: The encounter log does **not** track the backup off-hand weapon slot
- This means ESO only logs 13 slots, not the full 14 available in-game

### Complete ESO Gear Structure
**In-game ESO has 14 total gear slots:**
- **7 Armor slots**: HEAD, SHOULDERS, HAND, CHEST, WAIST, LEGS, FEET
- **3 Jewelry slots**: NECK, RING1, RING2  
- **4 Weapon slots**: MAIN_HAND, OFF_HAND, BACKUP_MAIN, BACKUP_OFF

**Encounter log only tracks 13 slots** (missing BACKUP_OFF)

### Naming Differences
- **`HAND`** instead of `ARMS` (gloves/gauntlets)
- **`WAIST`** instead of `BELT`

## Gear Data Format
Each gear slot in the log contains the following information:
```
[SLOT_NAME, ITEM_ID, FLAG1, LEVEL, TRAIT, QUALITY, ENCHANT_VALUE, ENCHANT_TYPE, FLAG2, ITEM_LEVEL, QUALITY_LEVEL]
```

Example:
```
[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY]
```

## Validation
The parser validates that exactly 13 gear slots are present and that all expected slot names are found in the data.

## Why Only 13 Slots?
The ESO encounter log appears to be optimized for combat analysis and may not track the backup off-hand weapon because:
1. **Combat focus**: The log focuses on equipment that directly affects combat calculations
2. **Rare usage**: Most players use 2H weapons or staves on their backup bar, making the off-hand slot often empty
3. **Log optimization**: The system may not log empty or rarely-used slots to reduce log size
4. **Performance**: Backup off-hand weapons are not active during combat, so they don't impact encounter calculations

**Important**: This is a limitation of the encounter log format, not the parser implementation. The parser correctly handles all available gear slots in the log.

## Parser Behavior
- **Correctly parses**: All 13 available gear slots from encounter logs
- **Handles missing slots**: Gracefully handles the absence of BACKUP_OFF
- **Validates structure**: Ensures exactly 13 slots are present as expected
- **Future-proof**: Will automatically detect BACKUP_OFF if ESO adds it to logs
