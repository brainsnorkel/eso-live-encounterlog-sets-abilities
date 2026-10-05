## 1. Dependencies and Setup

- [x] 1.1 Add `windows-curses` to `requirements.txt` (conditional on Windows)
- [x] 1.2 Update `esolog-tail.spec` PyInstaller config with hidden imports for `windows-curses` if needed
- [x] 1.3 Add `--no-tui` CLI flag to the Click command in `main()`

## 2. Role Heuristic

- [x] 2.1 Add `infer_role_from_resources()` function that compares max_health, max_magicka, max_stamina and returns T/H/D
- [x] 2.2 Add healing-vs-damage check for magicka-primary players (healing of other players > damage dealt -> H, otherwise D)
- [x] 2.3 Add 10% tie-detection that falls back to existing `_infer_role_from_skill_lines()` when top resources are close
- [x] 2.4 Integrate role inference into `CombatEncounter` finalization so role is available when encounter ends

## 3. Fight History Buffer

- [x] 3.1 Create a `FightHistory` class with a capped list (~100 entries) storing completed encounter summaries
- [x] 3.2 Each entry stores: header data (timestamp, zone, duration, group DPS, deaths), per-player rows (role, name, class, DPS, dmg%, H/M/S), buff summary, first damage dealer
- [x] 3.3 Add cursor tracking (current index, is_live flag) with methods for scroll up/down/snap-to-latest

## 4. TUI Renderer

- [x] 4.1 Create `TuiDisplay` class wrapping curses initialization, cleanup, and screen management
- [x] 4.2 Implement `render_fight()` method that draws: header line, separator, player table, separator, buff line, status bar
- [x] 4.3 Implement compact player line formatting: role column, player name (truncated), class abbreviation, DPS (k-suffix), damage%, H/M/S compact resources
- [x] 4.4 Implement first-damage-dealer `*` prefix on the relevant player line
- [x] 4.5 Implement status bar showing fight position (e.g. "Fight 12/14") and key hints
- [x] 4.6 Handle terminal resize events (redraw on SIGWINCH / KEY_RESIZE)

## 5. Input Handling

- [x] 5.1 Implement non-blocking key reading in the curses event loop
- [x] 5.2 Map up-arrow and `k` to scroll previous, down-arrow and `j` to scroll next
- [x] 5.3 Map `G` and `End` to snap-to-latest (re-enable live mode)
- [x] 5.4 Map `q` to clean exit (restore terminal, shutdown)

## 6. Integration with LogFileMonitor

- [x] 6.1 Modify `LogFileMonitor` main loop to drive TUI updates instead of printing when TUI is active
- [x] 6.2 On encounter end: append to fight history, if in live mode call `render_fight()` with latest entry
- [x] 6.3 Interleave input polling with file change polling (curses `nodelay` or short `timeout`)
- [x] 6.4 Ensure `--save-reports` and `--tail-and-split` continue to work unchanged alongside TUI

## 7. Fallback and Compatibility

- [x] 7.1 Detect non-TTY stdout and skip TUI initialization, use print-based output
- [x] 7.2 Wrap curses init in try/except -- fall back to print mode if curses fails (e.g. unsupported terminal)
- [x] 7.3 Ensure `_print_and_buffer()` still buffers text for report file saving even when TUI is active

## 8. Testing

- [x] 8.1 Unit test role heuristic: tank (health-primary), DPS (stam-primary), DPS (mag-primary, more damage), healer (mag-primary, more healing)
- [x] 8.2 Unit test role heuristic: tied resources fall back to ability-based, missing healing data defaults to D
- [x] 8.3 Unit test fight history: append, scroll, snap-to-latest, cap at 100
- [ ] 8.4 Unit test compact formatting: k-suffix numbers, truncated names, column alignment
- [ ] 8.5 Manual test: run TUI against live Encounter.log, verify display, scrolling, and quit
