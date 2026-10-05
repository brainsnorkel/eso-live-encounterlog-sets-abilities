# Archive

Documents kept for their history. None of them describes the app as it is now: they date from the terminal version (up to 0.2.7), which the desktop app replaced in 0.3.0. For the current app see the [README](../../README.md) and the [development guide](../development.md).

| Document | What it was | Written |
|---|---|---|
| [original-brief.md](original-brief.md) | The request the project started from: a command-line tool that tails the encounter log and prints each fight's group. | Sep 2025 |
| [gear-set-database-optimization.md](gear-set-database-optimization.md) | Why gear set data moved from an Excel file read at startup to a generated Python module. The module and its generator are still in use (`src/gear_set_data.py`, `scripts/generate_gear_data.py`); the file names and sizes in the document are out of date. | Sep 2025 |
| [auto-split-logs-feature.md](auto-split-logs-feature.md) | Specification of the `--tail-and-split` command-line option. Split files live on as a setting (Settings → Per-encounter split files), with a different file name pattern. | Sep 2025 |
| [testing-guide-terminal-version.md](testing-guide-terminal-version.md) | Testing guide for the terminal version. It names test files, a test runner, a sample log and command-line flags that no longer exist. | Sep 2025 |

`screencaps/` holds the screenshots that went with them: the terminal output, the split files it wrote, the full-screen terminal UI added in 0.2.6, and the main window as of 0.4.1.

Completed change proposals are archived separately, under [`openspec/changes/archive/`](../../openspec/changes/archive/).
