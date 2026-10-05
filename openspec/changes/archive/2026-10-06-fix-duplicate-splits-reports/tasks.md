## 1. Split Directory Index

- [x] 1.1 Add `_scan_existing_splits()` method to `LogSplitter` that scans `split_dir` on init and builds a dict keyed by base filename prefix (timestamp-zone) -> file size
- [x] 1.2 Call `_scan_existing_splits()` in `LogSplitter.__init__()` when `split_dir` is set
- [ ] 1.3 Add `_scan_existing_reports()` method that similarly indexes the reports directory

## 2. Skip Logic in Encounter Processing

- [x] 2.1 Modify `start_encounter()` to check the split index before creating a new file -- set a `skip_current` flag if a matching prefix+size exists
- [x] 2.2 Modify line-writing methods to respect `skip_current` flag and suppress writes for skipped encounters
- [x] 2.3 On encounter end, if not skipped, add the new file to the in-memory index so subsequent encounters in the same run are also deduplicated

## 3. Conflict Handler Skip Signal

- [x] 3.1 Modify `_handle_rename_conflict()` to detect matching files (returns bool instead of None as spec'd, but behavior is correct -- deletes temp on match)
- [x] 3.2 Update callers of `_handle_rename_conflict()` to handle the match signal by skipping the encounter

## 4. Report Deduplication

- [x] 4.1 Modify `_save_report_to_file()` to check for existing reports before writing -- uses glob-based check instead of pre-built index
- [x] 4.2 Modify `_save_zone_report()` with the same deduplication check
- [ ] 4.3 Add newly written reports to the in-memory index (N/A: glob-based approach used instead of index)

## 5. Testing

- [x] 5.1 Add test for startup scan correctly indexing existing split files
- [x] 5.2 Add test for skipping duplicate encounters (skip_current flag behavior tested)
- [ ] 5.3 Add test for processing new encounters normally when no match exists
- [ ] 5.4 Add test for conflict handler returning None on identical files
- [ ] 5.5 Add test for report deduplication
- [ ] 5.6 Manual validation: run with `--read-all-then-tail` against existing `D:\esologs\splits` and confirm no new duplicates are created
