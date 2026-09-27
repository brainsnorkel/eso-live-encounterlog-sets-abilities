# Proposal: Experimental Buff/Debuff Timeline Strip

**Status: EXPERIMENTAL — parked for a later release.** Must stay very compact and never get in the way of the primary fight-summary UI.

## Why

The fight summary shows buff *uptime percentages*, which hide the timing story: a 70% Major Force uptime could be a strong opener with a dead middle, or steady coverage that dropped at execute. Raid leads diagnosing rotations need to see *when* the big group buffs were up and who was providing them, without opening an external log site.

## What Changes

- **Per-fight buff/debuff interval tracking** in the engine for five tracked effects: Major Slayer, Major Force, Major Courage, Major Berserk (group buffs on players) and Major Vulnerability (debuff on enemies — requires adding its ability ID to the tracked set). Each interval records start/end offsets, casting unit, and receiving unit.
- **Mini timeline widget** in the GUI fight detail view: one thin colored line per tracked effect across the fight duration, with time tick marks; hovering a segment shows who cast it and who received it. Rendered as a compact strip (target: ≤ 6 rows of ~10 px) under the fight header.
- **Experimental gate**: off by default; enabled by an "Experimental: buff timeline" checkbox in Settings. When disabled, no intervals are retained (no memory/CPU cost) and the strip is absent.

## Capabilities

### New Capabilities

- `buff-timeline`: Tracking buff/debuff active intervals with cast/receive attribution during a fight, and rendering them as a compact, hoverable per-fight timeline strip in the GUI (experimental, opt-in).

### Modified Capabilities

<!-- none: existing buff uptime percentages are unchanged -->

## Impact

- **Code**: interval capture in `ESOLogAnalyzer`'s EFFECT_CHANGED handling (gated by config); a `buff_timeline` field on `FightHistoryEntry` (None when disabled); a new `TimelineStrip` widget in `src/gui/`; a settings checkbox; Major Vulnerability ability ID added to the tracked-buff table.
- **Performance**: interval lists are bounded per fight (long fights ≈ hundreds of intervals per effect); zero overhead when the experimental toggle is off.
- **No changes** to existing uptime percentages, reports, split files, or archiving.
