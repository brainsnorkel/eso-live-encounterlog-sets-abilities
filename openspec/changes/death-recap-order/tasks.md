# Tasks

## 1. The window

- [x] 1.1 In `src/gui/death_render.py`, draw each death as its heading, the "Killed by" line, the event table, then its kinds summary; draw the whole-fight block after the last death; verify `tests/unit/test_death_recap_gui.py` asserts the table precedes the summary within a death and the fight block follows the last death
- [x] 1.2 Write damage over time as `DoT` (`SIDE_LABELS` in `src/damage_kinds.py`, the ability kind words) and healing over time as `HoT` (the heal share, the star hover headings); verify the GUI tests for the labels and the hover headings
- [x] 1.3 Update the user guide's "Death recaps" section, the README's recap line and the changelog; retake `docs/screencaps/death-recap.png` with `scripts/capture_screenshots.py --hide-names` from the Dreadsail split the guide uses
- [x] 1.4 Check the dependencies for prudent upgrades (the maintainer's rule for every plan) and record the result here: checked 2026-10-27 against PyPI, PySide6-Essentials 6.12.0, platformdirs 4.13.6, Send2Trash 2.1.0, PyInstaller 6.22.3, Pillow 13.0.0, setuptools 84.2.1 and pip 26.2.2 are the newest and the floors in `requirements.txt` and `requirements-build.txt` admit them; the local interpreters are CPython 3.13.17 and 3.14.10; nothing to upgrade
