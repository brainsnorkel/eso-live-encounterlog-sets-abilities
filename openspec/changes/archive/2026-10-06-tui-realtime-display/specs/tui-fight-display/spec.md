## ADDED Requirements

### Requirement: Full-screen TUI renders last completed fight
The system SHALL display the most recently completed encounter in a full-screen terminal UI, replacing the scrolling print output when stdout is a TTY.

#### Scenario: Fight completes during tail mode
- **WHEN** an encounter ends (END_COMBAT event) during live tailing
- **THEN** the TUI SHALL render the encounter summary in a fixed-layout full-screen display
- **AND** the display SHALL remain visible until the next fight completes or the user scrolls

#### Scenario: Non-TTY output falls back to print mode
- **WHEN** stdout is not a TTY (piped or redirected)
- **THEN** the system SHALL use the existing print-based output format

#### Scenario: User passes --no-tui flag
- **WHEN** the `--no-tui` CLI flag is provided
- **THEN** the system SHALL use the existing print-based output format regardless of TTY status

### Requirement: Compact one-line-per-player display
Each player in the encounter SHALL be displayed on a single line containing: role indicator (T/H/D), player name, class abbreviation, DPS, damage percentage, and compact resource values (H/M/S with k-suffix).

#### Scenario: Four-player group fight completes
- **WHEN** a 4-player encounter ends with damage data for all players
- **THEN** the TUI SHALL show exactly 4 player lines, sorted by damage dealt descending
- **AND** each line SHALL contain role, name, class, DPS, damage%, and H/M/S values

#### Scenario: First damage dealer is marked
- **WHEN** an encounter has a tracked first damage dealer
- **THEN** that player's line SHALL be prefixed with `*` before the role indicator

### Requirement: Encounter header shows summary stats
The encounter header line SHALL display: timestamp, zone name (with vet indicator), duration, group DPS, and death count.

#### Scenario: Veteran trial encounter completes
- **WHEN** a veteran trial encounter ends with duration 12m34s, group DPS 245.3k, and 2 deaths
- **THEN** the header SHALL show the timestamp, zone name with "(vet)", formatted duration, group DPS, and death count

### Requirement: Fight history scrolling
The user SHALL be able to scroll through previous fights using keyboard controls while in the TUI.

#### Scenario: User scrolls to previous fight
- **WHEN** the user presses up-arrow or `k`
- **THEN** the TUI SHALL display the previous fight in the history
- **AND** the status bar SHALL show the current position (e.g. "Fight 11/14")

#### Scenario: User scrolls forward
- **WHEN** the user presses down-arrow or `j`
- **THEN** the TUI SHALL display the next fight in the history

#### Scenario: User returns to live mode
- **WHEN** the user presses `G` or `End`
- **THEN** the TUI SHALL snap to the latest fight and resume auto-advancing when new fights complete

#### Scenario: Auto-advance when at latest fight
- **WHEN** the user is viewing the latest fight (live mode)
- **AND** a new fight completes
- **THEN** the TUI SHALL automatically display the new fight

#### Scenario: No auto-advance when scrolled back
- **WHEN** the user is viewing a historical fight (not the latest)
- **AND** a new fight completes
- **THEN** the TUI SHALL NOT change the displayed fight
- **AND** the status bar SHALL update to reflect the new total count

### Requirement: Quit key exits the TUI
The user SHALL be able to exit the TUI and terminate the program by pressing `q`.

#### Scenario: User presses q
- **WHEN** the user presses `q` while the TUI is active
- **THEN** the program SHALL restore the terminal to normal mode and exit cleanly

### Requirement: Buff uptime summary line
When group buff data is available, a compact buff summary line SHALL be displayed below the player table.

#### Scenario: Trial encounter with buff tracking
- **WHEN** an encounter with 3+ players has buff uptime data
- **THEN** a summary line SHALL show tracked buff names and their uptime percentages
