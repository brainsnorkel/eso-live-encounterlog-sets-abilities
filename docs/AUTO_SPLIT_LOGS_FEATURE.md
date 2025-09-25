# Auto-Split Logs Feature Specification

## Overview

This feature adds a new command line option `--tail-and-split` to the ESO log analyzer that automatically splits encounter logs into individual encounter files while tailing the main log file.

## Feature Description

The `--tail-and-split` option will create new log files in the same directory as the tailed log file, automatically splitting encounters based on log markers.

### Behavior

1. **Monitor for BEGIN_LOG**: The system watches for `BEGIN_LOG` events in the tailed log file
2. **Extract Zone Information**: After detecting a `BEGIN_LOG`, it waits for the next `ZONE_CHANGED` event to acquire:
   - Zone name
   - Difficulty level (e.g., VETERAN)
3. **Create Split File**: Creates a new log file with the encounter data
4. **Write Log Events**: All subsequent log events are written to the split file until:
   - An `END_LOG` event is encountered, OR
   - A new `BEGIN_LOG` event is encountered (indicating a new encounter)
5. **File Closure**: The split file is closed when the encounter ends

### File Naming Convention

Split files are named using the following format:
```
YYMMDDHHMMSS{-Vet}-{ZoneName}.log
```

Where:
- `YYMMDDHHMMSS`: Local timestamp from the `BEGIN_LOG` event
- `{-Vet}`: Optional "-Vet" suffix for VETERAN difficulty encounters (blank for other difficulties)
- `{ZoneName}`: Zone name with spaces converted to dashes

### Examples

- `250115143022-Vet-Craglorn.log` - Veteran Craglorn encounter at 2:30:22 PM on Jan 15, 2025
- `250115143045-Spindleclutch-II.log` - Normal Spindleclutch II encounter at 2:30:45 PM on Jan 15, 2025

## Implementation Details

### Command Line Usage
```bash
python3 src/esolog_tail.py --tail-and-split --log-file /path/to/Encounter.log
```

### Log Event Processing
- The system processes log events in real-time as they appear in the tailed file
- Each encounter is tracked independently
- Multiple encounters can be processed simultaneously if they overlap

### File Management
- Split files are created in the same directory as the source log file
- Files are created immediately when a `BEGIN_LOG` is detected
- Files are closed and finalized when an `END_LOG` is encountered or a new encounter begins

## Technical Requirements

1. **Thread Safety**: The split functionality must work safely with the existing tailing mechanism
2. **File Locking**: Proper file locking to prevent corruption during concurrent writes
3. **Error Handling**: Graceful handling of incomplete encounters or malformed log data
4. **Performance**: Minimal impact on the existing tailing performance

## Testing Strategy

1. **Unit Tests**: Test the split logic with known log data
2. **Integration Tests**: Test with live log tailing
3. **Edge Cases**: Test with incomplete encounters, malformed data, and rapid encounter transitions

## Future Enhancements

- Optional compression of split files
- Configurable output directory
- Custom naming patterns
- Automatic cleanup of old split files
