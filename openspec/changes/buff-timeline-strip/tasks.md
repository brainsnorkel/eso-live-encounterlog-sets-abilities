# Tasks

## 1. Engine Interval Capture

- [x] 1.1 Add Major Vulnerability to the tracked ability table after confirming its ability ID against a real log (`--` check design open question); verify with a unit test parsing a fixture EFFECT_CHANGED line
- [x] 1.2 Implement `BuffTimelineRecorder` (GAINED opens, FADED closes, UPDATED continues with sub-500ms gap merging, END_COMBAT force-closes, per-effect cap, name resolution at capture) gated by `experimental.buff_timeline`; verify with unit tests for each spec scenario including the toggle-off zero-retention case
- [x] 1.3 Attach `buff_timeline` to `FightHistoryEntry` in `_build_fight_entry` (None when disabled); verify golden tests still pass unchanged with the flag off

## 2. GUI Strip

- [x] 2.1 Implement `TimelineStrip(QWidget)`: one 10 px row per active effect, stable colors, tick marks scaled to duration, hidden when dataless, "experimental" corner hint; verify with an offscreen render test asserting height bounds and row count
- [x] 2.2 Implement hover tooltips via QHelpEvent hit-testing listing all overlapping intervals (effect, time range, caster, receiver); verify with a widget test synthesizing a QHelpEvent at a known x-offset
- [x] 2.3 Mount the strip between the fight header and player table in the detail pane without displacing existing content; verify offscreen that summary content is unchanged when the strip is hidden

## 3. Settings & Docs

- [x] 3.1 Add the "Experimental: buff timeline" checkbox (default off) persisted to `experimental.buff_timeline`, applied on monitoring restart; verify round-trip through a reloaded AppConfig
- [x] 3.2 Document the experimental feature in README (one short subsection with the compactness caveat) and CHANGELOG; verify documented behavior matches the settings label and default
