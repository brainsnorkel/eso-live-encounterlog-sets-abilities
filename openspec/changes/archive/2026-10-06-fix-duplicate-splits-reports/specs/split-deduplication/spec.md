## ADDED Requirements

### Requirement: Existing split files are detected on startup
When `LogSplitter` is initialized with a `split_dir`, it SHALL scan that directory and build an in-memory index of existing split files keyed by their base filename prefix (timestamp-zone portion, e.g. `260112192756-Maw-of-Lorkhaj-vet`).

#### Scenario: Split directory contains previously created files
- **WHEN** `LogSplitter` starts with `split_dir` pointing to a directory containing `260112192756-Maw-of-Lorkhaj-vet-17.log`
- **THEN** the index SHALL contain an entry for prefix `260112192756-Maw-of-Lorkhaj-vet` with recorded file size

#### Scenario: Split directory is empty
- **WHEN** `LogSplitter` starts with an empty `split_dir`
- **THEN** the index SHALL be empty and all encounters SHALL be processed normally

### Requirement: Duplicate encounters are skipped during read-all pass
When processing an encounter whose base filename matches an existing split file with the same file size, the system SHALL skip writing that encounter's split file entirely.

#### Scenario: Encounter matches existing split by name and size
- **WHEN** `_process_entire_file()` encounters a BEGIN_LOG that would produce filename `260112192756-Maw-of-Lorkhaj-vet.log`
- **AND** the split directory already contains a file with prefix `260112192756-Maw-of-Lorkhaj-vet` and identical byte size
- **THEN** the system SHALL NOT create a new split file for this encounter
- **AND** the system SHALL NOT write any lines from this encounter to disk

#### Scenario: Encounter matches by name but different size
- **WHEN** `_process_entire_file()` encounters a BEGIN_LOG that would produce a filename matching an existing prefix
- **AND** the existing file has a different byte size
- **THEN** the system SHALL create a new split file with an incremented suffix as before

#### Scenario: Encounter has no match in the index
- **WHEN** `_process_entire_file()` encounters a BEGIN_LOG with no matching prefix in the index
- **THEN** the system SHALL create a new split file normally

### Requirement: Conflict handler returns skip signal for identical files
`_handle_rename_conflict()` SHALL return a skip signal (None) when it detects that an existing file has identical content, instead of generating a new suffixed filename.

#### Scenario: Identical file exists during conflict resolution
- **WHEN** `_handle_rename_conflict()` finds an existing file with the same name
- **AND** the existing file has the same byte size (and matching MD5 for files under 10MB)
- **THEN** it SHALL return None to signal the caller to skip this encounter

#### Scenario: Different file exists during conflict resolution
- **WHEN** `_handle_rename_conflict()` finds an existing file with the same name
- **AND** the existing file has a different byte size or different MD5 hash
- **THEN** it SHALL increment the suffix and continue as before

### Requirement: Duplicate reports are skipped
Report generation (`_save_report_to_file()` and `_save_zone_report()`) SHALL check for existing report files with the same base filename before writing. If a matching report exists, it SHALL skip writing.

#### Scenario: Report file already exists for this encounter
- **WHEN** `_save_report_to_file()` would write a report matching an existing file's base name in the reports directory
- **THEN** the system SHALL NOT create a duplicate report file

#### Scenario: No existing report for this encounter
- **WHEN** `_save_report_to_file()` generates a report filename with no match in the reports directory
- **THEN** the system SHALL write the report file normally

### Requirement: New encounters during tail mode are unaffected
Encounters seen for the first time during live tailing (after the read-all pass completes) SHALL always be split and reported normally, with no deduplication check.

#### Scenario: New encounter arrives during tail mode
- **WHEN** the system is in tail mode (after `_process_entire_file()` completes)
- **AND** a new BEGIN_LOG event arrives for an encounter not in the index
- **THEN** the system SHALL create a split file and report as normal
- **AND** the system SHALL add the new file to the in-memory index
