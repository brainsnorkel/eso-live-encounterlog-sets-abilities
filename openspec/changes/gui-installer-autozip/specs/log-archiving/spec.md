# Capability: log-archiving

## ADDED Requirements

### Requirement: Startup-only size-based trigger
The application SHALL check the active encounter log exactly once, at application startup before monitoring begins, and SHALL initiate an automatic archive when the log's size has grown beyond a configurable threshold since the last archive. The threshold SHALL default to 1024 MB (~5 veteran trials). Automatic archiving MUST NOT be attempted at any other time.

#### Scenario: Threshold exceeded at startup
- **WHEN** the app starts and the log has grown 1.5 GB since the last archive marker with the default 1 GB threshold
- **THEN** an automatic archive is initiated before monitoring attaches, and the user sees progress in the UI

#### Scenario: Below threshold
- **WHEN** the app starts and the log has grown less than the threshold since the last archive
- **THEN** no archive occurs and monitoring starts immediately

#### Scenario: No mid-session archiving
- **WHEN** the log grows past the threshold while the app is already monitoring
- **THEN** no automatic archive is attempted until the next app startup

### Requirement: Sizing guide in settings
The settings UI SHALL display guidance beside the size threshold explaining typical log sizes, including that a veteran trial run is typically 100–300 MB, a veteran dungeon roughly 25–75 MB, and that 1 GB corresponds to roughly five trials.

#### Scenario: Configuring the threshold
- **WHEN** the user opens the archive settings
- **THEN** the size guide text is visible beside the threshold field

### Requirement: In-use guard
Before archiving, the application MUST verify no other process has the log open by acquiring exclusive access (deny-all sharing) and MUST hold that exclusive access for the duration of the archive operation. If exclusive access cannot be acquired (e.g. ESO is running), the archive SHALL be skipped with a visible notification and normal monitoring SHALL proceed.

#### Scenario: ESO has the file open
- **WHEN** the app starts while ESO is running (log file held open)
- **THEN** the archive is skipped, the UI shows a notification that the log is in use, and monitoring starts normally

#### Scenario: File free at startup
- **WHEN** the app starts with no process holding the log
- **THEN** exclusive access is acquired, the archive proceeds, and access is released immediately after completion

### Requirement: Dated zip archive with progress
An archive operation SHALL create a zip archive of the active log named `Encounter-YYMMDDHHMMSS.zip`, where the timestamp is the date/time of the latest log entry (file mtime as fallback), in the configured archive directory (defaulting to the log file's directory), resolving name collisions with numeric suffixes. The operation SHALL support source files larger than 4 GB (zip64), stream in chunks, report progress to the UI, and keep the UI responsive.

#### Scenario: Archive created
- **WHEN** an archive of a log whose latest entry is 2026-09-27 14:33:02 completes
- **THEN** `Encounter-260927143302.zip` exists in the archive directory and contains the complete `Encounter.log` content

#### Scenario: Multi-GB source
- **WHEN** the log is 21 GB
- **THEN** the archive completes with visible progress updates and the window remains responsive throughout

### Requirement: Verification and original file handling
The archive MUST be integrity-verified after creation (zip test plus size match against the source). The original log SHALL be kept by default; deleting the original after archiving SHALL be an explicit opt-in setting, and deletion MUST occur only after verification succeeds.

#### Scenario: Default keep
- **WHEN** an automatic archive completes with default settings
- **THEN** the original `Encounter.log` remains untouched

#### Scenario: Opt-in delete
- **WHEN** the delete-original setting is enabled and an archive completes and verifies
- **THEN** the original log is deleted and the UI reports both the archive path and the deletion

#### Scenario: Verification failure
- **WHEN** the produced zip fails verification
- **THEN** the zip is removed, the original is untouched regardless of settings, and the failure is reported in the UI

### Requirement: Re-trigger control
The application SHALL persist the log's size at the time of the last archive and SHALL trigger the next automatic archive only when growth since that marker exceeds the threshold; if the log shrinks or is replaced, the marker SHALL reset.

#### Scenario: Archived but kept
- **WHEN** a 2 GB log was archived (original kept) and the app restarts with the log at 2.3 GB
- **THEN** no new automatic archive occurs (growth 0.3 GB < 1 GB threshold)

#### Scenario: Log rotated
- **WHEN** the user deletes the log after an archive and ESO creates a fresh one
- **THEN** the marker resets and the next archive triggers only after the new log exceeds the threshold

### Requirement: Manual archive action
The GUI SHALL offer a manual "Archive now" action that performs the same guarded, verified archive operation regardless of size, at any time (e.g. after the user closes ESO), without requiring an app restart.

#### Scenario: Manual archive below threshold
- **WHEN** the user triggers "Archive now" with a 200 MB log and no process holds the file
- **THEN** a dated zip archive is created as specified above

#### Scenario: Manual archive while ESO runs
- **WHEN** the user triggers "Archive now" while ESO holds the log open
- **THEN** the action reports that the log is in use and makes no changes
