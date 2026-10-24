# Design: Possible build issues

## Context

See proposal.md for the motivation and the rules as decided. What this builds on:

- `PLAYER_INFO` gives, per player and fight, the eleven fields of every equipped item (slot, item id, trait, set id, enchant type among them) and the ability ids of both bars. `player_build` already turns the item id into an armor weight or weapon type (bundled UESP tables), counts a set's pieces per bar with a two-hander as two (`piece_counts`), and knows a shield by its armor trait (`is_two_handed`).
- The engine's player dict for a fight already carries `role` (`infer_player_role`), `taunts` (the abilities taunted with this fight, from TAUNTED events), the bar slots with id, name and icon stem, and the gear rows.
- Effects a player sources arrive as `EFFECT_CHANGED` lines whose source unit is the player (`_handle_effect_changed`, `extract_effect_fields`). `CombatEncounter` is rebuilt at every BEGIN_COMBAT with its players carried over; a fight the game cut in two reopens the same encounter and republishes its entry (`_publish_fight`, `COMBAT_RESUME_MS`).
- A player's identity across the zones of one logging session is `_scribing_player_key` (the per-session id UNIT_ADDED gives); BEGIN_LOG resets the trackers that key on it.
- The fight pane's per-player links are `esolog:` anchors routed by `FightView._on_anchor_clicked` to signals the main window connects; the timeline strip's `SummaryPopup` is the transient-popup precedent (a `Qt.Popup` frame that deletes itself on close).
- Survey of 83 split logs of September and October 2026 (`survey16.py`, `glyph_cooldown.py`, `aggregate16.py` in the session scratchpad; numbers in the module docstring): per rule, player-fights and distinct characters as recommended: Nirnhoned off hand 429/17; same glyph on one bar 421/22; heavy 2 or more on a DPS 218/9 (5 or more 103/4); wrong-weapon skill with the bar in use 235/14 and 55 more on the back bar under Oakensoul; Elemental Drain 124/5; Alkosh never fired at a 60 s floor 12/3; Roaring Opportunist 19/8; the three group sets on one bar 80/3. Identical glyphs share one cooldown: the same glyph from one player never fired twice within 4.0 s and the proc rate was the same with one or two copies on a bar (Absorb Stamina 6.0 vs 6.5 per minute, Poisoned 6.2 vs 7.2). Roaring Opportunist wearers source Major Slayer as 135923 and 93109; Alkosh wearers source Roar of Alkosh as 76667 and 75751.

## Goals / Non-Goals

**Goals:**
- Findings a player can act on, each carrying its rule, computed from what the log proves and nothing the app guesses at beyond the role heuristic it already shows.
- No change to any other field of a fight entry: a replay of real logs through the old and the new engine differs only in the new `build_issues` key.
- The (i) is a cue only where there is something to say; rows of clean builds look as they do today.

**Non-Goals:**
- A user-editable rule text: a separate issue, with a feasibility analysis, at the maintainer's request. The lists this build hard-codes (set ids, proc effect ids, morph ids, the weapon-line table) are kept as module-level data so that issue can lift them out.
- Judging the plain-text copy (Copy fight): unchanged.
- Rules the issue does not list (missing enchants, gear below legendary, no food); candidates are recorded in the issue thread.
- Severity levels: one list, in rule order.

## Decisions

- **Structural rules per fight, proc rules per session.** Nirnhoned, glyphs, armor, weapon skills, Elemental Drain and the one-bar sets depend only on the fight's `PLAYER_INFO`, so they are computed when the fight entry is built, from the player dict's own data. Whether a set ever fired is a property of the session: a `BuildIssueTracker` on the analyzer records, per player key and set, each fight's start time, whether it was 60 s or longer and whether the proc was sourced, keyed by the fight's start so a fight the game cut in two overwrites its own record instead of counting twice. The finding is produced when the player has at least one long fight in the set and no fire at all; a single fire clears it for the session. *Alternative*: judge each fight alone. Rejected: 30 of 219 wearer-fights under 30 s had no proc in the survey though the set worked, and the first two short pulls of a trial would flag every Alkosh wearer.
- **The procs are read from EFFECT_CHANGED GAINED lines whose source is the player**, under the set's effect ids (Alkosh 76667, 75751, 75752, 120018; Roaring Opportunist's Major Slayer 93109 and 135923). The encounter keeps `proc_effects: source unit id -> set of ids`; it is rebuilt with each encounter, and a reopened fight keeps accumulating. *Alternative*: match effect names ("Major Slayer"). Rejected: names follow the client language; the tracked-effects rules use ids for the same reason.
- **Heavy armor needs the role and a taunt guard.** The role heuristic reads the dominant resource, and in the survey 363 "tank" player-fights wore no heavy at all while a stamina-heavy fake tank reads DPS. So the rule asks for role `D` and that the player has not taunted this session (the tracker remembers taunters by player key from the fight's `taunts`). Threshold two pieces, the maintainer's decision; one heavy piece is the Undaunted Mettle norm (618 of 8,766 DPS player-fights).
- **Weapon lines come from a bundled table, generated from UESP's playerSkills** like `class_passives.json`: every non-passive row of the six weapon lines with a rank of 1 or more (the rank -1 rows are internal effects such as Bash), crafted (scribed) rows included, written as id -> line. The log's slotted id of a scribed skill is in the table (217228 Elemental Explosion); when a slotted id is missing, the slot's icon stem names the grimoire (`scribing.GRIMOIRES`) and the grimoire its line. The bar's own line comes from `player_build.weapon_type` of the main hand and off hand: a two-hander, bow or staff by type; a one-hander with a shield is One Hand and Shield, with another one-hander Dual Wield, alone nothing. A bar whose main hand the table does not know is not judged.
- **Oakensoul Ring (set 658) silences the back bar** for the wrong-weapon and one-bar rules, since the ring forbids swapping; 1,006 player-fights wore it, 343 of them with a back bar logged.
- **Findings are dicts** `{'rule', 'title', 'detail', 'set', 'skill'}` on the player dict as `build_issues`, like every other per-player field: JSON-shaped, renderable without the engine. `title` is the specific observation ("Nirnhoned on the off-hand Dagger, front bar"), `detail` the rule; `set` and `skill` carry a name the renderer can link to ESO-Hub. *Alternative*: a dataclass. Rejected: the player dict is plain data throughout.
- **The (i) is a text anchor in the link color**, `esolog:issues/<unit id>`, after the class and subclass text, present only when the list is non-empty. The pane's hover map lists the titles; the click emits `issues_requested(unit_id)` like the other row links, and the window opens a `BuildIssuesPopup` (a `Qt.Popup` frame at the cursor, rich text, ESO-Hub links opened externally) built from `fight_render.issues_html`. *Alternative*: an image glyph as issue #34 explores for the dps links. Rejected for now: the text cue is what the issue asks for and needs no HiDPI handling; #34 can restyle both together.
- **The build window shows the same `issues_html`** under its header line, before the bars, so the window and the popup cannot drift apart.
- **Finding texts live in the module** as format strings, one per rule, with the game facts stated plainly (the 6% of Dual Wield Expert, the shared cooldown, the 7.5-second status effects, the set's trigger). The module docstring carries the survey evidence and the sources; `scripts/build_design_doc.py` gets a topic for it.

## Risks / Trade-offs

- [A set newer than the bundled tables shows no weight or weapon type] → the heavy rule counts known heavy pieces only, the weapon rule skips an unknown bar; both err towards silence, as the build window's dash does.
- [A player who swaps gear mid-session keeps the proc tracker's record under the same key] → the record is per player and set; a set taken off stops accruing long fights, and a fire in any fight clears it. The title says how many long fights were counted, so a stale note reads as such.
- [The role heuristic misreads a healer in heavy as a DPS] → healers read H from a restoration staff or out-healing; the survey's healers wore at most one heavy piece.
- [A healer slotting Elemental Drain for the group's Minor Magickasteal is flagged] → the maintainer's decision; the finding states both morphs' effects so the reader can judge.
- [The (i) adds a row decoration the 2026-10-06 build-window design avoided] → only on flagged players, and it is the issue's own request.

## Migration Plan

Nothing to migrate: no config, no saved state. A fight entry gains a key; older frontends ignore it.

## As built (2026-10-24)

- Built as designed, with two details settled in the code: the taunt guard counts any TAUNTED event of the player this session, including the ones the log does not tie to a cast (which the bars' taunt marks leave out), and the popup is placed after it is shown, since a popup frame's size is only settled then.
- The weapon-line table holds 605 ids (not the 1,038 first estimated: UESP's synthetic rank ids for crafted skills are dropped).
- Replay of 9 split logs (every tenth by name within 1.5 GB; 181 fights, 1,594 player-fights) through the committed and the new engine: 0 differences outside `build_issues`. Findings in that sample: a weapon skill on the wrong bar 53 player-fights (5 characters), Nirnhoned off hand 36 (1), the same glyph twice on a bar 21 (2), Elemental Drain 9 (1); the heavy-armor, never-fired and one-bar rules had no case in it (the September and October survey has theirs).
- Tests: `tests/unit/test_build_issues.py` (rules, tracker, engine), `tests/unit/test_build_issues_gui.py` (cue, hover, click, popup, build window), `TestWeaponSkillLines` in `tests/unit/test_build_data_scripts.py`.
