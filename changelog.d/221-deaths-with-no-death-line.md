### Changed
- **A boss left all but dead is a kill however many lay dead** (#221): under 0.01% of its health. Sanity's Edge's Archwizard Twelvane leaves his phase at 7 of 124 million health and writes no death line. Once the deaths below counted, his pull read as a wipe with exactly half the group dead. No other pull in 391 split logs ends that close to 0 without a kill

### Fixed
- **Deaths the log writes no death line for are counted** (#221): about one player death in thirteen in fights has no `DIED` line in the log, nor a fall's `KILLED_BY_SUBZONE`. The player's health reads 0 and stays there until they are resurrected or release. The app counted none of these deaths, so they had no recap, no time dead and no part in the kill or wipe verdict. Now:
  - A player at 0 health for a second with no death line in that time died, from the first 0. Every line that shows the player counts, not only hits: many of these players were out of your combat range or in another area, as in Cloudrest's portal or Sunspire.
  - The killer is the hit that left the player at 0, or else the last hit within 3 seconds; with neither, *an unknown cause*. The recap says the death was *read from health reaching 0*.
  - Over 391 split logs (8,932 fights), 1,327 deaths are added in 606 fights, the user guide's Yandir fight among them.
  - 19 pulls that read Lost sight or Left now read Wipe. Each was followed by another pull of the same boss, or ended with every player dead
- **Time dead no longer ends at a corpse's own healing** (#221): a dead player's healing and regeneration ticks write health on the corpse, and that ended their time dead about a second after the death. In 15 fights a player's time dead now runs 5 to 45 seconds longer, to their resurrection or release
