# Proposal: Possible build issues, an (i) on the player's row

## Why

Issue #16 asks for an info popup that points out likely mistakes in a player's build: a Nirnhoned weapon in an off hand, the same glyph on both weapons of a bar, heavy armor on a damage dealer, a weapon skill slotted on a bar that holds another weapon, Elemental Drain in place of Elemental Susceptibility, a proc set that never fires because its trigger is never met (Roar of Alkosh without a synergy, Roaring Opportunist without a fully charged heavy attack), and a group buff set that is complete on one bar only (Pearlescent Ward, Xoryn's Masterpiece, Lucent Echoes). The log carries everything these need, the build window already shows the raw facts, and a survey of 83 split logs of September and October 2026 (1,615 fights, 13,998 player-fights, 393 characters) found each of them in real groups: with the rules as decided on 2026-10-24, 17% of the characters seen would carry at least one note.

## What Changes

- **Build issue rules in the engine**: for every player in every fight, a list of findings, each naming what was found and the rule behind it, in plain language. The rules, as the maintainer decided them on 2026-10-24:
  - Nirnhoned on an off-hand weapon (either bar; a shield's Nirnhoned is the armor trait and does not count).
  - The same glyph on both weapons of one bar, whatever the glyph: identical glyphs share one cooldown (in the logs the same glyph from one player never fires twice within 4 seconds whether a bar carries it once or twice). The same glyph on both bars is not an issue.
  - Two or more heavy armor pieces on a damage dealer: the player's role reads DPS and they have not taunted this session (one heavy piece, the usual Undaunted Mettle split, is not flagged).
  - A weapon skill on a bar holding another weapon line (a Two Handed skill on a staff bar). The back bar under Oakensoul Ring is skipped, since it cannot be used.
  - Elemental Drain on a bar, per player, with the morph difference stated in the finding.
  - Roar of Alkosh or Roaring Opportunist worn at five pieces and never fired: judged per logging session over the fights of a minute or more the player wore it in, cleared by a single fire anywhere in the session.
  - Pearlescent Ward, Xoryn's Masterpiece or Lucent Echoes complete on one bar only, both bars logged and no Oakensoul Ring.
- **An (i) on the fight pane**: after a player's name and class, only for players with at least one finding, in the theme's link color. Hovering lists the findings; clicking opens a transient popup with each finding and its rule, set and skill names linking to ESO-Hub. Players without findings keep their plain row.
- **The build window repeats the list** under the player's header, so the notes are there when the build is read.
- **A bundled table of weapon skill lines**: ability id to skill line for the six weapon lines, from UESP's player skill table, with a generator script; the grimoire icon of a scribed skill supplies its line when the id is not in the table.
- Documentation: user guide section, changelog, design notes extracted into docs/design.md, a screenshot of the popup. The rules as a user-editable text is a separate issue (the maintainer's decision); each finding describes its rule in the meantime.

## Capabilities

### New Capabilities

- `build-issues`: the rules the app applies to a player's logged build and fight, what each finding says, where the fight pane and the build window show them.

### Modified Capabilities

(none; the project keeps no main specs for the fight pane or the build window)

## Impact

- Engine: a new `build_issues` module (rules, finding texts, the per-session tracker for the proc sets), `esolog_tail` (procs noted per fight from EFFECT_CHANGED, the findings attached to each player dict as `build_issues`, the tracker reset per log session), `player_build` reused for weights, weapon types and piece counts.
- Data: `data/skills/weapon_skill_lines.json` and `scripts/generate_weapon_skill_lines.py` (one request to UESP, or `--from` a saved reply).
- GUI: `fight_render` (the (i) anchor, its hover text, the popup's HTML), `fight_view` (a new `issues_requested` signal), `main_window` (opens the popup), a new popup widget, `build_render` (the repeated list).
- Behaviour elsewhere: nothing else on a fight entry changes; a replay of real logs through the old and the new engine must differ only in the new key.
- Docs: user guide, changelog under Unreleased, `docs/design.md` regenerated, `docs/screencaps/build-issues.png`.
