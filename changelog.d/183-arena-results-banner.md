### Changed
- **Arena results show their vitality maximum** (#183): `Vitality 11/15` in Maelstrom Arena and Vateshran Hollows and `14/24` in Dragonstar Arena and Blackrose Prison, where the row used to show the points alone. Maelstrom Arena, Vateshran Hollows and Sanctum Ophidia are named when the zone is unknown.
- **The trial timer rounds to the second as the game's banner does** (#183): a run of 44:09.5 reads `44:10`, as the banner shows it, in the result row, the strip, the session recap and the copied text.
- **The score banner capture waits long enough for an arena's banner and keeps it whole** (#183): it grabs until 45 seconds after the run ended (at least 15 seconds), since an arena's banner can come 25 seconds late. Once the score is read it takes two more grabs and keeps the one with the most of the banner drawn. The crop is centred on the screen, so the revives count is no longer cut off.

### Added
- **`banner.log`** (#183): each capture writes what it saw beside the settings file: when the run ended and was read, the outcome, and a line per grab with the lines of text that hold a digit. It keeps the last 50 captures and holds no pictures.
