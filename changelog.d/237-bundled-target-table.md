### Fixed
- **A player's area skills count as area from their first hit** (#237): the released app never found its table of which player skills strike an area, so the player window's Damage done tab counted an area skill as single target until one of its casts had struck two enemies. Every release since 0.15.0 had this; running from source did not.
