# Tasks

## 1. The mask

- [x] 1.1 `src/esolog_tail.py`: each entry's player dict carries `is_local` from `PlayerInfo.is_local`. Verified by `tests/unit/test_name_mask.py` on the build-session fixture: unit 1 is local, units 2 and 3 are not
- [x] 1.2 `src/gui/name_mask.py`: `NameMask` (`for_entry(entry, hide)`, `active`, `hides(name)`, `text(name)`, `html(name, color, pt, bold)`), the stand-in word (keyed hash, same length, lower-case letters, spaces kept), the `mask:` URL and its parser, `mask_image(word, color, pt, bold, font, dpr)` with the pixelation and the per-run cache; the module docstring carries the design note. Verified by `tests/unit/test_name_mask.py`: an inactive mask is the identity; the local player's handle and character name are kept; another player's handle, character name and a handle the entry never listed are hidden; an enemy name, `anon`, `unknown` and nothing are not; a friend's log keeps the friend; an entry with no local player hides everyone; the text form is `@` plus one block per character; the HTML form escapes a kept name and emits `@` plus an `<img src="mask:…">` for a hidden one, the space of a character name as an underscore; the stand-in is the same within a run, letters only, the name's length, and a repeated-letter name gives no repeated letters back; the URL round-trips and seven malformed ones are refused; the image is the word's advance wide and the line tall, drawn in the colour, pixelated (far fewer distinct colours than pixels), doubled at ratio 2, cached, and None for an empty word, a bad colour or size

## 2. The pages

- [x] 2.1 `fight_view.py`: `loadResource` answers `mask:` from `mask_image` with the view's font and ratio. Verified by `tests/unit/test_hide_names_gui.py`: the image is the word's advance wide in the view's font; four malformed URLs fall through; a rendered page resolves both of its mask images through the view and grabs
- [x] 2.2 `fight_render.py`: `render_html(names=)`, `render_plain_text(names=)`, `build_tooltips(entry, names=)` (with the character name as a second line, #71), `damage_tooltips(entry, names=)`, the "Also died" chips as blocks. Verified by the same file: the local player's row is text and another's `@` plus the image in the pane's colour and size, the player without a handle the image alone with its space, the unlisted dead player's chip as blocks; the three hover texts; the plain copy; a friend's log
- [x] 2.3 `death_render.py`: `death_tooltips(entry, names=)`, `render_death_recap_html(names=, text_color=)` (title name, heal sources; the theme gained its `text` colour), `death_chip_html` label; `death_recap_dialog.py` title, `entry`, `refresh(dark, names)`. Verified by the window test: the logging player's own recap keeps their name, hides the friend's heal, keeps the killer
- [x] 2.4 `build_render.py`: `build_title(entry, unit_id, names=)` reading `Build – @handle (Character)`, the header's title line `@handle · Character`, `_casters_text(casters, e, names, color, pt)`; `build_dialog.py` takes and keeps `names`, `entry`, `refresh(dark, names)`. Verified by `test_build_window_gui.py` (title and header updated) and `test_hide_names_gui.py` (the masked header's two images, the casters)
- [x] 2.5 `damage_render.py` (`damage_title`, header, `render_damage_html(names=, text_color=)`) and `damage_dialog.py`. Verified by the window test
- [x] 2.6 `dps_graph.py`: `show_graph(entry, dark, names=)`, the legend and hover names, `entry`, `refresh(dark, names)`. Verified by the window test: the legend's three entries before and after a flip
- [x] 2.7 `timeline_strip.py`: `set_timeline(…, names=)`, the hover lines and the click summary. Verified by the window test: the summary and a hover over the friend's interval

## 3. The switch

- [x] 3.1 `app_config.py`: `privacy.hide_names` default False. `settings_dialog.py`: a Privacy group with the box and a help line; `apply_to_config` writes it. Verified by the Settings test: the box follows the config, writes it back, and sets the action
- [x] 3.2 `main_window.py`: `hide_names_action` (checkable, Ctrl+H, after DPS graph) from the config; toggling saves and redraws the pane, the strip and every open window with a mask for its own fight (`_names_for`, `_toggle_hide_names`, `_refresh_names`); `_show_fight`, the four windows and the copy pass the mask; Settings saved sets the action (`_apply_privacy_settings`). Verified by the window tests: the action starts from the config; toggling writes the config and the pane gains and loses `mask:`; the key is Ctrl+H; a flip with nothing on screen is harmless; four open windows follow a flip and back; a hidden window is left alone and reopens masked; the copy follows
- [x] 3.3 `scripts/capture_screenshots.py --hide-names`. Verified by running it

## 4. Documentation

- [x] 4.1 User guide: "Hiding other players' names", the Settings list's Privacy entry, the build window header bullet, the hover bullet, the copy note; README feature bullet; CHANGELOG under Unreleased (#72, #71). Verified by reading them
- [x] 4.2 `scripts/build_design_doc.py` gains "Hidden names: the stand-in behind the blur"; `docs/design.md` regenerated (25 topics). Verified by the script's output
- [x] 4.3 The guide's pictures regenerated with `--hide-names` from the Kyne's Aegis log (13 changed; the death recap is the logging player's own and is byte-identical), the social card rebuilt, in a commit of their own. Verified by viewing the PNGs

## 5. Integration checks

- [x] 5.1 `python -m pytest tests/ -q` offscreen: 984 passed, 3 skipped (the review's cases included: a window holding a different fight than the pane, the strip after a flip, the graph's hover, another player's recap, a theme flip keeping the mask, Ctrl+H pressed in the main and the build window, the kept scroll, the roster and `anon`); ruff finding counts per touched file equal to main's; the three new files clean
- [x] 5.2 The pane drawn offscreen with the switch on: the logging player readable, the others pixelated, `@` kept, rows in place; the build window's header with both names pixelated; the penetration section's casters; the graph's legend; the Settings group. Verified by the grabbed PNGs
