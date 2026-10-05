#!/usr/bin/env python3
"""
Generate data/buffs/food_drink.json: the ability ids of food and drink buffs,
so the build window can tell a player's food from their other long-lived
effects.

The ids come from the LibFoodDrinkBuff addon by Scootworks and Baertram
(https://www.esoui.com/downloads/info1902-LibFoodDrinkBuff.html), whose
Data.lua holds two tables:

    lib.DRINK_BUFF_ABILITIES = {
        [61322] = LFDB_BUFF_TYPE_REGEN_HEALTH, -- Health Recovery
    lib.FOOD_BUFF_ABILITIES = {
        [61255] = LFDB_BUFF_TYPE_MAX_HEALTH_STAMINA, -- Increase Max Health & Stamina

Each id becomes {"kind": "food" | "drink", "type": "MAX_HEALTH_STAMINA"}. The
type says which stats the buff raises; player_build uses it to pick the
consumable itself when its companion effects are in the tables too.

The addon is read from --source (its folder, or Data.lua itself), else from
the ESO AddOns folder when it is installed there, else downloaded from ESOUI:
    python scripts/generate_food_buffs.py
    python scripts/generate_food_buffs.py --source "D:\\downloads\\LibFoodDrinkBuff"

After a patch, check a recent log for food the table does not know. This
changes nothing; it lists the players who had no known food or drink buff but
did have an effect with a food-style icon (exit code 2 when there are any):
    python scripts/generate_food_buffs.py --check-log "<path to Encounter.log>"
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "buffs" / "food_drink.json"
ADDON = "LibFoodDrinkBuff"
DOWNLOAD_URL = f"https://cdn.esoui.com/downloads/file1902/{ADDON}.zip"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
MIN_BUFFS = 40  # version 19 has 92; fewer means the file was not understood
TABLE_RE = re.compile(r"lib\.(FOOD|DRINK)_BUFF_ABILITIES\s*=\s*\{")
ENTRY_RE = re.compile(r"\[\s*(\d+)\s*\]\s*=\s*LFDB_BUFF_TYPE_([A-Z0-9_]+)")
VERSION_RE = re.compile(r"^##\s*Version:\s*(\S+)", re.MULTILINE)
# Icon families food and drink buffs use; only a hint for --check-log, since
# some foods use one-off icons and other effects use these families too
FOOD_ICON_PREFIXES = ("crafting_", "store_", "event_", "plate_")
ABILITY_INFO_RE = re.compile(r'^\d+,ABILITY_INFO,(\d+),"((?:[^"]|"")*)","([^"]*)"')
PLAYER_EFFECTS_RE = re.compile(r"^\d+,PLAYER_INFO,\d+,\[([^\]]*)\]")


def addon_dirs():
    """Where the addon sits when it is installed for the game."""
    homes = [os.environ.get("USERPROFILE"), str(Path.home())]
    seen = []
    for home in homes:
        if not home:
            continue
        for documents in ("Documents", "OneDrive/Documents"):
            path = Path(home) / documents / "Elder Scrolls Online" / "live" / "AddOns" / ADDON
            if path not in seen:
                seen.append(path)
    return seen


def parse_data_lua(text: str) -> dict:
    """ability id -> {'kind', 'type'} from LibFoodDrinkBuff's Data.lua.

    A table runs from its opening line to the closing brace on a line of its
    own; Lua comments are ignored, so a commented-out entry is not read.
    """
    buffs, kind = {}, None
    for line in text.splitlines():
        code = line.split("--", 1)[0]
        opening = TABLE_RE.search(code)
        if opening:
            kind = opening.group(1).lower()
            continue
        if kind is None:
            continue
        if code.strip().startswith("}"):
            kind = None
            continue
        entry = ENTRY_RE.search(code)
        if entry:
            buffs[entry.group(1)] = {"kind": kind, "type": entry.group(2)}
    return buffs


def addon_version(manifest_text: str) -> str:
    match = VERSION_RE.search(manifest_text or "")
    return match.group(1) if match else "unknown"


def read_folder(folder: Path):
    """(Data.lua text, version) from an addon folder, or None."""
    data = folder / "Data.lua"
    if not data.is_file():
        return None
    manifests = [folder / f"{ADDON}.txt", folder / f"{ADDON}.addon"]
    manifest = next((m.read_text(encoding="utf-8", errors="replace")
                     for m in manifests if m.is_file()), "")
    return data.read_text(encoding="utf-8", errors="replace"), addon_version(manifest)


def download():
    """(Data.lua text, version) from the addon's ESOUI download."""
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    names = {name.replace("\\", "/"): name for name in archive.namelist()}

    def member(suffix):
        name = names.get(f"{ADDON}/{suffix}")
        return archive.read(name).decode("utf-8", errors="replace") if name else ""

    return member("Data.lua"), addon_version(member(f"{ADDON}.txt") or member(f"{ADDON}.addon"))


def load_source(explicit: str):
    """(Data.lua text, version, where it came from)."""
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace"), "unknown", str(path)
        found = read_folder(path)
        if found is None:
            sys.exit(f"no Data.lua in {path}")
        return found[0], found[1], str(path)
    for folder in addon_dirs():
        found = read_folder(folder)
        if found is not None:
            return found[0], found[1], str(folder)
    text, version = download()
    return text, version, DOWNLOAD_URL


def previous_ids(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("buffs", {}))
    except ValueError:
        return set()


def write(path: Path, buffs: dict, version: str) -> None:
    before = previous_ids(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kinds = Counter(entry["kind"] for entry in buffs.values())
    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": f"{ADDON} {version} Data.lua", "count": len(buffs),
               "food": kinds["food"], "drink": kinds["drink"],
               "buffs": dict(sorted(buffs.items(), key=lambda kv: int(kv[0])))}
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    added, removed = sorted(set(buffs) - before), sorted(before - set(buffs))
    print(f"{path.relative_to(REPO_ROOT)}: {kinds['food']} food and {kinds['drink']} drink ids "
          f"(+{len(added)} -{len(removed)} vs previous)")
    for label, items in (("added", added), ("removed", removed)):
        if items:
            print(f"  {label}: {', '.join(items[:12])}{' ...' if len(items) > 12 else ''}")


def unknown_food(log_path: Path, known_ids) -> tuple:
    """(PLAYER_INFO lines, lines without a known buff, Counter of the
    food-style effects on those lines as (id, name, icon))."""
    known_ids = set(known_ids)
    abilities, lines, without = {}, 0, 0
    suspects = Counter()
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if ",ABILITY_INFO," in line:
                match = ABILITY_INFO_RE.match(line)
                if match:
                    icon = match.group(3).replace("\\", "/").rsplit("/", 1)[-1].lower()
                    abilities[match.group(1)] = (match.group(2), icon.rsplit(".", 1)[0])
            elif ",PLAYER_INFO," in line:
                match = PLAYER_EFFECTS_RE.match(line)
                if not match:
                    continue
                lines += 1
                effects = [e.strip() for e in match.group(1).split(",") if e.strip()]
                if known_ids.intersection(effects):
                    continue
                without += 1
                for effect in effects:
                    name, icon = abilities.get(effect, ("", ""))
                    if icon.startswith(FOOD_ICON_PREFIXES):
                        suspects[(effect, name, icon)] += 1
    return lines, without, suspects


def check_log(log_path: Path) -> int:
    known = previous_ids(OUT_PATH)
    if not known:
        sys.exit(f"{OUT_PATH} is missing or empty; generate it first")
    lines, without, suspects = unknown_food(log_path, known)
    print(f"{log_path}: {lines} PLAYER_INFO lines, {without} without a known food or drink buff")
    if not suspects:
        print("  none of those has an effect with a food-style icon")
        return 0
    print("  effects with a food-style icon on those lines (id, name, icon, lines):")
    for (effect, name, icon), count in suspects.most_common():
        print(f"    {effect}  {name}  {icon}  x{count}")
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="",
                    help="LibFoodDrinkBuff folder or its Data.lua (default: the installed "
                         "addon, else the ESOUI download)")
    ap.add_argument("--check-log", default="",
                    help="only check an Encounter.log against the bundled table")
    args = ap.parse_args()
    if args.check_log:
        return check_log(Path(args.check_log))

    text, version, origin = load_source(args.source)
    buffs = parse_data_lua(text)
    if len(buffs) < MIN_BUFFS:
        sys.exit(f"only {len(buffs)} food and drink ids found in {origin}; not overwriting")
    print(f"source: {origin} (version {version})")
    write(OUT_PATH, buffs, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
