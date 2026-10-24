#!/usr/bin/env python3
"""
Generate data/skills/weapon_skill_lines.json: every active skill of the six
weapon skill lines (Two Handed, One Hand and Shield, Dual Wield, Bow,
Destruction Staff, Restoration Staff) by game ability id, with its line and
name, for the build-issue rule that spots a weapon skill slotted on a bar
holding another weapon (build_issues.py).

The encounter log lists a bar's skills by ability id and never says which
skill line a skill belongs to. UESP's player skill table does: one request
(about 4,400 rows, 2 MB) lists every player skill with its line, rank and
whether it is a passive. The rows kept here are the non-passive rows of
the six lines with a rank of 1 or more: every rank of every morph (the log
writes the id of the rank the player has: Stampede is 38788, 39797, 39802
or 39807), the scribed grimoire skills of those lines included (Elemental
Explosion is logged as 217228 and a dozen other ids, one per focus script).
Left out: the passives (never in a bar), the rank -1 rows, which are
internal effects such as Bash and Follow Up, and UESP's own rank ids for
crafted skills (20217228 for rank 2 of 217228), which no log ever carries.
605 ids on the Update 51 client.

Run after an ESO update that adds a weapon skill or a grimoire (one request
to UESP, which asks heavy users to go lightly, so do not loop it):
    python scripts/generate_weapon_skill_lines.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_weapon_skill_lines.py --from build/esobuild-assets/sources/player_skills.json
"""

import argparse
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "skills" / "weapon_skill_lines.json"
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=playerSkills"
              "&fields=id,name,skillLine,rank,isPassive,isCrafted")
ATTRIBUTION = "Skill data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
WEAPON_LINES = ("Two Handed", "One Hand and Shield", "Dual Wield", "Bow",
                "Destruction Staff", "Restoration Staff")
MIN_ROWS = 400  # about 1,000 on the Update 51 client; fewer means a short reply
SYNTHETIC_ID = 10_000_000  # UESP numbers a crafted skill's ranks above this


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def weapon_skill_lines(payload: dict) -> dict:
    """{ability id: {'line', 'name'}} for every active weapon-line skill in
    UESP's player skill rows: rank 1 or more, no passives, no synthetic ids.
    Rows without a numeric id or outside the six lines are skipped."""
    rows = payload.get("playerSkills") if isinstance(payload, dict) else None
    found = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        line = str(row.get("skillLine") or "").strip()
        if line not in WEAPON_LINES:
            continue
        if str(row.get("isPassive", "")).strip() == "1":
            continue
        rank = str(row.get("rank", "")).strip()
        if not rank.isdigit() or int(rank) < 1:
            continue
        ability_id = str(row.get("id", "")).strip()
        if not ability_id.isdigit() or int(ability_id) >= SYNTHETIC_ID:
            continue
        found[ability_id] = {"line": line, "name": str(row.get("name") or "").strip()}
    return dict(sorted(found.items(), key=lambda item: int(item[0])))


def per_line(skills: dict) -> Counter:
    return Counter(entry["line"] for entry in skills.values())


def render(skills: dict, generated: str) -> str:
    """The file's JSON, one skill per line so a refresh diffs by id."""
    block = ",\n".join(f"  {json.dumps(ability_id)}: {json.dumps(entry)}"
                       for ability_id, entry in skills.items())
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps(EXPORT_URL)},\n'
            f' "attribution": {json.dumps(ATTRIBUTION)},\n'
            f' "count": {len(skills)},\n'
            ' "skills": {\n'
            f"{block}\n"
            " }\n"
            "}\n")


def previous_ids(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    return set((data.get("skills") or {}).keys()) if isinstance(data, dict) else set()


def write(path: Path, skills: dict) -> None:
    before = previous_ids(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(skills, generated), encoding="utf-8")
    now = set(skills)
    shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"{shown}: {len(skills)} weapon skills "
          f"(+{len(now - before)} -{len(before - now)} vs previous)")
    counts = per_line(skills)
    for line in WEAPON_LINES:
        print(f"  {line}: {counts.get(line, 0)}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from", dest="saved", metavar="FILE",
                        help="read a saved UESP playerSkills reply instead of requesting it")
    args = parser.parse_args(argv)
    if args.saved:
        text = Path(args.saved).read_text(encoding="utf-8")
    else:
        text = fetch(EXPORT_URL)
    try:
        payload = json.loads(text)
    except ValueError:
        sys.exit(f"{args.saved or EXPORT_URL} did not hold JSON; not overwriting")
    skills = weapon_skill_lines(payload)
    if len(skills) < MIN_ROWS:
        sys.exit(f"only {len(skills)} weapon skills found; not overwriting")
    write(OUT_PATH, skills)
    return 0


if __name__ == "__main__":
    sys.exit(main())
