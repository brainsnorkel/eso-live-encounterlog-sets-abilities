#!/usr/bin/env python3
"""
Compare every name the app bundles by game id with the installed client's own
English text, and keep the committed snapshot of the client's set names.

Design (issue #79): the client's language file, gamedata\\lang\\en.lang in
depot\\eso.mnf, holds the game's name for every set, ability and item, keyed
by id, and it is right on patch day. It holds no structure: not which items
are poisons, not a set's type or bonuses, not an ability's skill line. So the
external sources (the LibSets workbook, UESP, LibFoodDrinkBuff) stay for
structure, and this script checks their names against the client:

  table      Index      what is checked against it
  38727365   set id     src/gear_set_data.py, the set ids named in
                        src/build_issues.py, data/sets/offense.json, and the
                        names data/esohub/sets_en.json is keyed by
  198758357  ability    data/skills/class_passives.json (a mastery's effect
                        by the buff it grants, which is the effect's own
                        name), data/skills/weapon_skill_lines.json, and the
                        skill id lists in src/build_issues.py against their
                        name lists
  242841733  item id    data/items/poisons_en.json (the client writes a tiered
                        poison without its numeral, as the table does)

Item names carry grammar markers ("battle axe^n"); they are cut at the caret
before comparing. The code lists are read with ast, so nothing in src/ is
imported. Food and drink buffs are not checked: data/buffs/food_drink.json
holds ids and kinds only, no names.

Two kinds of finding. A name that differs from the client's, or a name the
client does not have at all, is a difference and makes the run exit 1. An id
the client has no name for is counted, not failed: UESP's tables keep the
rank II to IV ids that skills had before Update 34, which the client no
longer names (432 in weapon_skill_lines.json and 39 in build_issues.py's
skill lists on Update 51), and the LibSets workbook keeps template and
"(OLD)" rows (11). They are harmless in a lookup table, and failing on them
would make the check fail for good. The set lists are stricter: a set id in
build_issues.py or offense.json that the client does not name is a
difference, since every set there was chosen by hand.

Set names are also written to data/client/set_names_en.json with --write-sets.
scripts/generate_gear_data.py takes its set names from that snapshot (CI has
no game client, so the client's names have to be committed) and only the set
type from the LibSets workbook. Refresh it after every ESO update:

    python scripts/check_client_names.py --write-sets

The run extracts en.lang into a temporary folder with UESP's EsoExtractData
(about 20 s, read-only on the game folder; see scripts/extract_ability_icons.py
for how the extractor and the client are found), or reads an extracted
en.lang.csv given with --lang-csv. Then rerun scripts/generate_gear_data.py,
which reports the sets the snapshot added.
"""

import argparse
import ast
import csv
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_ability_icons as icons  # finds the client and the extractor

REPO_ROOT = Path(__file__).resolve().parent.parent
SET_TABLE, ABILITY_TABLE, ITEM_TABLE = "38727365", "198758357", "242841733"
SNAPSHOT = REPO_ROOT / "data" / "client" / "set_names_en.json"
MIN_SETS = 600  # Update 51 has 717; fewer means the wrong file or table
GRAMMAR_MARKER = re.compile(r"\^.*$")


def client_text(text: str) -> str:
    """A client string without its grammar marker ("battle axe^n")."""
    return GRAMMAR_MARKER.sub("", text).strip()


def read_tables(csv_path: Path, tables) -> dict:
    """table id -> {index: text} for the wanted tables of an en.lang.csv
    (columns ID, Unknown, Index, Offset, Text, as EsoExtractData writes it)."""
    csv.field_size_limit(1 << 30)
    found = {table: {} for table in tables}
    with open(csv_path, encoding="utf-8", newline="") as handle:
        rows = csv.reader(handle)
        next(rows, None)
        for row in rows:
            if len(row) >= 5 and row[0] in found:
                found[row[0]][row[2]] = client_text(row[4])
    return found


def extract_lang_csv(eso_dir: str, extractor: str, temp: Path) -> Path:
    """Extract en.lang from the installed client into *temp*; the extractor
    writes en.lang.csv beside it."""
    mnf = icons.find_eso_dir(eso_dir) / "depot" / "eso.mnf"
    exe = icons.find_extractor(extractor)
    icons.run_extractor(exe, [str(mnf), str(temp) + "\\", "-n", "en.lang"], cwd=temp)
    csv_path = temp / "gamedata" / "lang" / "en.lang.csv"
    if not csv_path.is_file():
        sys.exit(f"{csv_path} was not written; see {temp / 'exportmnf.log'}")
    return csv_path


def literal(source: Path, name: str):
    """The value of a module-level assignment *name* in *source*, read with
    ast: a literal, frozenset({...}), or a dict whose values are calls (the
    first argument of each call is taken, as for PROC_SETS' ProcSet)."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "frozenset":
            value = value.args[0]
        if isinstance(value, ast.Dict):
            return {ast.literal_eval(k): (ast.literal_eval(v.args[0]) if isinstance(v, ast.Call)
                                          else ast.literal_eval(v))
                    for k, v in zip(value.keys, value.values)}
        return ast.literal_eval(value)
    raise KeyError(f"{name} not found in {source}")


def by_id(label: str, ours: dict, client: dict, strict: bool = False):
    """(differences, ids the client does not name) between our {id: name}
    and the client's. *strict*: an id the client does not name is a
    difference too (a hand-kept list should hold no retired id)."""
    renamed, unnamed = [], []
    for key in sorted(ours, key=int):
        theirs = client.get(str(key))
        if theirs is None and strict:
            renamed.append(f"{label}: {key} {ours[key]!r} is not in the client")
        elif theirs is None:
            unnamed.append(f"{label}: {key}")
        elif theirs != ours[key]:
            renamed.append(f"{label}: {key} is {ours[key]!r} here, {theirs!r} in the client")
    return renamed, unnamed


def names_known(label: str, names, client_names):
    """(names of ours the client has under no id, nothing)."""
    return [f"{label}: {name!r} is not a name in the client"
            for name in sorted(set(names) - set(client_names))], []


def ids_named(label: str, ids, allowed, client: dict):
    """(ids of a skill list whose client name is not one of the list's
    names, ids the client does not name)."""
    renamed = [f"{label}: {key} is {client[key]!r} in the client, not one of the listed names"
               for key in sorted(ids, key=int) if key in client and client[key] not in allowed]
    unnamed = [f"{label}: {key}" for key in sorted(ids, key=int) if key not in client]
    return renamed, unnamed


def merged(*results):
    """One (differences, unnamed) pair from several."""
    return ([line for found, _ in results for line in found],
            [line for _, unnamed in results for line in unnamed])


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_sets() -> dict:
    """The committed snapshot's {set id: name}, empty when there is none."""
    return load_json(SNAPSHOT)["sets"] if SNAPSHOT.is_file() else {}


def differences(tables: dict) -> dict:
    """Section -> (difference lines, unnamed id lines), for every check."""
    sets, abilities, items = tables[SET_TABLE], tables[ABILITY_TABLE], tables[ITEM_TABLE]
    issues = REPO_ROOT / "src" / "build_issues.py"
    offense = load_json(REPO_ROOT / "data" / "sets" / "offense.json")["sets"]
    passives = load_json(REPO_ROOT / "data" / "skills" / "class_passives.json")
    weapon = load_json(REPO_ROOT / "data" / "skills" / "weapon_skill_lines.json")["skills"]
    poisons = load_json(REPO_ROOT / "data" / "items" / "poisons_en.json")["poisons"]
    out = {}
    out["sets"] = merged(
        by_id("gear_set_data", literal(REPO_ROOT / "src" / "gear_set_data.py", "SET_ID_TO_NAME"), sets),
        by_id("GROUP_SETS", literal(issues, "GROUP_SETS"), sets, strict=True),
        by_id("SLAYER_SETS", literal(issues, "SLAYER_SETS"), sets, strict=True),
        by_id("PROC_SETS", literal(issues, "PROC_SETS"), sets, strict=True),
        by_id("offense.json", {k: v["name"] for k, v in offense.items()}, sets, strict=True),
        names_known("esohub sets_en.json",
                    load_json(REPO_ROOT / "data" / "esohub" / "sets_en.json")["sets"], sets.values()))
    out["abilities"] = merged(
        by_id("class_passives", {k: v["name"] for k, v in passives["passives"].items()}, abilities),
        by_id("class mastery effects", {k: v.get("effect", v["name"])
                                        for k, v in passives["mastery_effects"].items()}, abilities),
        by_id("weapon_skill_lines", {k: v["name"] for k, v in weapon.items()}, abilities),
        ids_named("ELEMENTAL_DRAIN_IDS", literal(issues, "ELEMENTAL_DRAIN_IDS"),
                  {"Elemental Drain"}, abilities),
        ids_named("TAUNT_SKILL_IDS", literal(issues, "TAUNT_SKILL_IDS"),
                  literal(issues, "TAUNT_SKILL_NAMES"), abilities),
        ids_named("CLENCH_SKILL_IDS", literal(issues, "CLENCH_SKILL_IDS"),
                  literal(issues, "CLENCH_SKILL_NAMES"), abilities),
        ids_named("PULL_SKILL_IDS", literal(issues, "PULL_SKILL_IDS"),
                  literal(issues, "PULL_SKILL_NAMES"), abilities))
    out["items"] = by_id("poisons_en.json", {k: v["name"] for k, v in poisons.items()}, items)
    snapshot = snapshot_sets()
    out["snapshot"] = (([f"{SNAPSHOT.relative_to(REPO_ROOT)} is missing"] if not snapshot else
                        [f"set {k}: snapshot {snapshot.get(k)!r}, client {sets.get(k)!r}"
                         for k in sorted(set(snapshot) | set(sets), key=int)
                         if snapshot.get(k) != sets.get(k)]), [])
    return out


def report(found: dict) -> int:
    """Print the findings; 1 when there is a difference, else 0."""
    for section, (lines, unnamed) in found.items():
        print(f"\n{section}: {len(lines)} difference(s)")
        for line in lines:
            print(f"  {line}")
        sources = {}
        for line in unnamed:
            source, key = line.rsplit(": ", 1)
            sources.setdefault(source, []).append(key)
        for source, keys in sources.items():
            shown = ", ".join(keys[:8]) + (" ..." if len(keys) > 8 else "")
            print(f"  ({source}: {len(keys)} id(s) the client does not name: {shown})")
    return 1 if any(lines for lines, _ in found.values()) else 0


def write_snapshot(sets: dict, source: str) -> None:
    before = snapshot_sets()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": source, "count": len(sets),
               "sets": dict(sorted(sets.items(), key=lambda kv: int(kv[0])))}
    SNAPSHOT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    added = sorted(set(sets) - set(before), key=int)
    renamed = sorted((k for k in set(sets) & set(before) if sets[k] != before[k]), key=int)
    print(f"wrote {SNAPSHOT.relative_to(REPO_ROOT)}: {len(sets)} sets, "
          f"{len(added)} new, {len(renamed)} renamed since the last snapshot")
    for key in added:
        print(f"  new {key}: {sets[key]}")
    for key in renamed:
        print(f"  renamed {key}: {before[key]} -> {sets[key]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lang-csv", default="", help="an extracted en.lang.csv (skips extraction)")
    ap.add_argument("--eso-dir", default="", help="the ESO install folder")
    ap.add_argument("--extractor", default="", help="path to EsoExtractData.exe")
    ap.add_argument("--write-sets", action="store_true",
                    help=f"rewrite {SNAPSHOT.relative_to(REPO_ROOT)} from the client")
    args = ap.parse_args()

    wanted = (SET_TABLE, ABILITY_TABLE, ITEM_TABLE)
    with tempfile.TemporaryDirectory(prefix="esolang-") as temp:
        csv_path = Path(args.lang_csv) if args.lang_csv else extract_lang_csv(
            args.eso_dir, args.extractor, Path(temp))
        tables = read_tables(csv_path, wanted)
    if len(tables[SET_TABLE]) < MIN_SETS:
        sys.exit(f"only {len(tables[SET_TABLE])} set names in table {SET_TABLE}; "
                 f"is {csv_path} en.lang.csv?")
    print(f"client: {len(tables[SET_TABLE])} sets, {len(tables[ABILITY_TABLE])} abilities, "
          f"{len(tables[ITEM_TABLE])} items")

    if args.write_sets:
        write_snapshot(tables[SET_TABLE],
                       f"en.lang table {SET_TABLE} (gamedata\\lang\\en.lang in depot\\eso.mnf)")
    return report(differences(tables))


if __name__ == "__main__":
    sys.exit(main())
