# Design: Player Build Window

## Context

See proposal.md for the motivation. This section holds only the facts that shape the approach.

**What the log carries.** `PLAYER_INFO` has, per player: long-term effect ability ids, their stack counts, an equipment list, and the two bars. Each equipment entry is `slot, id, isCP, level, trait, displayQuality, setId, enchantType, isEnchantCP, enchantLevel, enchantQuality` (docs/encounterlog-format.md). A survey of 32 recent split logs (2.5 GB, 4,279 `PLAYER_INFO` lines, game version `eso.live.12.1`) found:

- One `PLAYER_INFO` per group member within a second of `BEGIN_COMBAT`, none outside combat, none repeated within a fight. The data is a snapshot of the pull.
- 17 slot names: `HEAD, SHOULDERS, CHEST, HAND, WAIST, LEGS, FEET, NECK, RING1, RING2, MAIN_HAND, OFF_HAND, POISON, BACKUP_MAIN, BACKUP_OFF, BACKUP_POISON, COSTUME`. Empty slots are omitted from the list, so its length varies (11 to 14 entries in a four-log sample). 66 lines had an empty equipment list.
- 28 trait values, 5 quality values (`TRASH, NORMAL, ARCANE, ARTIFACT, LEGENDARY`; `MAGIC` exists but was not seen), 30 enchant types including `INVALID` for no enchant.
- Mythic pieces are logged as `LEGENDARY`.
- A poison slot holds an item id and nothing else useful (8 distinct ids seen).
- Every line listed a mundus boon among the long-term effects. In a wider sample (53 logs, 10,116 lines) 159 lines listed one boon's id twice, which is still one stone, and 41 listed two different stones.
- Bars hold 6 ids normally. Empty ability slots are omitted, not zero-filled: shapes (6,0), (6,1) and (5,5) occur.

**What the code does with it.** `ESOLogAnalyzer._handle_player_info` stores the raw equipment lists on `PlayerInfo.gear` and the bars as per-slot dicts. `_build_fight_entry` reduces gear to set counts (`sets`, `all_sets`); trait, quality and enchant never leave the engine. The long-term effect ids are parsed (as the legacy field `ability_ids`) and not stored. `UNIT_ADDED` carries the race id, which is ignored.

**The pattern to follow.** The death recap is a modeless `QDialog` holding a `FightView`, opened by an `esolog:deaths/<unit id>` anchor that `FightView` turns into a signal. `FightView` already serves bundled icons, shows per-anchor hover text and opens http(s) links externally. Its HTML is produced by a pure render function with theme-aware colors, and the dialog re-renders on a theme switch.

**Scribed skills are already per player.** Since commit 2526a75 a bar slot can carry `scribed`, `grimoire`, `scripts` or `script_options`, and `fight_render` draws them: a per-slot hover (`_scribed_tip`), a line under the bars (`_scribed_html`), anchors whose targets differ per script combination (`_ability_href`), and `anchor_tooltips(entry, links, set_links, script_links)` for the hover map. The window reuses all of it and adds no scribing logic.

**Constraints.** Engine modules never import Qt. Nothing is downloaded at runtime; links to ESO-Hub open only on click, and any ESO-Hub link carries its target in the hover text. CI runs Python 3.11. Qt rich text ignores percentage font sizes and rounds percentage table widths up.

## Goals / Non-Goals

**Goals:**

- Carry the complete combat-start build to the GUI as structured data, once per fight, with no per-event cost.
- Render it with the machinery the death recap already uses, so icons, hover text, link clicks and theming need no new mechanism.
- Stay honest about gaps: say when something was not logged rather than guess.

**Non-Goals:**

- Any item attribute the log lacks (item name, weapon type, armor weight, stats). Armor weight has since been added, looked up by item id in `data/items/armor_weights.json` (UESP's item database lists 56,439 armor pieces with a weight; all 905 armor item ids in 48 real logs were among them).
- Changing how the fight view counts set pieces (see Open Questions).
- A general item database. The only item names bundled are the 50 poisons.

## Decisions

### D1. Build data is structured in the engine and travels on the fight entry

`_build_fight_entry` adds these keys to each player dict:

| Key | Value |
|---|---|
| `character` | Character name (the existing `name` key is the display name, usually the account handle). |
| `race` | Race name from the `UNIT_ADDED` race id, `''` when unknown. |
| `gear` | List of item dicts in display order, only for slots the log listed, costume excluded. Each: `slot`, `item_id`, `set_id`, `set` (LibSets name, `Set#<id>` when unknown, `''` for no set), `mythic`, `quality`, `trait`, `enchant`, `enchant_quality` (all four as logged), `cp` (bool), `level`, `pieces` (see D5). Poison items also carry `name` and leave the enchant fields empty. |
| `mundus` | List of `{id, name, icon}`, empty when none was logged. |
| `food` | `{id, name, kind}` with `kind` being `food` or `drink`; `None` when no known buff is present. The key is absent when the bundled food table could not be loaded, so the window can tell "none" from "not checked". |

Enum fields keep the log's values; readable labels are applied at render time (D2).

*Why:* `FightHistoryEntry` is documented as everything a frontend needs. Resolving set names, poison names and food in the engine keeps LibSets and the reference tables out of the GUI, and lets tests pin the data without Qt.

*Alternative considered:* pass the raw equipment lists and let the GUI interpret them. Rejected: the GUI would need the set database and both tables, and the interpretation could not be tested without Qt.

### D2. One Qt-free module owns slot order, labels and lookups

A new `src/player_build.py` holds: the slot order and the four groups, race names, label rules for quality, trait and enchant, the poison and food lookups (reading the bundled JSON through `ability_icons.bundle_root()`, cached), mundus detection, and the piece-count rule. The analyzer calls it to build the keys in D1; the renderer calls its label functions.

Label rules:

- **Quality**: `TRASH` Trash, `NORMAL` Normal, `MAGIC` Fine, `ARCANE` Superior, `ARTIFACT` Epic, `LEGENDARY` Legendary, `MYTHIC_OVERRIDE` Mythic. An item whose set type is `LIBSETS_SETTYPE_MYTHIC` is shown as Mythic whatever the log says.
- **Trait**: drop the `ARMOR_`, `WEAPON_` or `JEWELRY_` prefix and title-case the rest. Exceptions: `ARMOR_PROSPEROUS` is Invigorating (the game's internal name for it), `WELL_FITTED` is Well-fitted, `NONE` is a dash.
- **Enchant**: named after the glyph that applies it, without "Glyph of". For example `FIERY_WEAPON` Flame, `POISONED_WEAPON` Poison, `CHARGED_WEAPON` Shock, `FROZEN_WEAPON` Frost, `BEFOULED_WEAPON` Foulness, `BERSERKER` Weapon Damage, `REDUCE_ARMOR` Crushing, `REDUCE_POWER` Weakening, `DAMAGE_SHIELD` Hardening, `DAMAGE_HEALTH` Decrease Health, `INCREASE_PHYSICAL_DAMAGE` Increase Physical Harm, `INCREASE_SPELL_DAMAGE` Increase Magical Harm, `MAGICKA_REGEN` Magicka Recovery, `REDUCE_BLOCK_AND_BASH` Bracing, `INCREASE_BASH_DAMAGE` Bashing, `REDUCE_POTION_COOLDOWN` Potion Speed, `INCREASE_POTION_EFFECTIVENESS` Potion Boost, `PRISMATIC_REGEN` Prismatic Recovery. `MAGICKA`, `STAMINA`, `HEALTH`, the `ABSORB_*`, `PRISMATIC_DEFENSE`, `PRISMATIC_ONSLAUGHT` and `REDUCE_*_COST` values title-case as they are. `INVALID` and `NONE` are a dash.
- **Unknown value**: strip a known prefix, replace underscores with spaces, title-case. A new game value therefore shows as readable text the day it appears.

The mapping was checked against one real case: the maintainer's character in a 2026-10-03 log and the SuperStar screenshot of the same character agree on every slot (Divines / Magicka armor, Bloodthirsty jewelry, a Charged staff with a Poison enchant, an Infused staff with Weapon Damage, mundus The Thief).

*Alternative considered:* store display labels in the entry. Rejected: quality colors and the mythic override need the raw values anyway, and one label table is easier to correct than labels baked into stored data.

### D3. Mundus is detected by icon family or id, never by name

An effect is a mundus boon when its icon stem starts with `ability_mundusstones_` or its id is one of the thirteen boon ids (13940, 13943, 13974 to 13982, 13984, 13985). Both signals are independent of the log's language. The shown name is the logged name without a leading "Boon: ". The icon is the bundled `ability_mundusstones_NNN.png`; all thirteen ship already.

All thirteen ids have been seen in real logs (The Serpent, 13974, only in the wider 53-log sample). An id the log lists twice for a player is one stone, so ids are deduplicated.

### D4. Food and drink come from LibFoodDrinkBuff's id tables

`scripts/generate_food_buffs.py` parses the two tables in LibFoodDrinkBuff's `Data.lua` (`lib.FOOD_BUFF_ABILITIES`, 49 ids; `lib.DRINK_BUFF_ABILITIES`, 43 ids; version 19, May 2026) into `data/buffs/food_drink.json` as `id -> {kind, type}`, where `type` is the addon's stat constant without its `LFDB_BUFF_TYPE_` prefix. The source file is taken from a path argument, else from the local ESO AddOns folder, else from the addon's ESOUI download.

A consumable can be logged as several effects, and some companion effects are in the tables too (Witchmother's Potent Brew 84731 with 84732 and 84733). When several of a player's effects match, the one whose `type` names the most stats wins, lowest id on a tie. The shown name is the log's own name for that effect.

*Alternatives considered:*

- Guess from the effect's icon. Rejected: food icons come from many unrelated families (`crafting_*`, `store_*`, `event_*`, one-off names such as `plate_of_sugarskulls`), so no prefix rule finds them all, and the loose rule "anything that is not an ability or passive icon" also caught effects that are not food in the survey (the set aura Xoryn's Masterpiece, Violet Lamp Servant, Boiling Oil).
- SuperStar's built-in table (38 ids). Rejected: it lacks 3 of the 24 food ids found in the survey (127572, 72959, 100488).

### D5. Piece counts are per weapon bar

For each set: `body` is the number of armor and jewelry items of the set; `front` and `back` are the weapon pieces of the set on each bar, where a main hand with no off hand logged beside it counts as two. Pieces active on the front bar are `body + front`, on the back bar `body + back`. Each gear item's `pieces` is `[front_total, back_total]`, with `back_total` `None` when the log lists no back-bar weapon. The grid shows a weapon row's own bar; an armor or jewelry row shows one number when both agree and `front/back` otherwise.

Worked example from a real log: three jewelry and armor pieces of Perfected Whorl of the Depths, a staff of another set on the front bar, and a Whorl staff on the back bar. The body rows read `3/5` and the back staff reads `5`: the five-piece bonus is live on the back bar only. The fight view's summed count shows `5x` for the same build.

The two-handed rule moves into `player_build` as a pure function, and `ESOLogAnalyzer._is_two_handed_weapon` delegates to it, so the fight view and the window cannot disagree about what is two-handed.

*Alternative considered:* repeat the fight view's summed count. Rejected: it overstates sets that span both bars, which is the case a gear check looks for.

### D6. Poison names come from UESP's item database, at build time

`scripts/generate_poison_names.py` requests `minedItemSummary` for item type 30 from UESP's export endpoint (one request, 50 rows) and writes `data/items/poisons_en.json` as `id -> {name, tiered}`. A name ending in a tier numeral is stored without it and marked `tiered`; the numeral shown is derived from the logged level by the solvent tiers (I to V at levels 3, 10, 20, 30, 40; VI to IX at champion ranks 10, 50, 100, 150). The script refuses to overwrite the file when it receives fewer than 30 rows.

All 8 poison ids in the survey are covered. A crafted poison's id identifies its primary effect only; its other effects are not in the log, and the README says so.

*Alternatives considered:* extract names from the game's language file (more tooling for 50 names); look ids up at runtime (breaks the no-network rule).

### D7. The window is a modeless dialog around a FightView, rendering HTML

`gui/build_dialog.py` mirrors `DeathRecapDialog`: created on first use, reused afterwards, remembering `(entry, unit_id)` so `refresh(dark)` can redraw on a theme switch. Because it holds the entry it was opened with, it stays pinned to that fight by construction.

`gui/build_render.py` produces the HTML. Layout, top to bottom: header lines, a mundus and food line, the bars (a two-row table with a muted Front / Back label and 36 px icons; the bundled PNGs are 40 px), the scribed-skills line when the player has any, the gear table with muted group rows, and the pieces caption. The hover map is the fight's existing `anchor_tooltips` (ability, scribed, script and set anchors use the same targets in both places), so the window needs no hover logic of its own. Quality colors come from a two-theme palette in the renderer, like the other render modules, with darker variants for light backgrounds (game gold on white does not read).

*Alternative considered:* a native `QTableWidget`. Rejected: icons, link clicks and per-cell hover text would each need custom delegates, and sixteen rows gain nothing from sorting or column resizing.

### D8. The player's name is the link

`fight_render` wraps each listed player's name in `<a href="esolog:build/<unit id>">`, in both views. The anchor is styled with the pane's own text color and no underline, so the row looks as it does today while the pointer is elsewhere; hovering restyles the name (D9). `MainWindow` passes the pane's palette text color into `render_html`; when it is not given, a per-theme default is used. `FightView` gains a `build_requested` signal, emitted for that href prefix alongside the existing death-recap routing. `MainWindow` merges the build hints into the tooltip map it already assembles and opens the dialog.

Dependency direction: `build_render` imports the bar, scribed-line and theme helpers from `fight_render`, never the reverse. The href helpers for the build link live in `fight_render` with the row markup. The bar helper gains an icon-size parameter (22 px in the fight view, 36 px in the window).

### D9. The hover cue is an extra selection owned by FightView

Qt rich text has no `:hover` styling, so the widget applies the cue. `FightView` already receives `highlighted(url)` when the pointer enters an anchor and an empty URL when it leaves; it uses this for tooltips. For a build link it now also places an extra selection over that anchor's text, with an underline and the theme's link color, and removes it when the pointer leaves or when new HTML is set. An extra selection restyles text at paint time without changing the document, so layout, scroll position and search results are untouched.

The in-fight search uses the same mechanism: `MainWindow._apply_search` calls `setExtraSelections` directly, and a second caller would overwrite it. `FightView` therefore becomes the owner of both lists, the search selections handed in by the main window and its own hover selection, and applies their union.

The link color is a per-theme value in the render theme, handed to the view by the main window together with the tooltip map, so a theme switch updates it through the existing re-render path.

A prototype confirmed the approach offscreen, in both themes, with real pointer movement: the name restyles on entry and reverts on exit, and a search highlight on the same row stays throughout.

Only build links get the cue. Set, skill and script links keep their current hover (tooltip and pointing hand).

*Alternatives considered:*

- Re-render the HTML with the hovered name styled. Rejected: it resets the scroll position and any text selection on every pointer move.
- Change the document's character format on hover. Rejected: it enters the undo stack, forces a relayout, and invalidates the cursors the search holds.
- A permanent underline or link color on every name. Rejected: always-on clutter in twelve-player fights, which choosing the name as the link was meant to avoid.

### D10. Parser hardening

`PlayerInfoEntry.parse` requires at least one long-term effect and one stack count (`[^\]]+`). A player with none would lose their whole build. No such line appeared in the survey, but the pattern is relaxed to accept empty lists, with a test, since this change is the first to depend on that list.

## Risks / Trade-offs

- [The name link is easy to miss] → On hover the name is underlined in the link color (D9), with a tooltip and the pointing-hand cursor; documented in README and CHANGELOG. The name as the link was chosen by the maintainer over a per-row button to keep twelve-player fights uncluttered.
- [The hover selection and the search selections overwrite each other] → `FightView` owns both and applies their union (D9); a test hovers a name while search highlights are showing.
- [A food released after the bundled table reads as "none"] → The window says "no known food or drink buff". The generator has a `--check-log` mode that lists long-term effects with food-style icons that the table lacks, to run after a patch.
- [UESP changes its export, or ESOUI its download] → Both scripts are build-time only and guarded against short results; the committed JSON keeps working. Unknown poison ids fall back to "Poison (item <id>)".
- [A reference table is missing from a packaged build] → Poisons fall back to the item id and the food line is hidden (D1). The packaged-build check in tasks.md looks for both names.
- [The window's piece counts differ from the fight view's `Nx` line for sets that span both bars] → Intended (D5); the caption under the grid explains the two-number form. See Open Questions.
- [Gear swapped mid-fight is not reflected] → The header says the build is as logged at the start of the fight.
- [Qt rich-text quirks] → Point sizes instead of percentages, table width 99%, icons in their own cells, as `death_render` already does.

## Migration Plan

None. Fight entries live in memory for the session, so no stored data predates the new keys. Rollback is reverting the change.

## Open Questions

These can be settled later without changing this change's specs or tasks.

- Should the fight view's `Nx` set counts move to per-bar counting to match the window? It changes existing output and the golden fixtures, so it belongs in its own change.
- Show what a named food grants (max health, stamina recovery and so on) from LibFoodDrinkBuff's `type`? The data is bundled by D4; only the wording is undecided.
- ESO-Hub has pages for mundus stones, traits and glyphs. Linking them was declined for this version.
