# name-privacy

## Purpose

A switch that hides the identity of every player but the one writing the log, in everything the app shows or copies, so a screenshot or a pasted fight gives away no one else's handle or character name.

## ADDED Requirements

### Requirement: One switch, three faces

The app SHALL keep one setting, `privacy.hide_names`, off by default, shown as a checkable Hide names button on the toolbar, toggled by Ctrl+H, and editable in Settings under Privacy. Flipping it by any face SHALL change the other faces, be saved at once, and redraw the fight on screen and every open window without a restart.

#### Scenario: The key
- **WHEN** Ctrl+H is pressed with the switch off
- **THEN** the toolbar button shows pressed, the config file holds the switch on, and the fight pane is redrawn with other players' names hidden

#### Scenario: Settings
- **WHEN** Settings is saved with the Privacy box ticked
- **THEN** the toolbar button shows pressed and the pane is redrawn

### Requirement: Who is hidden

While the switch is on, the app SHALL hide the handle and the character name of every player except the one the log flags as local (the player whose client writes the log), wherever a player name is shown: the fight pane's rows and its Also died chips, the hover texts, the build window (title, header, casters), the damage window (title, header), the death recap (title, header, the source of each heal), the dps graph's legend and hover, the timeline strip's hover and click pop-up, and the Copy fight text. Enemy, pet, set and ability names SHALL never be hidden. A reviewed log written by another player SHALL keep that player.

#### Scenario: A trial fight
- **WHEN** a twelve-player fight is shown with the switch on
- **THEN** the logging player's row reads their handle AND the eleven other rows read a hidden name

#### Scenario: A heal in a death recap
- **WHEN** the recap of the logging player's death lists a heal from another player
- **THEN** the heal's source is hidden AND the killing enemy's name is not

### Requirement: How a hidden name looks

In a page drawn as rich text a hidden name SHALL be a pixelated word of the hidden name's length with a leading `@` kept readable when the name had one; in a place that holds text only (a tooltip, a pop-up, a legend, a window title, the clipboard, and the `Also died` chip, a button whose label is text) it SHALL be `@` followed by one shade block per hidden character. The pixelated word SHALL NOT be made from the hidden name's own glyphs: it is a stand-in word that carries nothing of the name but its length.

#### Scenario: The row keeps its place
- **WHEN** a hidden name replaces a handle of ten characters in a row
- **THEN** the row's columns stay where they were

### Requirement: The character name beside the handle

The build window's title line SHALL read the handle then the character name, its window title `Build – @handle (Character)`, and the hover on a handle in the fight pane SHALL show the character name as a second line, each following the switch.

#### Scenario: Hover
- **WHEN** the pointer is over a player's handle in the fight pane
- **THEN** the hover shows the handle in bold, the character name under it, and the note that a click opens the build
