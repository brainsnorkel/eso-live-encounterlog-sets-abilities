# Capability: buff-timeline (EXPERIMENTAL)

## ADDED Requirements

### Requirement: Interval tracking for tracked effects
When the experimental buff-timeline setting is enabled, the engine SHALL record, per fight, the active intervals of Major Slayer, Major Force, Major Courage, Major Berserk, and Major Vulnerability, where each interval carries the start and end time offsets within the fight, the casting unit, and the receiving unit. When the setting is disabled the engine MUST NOT retain interval data.

#### Scenario: Buff gained and faded
- **WHEN** a player gains Major Force 10s into a fight from another player's cast and it fades at 20s
- **THEN** the fight's timeline data contains a Major Force interval [10s, 20s] attributing the caster and the receiver

#### Scenario: Buff active at fight end
- **WHEN** Major Courage is still active when END_COMBAT arrives
- **THEN** the interval is closed at the fight's end time

#### Scenario: Toggle off
- **WHEN** the experimental setting is disabled
- **THEN** completed fights carry no timeline data and the strip is not rendered

### Requirement: Compact timeline strip
The GUI SHALL render the tracked effects as a mini timeline in the fight detail view: one thin colored row per effect (a stable color per effect), the row filled where the effect was active, with time tick marks along the axis. The strip MUST stay compact (on the order of 6 rows of roughly 10 pixels plus an axis) and MUST NOT displace or obscure the existing fight summary content; it SHALL carry an "experimental" marking.

#### Scenario: Strip renders under the fight header
- **WHEN** the setting is enabled and a fight with timeline data is displayed
- **THEN** the strip appears between the fight header and the player table, with one row per tracked effect that had any activity and tick marks scaled to the fight duration

#### Scenario: Effect with no activity
- **WHEN** a tracked effect never occurred during the fight
- **THEN** its row is omitted (or rendered empty) without expanding the strip

### Requirement: Hover attribution
Hovering a filled segment SHALL show a tooltip naming the effect, the interval's time range, who cast it, and who received it; overlapping intervals at the hovered instant SHALL all be listed.

#### Scenario: Hovering a segment
- **WHEN** the user hovers the Major Slayer row 45s into the fight where two casters' procs overlap
- **THEN** the tooltip lists both intervals with caster and receiver names

### Requirement: Experimental settings gate
The settings dialog SHALL offer an "Experimental: buff timeline" toggle, off by default, persisted with the other settings.

#### Scenario: Enabling the experiment
- **WHEN** the user enables the toggle and a new fight completes
- **THEN** that fight (and later ones) render the strip; previously recorded fights without data render without it
