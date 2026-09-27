## Why

Every time `esolog-tail` is launched with `--read-all-then-tail --tail-and-split`, it re-processes the entire Encounter.log from the beginning and creates duplicate split files with incrementing numeric suffixes. The same encounter ends up saved 3-4 times (e.g. `260112192756-Maw-of-Lorkhaj-vet-17.log`, `-18.log`, `-19.log` — all identical 305MB files). This wastes ~23GB of disk space in `D:\esologs\splits` and produces duplicate reports in `D:\esologs\reports`. The tool should detect already-split encounters and skip them.

## What Changes

- Add deduplication logic to `LogSplitter` so encounters already present in the split directory are skipped during the `--read-all-then-tail` initial pass
- Modify `_handle_rename_conflict()` to return a skip signal when an identical file already exists, instead of incrementing the suffix
- Apply the same deduplication to report generation in `_save_report_to_file()` and `_save_zone_report()`
- On startup, scan the split-dir to build an index of existing splits keyed by base filename (timestamp + zone)

## Capabilities

### New Capabilities
- `split-deduplication`: Detect and skip already-existing split files and reports during the read-all-then-tail initial pass, preventing duplicate output files

### Modified Capabilities

## Impact

- `src/esolog_tail.py`: `LogSplitter` class (startup scan, `start_encounter()`, `_handle_rename_conflict()`, `_save_report_to_file()`, `_save_zone_report()`)
- No new dependencies required — uses stdlib `os.path` and existing MD5 hashing
- No CLI argument changes — existing `--tail-and-split` / `--save-reports` flags behave the same but without creating duplicates
- No breaking changes
