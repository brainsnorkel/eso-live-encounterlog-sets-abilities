#!/usr/bin/env python3
"""
Generate data/skills/class_passives.json: every class skill line passive and
Class Mastery passive by game ability id, with its class, skill line, name
and rank, for the skill lines shown beside a player's class.

The encounter log lists a player's passives by id on their PLAYER_INFO line
and never says which skill line a passive belongs to. UESP's player skill
table does: one request (about 4,400 rows, 2 MB) lists every player skill
with its class, skill line, whether it is a passive and its rank. The class
passives are kept here: 7 classes x (3 lines x 4 passives x 2 ranks + 5
masteries) = 203 ids on the Update 51 client. Both rank ids are needed (a
character with rank 1 of Hemorrhage lists 36641, with rank 2 lists 45060).

Matching by id matters: five effects share a passive's name and reach the
same list (the Combustion resource return a Dragonknight gives the group,
the Reusable Parts ally effect, the Resolute Defense and Steadfast
Candescence procs), and a passive's icon does not tell it from an active
(Blessing at the Peak and Landslide use ability_* icons).

Run after an ESO update that adds a class or a skill line (one request to
UESP, which asks heavy users to go lightly: do not loop it):
    python scripts/generate_class_passives.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_class_passives.py --from build/esobuild-assets/sources/player_skills.json
"""

import argparse
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "skills" / "class_passives.json"
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=playerSkills"
              "&fields=id,name,classType,skillLine,baseAbilityId,rank,isPassive,skillType")
ATTRIBUTION = "Skill data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
SKILL_TYPE_CLASS = "1"  # UESP's skillType for class skill lines
MASTERY_LINE = "Class Mastery"
# A class has three lines of four passives in two ranks, plus five masteries
PASSIVES_PER_CLASS = 3 * 4 * 2 + 5
CLASSES = ("Dragonknight", "Sorcerer", "Nightblade", "Warden", "Necromancer",
           "Templar", "Arcanist")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def class_passives(payload: dict) -> dict:
    """{ability id: {'class', 'line', 'name', 'rank'}} for every class-line
    passive in UESP's player skill rows, masteries under the line
    'Class Mastery'. Rows that are not class passives, or lack an id, a class
    or a line, are skipped."""
    rows = payload.get("playerSkills") if isinstance(payload, dict) else None
    found = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("isPassive", "")).strip() != "1":
            continue
        if str(row.get("skillType", "")).strip() != SKILL_TYPE_CLASS:
            continue
        ability_id = str(row.get("id", "")).strip()
        class_name = str(row.get("classType") or "").strip()
        line = str(row.get("skillLine") or "").strip()
        if not (ability_id.isdigit() and class_name and line):
            continue
        rank = str(row.get("rank", "")).strip()
        found[ability_id] = {
            "class": class_name,
            "line": line,
            "name": str(row.get("name") or "").strip(),
            "rank": int(rank) if rank.isdigit() else 1,
        }
    return dict(sorted(found.items(), key=lambda item: int(item[0])))


def per_class(passives: dict) -> Counter:
    return Counter(entry["class"] for entry in passives.values())


def render(passives: dict, generated: str) -> str:
    """The file's JSON, one passive per line so a refresh diffs by id."""
    entries = ",\n".join(f"  {json.dumps(ability_id)}: {json.dumps(entry)}"
                         for ability_id, entry in passives.items())
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps(EXPORT_URL)},\n'
            f' "attribution": {json.dumps(ATTRIBUTION)},\n'
            f' "count": {len(passives)},\n'
            ' "passives": {\n'
            f"{entries}\n"
            " }\n"
            "}\n")


def previous_ids(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    return set((data.get("passives") or {}).keys()) if isinstance(data, dict) else set()


def write(path: Path, passives: dict) -> None:
    before = previous_ids(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(passives, generated), encoding="utf-8")
    now = set(passives)
    print(f"{path.relative_to(REPO_ROOT)}: {len(passives)} class passives "
          f"(+{len(now - before)} -{len(before - now)} vs previous)")
    counts = per_class(passives)
    for class_name in CLASSES:
        masteries = sum(1 for entry in passives.values()
                        if entry["class"] == class_name and entry["line"] == MASTERY_LINE)
        print(f"  {class_name}: {counts.get(class_name, 0)} ({masteries} masteries)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--from", dest="source", type=Path,
                        help="a saved UESP playerSkills reply to read instead of fetching")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.source.read_text(encoding="utf-8") if args.source
                             else fetch(EXPORT_URL))
    except ValueError:
        sys.exit(f"{args.source or EXPORT_URL} did not hold JSON; not overwriting")
    passives = class_passives(payload)
    short = [f"{class_name} {per_class(passives).get(class_name, 0)}"
             for class_name in CLASSES
             if per_class(passives).get(class_name, 0) < PASSIVES_PER_CLASS]
    if short:
        sys.exit(f"fewer than {PASSIVES_PER_CLASS} passives for {', '.join(short)}; "
                 "not overwriting")
    write(OUT_PATH, passives)
    return 0


if __name__ == "__main__":
    sys.exit(main())
