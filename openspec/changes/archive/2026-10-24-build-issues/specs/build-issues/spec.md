# build-issues

## Purpose

The rules the app applies to a player's build as the encounter log records it, to point out likely mistakes; what each finding says; and where the fight pane and the build window show the findings.

## ADDED Requirements

### Requirement: Findings per player per fight

For every player listed in a fight, the app SHALL evaluate the build issue rules against the build the log recorded for that fight and attach the findings to the player. Each finding SHALL say what was found in that player's build (the slot, glyph, piece count, skill or set concerned) and state the rule it comes from in plain language, so a reader who does not know the rule learns it from the finding. A player with no finding SHALL carry an empty list.

#### Scenario: A clean build
- **WHEN** a player's logged build matches no rule
- **THEN** the player has no findings

#### Scenario: A finding states its rule
- **WHEN** a finding is produced
- **THEN** its text names the item it is about AND explains why it is an issue

### Requirement: Nirnhoned on an off-hand weapon

The app SHALL report a weapon with the Nirnhoned weapon trait in the off hand of either bar, naming the bar and the weapon, and stating that Dual Wield Expert counts only 6% of an off-hand weapon's damage so the trait gives about a sixteenth of what it gives in the main hand. A shield with the Nirnhoned armor trait SHALL NOT be reported.

#### Scenario: Nirnhoned off-hand dagger
- **WHEN** the front-bar off hand is a dagger with trait `WEAPON_NIRNHONED`
- **THEN** a finding names the front bar's off-hand dagger

#### Scenario: Nirnhoned shield
- **WHEN** the off hand is a shield with trait `ARMOR_NIRNHONED`
- **THEN** no finding

### Requirement: The same glyph on both weapons of a bar

The app SHALL report a bar whose two weapons carry the same weapon enchantment, whatever the enchantment, stating that identical glyphs share one cooldown so the second never fires. A shield's enchantment SHALL NOT be compared with the weapon's. The same enchantment on the weapons of different bars SHALL NOT be reported.

#### Scenario: Two Absorb Stamina daggers
- **WHEN** the front bar holds two weapons both enchanted `ABSORB_STAMINA`
- **THEN** a finding names the front bar and the glyph

#### Scenario: One glyph per bar
- **WHEN** the front-bar weapon and the back-bar weapon both carry `BERSERKER`
- **THEN** no finding

### Requirement: Heavy armor on a damage dealer

The app SHALL report a player whose role reads DPS, who has not taunted in the logging session, and who wears two or more heavy armor pieces, naming the count and stating that Heavy Armor's passives add nothing to damage and that one heavy piece is the usual Undaunted Mettle split. One heavy piece SHALL NOT be reported. A tank or healer, or a player who taunted earlier in the session, SHALL NOT be reported.

#### Scenario: Five heavy on a DPS
- **WHEN** a player whose role is DPS wears five heavy pieces and never taunted
- **THEN** a finding names five heavy pieces

#### Scenario: The Undaunted Mettle piece
- **WHEN** a DPS wears one heavy, one light and five medium pieces
- **THEN** no finding

#### Scenario: A stamina-heavy tank
- **WHEN** a player whose role reads DPS wears five heavy pieces and taunted in an earlier fight of the session
- **THEN** no finding

### Requirement: A weapon skill on the wrong bar

The app SHALL report a slotted skill of a weapon skill line (Two Handed, One Hand and Shield, Dual Wield, Bow, Destruction Staff, Restoration Staff) on a bar whose weapons belong to another of those lines, naming the skill, its line, the bar and the weapon held, and stating that the skill cannot be cast from that bar. A bar whose weapon the app cannot identify SHALL NOT be judged. The back bar of a player wearing Oakensoul Ring SHALL NOT be judged. A scribed skill SHALL be judged by its grimoire's weapon line.

#### Scenario: Stampede on a staff
- **WHEN** the back bar holds an inferno staff and Stampede is slotted on it
- **THEN** a finding names Stampede, Two Handed and the staff

#### Scenario: Under Oakensoul
- **WHEN** the player wears Oakensoul Ring and the back bar holds a bow skill over daggers
- **THEN** no finding

#### Scenario: Unknown weapon
- **WHEN** the main-hand item id is not in the bundled weapon table
- **THEN** no finding for that bar

### Requirement: Elemental Drain

The app SHALL report Elemental Drain slotted on either bar, naming the bar and stating what the other morph, Elemental Susceptibility, applies (Burning, Chilled and Concussion every 7.5 seconds on top of Major Breach) and what Drain gives instead (Major Breach and Minor Magickasteal).

#### Scenario: Drain slotted
- **WHEN** a bar holds Elemental Drain at any rank
- **THEN** a finding names the bar

#### Scenario: Susceptibility slotted
- **WHEN** a bar holds Elemental Susceptibility
- **THEN** no finding

### Requirement: A proc set that never fires

For Roar of Alkosh and Roaring Opportunist worn at five pieces on either bar, the app SHALL count, per player and logging session, the fights of 60 seconds or more in which the set was worn, and whether the set's effect was ever sourced by the player in any fight of the session. When at least one such fight has passed and the effect never fired, each fight's findings for that player SHALL name the set, the count of long fights, and what triggers the set (a synergy activated; a fully charged heavy attack). A fire in any fight of the session, long or short, SHALL clear the finding for the rest of the session. A fight the game cut in two SHALL count once.

#### Scenario: Alkosh without a synergy
- **WHEN** a player wears five pieces of Roar of Alkosh through a 90-second fight and never sources its effect
- **THEN** that fight's findings name Roar of Alkosh and one fight of a minute or more

#### Scenario: A short fight
- **WHEN** the same player's only fight so far lasted 20 seconds
- **THEN** no finding

#### Scenario: It fired once
- **WHEN** the player sourced the effect in a 15-second fight and then fought 120 seconds without it firing
- **THEN** no finding

### Requirement: A group buff set on one bar

For Pearlescent Ward, Xoryn's Masterpiece and Lucent Echoes (perfected or not), the app SHALL report a build that reaches five pieces on one weapon bar and fewer on the other, naming the set, the bar it is complete on and both counts, and stating that the group loses the buff whenever the player swaps bars. A build with no back-bar weapon logged, or wearing Oakensoul Ring, SHALL NOT be reported. Other sets SHALL NOT be reported by this rule.

#### Scenario: Pearlescent Ward on the back bar only
- **WHEN** four body pieces of Pearlescent Ward and a Pearlescent Ward sword on the back bar
- **THEN** a finding names Pearlescent Ward, the back bar and 4/5

#### Scenario: A front-bar damage set
- **WHEN** Deadly Strike reaches five on the front bar and three on the back
- **THEN** no finding

### Requirement: A tank with no taunt or pull

The app SHALL report a player who reads as a tank and holds neither a taunt nor a pull. A player reads as a tank when their role is tank, they hold a shield or an ice staff on a bar or five or more heavy pieces, they dealt at most half an equal share of the group's damage in the fight, no restoration staff is on their bars and they did not heal others for more than they dealt. A taunt is Puncture, Inner Fire or Runic Jolt or one of their morphs, Destructive Clench on a bar holding an ice staff, or a scribed skill with the Taunt focus; a pull is Chains of Flame or its morphs, Silver Leash, Frozen Gate or its morphs, or a scribed skill with the Pull focus. A player who taunted at any time in the logging session, or whose bars are not logged, SHALL NOT be reported. The finding SHALL say what made the player read as a tank and name the kinds of skill missing. (Added 2026-10-24 at the maintainer's request, after a survey in which real tanks dealt a median tenth of an equal share and the health pool alone misread healers and damage dealers as tanks.)

#### Scenario: A shield tank with nothing to hold the boss
- **WHEN** a player whose role is tank holds a shield, dealt a tenth of an equal share, has no taunt or pull on either bar and never taunted this session
- **THEN** a finding says the tank has no taunt or pull

#### Scenario: A pull is enough
- **WHEN** the same player slots Chains of Flame
- **THEN** no finding

#### Scenario: A heavy-armor healer
- **WHEN** a health-dominant player in seven heavy pieces holds a restoration staff and no taunt
- **THEN** no finding

#### Scenario: A damage dealer with a shield
- **WHEN** a health-dominant player with a shield dealt one and a half times an equal share
- **THEN** no finding

### Requirement: The (i) on the fight pane

The fight pane SHALL show an `(i)` after the name and class of each player with at least one finding, in the theme's link color, and nothing for a player without one. Hovering the `(i)` SHALL list the findings' titles. Clicking it SHALL open a transient popup near the pointer listing each finding with its rule, where a set or skill the finding names links to its ESO-Hub page when one is known. The popup SHALL close on a click elsewhere or Esc.

#### Scenario: One flagged player among three
- **WHEN** a fight lists three players and one has findings
- **THEN** that player's row carries the `(i)` AND the other two rows do not

#### Scenario: Opening the popup
- **WHEN** the `(i)` is clicked
- **THEN** a popup shows every finding of that player with its rule text

### Requirement: The build window repeats the findings

The build window SHALL list the same findings under the player's header, each with its rule, and show nothing there for a player without findings.

#### Scenario: Build window of a flagged player
- **WHEN** the build window opens for a player with two findings
- **THEN** both findings and their rules appear under the header
