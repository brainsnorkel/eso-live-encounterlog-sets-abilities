# Design: Hidden names

## Context

See proposal.md for the motivation. What this builds on:

- The log's `UNIT_ADDED` line for a player carries `isLocalPlayer` (field 5), `T` on exactly one player per session: the one whose client writes the log. The engine keeps it as `PlayerInfo.is_local` (the `self` scope of effect rules) but does not put it on the fight entry. Checked on 2026-10-27 over all 899 split logs on the maintainer's machine: every one has exactly one local player, the same handle on 14 characters; the oldest full log (September 2025) and the live one carry the flag in the same place.
- A fight entry's player dict carries `name` (the handle, or the character name when the log gave no handle, or `anon`) and `character`. Names also sit in nested data: a death recap's `name` and each row's `source` (a heal from a player), the timeline intervals' `source` and `target`, the uptime summary's `sources` and `targets`, the penetration section's `casters`. Every one of those is the player's display name, which starts with `@` whenever the player has a handle. Enemy and pet names never start with `@`.
- The fight pane, the build window, the damage window and the death recap are `FightView`s (a `QTextBrowser`): they draw HTML and answer the page's image requests in `loadResource` by URL scheme, `icon:` for ability icons and `glyph:` for the link glyphs drawn with QPainter (issue #34). An `<img>` inside an anchor is part of its click and hover target. Tooltips (`QToolTip`), the strip's pop-up and the graph's legend are `QLabel` or `QListWidget` text and cannot ask a view for an image.
- The window re-renders everything that bakes a colour in when the theme flips (`_on_theme_maybe_changed`): the pane, the strip, and each open window through its `refresh(dark)`. The same path serves a flip of the switch.
- The toolbar holds `QAction`s; `Detail view` is a checkable one with Tab as its key. Config values are read with `config.get` and saved atomically; Settings saves restart monitoring.
- `scripts/capture_screenshots.py` draws the app offscreen over a log under a scratch config and writes the guide's pictures; the guide's pictures come from `D:/esologs/splits/261015191452-Kyne's-Aegis-vet.log --boss Yandir`.

## Goals / Non-Goals

**Goals:**
- One switch, visible on the toolbar, that hides every other player's identity in everything the app shows or copies, and keeps the logging player's.
- A hidden name that looks like a blurred name in a screenshot and gives nothing away.
- The character name where #71 asks for it, obeying the switch.

**Non-Goals:**
- Hiding the logging player, or choosing by hand who is kept (a later `privacy.keep` list is one line away, not asked for).
- Hiding anything else: zone names, boss names, the log path in the review banner, the timestamps.
- Masking in the engine or in saved data: the entries keep the real names; the switch is a view.
- A true Gaussian blur: the issue offers either look, and a pixelated stand-in is simpler and safer (see Decisions).

## Decisions

- **The logging player is the one kept, known by the log's own flag.** The engine stamps `is_local` on each entry's player dict; nothing is configured. *Alternative*: keep a handle named in Settings. Rejected for now: the flag is always right for the app's own user, needs no setup, and a configured name would be wrong on a reviewed log written by a friend, where the flag names the friend; the maintainer's wording ("the handle of the person logging") is the flag's meaning.
- **What counts as a player name.** A name is hidden when the switch is on, it is not the logging player's handle or character name, and either it starts with `@` or it is a character name of another player in the entry. The `@` rule reaches every nested place a handle lands (recap heal sources, strip intervals, casters) without threading the player list into each; the character-name set reaches a player the log gave no handle. `anon` and enemy names fall through. An entry with no local player at all hides every name, the safe direction.
- **Masking is a render-time transform, passed explicitly.** A `NameMask` built per entry (`NameMask.for_entry(entry, hide)`) is passed to each renderer and widget as `names`; `None` means no masking, so every existing call and test is unchanged. Each place that writes a name calls `names.text(name)` or `names.html(name, colour, pt, bold)`. *Alternative*: a regex pass over the rendered HTML. Rejected: it cannot tell a name from a substring of an ability name, would touch escaped text, and could not produce the image. *Alternative*: a module-level "current mask" global. Rejected: invisible coupling, and the dialogs keep their own fight, which may not be the one on screen.
- **A hidden name is a pixelated stand-in, not the real name pixelated.** The mask makes a stand-in word of the same length from a keyed hash of the name (the key is random per run, so the same name gives the same word within a run, and nothing persists), draws it in the view's font at the requested size and weight, downscales it smoothly by the block size and upscales it with nearest-neighbour, so the result has the blocky texture of a pixelated word: the ascender and descender pattern of a word nobody has ever seen. Pixelating or blurring the real text was rejected: both are reversible for short text in a known font (the font, size and rendering here are all public), so a screenshot meant to hide a handle would carry it. Keeping the stand-in the same length keeps the row's layout where it was. The `@` is left as text before the image, so the row still reads as a handle and the hover cue (which underlines the anchor's text) has something to underline.
- **Where text is all there is, blocks.** Tooltips, the strip's pop-up, the graph's legend, the window titles and the clipboard copy get `@` followed by one `▒` per hidden character. A `QLabel` cannot ask the view for an image, and a title bar cannot hold one. *Alternative*: turn the pop-up into a `QTextBrowser` so it can. Rejected: scope, for a pop-up few will screenshot.
- **The page asks for the image by URL.** `mask:<stand-in>?color=rrggbb&pt=<points>&b=<0|1>`, answered by `FightView.loadResource` from `name_mask.mask_image` with the view's font family and device pixel ratio, cached per run by its parameters, exactly as the glyphs are. The stand-in is lower-case letters only, so the URL needs no escaping and a malformed one is refused.
- **Block size** is a quarter of the line height (4 px at 9 pt). Chosen by looking at the result offscreen: finer and a letter shape shows through, coarser and the word becomes a bar.
- **The switch has three faces and one state.** `privacy.hide_names` in the config; `hide_names_action`, checkable, on the toolbar after DPS graph, with Ctrl+H (free in this app; Qt's own use of Ctrl+H is Replace, which the app has no notion of); a box in Settings under Privacy. Toggling the action sets the state, saves the config at once and redraws; saving Settings sets the action. The toggle is saved rather than held for the session because the toolbar button shows the state: a user who turned it on for a screenshot and starts the app a week later sees a pressed button, not a mystery. *Alternative*: Settings gives the start state and the key flips the session only. Rejected: two states for one idea.
- **A flip redraws everything open.** The pane and the strip through `_show_fight`; each open window through `refresh(dark, names)`, the same hook the theme flip uses, now taking the new mask. Nothing is rebuilt: the dialogs keep their fight and only re-render it.
- **Copy fight obeys the switch.** The issue's second purpose is sharing fight information without the identities; the clipboard is how fights are shared from this app. A user who wants the names in the text turns the switch off first.
- **The character name beside the handle (#71).** The build window's title line becomes `@handle · Character` at the title size, the character name no longer repeated among the muted facts; the window title `Build – @handle (Character)`. The handle's hover in the fight pane gains the character name as its second line. When the player has no handle the character name is the name already and nothing is doubled.
- **The guide's pictures are regenerated with the switch on**, from the same log and boss as before, in a commit of their own so it can be dropped alone. The social card is rebuilt from the new main-window picture. The Settings picture shows the new group.

## Review of the plan

Objections raised against the plan above, and what was done about each:

- *A keyed hash is more machinery than the problem needs; why not a fixed word?* A fixed word would make every hidden name the same blob; two players of equal handle length would be indistinguishable in a picture, which makes a screenshot of a fight harder to read (who died, who topped the meter). The hash is three lines and keeps each player's blob consistent across the row, the strip and the windows within a run.
- *The length of a name leaks.* It does, and the layout is the reason to keep it; a handle's length identifies nobody. Noted in the guide's section.
- *Pixelating a stand-in is theatre: why not just write `@▒▒▒▒▒` everywhere?* Because the maintainer asked for the look of a blurred name, for pictures that should look like the app and not like a redacted form. The blocks are the fallback where an image cannot go.
- *The in-fight search cannot find a hidden name.* True: the name is an image, not text. With the switch on, that is the point; the status is visible on the toolbar. Noted in the guide.
- *A keypress writes the config file.* One atomic write of a small file, the same as closing the window does for its geometry.
- *Reviewing a friend's log hides the maintainer and keeps the friend.* By the issue's wording. If it bites, a `privacy.keep` list of handles is the fix, and the mask already takes a set of kept names.
- *Why not hide names in the plain copy only when asked?* Two switches for one idea; the clipboard is the sharing path the app has.
- *The `@` left visible before the image gives away that the hidden player has a handle.* Every player in a group has one; the `@` says "a handle is hidden here", which is what a reader should understand.
- *Twelve images per fight, redrawn on every render.* Cached per run by stand-in, colour, size, weight and ratio: a trial fight costs twelve small images once.
- *A hover on a hidden name still shows a tooltip.* With the name and character name as blocks; the build window still opens. Nothing identifying is in either.

## Risks / Trade-offs

- [The `@` rule hides a non-player name that starts with `@`] → no such name exists in the log's enemy, pet, set or ability names.
- [A player with no handle and no build in the entry] → would have shown as their character name; closed in the build by the entry's full roster (see As built).
- [Qt rich text lays the image out a pixel off the baseline] → the image is the font's line height, aligned middle, checked offscreen in both themes.
- [The shade block has no glyph in the pane's font] → Qt falls back to a font that has it (Segoe UI Symbol on Windows, DejaVu on Linux); checked offscreen.
- [An entry built before this change (none persist; review mode re-parses)] → no `is_local`: every name hidden, the safe direction.

## Migration Plan

Nothing to migrate: a new config key with a default; entries are rebuilt from the log on every start.

## Open Questions

- Whether the maintainer wants the toggle saved (as built) or session-only with Settings as the start state.
- Whether the `Hide names` button pressed in the guide's pictures is acceptable, or the pictures should be taken with the button hidden.

## As built (2026-10-27)

Built as designed, with these particulars:

- The mask is `gui/name_mask.py`; the renderers take `names=None` and treat None as the identity (`NO_MASK`), so no existing call changed. The dialogs keep the mask in `_shown`, expose `entry`, and `refresh(dark, names=None)` re-renders with a new mask or the one shown. The window's `_refresh_names` redraws the pane through `_show_fight` and each visible window with a mask for its own fight.
- The "Also died" chip's label uses the block form rather than the image: the chip escapes its label, and the case (a dead player with no build in the log) is rare.
- The death recap's theme gained a `text` colour (the module has its own theme table); the window passes the view's palette colour as the other windows do.
- The Settings box reads "Hide other players' handles and character names (Ctrl+H toggles it)" over a muted help line; the first wording did not fit the dialog's width.
- Block size: a quarter of the line height (`BLOCKS_PER_LINE = 4`), 4 px at 9 pt, judged on the offscreen captures: the words read as smudged handles, no letter shape shows, the rows do not move.
- Tests: `tests/unit/test_name_mask.py` (the mask, the stand-in, the URL, the image, the engine's `is_local` stamp) and `tests/unit/test_hide_names_gui.py` (the pane, the view, the four windows, the strip, the switch's three faces, the copy, and #71's hover and header), rather than cases spread over nine files; `test_build_window_gui.py` updated for the new title line.
- The guide's 14 pictures were retaken with `--hide-names`; 13 changed, the death recap (the logging player's own, with only enemies in it) is byte-identical. `site/social-card.png` rebuilt.
- **Review of the result** (an independent read of the diff, 2026-10-27) found no crash and no leak of a handle, and one real gap: the character-name set was read from the entry's rows, and a player whose PLAYER_INFO never reached the log has no row, so with no handle their character name would have shown in clear in the strip's hover and pop-up, the casters and a recap. Fixed at the source: the engine stamps `player_names` on every entry, one dict (name, character, is_local) per player unit of the fight, rows or not, and the mask reads that roster, falling back to the rows for an entry without one. The review's other points, taken: `anon` is left alone; Ctrl+H has application context, so it works from a build, damage or recap window; a flip keeps the pane's and the windows' scroll position; tests for a window holding a different fight than the pane, the strip after a flip, the graph's hover, another player's recap, a theme flip keeping the mask, the key itself, and the kept scroll. Noted, not changed: on macOS (not shipped, #32) Qt maps Ctrl+H to Cmd+H, the system's hide-application key, so the binding will need a platform case there; a hidden player with no handle has no text in their anchor, so the hover underline does not show for them (the tooltip does).
- The dependency check the planning rule asks for found nothing to bump: every package the 0.14.4 build installed on 2026-10-26 is the newest on PyPI with no advisory (PySide6-Essentials 6.12.0, Pillow 13.0.0, pyinstaller 6.22.3, platformdirs 4.13.5, setuptools 84.2.1, pip 26.2.2); Qt's two newest advisories (CVE-2026-107472 QTextCodec, CVE-2026-107157 QCborValue, 2026-10-26) end at 6.11.2, 6.12.0 listed as fixed; CPython 3.14.10 (2026-10-25: the tarfile filter bypass and the eMudhra CA distrust) is what the next unpinned `3.14` build will take, and the app never imports tarfile.
