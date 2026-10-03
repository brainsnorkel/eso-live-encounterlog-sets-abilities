---
name: refresh-ability-icons
description: Re-extract ESO ability icons from the installed game files and convert them to PNG for the app's ability bars. Use after an ESO patch, when a new skill shows as text instead of an icon, or when asked to refresh/update/regenerate the ability icons.
license: MIT
compatibility: Windows only. Needs an installed ESO client, UESP's EsoExtractData v0.53+, and Pillow (requirements-build.txt).
metadata:
  author: eso-log-tail
  version: "1.0"
---

Refresh the bundled ability icons from the live game data.

The encounter log names each slotted ability's icon (`ABILITY_INFO ... "/esoui/art/icons/ability_arcanist_002_b.dds"`), and the app resolves that basename to `data/icons/abilities/<basename>.png`. The PNGs come from the game's `depot\eso.mnf` via `scripts/extract_ability_icons.py`; nothing is downloaded from any website.

**Prerequisites** (check before running)

1. ESO is installed and patched to the current live version (Steam/Zenimax launcher has finished updating). The script reads `depot\eso.mnf`; it never writes to the game folder.
2. `EsoExtractData.exe` (UESP, v0.53+) is available: default `D:\extract-eso\EsoExtractData.exe`, or set `ESO_EXTRACT_DATA`, or pass `--extractor`. Download: https://en.uesp.net/wiki/ESO_Mod:EsoExtractData
3. Pillow is installed: `pip install -r requirements-build.txt`.
4. Quote every path that contains a space (the user's home folder does).

**Steps**

1. Preview what will be extracted (no extraction, ~5 s):

   ```cmd
   python scripts\extract_ability_icons.py --dry-run
   ```

   Expect roughly 1,800 `ability_*.dds` icons grouped into a few dozen `-s/-e` ranges. If the count is zero or the eso.mnf path is wrong, fix `--eso-dir` / `ESO_INSTALL_DIR` before continuing.

2. Extract and convert (2-3 minutes; icons land in `data/icons/abilities/`, 40 px by default):

   ```cmd
   python scripts\extract_ability_icons.py --check-log "%USERPROFILE%\OneDrive\Documents\Elder Scrolls Online\live\Logs\Encounter.log"
   ```

   `--check-log` is optional: it scans a log and reports any icon slotted on a player bar that has no PNG (exit code 2). Use `--size 64` for native resolution if the UI needs it (about 2x the repo weight).

3. Read the summary the script prints:
   - `manifest: N icons; vs previous: +added -removed ~changed` — added icons are the new skills from the patch; removed ones are abilities the game dropped. A large "removed" count usually means the wrong `eso.mnf` was read.
   - `converted N icons ... FAILED` — a failed conversion means Pillow could not decode a DDS; report the filename rather than retrying.
   - `check-log: ... 0 without a PNG` — bars in that log are fully covered.

4. Spot-check one added icon visually (open the PNG) and make sure `data/icons/abilities/manifest.json` records the new eso.mnf modification date.

5. Commit `data/icons/abilities/` (PNGs + manifest.json) together with a CHANGELOG entry naming the ESO update, and the PyInstaller spec must keep bundling `data/icons/abilities` (see `datas` in `esolog-tail.spec`).

**Notes**

- Scribed (Grimoire) skills log a normal icon (`ability_grimoire_<weapon>.dds`) but append three extra quoted fields after the two flags (focus/signature/affix script names, e.g. `...,F,T,"Magic Damage","Assassin's Misery","Berserk"`). Parsers must read the icon from field 4, never from the end of the line.
- `EsoExtractData -n <name>` only matches exact filenames and reloads the MNF per run (~3 s), which is why the script extracts index ranges instead. Its `-c` (convert DDS) option does not exist in the v0.53 command-line build; Pillow does the conversion.
- Everything else under `esoui/art/icons` (gear, achievements, ~34,600 files) is deliberately not extracted; pass `--prefix` to pull a different family.
