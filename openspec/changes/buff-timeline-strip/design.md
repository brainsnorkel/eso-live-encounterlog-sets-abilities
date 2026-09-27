# Design: Buff/Debuff Timeline Strip (EXPERIMENTAL)

## Context

The engine already resolves the tracked buffs' ability IDs (`BUFF_ABILITY_IDS` in `src/esolog_tail.py`: Major Slayer 93109, Major Force 61747, Major Courage 109966, Major Berserk 62195) and processes `EFFECT_CHANGED GAINED/FADED/UPDATED` events with source and target unit fields for uptime accounting. Major Vulnerability (enemy debuff) is not yet in the table and must be added. Fight results reach the GUI as `FightHistoryEntry` objects via `on_fight_completed`; the detail pane is a QTextBrowser fed by `gui/fight_render.py`.

## Goals / Non-Goals

**Goals:** per-fight interval capture with cast/receive attribution for the five effects; a compact hoverable strip in the detail view; strictly opt-in (experimental), zero cost when off.

**Non-Goals:** full damage/uptime charting, per-player timeline matrices, export, tracking effects beyond the five named ones, changing existing uptime percentage calculations.

## Decisions

- **Capture**: a small `BuffTimelineRecorder` keyed by effect → list of open/closed intervals `(start_ms, end_ms, source_unit_id, target_unit_id)`, driven from the existing EFFECT_CHANGED handler; opened on GAINED, closed on FADED, force-closed at END_COMBAT. Gated by `experimental.buff_timeline` in AppConfig (read once per analyzer construction). Interval lists capped (e.g. 2,000 per effect) as a runaway guard.
- **Transport**: `FightHistoryEntry.buff_timeline: dict[str, list[Interval]] | None` (None when disabled) plus the fight start offset so the widget can normalize times. Unit IDs are resolved to display names at capture time (names are only reliably known during the fight).
- **Rendering**: the QTextBrowser can't do hover hit-testing, so the detail pane becomes a small vertical layout: a custom `TimelineStrip(QWidget)` painted with QPainter (rows, fills, ticks every 30s — or 10s for fights under 2 minutes) above the existing QTextBrowser. The strip implements `event(QHelpEvent)` for tooltips listing overlapping intervals at the hovered x-offset. Fixed row height 10 px, max height ≈ 70 px, hidden entirely when the fight carries no timeline data. Colors: Slayer #e57373, Force #64b5f6, Courage #ffd54f, Berserk #ba68c8, Vulnerability #4db6ac; an "EXPERIMENTAL" hint in the corner at 60% opacity.
- **Settings**: one checkbox in an "Experimental" group of the settings dialog writing `experimental.buff_timeline` (default false). Toggle applies from the next monitoring restart (same restart path as other settings).

## Risks / Trade-offs

- [EFFECT_CHANGED attribution fields may be ambiguous for ground/synergy-sourced buffs] → attribute to the event's source unit; fall back to "unknown" rather than guessing.
- [Strip could crowd small windows] → fixed max height, collapses to nothing when disabled or dataless; never scrolls the summary.
- [UPDATED events (stack refreshes) could fragment intervals] → treat UPDATED as continuation; merge adjacent intervals with gaps below 500 ms.

## Migration Plan

Pure addition behind an off-by-default flag; no migration. Ship dark (flag off), gather feedback, then decide default.

## Open Questions

- Confirm the live Major Vulnerability ability ID (expected 106754) against a current log before wiring it in.
- Whether receivers should be aggregated ("8 players") above some count to keep tooltips short.
