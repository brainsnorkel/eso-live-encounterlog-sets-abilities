# Tasks

## 1. The classification module

- [x] 1.1 Create `src/damage_kinds.py` with the result and damage-type tables (direct, over time, fall; Martial, Magical, Oblivion, drowning, untyped; heal and heal-over-time results; the frost wording) and a `classify(result, damage_type)` function; verify with `tests/unit/test_damage_kinds.py` cases for every result and type the survey listed, FALL_DAMAGE/GENERIC, DROWN, EARTH, NONE and a made-up type included (the unknown ones count and are named, never raised)
- [x] 1.2 Add `CastIndex` (per-encounter `(source, cast id) -> units struck`, per-session `ability -> max units on one cast`, per-cast damage held until a second target lands) and `area_of(source, cast, ability, player_source)` with the rule order of design D2; verify with tests for one cast many players, one cast one player, the session memory across a reset-free second pull, and the player-table fallback
- [x] 1.3 Add `TakenTally` (totals by kind, per-ability damage with source and kinds, first and last hit, blocked-through, absorbed, avoided count, healed, overheal, overkill) and `summary(rows_or_tally)` that returns the dict both renderers draw (sides with amounts and percentages, types, outside amounts, lines); verify with tests that reproduce the Dreadsail death (29,626; 24/76; 76/24; fire 100%) and the one-shot
- [ ] 1.4 Add the Warfare star table (side -> stars, tooltip text, ESO-Hub URL) and `stars_for(side, dealt_or_taken_or_heal)`; verify every entry's URL has the ESO-Hub host and every side of every split has at least one star, and check the star list and texts against the live game (Update 51) before marking done
- [x] 1.5 Write the module docstring as the design note (rules, survey numbers, why casts beat the table for monsters, what is not claimed) and add a "Kinds of damage" topic to `scripts/build_design_doc.py`; verify `python scripts/build_design_doc.py` regenerates docs/design.md with the topic

## 2. The death recap engine

- [x] 2.1 Make the recorder keep the damage type on each event and the pure overheals as two-field tuples, and give each row `damage_type`, `area`, `targets_hit` and `area_rule` using a `CastIndex` passed in; verify with `tests/unit/test_death_recap.py` cases where the second target of the killing cast lands after the DIED line (the row is reclassed on refill) and the overheal sum appears on the recap
- [x] 2.2 Wire `_handle_combat_event` to feed the `CastIndex` and the per-player `TakenTally` for every recap-result event on a player, and snapshot `taken` onto each player's dict in `_build_fight_entry`; reset both with the recorder; verify with an engine test on a two-fight log that the second fight's tally starts at zero and the first fight's dict keeps its own
- [x] 2.3 The golden test compares named fields only, so the fixture needed no change (it passes); the replay comparison ran over 8 of the sample's logs (928 MB, 241 fights) through the merge-base's src and this branch's: every pre-existing field identical, the new keys (`taken`, `kinds`, the ability rows' `tick_damage`/`area_damage`/`types`, the recaps' `overheal`, the rows' kinds) the only additions

## 3. The damage-dealt record

- [x] 3.1 Pass the damage type and cast id through `add_damage_to_player` to `FightDamage.note` and extend `AbilityDamage` with `by_type`, `tick_damage` and `area_damage` (area from the shared `CastIndex`, player rule); verify with `tests/unit/test_damage_attribution.py` cases for a cleave on three mobs (area by cast), Impulse on one boss (area by table) and a single-target skill
- [x] 3.2 Add `kinds` to `PlayerDamage.snapshot` (sides, types, outside amounts, shield share, the table-vs-cast share for area); verify the snapshot test asserts the dict and that the existing `abilities` rows are unchanged

## 4. The player-skill target table

- [x] 4.1 Write `scripts/generate_ability_targets.py` reading the cached UESP reply (path argument, default `build/esobuild-assets/sources/mined_skills.json`, which `scripts/export_esobuild_assets.py` writes on its fetch step; when the build folder is absent run that script once rather than fetching UESP by hand), keeping `isPlayer` rows and ids cast by players in the fixture logs, dropping Self and empty targets, writing `data/skills/ability_targets.json` with a `generated` date and the CC-BY-SA attribution; verify the script runs offline and `tests/unit/test_build_data_scripts.py` checks the file's shape and that Impulse is area and Crystal Fragments single
- [x] 4.2 Load the table lazily in `damage_kinds` (missing file tolerated) and document the generator in `docs/development.md` beside the other UESP tables; verify the loader test with the file absent and present

## 5. The death recap window

- [x] 5.1 Add the bar renderer (two-cell table, 99% width, small-side text outside, `esolog:kind/<side>` hover links) and the per-death summary block to `death_render.py`, which now also returns the hover map beside the HTML, with the "no damage other than the killing blow" line and the "not recorded" line for rows without `damage_type`; verify with `tests/unit/test_death_recap_gui.py` that the HTML holds the percentages and the lines for the Dreadsail death, the one-shot and an old entry
- [x] 5.2 Add the whole-fight "Damage taken this fight" block at the top (bars, lines, top five abilities with kind words and source, alive seconds) from the player's `taken` dict; verify the GUI test with a two-death player shows the block once and the per-death summaries twice
- [x] 5.3 Add the damage type and "area · hit N players" to the Result cell and serve the star hover texts through the fight view's tooltip map (`DeathRecapDialog.show_recap` must call `set_tooltips`, which it does not today; the build dialog already does); a side's label is a link to the first star's ESO-Hub page, as ability names are; verify the GUI test finds Enduring Resolve in the tooltip of the "over time" link and a click on it opens the page through the view's external opener
- [x] 5.4 `docs/screencaps/death-recap.png` retaken from the Dreadsail Reef split of 2026-09-02 with `scripts/capture_screenshots.py --hide-names` (the first death, Ignite): fight block, per-death bars, kind words in the Result column, no horizontal scrollbar; the dark theme checked on an offscreen render

## 6. The build window

- [x] 6.1 Add the "Damage dealt" section to `build_render.py` between the bars and Penetration, reading `damage.kinds`, with the no-damage and not-recorded lines and the dealt-side star hovers; verify with `tests/unit/test_build_window_gui.py` for a fire damage dealer, a healer with no damage and an old entry
- [x] 6.2 The guide's build-window picture crops above the section; `build-pen-crit.png`, scrolled to the penetration sections, now opens on the Damage dealt bars and was retaken from the fixture log with Hide names on

## 7. Documentation

- [x] 7.1 Update the user guide's "Death recaps" (the two summaries, the kind words, the hovers), "A player's build" (the Damage dealt section) and "What the log cannot show" (melee or ranged, pre-block amounts, crits taken), and the README's death recap line; verify the guide's section anchors still resolve and the screenshots referenced exist
- [x] 7.2 Add the changelog entry under a new version heading with the survey numbers that justify the rules; verify `scripts/build_design_doc.py` output is committed and the changelog renders

## 8. Integration

- [x] 8.1 Whole suite 1,036 passed (3 skipped) on the tree merged with main at 5f8c4e9; ruff on every touched file shows the same rule counts as its baseline (the house-tolerated typing and concatenation styles) with the new module and script clean; the replay comparison over 8 logs and 241 fights identical in every pre-existing field
- [ ] 8.2 Launch the app on a scratch copy of the Dreadsail Reef split with a scratch config (no real config touched), open a recap and a build window in both themes, and confirm the bars, hovers and no scrollbar; verify by the offscreen PNGs attached to the PR
- [ ] 8.3 Open the PR with the release commit (0.15.0) inside it per the main-branch ruleset; verify both CI jobs pass
