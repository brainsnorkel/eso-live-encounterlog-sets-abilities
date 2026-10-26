# Proposal: Hide other players' names for screenshots, and the character name beside the handle

## Why

Issue #72: the maintainer takes screenshots of the app for the project's documentation and shares fight pictures, and both show the handles and character names of everyone in the group. He wants a switch that keeps his own handle (the player writing the log) and blurs or pixelates everyone else's, as a setting with a key to toggle it. Issue #71, filed the same evening: the build window should show the character name, and hovering a handle in the fight pane should show the character name too.

Today the user guide's pictures and the README's main-window picture carry the real handles of the maintainer's raid group.

## What Changes

- **A switch, `privacy.hide_names`**, off by default, with three faces that are one state: a checkable **Hide names** button on the toolbar, **Ctrl+H**, and a box in Settings under a new Privacy group. Flipping it redraws the fight on screen and every open window at once, and is saved, so the toolbar always shows the state the app will start in.
- **What is hidden while it is on**: every player name except the logging player's, that is their handle and their character name, in every place the app shows a name: the fight pane's rows and "Also died" chips, the hover texts, the build, damage and death-recap windows (header, title, the casters in the penetration section, the heal sources in a recap), the dps graph's legend and hover, the timeline strip's hover and click pop-ups, and the Copy fight text. Enemy, pet, set and ability names are never hidden. The logging player is the one the game flags as local on its own UNIT_ADDED line, so in a reviewed log written by someone else, that someone is the one kept.
- **The look**: in the pages drawn as rich text (the fight pane and the three windows) a hidden name is a pixelated word of the same length, with its `@` left readable so it still reads as a handle; everywhere text is all there is (tooltips, pop-ups, the graph's legend, window titles, the clipboard) it is `@▒▒▒▒▒▒`. The pixelated word is **not** the real name blurred: it is a stand-in word of the same length drawn and then pixelated, since blurred or pixelated text can be read back (the font and size are known, the words are short), which would defeat the purpose without anyone noticing.
- **The character name** (#71): the build window's title line reads `@handle · Character` (it was a muted fact on the line below) and its window title `Build – @handle (Character)`; the hover on a handle in the fight pane gains a line with the character name. Both follow the switch.
- **Documentation pictures**: `scripts/capture_screenshots.py --hide-names` captures with the switch on; the user guide's pictures and the README's are regenerated that way, so the raid group's handles leave the repository's current pictures.
- Documentation: the user guide (a short section on hiding names, the Settings list, the build window header, the hover), the README's feature list, the changelog, and a design note extracted into docs/design.md.

## Capabilities

### New Capabilities

- `name-privacy`: what the switch hides and keeps, where, how a hidden name looks, how the switch is flipped and remembered.

### Modified Capabilities

(none; the build window and the hover had no spec)

## Impact

- `src/esolog_tail.py`: each fight entry's player dict gains `is_local`, from the flag the engine already keeps on the player.
- New `src/gui/name_mask.py`: the mask (which names are hidden, their text and image forms, the stand-in word, the pixelated image served to the pages).
- `src/gui/fight_view.py`: serves `mask:` images, as it serves `icon:` and `glyph:`.
- `src/gui/fight_render.py`, `build_render.py`, `damage_render.py`, `death_render.py`: every name goes through the mask; the character name beside the handle and in the hover.
- `src/gui/build_dialog.py`, `damage_dialog.py`, `death_recap_dialog.py`, `dps_graph.py`, `timeline_strip.py`: take the mask and keep it for redraws.
- `src/gui/main_window.py`: the action, the key, the config value, the redraw of the fight and the open windows on a flip; `src/gui/settings_dialog.py`: the Privacy group; `src/app_config.py`: the default.
- `scripts/capture_screenshots.py`: `--hide-names`; `docs/screencaps/*.png`, `site/social-card.png` regenerated.
- Tests: a new `tests/unit/test_name_mask.py`; cases added to the fight view, fight render, build window, death recap, damage window, dps graph, timeline strip, main window and settings tests.
- Behaviour with the switch off: unchanged, except the character name in the build window's title line and in the handle's hover.
