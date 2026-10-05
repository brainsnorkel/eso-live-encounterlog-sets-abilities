## Context

The current real-time display in `esolog_tail.py` uses `print()` with colorama for ANSI colors. Each encounter summary is printed sequentially — once it scrolls past the terminal viewport, the only way to review it is scrolling the terminal buffer. The display shows full ability lists, gear, buff uptimes, and per-player stats in a multi-line format that can be 20+ lines per player.

The tool runs on Windows (primary), Linux, and macOS. It's distributed as a PyInstaller binary (`esolog-tail.exe`) via a bat file that passes `--read-all-then-tail --tail-and-split --save-reports`.

Player data available per encounter: name, handle, class, max health/magicka/stamina, champion points, damage dealt, DPS, damage%, deaths, equipped abilities, front/back bar, gear, buff uptimes. Role inference currently exists in `eso_sets.py` based on ability names, but no resource-based heuristic.

## Goals / Non-Goals

**Goals:**
- Full-screen TUI that shows the last completed fight in a compact format
- Scrollable fight history (up/down or j/k) with auto-snap to latest fight
- Per-player role indicator (T/H/D) based on resource and healing heuristics
- Compact one-line-per-player display with essential stats
- Continue working alongside `--tail-and-split` and `--save-reports` (those write to disk independently)

**Non-Goals:**
- Real-time mid-fight DPS meter (display updates only on fight completion)
- Interactive drill-down into per-player details (future enhancement)
- Replacing the report file format — reports continue as text files
- Mobile or web display

## Decisions

**1. curses (stdlib + windows-curses) over textual**

Use Python's `curses` module with the `windows-curses` pip package for Windows support.

*Why not textual?* Textual is a large dependency (~5MB) with an async runtime that would require restructuring the main polling loop. `curses` is stdlib on Linux/macOS and only needs a small pip package on Windows. It fits the existing synchronous architecture — the `LogFileMonitor.check_for_changes()` poll loop can drive screen refreshes directly. The display is simple enough (table of players, header line) that curses is sufficient.

*Why not blessed/blessings?* Adds a dependency for convenience wrappers we don't need. Raw curses is fine for this scope.

**2. Fight history as a ring buffer**

Store completed encounters in a list (capped at ~100 most recent). A cursor index tracks which fight is displayed. When cursor is at the end (latest fight), auto-advance on new fight completion. When cursor is moved backward, freeze display until the user presses a "return to live" key (e.g., `G` or `End`).

**3. Resource-based role heuristic**

Role inference order:
1. Compare `max_health`, `max_magicka`, `max_stamina` from `PlayerInfo`
2. If highest resource is health → **T** (tank)
3. If highest resource is magicka → check healing vs damage ratio:
   - If healing-of-others > damage-dealt → **H** (healer)
   - Otherwise → **D** (DPS)
4. If highest resource is stamina → **D** (DPS)

This supplements (not replaces) the existing ability-based inference in `eso_sets.py`. The resource heuristic is the primary signal; ability-based detection is a tiebreaker when resources are close (within 10%).

**4. Compact display layout**

```
[260112 19:27] Maw of Lorkhaj (vet) | 12m 34s | GrpDPS: 245.3k | Deaths: 2
─────────────────────────────────────────────────────────────────────────────
 R  Player              Class      DPS      Dmg%   H/M/S
 T  @tankplayer         DK         12.3k    5.0%   45k/20k/22k
*D  @firstdamage        Sorc       62.1k   25.3%   22k/18k/48k
 D  @otherdps           NB         58.4k   23.8%   20k/16k/50k
 H  @healername         Templar    8.2k     3.3%   21k/42k/18k
─────────────────────────────────────────────────────────────────────────────
 Buffs: MCourage:92% MForce:88% Mslayer:76%
 [Fight 12/14] ↑↓/jk:scroll  G:latest  q:quit
```

One line per player, sorted by damage descending. First damage dealer marked with `*`. Role column uses T/H/D. Resources shown as compact `H/M/S` values with k-suffix.

**5. TUI activation**

The TUI activates automatically when the terminal is interactive (isatty). When stdout is not a TTY (piped or redirected), fall back to the existing print-based output for compatibility. A `--no-tui` flag provides an explicit opt-out.

## Risks / Trade-offs

**[Risk] curses on Windows has rendering quirks** → `windows-curses` is well-maintained and widely used. Test on Windows Terminal, CMD, and PowerShell. Fall back to print mode if curses init fails.

**[Risk] Role heuristic may misclassify hybrid builds** → Resource-based detection is a best guess, not authoritative. The ability-based fallback in `eso_sets.py` provides a second signal. Misclassification is cosmetic — it doesn't affect data.

**[Risk] PyInstaller bundling with curses** → `windows-curses` works with PyInstaller. Add it to the spec's hidden imports if needed.

**[Risk] Healing data may not be available for all encounters** → If healing data is missing, fall back to resource-only heuristic (magicka-primary without healing check → D).

## Open Questions

- Should the TUI show buff uptimes in the compact view, or only in an expanded detail view?
- Should there be a key to toggle between compact and full (current) display format?
