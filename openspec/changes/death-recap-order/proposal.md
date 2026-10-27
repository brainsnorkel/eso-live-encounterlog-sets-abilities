# Proposal: The death recap leads with the deaths

## Why

Issue #95: the recap window opened with the whole fight's "Damage taken this fight" block (three bars, the lines under them, the top abilities), and each death put its own bars between the "Killed by" line and the event table, so the table of what hit and healed the player in the last seconds, the thing the window is opened for, sat a screen down. The maintainer asked for the last seconds first and the kinds-of-damage graphs and figures below them, and for "over time" to be written as DoT.

## What Changes

- **Each death's event table comes right under its "Killed by" line**, and that death's kinds summary (the bars and the lines) sits under the table instead of above it.
- **"Damage taken this fight" closes the window**, after the last death, with its bars, lines and top abilities unchanged.
- **Damage over time is written `DoT`**, and healing over time `HoT`, beside the bars, in the heal share, in the ability kind words and in the star hover text, as the Result column already wrote them. The build window's Damage dealt bars share the block and say the same.
- **The recap window is a setting**: Settings → Death recaps, 5 to 10 seconds in steps of one, 5 by default (the issue said 10 s; asked, the maintainer first kept 5, then asked for the range). The engine reads it when it is built, so a save's replay rebuilds the listed fights with the new window, and each recap records the window it was built with so the window names the right number of seconds.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `death-recap-damage-kinds` (from the change `death-recap-damage-types`): the order of the per-death summary and the event table, the place of the whole-fight block, the word for damage over time.

## Impact

- `src/gui/death_render.py`: the order in `_death_html` and `render_death_recap_html`, the heal share and ability kind words, the window read from each recap; `src/damage_kinds.py`: `SIDE_LABELS`.
- `src/death_recap.py`: the window on the recorder and on each recap, the bounds and the clamp; `src/app_config.py`: the `death_recap.window_s` default; `src/app_startup.py`: the recorder's window from the config; `src/gui/settings_dialog.py`: the Death recaps group.
- Tests: `tests/unit/test_death_recap_gui.py`, `test_settings_dialog.py`, a new `test_death_recap_window.py`.
- Docs: the user guide's "Death recaps" and "Settings" sections, the README's recap line, the home page's card, the changelog, `docs/design.md` regenerated, `docs/screencaps/death-recap.png` and `settings.png` retaken.
- No new dependency (the check is task 1.4).
