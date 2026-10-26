# Spec Delta

## Purpose

What the death recap window shows about the kinds of damage a player took and the healing they received: a summary of each death's last five seconds and a summary of the whole fight, in the vocabulary of the `damage-kinds` capability.

## ADDED Requirements

### Requirement: A summary of each death's last seconds

For each death the window SHALL show, between the "Killed by" line and the event table, a summary of the events in the recap window: the damage that reached health as a total and as three two-sided bars (direct against over time, area against single target, Martial against Magical) each carrying its percentages, the damage types behind the two sides as a line of text, the amounts that fall outside the sides (Oblivion, fall, drowning, untyped) named, what got through while blocking, what shields absorbed, how many hits were avoided, the healing that landed against the overheal with its direct and over-time shares, and the killing blow's overkill. A line whose amount is zero SHALL be left out. A death whose window holds no damage SHALL say so in one line instead of drawing empty bars.

#### Scenario: A death by a damage over time mechanic

- **WHEN** a player died with 29,626 damage in the window, 76% of it ticks of one area ability, all fire, 3,848 absorbed by a shield, 2,419 healed and 45,236 overheal
- **THEN** the summary shows the total 29,626, a direct/over time bar at 24%/76%, an area/single bar at 76%/24%, a Martial/Magical bar at 0%/100%, the types line "fire 100%", "3,848 absorbed by shields", "healed 2,419 · 45,236 overheal", and no line for blocking or avoided hits

#### Scenario: A one-shot

- **WHEN** a player at full health died to a single 20,372 hit and nothing else landed in the window
- **THEN** the summary shows the total and the bars at 100%/0% for direct and single target, the type line "physical 100%", and the overkill from the killing blow's line

#### Scenario: Only heals in the window

- **WHEN** the window holds heals and no damage line (the killing blow is the only damage and is folded into the row above the table)
- **THEN** the summary is one line saying no damage was logged in the window other than the killing blow, with the healing and overheal figures

### Requirement: The whole fight's damage taken

The window SHALL open with a block for the player's whole fight: every hit the player took from the first to the last, as the same total, bars and lines as the per-death summary, followed by the abilities that did the most damage to them, at most five, each with its damage, its share, its kind words (direct or over time, area or single target, type) and its source. The block SHALL be measured over the fight as the engine recorded it, including hits after the last death, and SHALL say over how many seconds of combat the player was alive.

#### Scenario: A player who died twice

- **WHEN** a player died twice in a fight of four minutes and took 310,000 damage in all
- **THEN** the block at the top shows 310,000 with its bars once, and the two per-death summaries below show only their own five seconds

#### Scenario: The top abilities

- **WHEN** a player took 60% of their damage from Maelstrom (area, physical, direct) and 20% from Soaked Wound (single target, frost, over time)
- **THEN** the block lists Maelstrom first with "60% · direct · area · physical" and Soaked Wound second with "20% · over time · single target · frost"

### Requirement: Each row names its kind

The Result column of the event table SHALL add the damage type after the result ("Hit · fire", "DoT · physical") and, for a hit classed area, "area · hit N players" with N the number of distinct players its cast struck in the fight; the existing absorbed, overkill and avoided texts stay.

#### Scenario: An area hit's row

- **WHEN** a row is a `DAMAGE` of `SHOCK` from a cast that struck 12 players
- **THEN** its Result cell reads "Hit · shock · area · hit 12 players"

### Requirement: Hovering a side names the stars

Hovering either side of a bar in this window SHALL show the hover text the `damage-kinds` capability defines for damage taken (Ironclad, Enduring Resolve, Unassailable, Duelist's Rebuff, Elemental Aegis, Hardy, Preparation) and, on the healing line, for healing received.

#### Scenario: Hover on the Martial side

- **WHEN** the reader hovers the Martial side of the whole-fight bar
- **THEN** the hover names Hardy and Preparation with their tooltip texts and ESO-Hub links

### Requirement: Fights recorded before the change

A fight entry recorded before the kinds were kept SHALL render the window as before, with one muted line in place of each new block saying the kinds were not recorded for this fight, and no error.

#### Scenario: An old fight

- **WHEN** the window is opened on a fight entry whose recaps carry no kinds and whose player dict has no damage-taken record
- **THEN** the event table renders as it did, and the two new blocks read "Damage kinds were not recorded for this fight"

### Requirement: Theme

The bars and texts SHALL follow the window's dark and light themes like the rest of the recap, and re-render on a theme switch.

#### Scenario: Theme switch while open

- **WHEN** the theme changes while the window is open
- **THEN** the bars are redrawn in the new theme's colours
