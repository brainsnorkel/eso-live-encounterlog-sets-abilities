# Capability: player-build-window

## Purpose

Lets a raid lead inspect one player's full build for a fight in a window of its own: ability bars, per-slot gear with trait and enchant detail, slotted poisons, mundus stone and food. It shows only what the encounter log recorded for that player at the start of that fight, named with the help of bundled reference data.

## ADDED Requirements

### Requirement: Open a player's build from the fight view
Every player listed in the fight view SHALL have their name act as a link that opens the build window for that player in the fight on screen, in both the detail view and the compact view. While the pointer is elsewhere the name SHALL keep its existing appearance, and it SHALL remain findable by the in-fight search. Existing links in the fight view (death recap buttons, ESO-Hub skill and set links) MUST keep working unchanged.

#### Scenario: Clicking a name in the detail view
- **WHEN** the user clicks a listed player's name in the detail view
- **THEN** the build window opens showing that player's build for the fight on screen

#### Scenario: Clicking a name in the compact view
- **WHEN** the detail view is switched off and the user clicks a listed player's name
- **THEN** the same build window opens for that player

#### Scenario: Other links are unaffected
- **WHEN** the user clicks a death recap button or an ESO-Hub link in the same fight
- **THEN** the death recap window or the browser opens as before, and no build window opens

#### Scenario: Player without a logged build
- **WHEN** a player appears only under "Also died" because the log never carried a build for them
- **THEN** their name is not a build link

### Requirement: Hover cue on a player's name
While the pointer is over a listed player's name, the fight view SHALL show that the name can be clicked: the name SHALL be underlined and drawn in the theme's link color, the pointer SHALL become a pointing hand, and a tooltip SHALL say that clicking opens the player's build. When the pointer leaves, the name SHALL return to its normal appearance. Only the hovered name SHALL change. The cue MUST NOT remove or alter the in-fight search's highlights. It SHALL work in the detail view and the compact view, in light and dark themes.

#### Scenario: Pointer over a name
- **WHEN** the pointer moves onto a listed player's name
- **THEN** that name is underlined and drawn in the link color, the pointer is a pointing hand, and a tooltip says that clicking opens the player's build

#### Scenario: Pointer leaves the name
- **WHEN** the pointer moves off the name
- **THEN** the name looks as it did before, and no other name changed in the meantime

#### Scenario: Search highlights stay
- **WHEN** the in-fight search has highlighted matches and the pointer moves onto and off a player's name
- **THEN** the search highlights are shown throughout

#### Scenario: Another fight is drawn while a name is hovered
- **WHEN** a different fight is drawn while the pointer is over a name
- **THEN** the newly drawn fight carries no leftover hover styling

#### Scenario: Other links
- **WHEN** the pointer is over an ability icon, a set name or a death recap button
- **THEN** their existing hover text appears and no player name is restyled

### Requirement: One reusable window pinned to its fight
The build window SHALL be modeless, so the main window stays usable beside it. Asking for another player's build SHALL reuse the same window. Once opened, the window SHALL keep showing the fight and player it was opened for until the user clicks another name, even when a new fight arrives or another fight is selected in the history list.

#### Scenario: Second player reuses the window
- **WHEN** the build window is open for one player and the user clicks another player's name
- **THEN** the same window now shows the second player, and its title names them

#### Scenario: New fight arrives while the window is open
- **WHEN** the build window is open and a new fight completes and becomes the fight on screen
- **THEN** the build window still shows the build it was opened for

### Requirement: Build header
The window SHALL show the player's display name as in the fight view, their character name, race, class, champion points and role, and the fight the build belongs to (boss or mob name, zone with the veteran marker, and time). When the build borrows a skill line from another class, the header SHALL show the skill lines as the fight view does. The header SHALL state that the build is as logged at the start of the fight. A part the log did not supply SHALL be left out rather than shown as a placeholder.

#### Scenario: Full header
- **WHEN** the window opens for a Dark Elf Nightblade with 3225 champion points who dealt damage as a DPS in a veteran Sunspire fight
- **THEN** the header shows the display name, the character name, "Dark Elf Nightblade", "CP 3225", the role, and the boss, zone, veteran marker and time of that fight

#### Scenario: Anonymous player
- **WHEN** the log carried no account or character name for the player
- **THEN** the header shows the same name the fight view shows for them and omits the character name

#### Scenario: Snapshot caption
- **WHEN** the window opens for any player
- **THEN** it states that the build is as logged at the start of the fight

### Requirement: Ability bars stacked
The window SHALL show the front bar above the back bar. Each slotted ability SHALL be drawn as its bundled icon, or as its name when no icon is bundled. On a bar with six logged abilities the sixth (the ultimate) SHALL be set apart from the first five. Hovering an ability SHALL show its name, and clicking it SHALL open its ESO-Hub page when one is known. A bar the log lists as empty SHALL be omitted. Scribed skills SHALL be presented as the fight view presents them: hovering one names its grimoire and scripts, and the bars SHALL be followed by a line listing each scribed skill with its signature and affix scripts, or saying that the scripts are not in the log.

#### Scenario: Two full bars
- **WHEN** the log lists six abilities on each bar
- **THEN** the window shows two rows of six, front above back, with each ultimate set apart

#### Scenario: No back bar
- **WHEN** the log lists six front-bar abilities and none on the back bar
- **THEN** the window shows the front bar only

#### Scenario: Ability without a bundled icon
- **WHEN** a slotted ability has no bundled icon
- **THEN** its name appears in that slot, with the same hover and click behavior

#### Scenario: Ability without an ESO-Hub page
- **WHEN** a slotted ability has no known ESO-Hub page
- **THEN** hovering shows its name and clicking opens nothing

#### Scenario: Scribed skill with known scripts
- **WHEN** a bar holds Shocking Banner scribed with the Class Flourish and Heroism scripts
- **THEN** the line under the bars reads "Shocking Banner (Class Flourish / Heroism)", and hovering the skill's icon names its grimoire and all three scripts

#### Scenario: Scribed skill whose scripts the log does not give
- **WHEN** the log does not tie a script combination to the player for a scribed skill on their bar
- **THEN** the line under the bars shows that skill with "(scripts not in log)", as the fight view does

#### Scenario: Bar with fewer than six abilities
- **WHEN** the log lists fewer than six abilities on a bar
- **THEN** they are shown in logged order with none set apart, because the log does not say which slot was empty

### Requirement: Gear grid
The window SHALL show a grid with one row per gear slot, in this fixed order and grouping: Armor (Head, Shoulders, Chest, Hands, Waist, Legs, Feet), Jewelry (Neck, Ring 1, Ring 2), Front bar (Main hand, Off hand), Back bar (Main hand, Off hand). Each row SHALL show the slot, the item's set, the pieces of that set that are active, the item's quality, its trait, its enchant, and the enchant's quality. A slot the log did not list SHALL still have its row, showing a dash in place of the item's details. Costume items SHALL NOT be shown.

#### Scenario: Complete build
- **WHEN** the log lists items in all fourteen slots
- **THEN** the grid shows fourteen item rows under the four group headings, each with set, pieces, quality, trait, enchant and enchant quality

#### Scenario: Two-handed front bar
- **WHEN** the log lists a front-bar main hand and no front-bar off hand
- **THEN** the Off hand row under Front bar shows a dash

#### Scenario: Item that belongs to no set
- **WHEN** an item's set id is zero
- **THEN** its row shows a dash in the set and pieces columns and still shows quality, trait and enchant

#### Scenario: Set the bundled data does not know
- **WHEN** an item's set id is not in the bundled set data
- **THEN** its row shows `Set#<id>` without a link

### Requirement: Armor weight
Each row of an armor slot SHALL show whether the piece is light, medium or heavy. The log does not carry this, so the weight SHALL be looked up by item id in a table bundled with the app, with no network access at run time. An armor piece the table does not know SHALL show a dash. Jewelry, weapon, shield and poison rows SHALL show no weight. The Armor group heading SHALL count the pieces worn of each weight, the most worn first.

#### Scenario: Mixed weights
- **WHEN** a player wears five medium pieces, one light and one heavy
- **THEN** each armor row names its piece's weight and the Armor heading reads `5 medium, 1 light, 1 heavy`

#### Scenario: Piece newer than the bundled table
- **WHEN** an armor piece's item id is not in the bundled table
- **THEN** its weight cell shows a dash and the Armor heading counts it as unknown

#### Scenario: Jewelry and weapons
- **WHEN** a row is for a jewelry or weapon slot
- **THEN** its weight cell is empty

#### Scenario: No armor logged
- **WHEN** the log lists no item in any armor slot
- **THEN** the Armor heading shows no count

### Requirement: Readable item attributes
Quality and enchant quality SHALL be shown under their in-game names (Normal, Fine, Superior, Epic, Legendary) in the matching quality color, with adequate contrast in both light and dark themes. A piece of a mythic set SHALL be shown as Mythic, although the log reports it as legendary. Traits and enchants SHALL be shown as readable names rather than log identifiers. An item with no enchant SHALL show a dash. A trait, enchant or quality value the app does not know SHALL be shown as a readable form of the logged value, never dropped. An armor, jewelry or weapon item below champion rank 160 SHALL show its level beside its quality.

#### Scenario: Mythic piece
- **WHEN** an item belongs to a mythic set and the log reports its quality as `LEGENDARY`
- **THEN** its quality reads "Mythic" in the mythic color

#### Scenario: Internal trait name
- **WHEN** the log records the trait `ARMOR_PROSPEROUS`
- **THEN** the row shows "Invigorating"

#### Scenario: Epic gear with a legendary enchant
- **WHEN** an item's quality is `ARTIFACT` and its enchant quality is `LEGENDARY`
- **THEN** the row shows "Epic" in the epic color and "Legendary" in the legendary color

#### Scenario: No enchant
- **WHEN** the log records the enchant type `INVALID`
- **THEN** the enchant and enchant quality cells show a dash

#### Scenario: Unknown value
- **WHEN** the log records a trait the app has no name for, such as `WEAPON_NEW_TRAIT`
- **THEN** the row shows "New Trait"

#### Scenario: Item below the level cap
- **WHEN** an item is logged at champion rank 150
- **THEN** "CP150" appears beside its quality

### Requirement: Set links
A set name in the grid SHALL link to the set's ESO-Hub page when the bundled link map knows it. Hovering the name SHALL show the set name and the link target, and clicking SHALL open the page in the system browser. A set with no known page SHALL be shown as plain text.

#### Scenario: Known set
- **WHEN** the user hovers a set name that has an ESO-Hub page and then clicks it
- **THEN** the tooltip shows the set name and the page address, and the page opens in the browser

#### Scenario: Set without a page
- **WHEN** a set has no entry in the bundled link map
- **THEN** its name is plain text with no tooltip and no click action

### Requirement: Set piece counts per bar
The pieces column SHALL show how many pieces of the row's set are active, counted per weapon bar: the armor and jewelry pieces of the set, plus that bar's weapons of the set, where a main-hand weapon logged with no off hand beside it counts as two. A weapon row SHALL show the count for its own bar. An armor or jewelry row SHALL show one number when both bars give the same count, and the front and back counts separated by a slash when they differ. When the log lists no back-bar weapon, only the front-bar count SHALL be shown. The grid SHALL carry a caption explaining the two-number form.

#### Scenario: Same count on both bars
- **WHEN** a player wears five armor pieces of a set and no weapon on either bar belongs to it
- **THEN** each of those five rows shows 5

#### Scenario: Set completed by front-bar weapons only
- **WHEN** a player wears three jewelry pieces of a set, wields two one-handed weapons of it on the front bar, and a staff of another set on the back bar
- **THEN** the three jewelry rows show 5/3 and the two front-bar weapon rows show 5

#### Scenario: Two-handed weapon
- **WHEN** the back-bar main hand belongs to a set, no back-bar off hand is logged, and no armor or jewelry belongs to that set
- **THEN** that row shows 2

#### Scenario: No back bar
- **WHEN** the log lists no back-bar weapon
- **THEN** every count is a single number

### Requirement: Slotted poisons
When the log lists a poison for a weapon bar, that bar's group SHALL gain a Poison row naming the poison and showing its quality. The name SHALL come from the bundled poison table; a poison whose strength scales with level SHALL show its tier. A poison id the table does not know SHALL be shown as "Poison" with its item id. The row SHALL note that the bar's weapon enchants do not fire while a poison is slotted. A bar with no poison logged SHALL have no Poison row.

#### Scenario: Named poison on the front bar
- **WHEN** the log lists item 79690 in the front-bar poison slot
- **THEN** a Poison row under Front bar reads "Crown Lethal Poison" with its quality

#### Scenario: Level-scaled poison
- **WHEN** the log lists item 76827 at champion rank 150 in a poison slot
- **THEN** the row reads "Damage Health Poison IX"

#### Scenario: Unknown poison
- **WHEN** the log lists a poison item id that the bundled table does not contain
- **THEN** the row reads "Poison (item <id>)"

#### Scenario: No poison
- **WHEN** the log lists no poison for either bar
- **THEN** the grid has no Poison rows

### Requirement: Mundus stone
The window SHALL show the player's mundus stone when one is among the long-term effects the log lists for them at combat start, with the stone's icon when it is bundled. Two stones SHALL both be shown, and a stone the log lists more than once SHALL be shown once. Detection MUST NOT depend on the log's language. When no stone is logged the window SHALL say so.

#### Scenario: One stone
- **WHEN** the player's logged effects include "Boon: The Thief"
- **THEN** the window shows "The Thief" as the mundus stone, with its icon

#### Scenario: Two stones
- **WHEN** the player's logged effects include two different mundus boons
- **THEN** the window shows both

#### Scenario: One stone listed twice
- **WHEN** the player's logged effects list the same mundus boon twice
- **THEN** the window shows that stone once

#### Scenario: Non-English log
- **WHEN** a log from a non-English client lists the same mundus effect under its translated name
- **THEN** the window shows that effect as the mundus stone, under the logged name

#### Scenario: No stone logged
- **WHEN** none of the player's logged effects is a mundus boon
- **THEN** the window shows that no mundus stone was logged

### Requirement: Food or drink buff
The window SHALL show the player's food or drink buff when one of their long-term effects at combat start is in the bundled list of food and drink buffs, under the name the log gives it and marked as food or drink. When a consumable is logged as several effects, the window SHALL show one entry for the consumable itself. When the player has no known food or drink buff, the window SHALL say that none was active at combat start.

#### Scenario: Named food
- **WHEN** the player's logged effects include "Artaeum Takeaway Broth"
- **THEN** the window shows it as the player's food

#### Scenario: Crafted food logged by its effect
- **WHEN** the player's logged effects include "Increase Max Health & Stamina"
- **THEN** the window shows that name as the player's food

#### Scenario: Drink logged as several effects
- **WHEN** the player's logged effects include "Witchmother's Potent Brew" and its two "Increase Health Regen" companion effects
- **THEN** the window shows one drink, "Witchmother's Potent Brew"

#### Scenario: No food
- **WHEN** none of the player's logged effects is a known food or drink buff
- **THEN** the window says no food or drink was active at combat start

### Requirement: Players without logged gear
When the log carried abilities but no equipment for a player, the window SHALL still open and show the header, bars, mundus stone and food, and SHALL state that the log carried no gear for that player in place of the grid.

#### Scenario: Empty equipment list
- **WHEN** the log's equipment list for a listed player is empty
- **THEN** the window shows their bars, mundus and food, and a line saying no gear was logged for them

### Requirement: Available for every fight, without network access
Build data SHALL be available for every completed fight, both in the live session and in a log opened for review. The window MUST NOT fetch anything from the network: every name comes from the log or from data bundled with the app, and ESO-Hub is contacted only when the user clicks a link.

#### Scenario: Reviewing an old log
- **WHEN** the user opens a log for review, selects a fight and clicks a player's name
- **THEN** the build window shows that player's build for that fight

#### Scenario: Offline
- **WHEN** the machine has no network connection and the user opens a build
- **THEN** the window shows set, poison, mundus and food names as usual

### Requirement: Theme awareness
The window's colors SHALL suit the current light or dark theme, and an open window SHALL redraw when the theme changes.

#### Scenario: Theme switch while open
- **WHEN** the build window is open and the system switches from light to dark
- **THEN** the window redraws with the dark theme's colors
