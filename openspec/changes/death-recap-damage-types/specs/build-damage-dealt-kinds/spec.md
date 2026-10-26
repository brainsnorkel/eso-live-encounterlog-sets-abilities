# Spec Delta

## Purpose

The build window's "Damage dealt" section: the kinds of damage a player dealt in the fight, in the vocabulary of the `damage-kinds` capability, so a damage dealer can read what kind of build the fight shows.

## ADDED Requirements

### Requirement: A Damage dealt section in the build window

The build window SHALL show, after the ability bars and before the Penetration section, a "Damage dealt" section over the player's damage in the fight as the damage record counts it (the player's and their pets' hits on every target, shield absorbs included): the total, three two-sided bars with percentages (direct against over time, area against single target, Martial against Magical), a line of the damage types behind the sides, the amounts outside the sides named, and the share of the damage that shield absorbs made up. A player who dealt no damage SHALL get one line saying so.

#### Scenario: A fire damage dealer

- **WHEN** a player dealt 3,200,000 damage, 62% of it ticks, 55% from area skills, 97% fire or magic and 3% physical
- **THEN** the section shows 3,200,000, a direct/over time bar at 38%/62%, an area/single bar at 55%/45%, a Martial/Magical bar at 3%/97%, and the types line

#### Scenario: A healer who dealt nothing

- **WHEN** a player's damage record holds no damage
- **THEN** the section is one line, "This player dealt no damage in this fight"

### Requirement: Area or single target for a player's skills

The section SHALL class a player's hits by the `damage-kinds` rule for player damage: a cast that struck two or more units is area; otherwise the bundled table of player skills decides; a skill in neither is single target, and the section's hover text SHALL say how many of the damage's percent points rest on the table and how many on casts.

#### Scenario: Area skills on a single boss

- **WHEN** every cast in the fight struck the one boss and 70% of the damage came from skills the table lists as Area or Ground
- **THEN** the area side reads 70%, and its hover says the share rests on the skill table

### Requirement: Hovering a side names the stars

Hovering either side of a bar SHALL show the hover text the `damage-kinds` capability defines for damage dealt (Master-at-Arms, Thaumaturge, Biting Aura, Deadly Aim, War Mage, Mighty).

#### Scenario: Hover on the area side

- **WHEN** the reader hovers the area side
- **THEN** the hover names Biting Aura with its tooltip text and ESO-Hub link

### Requirement: Fights recorded before the change

A fight entry whose damage record has no kinds SHALL show one muted line saying the kinds were not recorded for this fight, and the rest of the build window as before.

#### Scenario: An old fight

- **WHEN** the build window opens on an entry from before the change
- **THEN** the section reads "Damage kinds were not recorded for this fight" and the Penetration section follows as usual
