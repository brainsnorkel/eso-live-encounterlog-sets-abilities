## Context

`esolog-tail` can be launched with `--read-all-then-tail` to process an existing Encounter.log from the beginning before switching to tail mode. When combined with `--tail-and-split` and `--save-reports`, each encounter in the log produces a split file and a report file. Currently, every restart re-processes all encounters and creates new files with incrementing numeric suffixes because `_handle_rename_conflict()` treats identical content as a collision to resolve rather than a duplicate to skip. The result is 3-4x disk usage in `D:\esologs\splits` (~23GB of duplicates).

The `LogSplitter` class in `src/esolog_tail.py` manages split file creation. Filenames are based on `YYMMDDHHMMSS-{Zone-Name}{-vet}.log`. Conflicts are handled by MD5 comparison followed by suffix incrementing. No state persists between runs.

## Goals / Non-Goals

**Goals:**
- Prevent duplicate split files when re-processing an already-split encounter
- Prevent duplicate report files for the same encounters
- Zero behavior change for new/unseen encounters — they continue to be split and reported normally
- No new CLI flags required — deduplication is automatic

**Non-Goals:**
- Cleaning up existing duplicates (user can do this manually or we add a separate cleanup command later)
- Persisting state in a manifest file — filesystem-based detection is sufficient and simpler
- Changing the filename format or suffix numbering scheme for genuinely different encounters

## Decisions

**1. Filesystem-based deduplication over manifest file**

On startup (when `--tail-and-split` is active), scan the split directory and build an in-memory set of existing base filenames (timestamp-zone prefix). When `start_encounter()` generates a filename that matches an existing prefix, compare file sizes. If a size-matched file exists, skip the encounter entirely — don't open a write handle.

*Why not a manifest?* A manifest adds a new file to manage, can drift out of sync, and requires handling corruption. The split directory IS the manifest — files on disk are the source of truth.

*Why size comparison instead of MD5?* MD5 requires reading potentially hundreds of MB per file on startup. File size is a fast proxy — encounters from the same BEGIN_LOG timestamp with the same zone will have identical sizes if they contain the same data. For the rare false-positive (different encounter, same size), falling through to the existing suffix logic is correct.

**2. Skip signal from `_handle_rename_conflict()` rather than new suffix**

When `_handle_rename_conflict()` detects an existing file with identical size (and optionally MD5 for files under a size threshold), return `None` to signal "skip this encounter" instead of generating a new suffixed filename. The caller (`start_encounter`) checks for `None` and sets a `skip_current` flag that suppresses line writing for that encounter.

**3. Apply same logic to reports**

`_save_report_to_file()` and `_save_zone_report()` check for existing report files with the same base name before writing. If a report already exists, skip it.

## Risks / Trade-offs

**[Risk] Size-only comparison could miss genuinely different encounters with the same timestamp and size** → This is extremely unlikely (would require two different encounters starting in the same second in the same zone with byte-identical log sizes). The existing suffix logic handles this as fallback. For extra safety, do MD5 verification for files under 10MB.

**[Risk] Large split directories could slow startup scan** → `os.listdir()` on a directory with thousands of files is still sub-second. Building a set from filenames is O(n) and negligible.

**[Risk] Encounter skipping could suppress legitimate re-splits if log content changed** → The Encounter.log is append-only during a session and immutable after. Re-processing the same log will always produce identical splits.
