#!/usr/bin/env python3
"""
Write data/version.json: the game version the bundled data was built
against, the date, and each bundled table's own date (issue #173).

The app compares the version with the one every logging session's BEGIN_LOG
line names, and shows a status line when the log is newer
(src/data_staleness.py); the About dialog lists the dates. Run it as the
last step of a data refresh, once the tables are committed or ready to be:

    python scripts/stamp_data_version.py --game-version eso.live.12.1
    python scripts/stamp_data_version.py --log "<a log written by the game now>"
    python scripts/stamp_data_version.py            (the newest split log)

Without --game-version the version is read from a log's BEGIN_LOG line:
--log names the file (its last session counts), and with neither the newest
split log in the app's split folder (the setting, or --dir) is read. The
date of each table is its own "generated" stamp; the LibSets workbook,
which has none, gives the date it was last saved. --check exits 1 when a
table's date no longer matches data/version.json, so a refreshed table
whose stamp was forgotten is caught (the unit tests run it).
"""

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = ROOT / "data" / "version.json"
# (name shown in About, file under the repository) for every table that
# carries a "generated" stamp; the LibSets workbook is dated by its own save
TABLES = (
    ("Set names (game client)", "data/client/set_names_en.json"),
    ("Set types (LibSets)", "data/gear_sets/LibSets_SetData.xlsm"),
    ("Set bonus texts (UESP)", "data/sets/bonuses_en.json"),
    ("Set penetration and critical damage (UESP)", "data/sets/offense.json"),
    ("Set buffs (split logs)", "data/sets/set_buffs.json"),
    ("Ability icons (game client)", "data/icons/abilities/manifest.json"),
    ("Class passives and masteries (UESP)", "data/skills/class_passives.json"),
    ("Weapon skill lines (UESP)", "data/skills/weapon_skill_lines.json"),
    ("Skill target kinds (UESP)", "data/skills/ability_targets.json"),
    ("Armor weights (UESP)", "data/items/armor_weights.json"),
    ("Weapon types (UESP)", "data/items/weapon_types.json"),
    ("Poison names (UESP)", "data/items/poisons_en.json"),
    ("Food and drink (LibFoodDrinkBuff)", "data/buffs/food_drink.json"),
    ("ESO-Hub set links", "data/esohub/sets_en.json"),
    ("ESO-Hub skill links", "data/esohub/skills_en.json"),
    ("ESO-Hub scribing links", "data/esohub/scribing_en.json"),
)
_GAME_VERSION = re.compile(r"^eso\.[a-z]+\.\d+\.\d+", re.IGNORECASE)


def table_date(path: Path) -> str:
    """The table's own date, YYYY-MM-DD: its "generated" stamp, or for the
    LibSets workbook the date it was last saved; '' when there is none."""
    try:
        if path.suffix.lower() == ".xlsm":
            with zipfile.ZipFile(path) as workbook:
                core = workbook.read("docProps/core.xml").decode("utf-8")
            match = re.search(r"<dcterms:modified[^>]*>([^<]+)<", core)
            return match.group(1)[:10] if match else ""
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return ""
    return str(data.get("generated") or "")[:10] if isinstance(data, dict) else ""


def tables(root: Path = ROOT) -> list:
    """[{'name', 'file', 'generated'}] for every bundled table that exists."""
    return [{"name": name, "file": file, "generated": table_date(root / file)}
            for name, file in TABLES if (root / file).exists()]


def begin_log_version(log: Path) -> str:
    """The game version on the last BEGIN_LOG line of *log* ('' when none).
    The line is found by the engine's backward search (1 MB at a time from
    the end), so the live Encounter.log of several GB is not read through."""
    from esolog_tail import find_session_start_offset
    size = log.stat().st_size
    offset = find_session_start_offset(log, size, size)
    if offset is None:
        return ""
    with open(log, "rb") as handle:
        handle.seek(offset)
        line = handle.readline()
    fields = line.decode("utf-8", "replace").strip().replace('"', "").split(",")
    return fields[6].strip() if len(fields) >= 7 and fields[1] == "BEGIN_LOG" else ""


def newest_split(folder: Path) -> Path | None:
    logs = sorted(folder.glob("*.log"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def stamp(game_version: str, root: Path = ROOT, today: str | None = None) -> dict:
    """The stamp; *today* is the maintainer's local date unless given."""
    return {
        "game_version": game_version,
        "built": today or datetime.now().astimezone().strftime("%Y-%m-%d"),
        "tables": tables(root),
    }


def check(root: Path = ROOT) -> list:
    """The tables whose date differs from data/version.json's, as text;
    [] when the stamp is current."""
    try:
        current = json.loads((root / "data" / "version.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["data/version.json is missing or unreadable"]
    stamped = {t.get("file"): t.get("generated") for t in current.get("tables") or ()}
    problems = []
    for table in tables(root):
        if table["file"] not in stamped:
            problems.append(f"{table['file']} is not in data/version.json")
        elif stamped[table["file"]] != table["generated"]:
            problems.append(f"{table['file']} is dated {table['generated']}, "
                            f"data/version.json says {stamped[table['file']]}")
    if not _GAME_VERSION.match(str(current.get("game_version") or "")):
        problems.append(f"game_version {current.get('game_version')!r} is no game version")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--game-version", default="", help="e.g. eso.live.12.1")
    parser.add_argument("--log", type=Path, help="read the version from this log's BEGIN_LOG")
    parser.add_argument("--dir", type=Path, help="the split folder (default: the app's setting)")
    parser.add_argument("--check", action="store_true",
                        help="only check data/version.json against the tables")
    args = parser.parse_args(argv)
    if args.check:
        problems = check()
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    version = args.game_version.strip()
    if not version:
        log = args.log
        if log is None:
            from dedupe_splits import config_split_dir
            folder = args.dir or config_split_dir()
            log = newest_split(folder) if folder and folder.is_dir() else None
        if log is None or not log.is_file():
            print("No log to read the game version from: pass --game-version or --log",
                  file=sys.stderr)
            return 1
        version = begin_log_version(log)
        print(f"{log.name}: {version or 'no BEGIN_LOG line'}")
    if not _GAME_VERSION.match(version):
        print(f"Not a game version: {version!r} (expected e.g. eso.live.12.1)", file=sys.stderr)
        return 1
    data = stamp(version)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: game {version}, built {data['built']}, "
          f"{len(data['tables'])} tables")
    for table in data["tables"]:
        print(f"  {table['generated'] or '(no date)':10}  {table['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
