# Design

## Context

See proposal.md for the motivation. What the code and the logs give us to build on:

- **The recap pipeline.** `_handle_combat_event` in `src/esolog_tail.py` routes every COMBAT_EVENT on a player whose result is in `RECAP_RESULTS` to `DeathRecapRecorder.record`, which keeps a five-second deque per player of `(ts, result, hit, overflow, castTrackId, abilityId, sourceId, health)` and drops pure overheals; `note_death` turns the deque into rows and keeps refilling for 100 ms while the killing blow lands after the DIED line. The rows carry the result but not the damage type (field index 1 of the parsed line, never read today) and nothing about the cast's other targets. `death_render.render_death_recap_html` draws the rows as a table in a `FightView` (a QTextBrowser), theme-aware, with hover text served through the fight view's tooltip map.
- **The damage-dealt pipeline.** `CombatEncounter.add_damage_to_player` feeds `damage_stats.FightDamage.note` with `(ts, hit, result, ability_id, pet, target_id, boss)`; `AbilityDamage` keeps damage, hits, crits, blocked, shielded, tick counts, max and min per ability; `PlayerDamage.snapshot` writes plain dicts onto the player's fight dict under `damage`, which `damage_render` and `build_render` (the pen_crit sections) read on the GUI thread.
- **What the log says, measured on 87 of Chris's split logs (10.8 GB, 11.6 million combat lines, 6,831 player deaths), 2026-10-27:**
  - Damage types on players: PHYSICAL, MAGIC, SHOCK, FIRE, POISON, COLD, OBLIVION, BLEED, DISEASE, GENERIC, DROWN, and EARTH on 5 hits (6,526 damage); NONE on REFLECTED lines and on the 368 zero-value DAMAGE lines the game writes beside a DAMAGE_SHIELDED line when a shield took the whole hit. Fall damage is result `FALL_DAMAGE`, type GENERIC, ability 10950 "Fall Snare" (1,578 lines, 15.4M damage). Drowning is type DROWN (121k damage, 3 deaths). The classifier therefore names every unknown type under the log's own word rather than refusing it.
  - Of the damage that reached players' health, 89% was direct and 11% ticks; 885M Magical, 411M Martial, 44M Oblivion, 20M fall, drowning or untyped. Death lines by type: MAGIC 1,434, PHYSICAL 1,391, SHOCK 1,257, FIRE 1,053, OBLIVION 770, COLD 587, POISON 243, GENERIC 59, BLEED 17, DISEASE 17, DROWN 3.
  - Shields absorbed 726M on players, more than any single damage type reached health; heals landed 1.17B and overflowed 12.4B (3.1M of 3.6M heal lines were pure overheal); HEAL_ABSORBED 7,691 lines.
  - The killing blow's damage line followed the death line within 100 ms in 6,398 deaths and carried overflow in 6,039 of them; the 244 `BLOCKED_DAMAGE` and 12 `FALL_DAMAGE` killing blows carried none.
  - Every hostile hit on a player carried a non-zero castTrackId. Grouping hits by (source, cast id): Maelstrom 147 casts for 30,913 hits, up to 12 players each; Grievous Pulse 38 casts, 100% multi-target; Oppressive Bolts 266 casts, 98% multi-target although UESP's skill table calls it "Enemy"; Piercing Hailstone, Venom Injection, Temporal Splinters, Swipe, Claw, Clash one target per cast, always. Weighted by damage, 69% of hostile damage on players came from abilities whose casts struck two or more players at least a tenth of the time. UESP's `target` field knows 74% of that damage (45% Area/Cone/Ground, 27% Enemy, 1% Self) and disagrees with the log on 6% (Enemy with multi-target casts), so for monster abilities the log is the better judge.
  - Monsters do not crit players: the 94 CRITICAL_DAMAGE and 61 DOT_TICK_CRITICAL lines on players (0.1% of the damage taken) all came from other players.
  - Unit positions are normalised map coordinates: medians per ability range from 0.002 to 0.25 with no scale across maps, so range cannot be read.
  - In the Dreadsail Reef log of 2026-09-02 (550 deaths) the five-second window before a death is usually one mechanic, often a single full-health hit (Lost to the Depths, 20,372) that is the whole table.
- **UESP's skill table** is already fetched and cached by `scripts/export_esobuild_assets.py` (`build/esobuild-assets/sources/mined_skills.json`, 159,254 abilities, fields `target`, `mechanic`, `castTime`, `isPlayer`, `isPassive`); 4,397 rows are player abilities. UESP is a volunteer service that has blocked bursts from this machine; nothing here may add a request to it.
- **Precedent.** `pen_crit.py` already names Champion Point stars (Piercing, Fighting Finesse, Backstabber, Force of Nature) as rows the log cannot show; the Settings let the reader assume them. ESO-Hub data shown in the app must carry a link to its ESO-Hub page.

## Goals / Non-Goals

**Goals:**

- One classification, written once (`damage_kinds.py`) and drawn the same way in both windows, so a reader learns the vocabulary once.
- Every figure comes from the log; the only table consulted is for a player's own skills, and the hover says when a figure rests on it.
- No new Settings, no assumptions about the player's stars; the star names are hover text.
- Fight entries stay plain dicts the GUI thread reads; old entries render without error.

**Non-Goals:**

- Melee against ranged, pre-mitigation amounts, resistances, critical hits taken (not in the log).
- Per-session or cross-fight totals beyond the area memory (the fight is the unit the app reports on).
- A boss-only view of damage taken or dealt kinds (the damage window keeps its boss toggle; the build section reads all targets).
- Changing the damage window.

## Decisions

**D1. The per-death summary is drawn from the recap rows; the fight total is a new engine aggregate.** The rows already hold everything the per-death summary needs once they carry the damage type and the area flag, so the summary is computed at render time from them (no new engine state, and old rows without the fields are detected). The whole-fight figures cannot come from rows (the deque is five seconds), so the recap branch of `_handle_combat_event` also feeds a per-player `TakenTally` in `damage_kinds.py` (totals by kind, per-ability damage with source, first and last hit) that `_build_fight_entry` snapshots onto the player's dict as `taken` for every player, not only the dead, so the block costs nothing extra and a later window can show it for the living. Alternative considered: extend the deque to the whole fight. Rejected: a tank in a ten-minute fight takes tens of thousands of lines; the tally is a dozen counters per player.

**D2. Area or single target is read from cast ids, with a session memory, and UESP only for a player's own skills.** A `CastIndex` holds two maps: `(source, castTrackId) -> set of unit ids struck`, cleared at each fight's end so it never holds more than one fight's casts, and `ability -> max units struck on one cast`, kept for the zone session (cleared with the recorder's `reset`, which runs on BEGIN_LOG and zone change, where unit ids start over). A pet's hits count as the owner's for the player rule, the table is looked up by the pet ability's id, and a pet ability in neither falls to single target like any other. Classification order: this cast struck two or more units → area; the ability struck two or more units on a cast earlier in the session → area; a player's or pet's ability in the bundled table → the table (Area, Cone, Ground → area; Enemy → single); otherwise single. Monster abilities never consult the table because the survey shows UESP's "Enemy" on group-wide mechanics (Oppressive Bolts hit 12 players on one cast id in 98% of casts). The per-death rows are classed when the recap is built or refilled (so a later hit of the same cast reclasses the earlier row); the tally counts area damage as hits arrive and corrects itself when a cast's second target appears by moving that cast's earlier damage from single to area (the index keeps per-cast damage until the second target lands, then drops it). Alternatives: UESP for everything (wrong on 6% of damage and unknown on 26%); nothing but this fight's casts (misses the one-target cast on a repeat pull). The hover says which rule applied.

**D3. The player-skill target table is generated from the cached UESP reply, never fetched here.** `scripts/generate_ability_targets.py` reads `build/esobuild-assets/sources/mined_skills.json` (or a path given) and writes `data/skills/ability_targets.json` as `{ability_id: "area" | "single"}` for rows with `isPlayer` set or whose id a player cast in the fixture logs, dropping Self and empty targets; about 4,400 entries, a few tens of kilobytes. The file carries the same CC-BY-SA attribution line as the other UESP-derived tables and a `generated` date. Alternative: bundle all 159k rows (1.5 MB for mostly monster abilities we have decided not to trust).

**D4. The damage-dealt kinds extend `AbilityDamage`, not a second record.** Each row gains `by_type` (damage per damage type), `tick_damage` and `area_damage`; `PlayerDamage.snapshot` adds a `kinds` dict with the sides, the types and the shares, so `build_render` reads one dict and the ability table in the damage window is untouched. The engine passes the damage type and the cast id through `add_damage_to_player` to `FightDamage.note`; the `CastIndex` is shared with D2 so a player's cleave on three mobs is one lookup.

**D5. Bars are HTML tables in the QTextBrowser.** A two-sided bar is a one-row table of two `<td>` cells with `bgcolor` and percentage widths and the percentage as the cell text, which Qt's rich text renders without images (the final-blow highlight already uses `bgcolor`). The outer table is 99% wide and a side under 8% carries no text on the bar; each side's label beside the bar gives its amount and percentage, so a thin side is still read. The label is a link to the ESO-Hub page of the first Warfare star that acts on that side, with the hover text naming every such star and its tooltip (the pattern the ability names use: the hover tells, the click opens the page), because a tooltip cannot carry a clickable link and ESO-Hub data shown in the app must link to its page. Alternative: a QWidget strip like the buff timeline. Rejected: the recap and build windows are text pages, and a widget would need its own layout per death.

**D6. The star table is static data in `damage_kinds.py`**: for each side of each split, the star names, the game's tooltip text as UESP's Warfare page gives it, and the ESO-Hub URL. The list is checked against the current game (Update 51) at implementation time, since UESP's page was last edited in 2024. No Settings, no "assumed" rows: the issue puts the star angle second, and the log cannot see slotted stars.

**D7. Backward compatibility by key presence.** A recap row without a `damage_type` key, or a player dict without `taken` or `damage.kinds`, renders the "not recorded" line. No fight-entry version number: the project has used key presence for every such addition (build issues, pen_crit, damage).

**D8. Design notes live in the code.** The classification rules, the survey numbers and the reasons for D2 go in `damage_kinds.py`'s module docstring; `scripts/build_design_doc.py` gets a "Kinds of damage" topic that extracts it; docs/design.md is regenerated.

## Risks / Trade-offs

- [An area hit that struck one player reads as single target] → the session memory catches repeat pulls; the hover says "no cast of this ability struck two players this session", so the reader can judge.
- [A bounce or chain mechanic that the game treats as single target reads as area] → the row says "hit N players", which is what the reader saw happen; the hover says the class rests on the cast, not on the game's flag.
- [Reclassing an earlier row or moving tally damage from single to area when a cast's second target lands] → covered by unit tests with the hits in both orders; the index drops a cast's per-cast damage after the second target, so memory is bounded by live casts.
- [Overheal kept in the deque grows it] → pure-overheal events are stored as a two-field tuple and never become rows; the five-second cut applies as before.
- [Qt's percentage-width rounding summons a horizontal scrollbar] → 99% total width as the existing tables do, checked with the offscreen screenshot recipe before merge.
- [The hover links change how clicking the bars behaves] → `esolog:kind/` hrefs are swallowed by the fight view's link handler like `esolog:ability/`; a GUI test clicks one.
- [The golden fixture gains keys] → the golden test is updated once with the new keys and the replay comparison over the sample logs proves every existing field unchanged.
- [Another branch (hide-names-72) edits `death_render.py` at the same time] → the new rendering goes in new functions called from two places, so the merge is additive.
- [UESP's target table for player skills has gaps (Pure Agony's target is empty)] → the cast rule runs first and "single" is the fallback; the hover says the share that rests on the table.
- [A damage type the tables do not list (EARTH today, anything a patch adds)] → the classifier never refuses a type: unknown types count in the totals and are named under the log's word; a test feeds it EARTH and a made-up type.
- [The recap window serves no hover text today: `DeathRecapDialog.show_recap` calls `setHtml` and never `set_tooltips`] → `render_death_recap_html` returns the tooltip map beside the HTML (as `build_render` does for the build dialog) and `show_recap` passes it to the view; a GUI test hovers a side.
- [ESO-Hub's champion point page URLs could not be checked from this machine (its servers answer 403 to the fetcher)] → the generator confirms them from ESO-Hub's sitemap the way the skill and set link tables were built; if ESO-Hub has no star pages, the hover links UESP's Warfare page instead and the spec's wording is amended.

## Migration Plan

- No config, file-format or dependency change. Entries recorded by older versions render with the "not recorded" lines; new entries carry the keys.
- Ships as a feature release (0.15.0) through the usual PR; rollback is the previous release, since the new keys are ignored by older code.

## Open Questions

- The exact colours of the two sides in each theme and whether the three bars share a width; settled with the offscreen screenshots.
- How many top abilities the fight block lists (five proposed) and whether it names the source unit when every row has the same one.
- Whether the Warfare star texts should quote the per-stage numbers or only the max-stage effect; the hover has room for either.
