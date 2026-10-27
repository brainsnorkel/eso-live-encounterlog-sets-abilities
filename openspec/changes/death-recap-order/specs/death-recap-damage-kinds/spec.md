# Spec Delta

## Purpose

The order of the death recap window and the word for damage over time (issue #95), modifying the `death-recap-damage-kinds` capability of the change `death-recap-damage-types`.

## MODIFIED Requirements

### Requirement: A summary of each death's last seconds

For each death the window SHALL show the "Killed by" line, then the event table, then under the table a summary of the events in the recap window: the damage that reached health as a total and as three two-sided bars (direct against DoT, area against single target, Martial against Magical) each carrying its percentages, the damage types behind the two sides as a line of text, the amounts that fall outside the sides (Oblivion, fall, drowning, untyped) named, what got through while blocking, what shields absorbed, how many hits were avoided, the healing that landed against the overheal with its direct and HoT shares, and the killing blow's overkill. A line whose amount is zero SHALL be left out. A death whose window holds no damage SHALL say so in one line under the table instead of drawing empty bars.

#### Scenario: The table before its summary

- **WHEN** a player died with hits and heals in the window
- **THEN** the event table follows the "Killed by" line at once, and the summary's total, bars and lines follow the table

### Requirement: The whole fight's damage taken

The window SHALL close with a block for the player's whole fight, after the last death: every hit the player took from the first to the last, as the same total, bars and lines as the per-death summary, followed by the abilities that did the most damage to them, at most five, each with its damage, its share, its kind words (direct or DoT, area or single target, type) and its source. The block SHALL be measured over the fight as the engine recorded it, including hits after the last death, and SHALL say the span from the first hit the player took to the last.

#### Scenario: A player who died twice

- **WHEN** a player died twice in a fight of four minutes and took 310,000 damage in all
- **THEN** the two per-death summaries come first, each under its own table, and the block at the bottom shows 310,000 with its bars once

### Requirement: Damage over time is written DoT

Beside the bars, in the heal share, in the ability kind words and in the star hover headings the window SHALL write damage over time as `DoT` and healing over time as `HoT`, the words the Result column uses; the build window's Damage dealt bars, drawn by the same block, SHALL say the same.

#### Scenario: The top abilities

- **WHEN** a player took 20% of their damage from Soaked Wound (single target, frost, over time)
- **THEN** the block lists it with "20% · DoT · single target · frost"

#### Scenario: Hover on the DoT side

- **WHEN** the reader hovers the DoT label of a damage-taken bar
- **THEN** the hover is headed "Warfare stars for DoT damage taken" and names Enduring Resolve and Preparation with their tooltip texts
