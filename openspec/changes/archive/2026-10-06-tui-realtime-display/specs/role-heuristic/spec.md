## ADDED Requirements

### Requirement: Role inferred from max resources
The system SHALL infer each player's role (T, H, or D) based on their highest max resource value observed during the encounter.

#### Scenario: Highest resource is health
- **WHEN** a player's `max_health` is strictly greater than both `max_magicka` and `max_stamina`
- **THEN** the player's inferred role SHALL be **T** (tank)

#### Scenario: Highest resource is stamina
- **WHEN** a player's `max_stamina` is strictly greater than both `max_health` and `max_magicka`
- **THEN** the player's inferred role SHALL be **D** (DPS)

#### Scenario: Highest resource is magicka and player deals more damage than healing
- **WHEN** a player's `max_magicka` is strictly greater than both `max_health` and `max_stamina`
- **AND** the player's total damage dealt to enemies is greater than or equal to their total healing done to other players
- **THEN** the player's inferred role SHALL be **D** (DPS)

#### Scenario: Highest resource is magicka and player heals more than damages
- **WHEN** a player's `max_magicka` is strictly greater than both `max_health` and `max_stamina`
- **AND** the player's total healing done to other players is strictly greater than their total damage dealt to enemies
- **THEN** the player's inferred role SHALL be **H** (healer)

### Requirement: Ability-based fallback for tied resources
When two or more max resources are within 10% of each other, the system SHALL fall back to the existing ability-based role inference from `_infer_role_from_skill_lines()`.

#### Scenario: Resources are within 10% of each other
- **WHEN** a player's top two max resources differ by less than 10% of the higher value
- **THEN** the system SHALL use ability-based role inference as the tiebreaker

#### Scenario: Ability-based inference also inconclusive
- **WHEN** resources are tied and ability-based inference returns no clear role
- **THEN** the player's inferred role SHALL default to **D** (DPS)

### Requirement: Missing healing data defaults to resource-only
When healing data is unavailable for a magicka-primary player, the system SHALL skip the healing-vs-damage check and classify based on abilities or default to D.

#### Scenario: Magicka primary with no healing data
- **WHEN** a player's highest resource is magicka
- **AND** no healing data is available for the encounter
- **THEN** the system SHALL use ability-based inference or default to **D** (DPS)

### Requirement: Role displayed as single character
The role indicator SHALL be displayed as a single uppercase character: `T`, `H`, or `D`.

#### Scenario: Role column in TUI display
- **WHEN** a player's role is inferred
- **THEN** it SHALL appear as exactly one character (`T`, `H`, or `D`) in the role column of the player line
