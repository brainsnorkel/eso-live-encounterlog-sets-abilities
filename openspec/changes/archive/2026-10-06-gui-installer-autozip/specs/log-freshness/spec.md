# Capability: log-freshness

## ADDED Requirements

### Requirement: Latest-entry timestamp derivation
The system SHALL derive the date/time of the most recent log entry from log content: the most recent `BEGIN_LOG` Unix epoch plus the latest entry's relative millisecond offset. When log content is unavailable for exact derivation (e.g. tailing without a full read and no reachable `BEGIN_LOG`), the system SHALL fall back to the file modification time and mark the value as approximate.

#### Scenario: Exact derivation while tailing
- **WHEN** a new log line with relative offset 3600000 is read under a `BEGIN_LOG` epoch of 1790000000
- **THEN** the latest-entry time is reported as the local time for epoch 1790003600 and marked exact

#### Scenario: Fallback to mtime
- **WHEN** monitoring starts mid-file and no `BEGIN_LOG` epoch can be located in the lookback window
- **THEN** the file's modification time is reported as the latest-entry time and marked approximate

### Requirement: Freshness display in the GUI
The GUI SHALL continuously display the latest-entry date/time together with a human-readable elapsed age (e.g. "3m ago") that updates at least every second, and SHALL distinguish visual states: live (< 2 minutes), idle (2–30 minutes), stale (> 30 minutes), and no log file.

#### Scenario: Fresh entries
- **WHEN** a log entry was written 40 seconds ago
- **THEN** the status area shows the entry's absolute local time with an age of "40s ago" in the live state

#### Scenario: Stale log
- **WHEN** no entry has been written for 45 minutes
- **THEN** the status area shows the stale state with the last entry's time and "45m ago"

#### Scenario: Missing log
- **WHEN** the configured log file does not exist
- **THEN** the status area shows a distinct "no log file" state naming the expected path

### Requirement: Freshness available to the archiver
The latest-entry derivation SHALL be usable at startup, before monitoring begins, so the archive filename timestamp reflects the newest data in the log being archived.

#### Scenario: Archive naming
- **WHEN** a startup archive runs on a log whose last entry derives to 2026-09-27 14:33:02
- **THEN** the archiver receives that timestamp for the archive filename
