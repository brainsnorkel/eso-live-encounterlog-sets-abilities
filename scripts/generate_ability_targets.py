#!/usr/bin/env python3
"""
Generate data/skills/ability_targets.json: whether each player skill is an
area or a single-target ability, by the ability id the encounter log writes,
for the area rule of the kinds of damage (damage_kinds.py, issue #73).

The log does not say whether a hit was area or single target. For a
monster's hit the cast id tells (a cast that struck two or more units), and
no table is consulted. For a player's own skill the cast id fails against
a lone boss (an area skill strikes one unit there), so the player skills'
target kinds from UESP's mined skill table decide when the casts say
nothing: Area, Cone and Ground are area, Enemy is single target; Self, Ally
and an empty target are dropped (a heal or a buff, not a hit). Only rows
flagged isPlayer are kept, about 4,400 of the table's 159,000, because the
survey of 87 logs showed UESP's target for monster abilities disagreeing
with the log on group-wide mechanics (Oppressive Bolts, "Enemy", struck up
to 12 players on one cast).

Reads the reply the esobuild export keeps (one request, cached for a day,
see scripts/export_esobuild_assets.py), so this script asks UESP nothing:
    python scripts/generate_ability_targets.py
    python scripts/generate_ability_targets.py --from path/to/mined_skills.json
With --fetch it makes one trimmed request of its own; UESP asks heavy users
to go lightly, so do not loop it.
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "skills" / "ability_targets.json"
CACHED_REPLY = REPO_ROOT / "build" / "esobuild-assets" / "sources" / "mined_skills.json"
EXPORT_URL = "https://esolog.uesp.net/exportJson.php?table=minedSkills&fields=id,name,target,isPlayer"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
ATTRIBUTION = "Skill data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
AREA_TARGETS = ("Area", "Cone", "Ground")
SINGLE_TARGETS = ("Enemy",)
MIN_ROWS = 2000  # the game has 4,000-odd player skills; fewer means a bad reply
PER_LINE = 16


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def ability_targets(payload: dict) -> dict:
    """{'area': [ids], 'single': [ids]} from a minedSkills reply, player
    skills only, ids as sorted ints; and the number of rows read."""
    rows = payload.get("minedSkills") if isinstance(payload, dict) else None
    area, single = set(), set()
    read = 0
    for row in rows or []:
        if str(row.get("isPlayer", "0")) != "1":
            continue
        read += 1
        try:
            ability_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        target = str(row.get("target") or "")
        if target in AREA_TARGETS:
            area.add(ability_id)
        elif target in SINGLE_TARGETS:
            single.add(ability_id)
    return {"area": sorted(area), "single": sorted(single), "read": read}


def render(kinds: dict, generated: str, source: str) -> str:
    def id_lines(ids):
        chunks = [ids[i:i + PER_LINE] for i in range(0, len(ids), PER_LINE)] or [[]]
        return ",\n".join("  " + ", ".join(str(i) for i in chunk) for chunk in chunks)
    return (
        "{\n"
        f' "generated": {json.dumps(generated)},\n'
        f' "source": {json.dumps(source)},\n'
        f' "attribution": {json.dumps(ATTRIBUTION)},\n'
        f' "count": {len(kinds["area"]) + len(kinds["single"])},\n'
        f' "area": [\n{id_lines(kinds["area"])}\n ],\n'
        f' "single": [\n{id_lines(kinds["single"])}\n ]\n'
        "}\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from", dest="from_file", type=Path,
                        help=f"a saved minedSkills reply (default: {CACHED_REPLY.relative_to(REPO_ROOT)})")
    parser.add_argument("--fetch", action="store_true",
                        help="make one trimmed request to UESP instead of reading a saved reply")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)
    if args.fetch:
        text = fetch(EXPORT_URL)
        source = EXPORT_URL
    else:
        path = args.from_file or CACHED_REPLY
        if not path.exists():
            print(f"No saved reply at {path}: run scripts/export_esobuild_assets.py once "
                  f"(it caches UESP's tables) or pass --from or --fetch", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        source = EXPORT_URL + f" (from {path.name})"
    payload = json.loads(text)
    kinds = ability_targets(payload)
    if kinds["read"] < MIN_ROWS:
        print(f"Only {kinds['read']} player skills in the reply; not writing", file=sys.stderr)
        return 1
    if not kinds["area"] and not kinds["single"]:
        print("The reply has no 'target' field; not writing", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(kinds, datetime.now(timezone.utc).isoformat(timespec="seconds"), source),
                        encoding="utf-8")
    print(f"Wrote {args.out}: {len(kinds['area'])} area, {len(kinds['single'])} single-target "
          f"player skills of {kinds['read']} read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
