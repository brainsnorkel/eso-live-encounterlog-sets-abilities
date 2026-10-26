# Spec Delta

## Purpose

How the app classifies a hit or a heal written in the encounter log into the kinds the Warfare champion point stars act on, what it refuses to claim because the log does not carry it, and the vocabulary every window that shows these kinds shares.

## ADDED Requirements

### Requirement: Direct damage or damage over time

A damage line SHALL be classed by its result: `DAMAGE`, `CRITICAL_DAMAGE` and `BLOCKED_DAMAGE` are direct damage; `DOT_TICK` and `DOT_TICK_CRITICAL` are damage over time; `FALL_DAMAGE` is fall damage, neither direct nor over time, and is named as such. The amount classed is the hit value, the damage that reached health.

#### Scenario: A tick and a hit of the same ability

- **WHEN** a player takes a `DOT_TICK` of 1,200 and a `DAMAGE` of 8,000 from the same ability
- **THEN** 1,200 is counted as damage over time and 8,000 as direct damage

#### Scenario: Fall damage

- **WHEN** a player takes a `FALL_DAMAGE` line of 15,000 (damage type `GENERIC`, the ability "Fall Snare")
- **THEN** it is counted as fall damage, under neither direct nor over time and neither Martial nor Magical, and the summary names it "fall"

### Requirement: Martial, Magical, Oblivion or unresisted

A damage line SHALL be classed by its damage type: `PHYSICAL`, `BLEED`, `POISON` and `DISEASE` are Martial; `MAGIC`, `FIRE`, `COLD` and `SHOCK` are Magical; `OBLIVION` is Oblivion; `DROWN` is drowning; `GENERIC`, `NONE`, `EARTH` and any type the app does not know are untyped and shown under the log's own word in lower case, so a type a later game patch adds is counted and named rather than dropped or refused. Oblivion, drowning and the untyped are named apart from the Martial and Magical sides rather than folded into either. The individual damage types SHALL be kept beside the two sides, with `COLD` shown as "frost", the game's word.

#### Scenario: A mixed five seconds

- **WHEN** the damage a player took was 16,000 of `FIRE`, 4,000 of `SHOCK` and 13,000 of `PHYSICAL`
- **THEN** the Magical side is 20,000 (61%) and the Martial side 13,000 (39%), and the types read fire 48%, physical 39%, shock 12%

#### Scenario: Oblivion damage

- **WHEN** a player took 9,000 of `OBLIVION` damage and 9,000 of `MAGIC`
- **THEN** the Magical side is 9,000, the Martial side 0, and 9,000 is shown as Oblivion, outside both sides

#### Scenario: A type the app does not know

- **WHEN** a player takes a `DAMAGE` line of 6,526 whose damage type is `EARTH`, or a type no release of the app has seen
- **THEN** the hit counts in the total and in direct damage, is named "earth" (the log's word in lower case) among the untyped amounts, and nothing is raised or dropped

### Requirement: Area or single target from the log

A hit SHALL be classed area when the cast it belongs to (the same source unit and cast id) struck two or more distinct units in the fight, counting every hit of that cast in the fight, before and after this one. A hit of a cast that struck one unit SHALL be classed area when another cast of the same ability struck two or more units earlier in the logging session, and single target otherwise. For a hit dealt by a player or their pet whose cast and ability give no such evidence, the bundled table of player skills' target kinds decides: Area, Cone or Ground is area, Enemy is single target. The app SHALL say which evidence classed a hit when asked (the hover text), and SHALL never class a hit from a monster by a table.

#### Scenario: One cast, many players

- **WHEN** a monster's cast id 4711 hits player A at 0.0 s and players B, C and D within the next second
- **THEN** all four hits are area hits, A's included, and the hover text says the cast hit 4 players

#### Scenario: One cast, one player, in a group of twelve

- **WHEN** a monster's cast id 4712 hits only player A in the fight and no earlier cast of that ability struck two or more units this session
- **THEN** the hit is single target

#### Scenario: A boss seen before in the session

- **WHEN** an ability struck 8 players on one cast in the first pull and strikes one player on a cast in the third pull
- **THEN** the third pull's hit is area, and the hover text says the ability struck 8 players on one cast earlier in the session

#### Scenario: A player's area skill on a lone boss

- **WHEN** a player's Impulse hits the only enemy of the fight, so no cast of it struck two units
- **THEN** the hit is area because the bundled table says Impulse's target is Area

### Requirement: Blocked, absorbed and avoided

The hit value of a `BLOCKED_DAMAGE` line is the damage that got through the block and SHALL be counted as direct damage and also reported as "got through while blocking"; the app SHALL NOT state how much the block prevented, which the log does not carry. A `DAMAGE_SHIELDED` line SHALL be reported as damage a shield absorbed and SHALL NOT be added to the damage that reached health. `DODGED` and `MISS` SHALL be reported as avoided, by count. `IMMUNE` and `REFLECTED` lines SHALL NOT be counted.

#### Scenario: A blocked hit

- **WHEN** a player takes a `BLOCKED_DAMAGE` line of 4,073
- **THEN** 4,073 counts in direct damage and the summary says 4,073 got through while blocking, with no figure for what the block saved

### Requirement: Healing, overheal and absorbed healing

`HEAL` and `CRITICAL_HEAL` SHALL be classed direct heals and `HOT_TICK` and `HOT_TICK_CRITICAL` heals over time; the hit value is healing that landed and the overflow is overheal, and a heal line whose hit value is zero still contributes its overflow to the overheal sum. `HEAL_ABSORBED` SHALL be reported as healing a healing-absorb effect ate.

#### Scenario: Mostly overheal

- **WHEN** the heals on a player in a window landed 2,419 and overflowed 45,236
- **THEN** the summary says healed 2,419 with 45,236 overheal

### Requirement: Overkill

The overflow on the killing blow's damage line SHALL be reported as overkill; a killing blow written as `BLOCKED_DAMAGE` or `FALL_DAMAGE` carries none in the log and the summary SHALL show none.

#### Scenario: Overkill on the killing blow

- **WHEN** the killing blow's line carries a hit value of 20,372 and an overflow of 6,100
- **THEN** the summary reports 6,100 overkill

### Requirement: What the app does not claim

The app SHALL NOT class a hit as melee or ranged, SHALL NOT state the damage a resistance or a block prevented, and SHALL NOT report critical hits taken; the user guide's list of what the log cannot show SHALL say so.

#### Scenario: No range figure anywhere

- **WHEN** a recap, a fight summary or a build section is rendered
- **THEN** no text classes damage as melee or ranged

### Requirement: The Warfare stars named for each side

Each side of each split SHALL have hover text naming the Warfare champion point stars that act on it, with the game's tooltip text and a link to the star's page on eso-hub.com: damage dealt direct Master-at-Arms, over time Thaumaturge, area Biting Aura, single target Deadly Aim, Magical War Mage, Martial Mighty; damage taken direct Ironclad, over time Enduring Resolve, area Unassailable, single target Duelist's Rebuff, Magical Elemental Aegis, Martial Hardy, with Preparation on all damage from monsters; healing direct Focused Mending, over time Swift Renewal, landed Blessed and Quick Recovery, overheal Enlivening Overflow. The app SHALL NOT state or assume which stars a player has slotted.

#### Scenario: Hovering the damage over time side

- **WHEN** the reader hovers the "over time" side of a damage-taken bar
- **THEN** the hover text names Enduring Resolve with its tooltip text and links to its ESO-Hub page, and says nothing about whether the player has it

#### Scenario: Preparation on every damage-taken side

- **WHEN** the reader hovers any side of any damage-taken bar
- **THEN** the hover also names Preparation, since every hit from a monster is "non-player" damage, and the hover of a damage-dealt bar does not
