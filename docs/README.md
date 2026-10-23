# Documentation

The [README](../README.md) covers installing the app and turning on logging. This folder holds everything else.

| Document | For |
|---|---|
| [user-guide.md](user-guide.md) | Using the app: every screen and setting, tracked effects, what the numbers are based on, and what to do when something looks wrong. |
| [design.md](design.md) | How the hard problems are solved, collected from the code's docstrings by `scripts/build_design_doc.py`. Do not edit it by hand. |
| [development.md](development.md) | Working on the code: repository layout, running from source, tests, building the installer, refreshing game data after a patch, releasing. |
| [reference/encounterlog-format.md](reference/encounterlog-format.md) | The encounter log's line types and fields. |
| [reference/gear-slots.md](reference/gear-slots.md) | The gear part of a `PLAYER_INFO` line: slot names, item fields, and what the log leaves out. |
| [research/esohub-icons-and-tooltips.md](research/esohub-icons-and-tooltips.md) | Research notes (October 2026) on ESO-Hub's tooltip API and page links, and on extracting ability icons from the game files. |
| [archive/](archive/README.md) | Documents from the terminal version, kept for their history. |

`screencaps/` holds the screenshots the README and the user guide show; `scripts/capture_screenshots.py` regenerates them.
