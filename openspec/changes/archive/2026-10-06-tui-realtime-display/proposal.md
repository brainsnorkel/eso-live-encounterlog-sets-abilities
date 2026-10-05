## Why

The current real-time display is a plain scrolling `print()` output that disappears off-screen as new encounters arrive. There is no way to review previous fights without scrolling the terminal buffer, and the output is verbose — showing full ability lists and gear when most of the time you just want a compact combat summary. Replacing it with a TUI provides a fixed-layout display of the last fight with the ability to scroll back through history, plus a more compact per-player format that includes an inferred role indicator (T/H/D).

## What Changes

- Replace the scrolling `print()`-based encounter display with a full-screen TUI (using `curses` or `textual`)
- The TUI shows the most recent completed fight by default, with a compact per-player summary
- Arrow-up / k scrolls back through previous fights; arrow-down / j returns toward the latest; a "live" mode auto-snaps to the newest fight when it completes
- Each player line includes an inferred role tag: **T** (tank), **H** (healer), **D** (DPS) based on resource heuristics:
  - Tank: highest max resource is health
  - DPS: highest max resource is stamina or magicka (and not primarily a healer)
  - Healer: highest max resource is magicka AND heals other players more than they deal damage
- The display is more compact than the current report format — one line per player with role, name, DPS, damage%, and key resources

## Capabilities

### New Capabilities
- `tui-fight-display`: Full-screen TUI showing the last fight with scrollable fight history and compact layout
- `role-heuristic`: Resource-and-healing-based player role inference (T/H/D) displayed per player line

### Modified Capabilities

## Impact

- `src/esolog_tail.py`: `_display_encounter_summary()` and `_print_and_buffer()` replaced/wrapped by TUI rendering; `LogFileMonitor` main loop needs to drive TUI updates instead of printing
- New dependency: `curses` (stdlib on Linux/macOS, `windows-curses` pip package on Windows) or `textual` (pip)
- `src/eso_sets.py`: Existing `_infer_role_from_skill_lines()` supplemented or replaced by resource+healing heuristic
- Report file saving (`--save-reports`) continues to work unchanged — TUI is display-only
- The `--tail-and-split` workflow is unaffected
