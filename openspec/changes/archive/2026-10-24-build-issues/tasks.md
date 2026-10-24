# Tasks

## 1. Weapon skill line table

- [x] 1.1 `scripts/generate_weapon_skill_lines.py` writes `data/skills/weapon_skill_lines.json` (id -> line for the six weapon lines, non-passive rows of rank 1 or more, crafted rows included, UESP attribution) from one UESP request or `--from` a saved reply; verified by running it with `--from build/esobuild-assets/sources/player_skills.json` and checking Stampede's four rank ids, Elemental Explosion's log id 217228 and no `Bash` row in the output
- [x] 1.2 A unit test in `tests/unit/test_build_data_scripts.py` covers the row filter (passives, rank -1 and other lines left out, crafted kept) and the file shape; verified by `python -m pytest tests/unit/test_build_data_scripts.py -q`

## 2. The rules module

- [x] 2.1 `src/build_issues.py`: the finding dict, the rule tables (Elemental Drain ids, Oakensoul, the three one-bar sets, the proc sets with their effect ids and triggers), `bar_weapon_line`, `weapon_line_of_slot` (table, then grimoire icon), and `structural_findings(gear, front_slots, back_slots, role, taunted)` for the six per-fight rules with the texts the spec asks for; verified by `tests/unit/test_build_issues.py` covering every scenario of the spec's per-fight requirements (Nirnhoned dagger and shield, two Absorb Stamina daggers and one glyph per bar, five heavy and the Undaunted Mettle piece and the taunting tank, Stampede on a staff, Oakensoul's back bar, an unknown weapon, Drain and Susceptibility, Pearlescent Ward 4/5 and Deadly Strike 5/3)
- [x] 2.2 `BuildIssueTracker`: `note_taunt`, `note_fight(player_key, fight_start_ms, duration_s, worn, fired)`, `findings(player_key, worn)` with the 60 s floor, the clear-on-fire rule and the overwrite by fight start, `reset()`; verified by tests for the three proc-set scenarios of the spec plus a fight cut in two counted once
- [x] 2.3 The module docstring carries the design notes (what the log gives each rule, the survey numbers, the shared-cooldown measurement, the effect ids and where they were seen) and `scripts/build_design_doc.py` gets a "Build issues" topic; verified by `python scripts/build_design_doc.py` regenerating `docs/design.md` with the topic

## 3. Engine integration

- [x] 3.1 `esolog_tail`: `CombatEncounter.proc_effects` filled from EFFECT_CHANGED GAINED lines whose ability id is a proc effect id, `BuildIssueTracker` on the analyzer reset at BEGIN_LOG, taunters noted, and in `_build_fight_entry` every player dict gets `build_issues` (structural findings plus the tracker's); verified by `tests/unit/test_build_issues.py` replaying crafted log sessions through the engine (the `build_session` fixture style): a Nirnhoned off hand flagged, a clean player with `[]`, an Alkosh wearer flagged after a 90 s fight without the effect and not after a fight in which it fired, a fight cut in two counted once
- [x] 3.2 Replay the survey's logs (`D:/esologs/splits`, every tenth file by name within 1.5 GB) through the committed engine and this one and compare every fight entry: the only difference is the new key; the finding counts per rule go into the changelog entry; verified by the comparison script's report

## 4. The fight pane and the popup

- [x] 4.1 `fight_render`: `ISSUES_HREF`, `issues_href`, `issues_unit_from_href`, the `(i)` anchor after the class text for players with findings, `issues_tooltips(entry)` and `issues_html(player, dark, set_links, links)`; verified by tests in `tests/unit/test_build_issues_gui.py` that a three-player entry renders one `(i)`, the hover text lists the titles, and the HTML holds each finding's title, detail and ESO-Hub link
- [x] 4.2 `fight_view.issues_requested`, `gui/build_issues_popup.py` (`BuildIssuesPopup`, a `Qt.Popup` frame that opens external links and closes on Esc), `main_window._show_issues` wired to the signal and the hover map including `issues_tooltips`; verified by a GUI test that clicks the anchor through the view's `anchorClicked`, sees the signal, opens the popup through the window and reads its label, and that Esc closes it

## 5. The build window

- [x] 5.1 `build_render.render_build_html` adds the findings under the header through `issues_html`, nothing for an empty list; verified by tests in `tests/unit/test_build_issues_gui.py` for a flagged and a clean player's window HTML

## 6. Documentation

- [x] 6.1 User guide: the `(i)` in "A player's row in detail", a "Possible build issues" section listing each rule as the finding states it, the build window bullet, Limitations (the role heuristic, per-session proc rules, the build is as logged at the pull); verified by reading the rendered sections
- [x] 6.2 `scripts/capture_screenshots.py` captures `build-issues.png` (the popup for the first flagged player of the selected fight, skipped with a note when none) and the user guide shows it; verified by running the script against a split log with a flagged player and viewing the PNG
- [x] 6.3 CHANGELOG under Unreleased: the feature, the rules, the survey and replay numbers, the decisions; `docs/design.md` regenerated; verified by reading both

## 7. Integration checks

- [x] 7.1 `python -m pytest tests/ -q` passes with `QT_QPA_PLATFORM=offscreen`, and `python -m ruff check` is clean on every touched file; verified by the commands' output
- [x] 7.2 The app drawn offscreen over a real split log shows the `(i)` on a flagged player, the popup on click, and the list in the build window; verified by the grabbed PNGs
