# Capability: gui-application

## ADDED Requirements

### Requirement: Windowed live monitoring
The application SHALL provide a windowed desktop GUI, as the sole frontend, that monitors the active encounter log and displays each completed fight's summary (zone, difficulty, duration, group DPS, primary target, group buff uptimes, and per-player build/DPS breakdown).

#### Scenario: Fight completes while monitoring
- **WHEN** the GUI is monitoring a log file and an END_COMBAT event completes an encounter
- **THEN** the fight summary appears in the live view within one second, with players sorted by damage contribution and role-colored (tank/healer/DPS)

#### Scenario: Waiting for log file
- **WHEN** the GUI starts and the configured log file does not exist
- **THEN** the GUI displays a waiting state naming the expected path and begins monitoring automatically once the file appears

### Requirement: Fight history navigation
The GUI SHALL retain completed fights for the session and let the user browse previous fights, toggle between compact and detailed views, and copy a fight summary to the clipboard, without interrupting live monitoring.

#### Scenario: Browsing while live
- **WHEN** the user selects an earlier fight from the history list during active monitoring
- **THEN** that fight's summary is displayed, new fights continue to be recorded, and a single action returns the view to live

#### Scenario: Clipboard copy
- **WHEN** the user triggers the copy action on a displayed fight
- **THEN** a plain-text summary of that fight is placed on the system clipboard

### Requirement: Terminal feature parity
The GUI SHALL preserve the retired terminal frontends' features: per-encounter split files, saved encounter reports (both with the existing naming conventions), and automatic log file detection across known ESO install locations.

#### Scenario: Split files while monitoring
- **WHEN** split-file output is enabled in settings and an encounter completes
- **THEN** a split log file named `YYMMDDHHMMSS-{Zone-Name}{-vet}.log` is created in the configured split directory, identical in content to the previous release's output

#### Scenario: Saved reports
- **WHEN** report saving is enabled in settings and an encounter completes
- **THEN** a report file named `YYMMDDHHMMSS-{Zone-Name}{-vet}-report.txt` is created in the configured reports directory

#### Scenario: Log auto-detection
- **WHEN** the GUI starts with no log path configured
- **THEN** it selects the most recently updated `Encounter.log` from the known ESO log locations

### Requirement: Open a log file for review
The GUI SHALL let the user open an arbitrary encounter log file (e.g. a split file or an unzipped archive) and browse its fights without affecting live monitoring configuration.

#### Scenario: Reviewing a split file
- **WHEN** the user opens a previously created split log via the review action
- **THEN** the fights in that file are parsed and browsable in the history view, and closing the review returns to live monitoring

### Requirement: Settings dialog
The GUI SHALL provide a settings dialog for the log file path, split-file directory and toggle, reports directory and toggle, and archive options (size threshold with sizing guide, archive directory, delete-original opt-in), persisting them so they survive restarts.

#### Scenario: Changing the log path
- **WHEN** the user selects a different Encounter.log via the settings dialog and confirms
- **THEN** monitoring restarts against the new file and the choice is restored on next launch

### Requirement: Engine reuse without presentation coupling
The GUI SHALL consume the analysis engine through the engine's listener interface; engine modules MUST NOT import GUI toolkits or terminal libraries (curses, colorama, click).

#### Scenario: Identical analysis results
- **WHEN** the same log file is replayed through the GUI review path and through the engine-level test harness
- **THEN** both report the same fights with the same players, DPS percentages, gear sets, and buff uptimes
