#!/usr/bin/env python3
"""
Generate data/sets/proc_abilities.json: the hidden ability a set's bonus
fires, by ability id, with the set it belongs to (issue #79, decision 5), so
the uptime line can name the set behind a proc buff.

The encounter log names a proc by its ability ("Major Slayer" from Roaring
Opportunist) and never by its set; the client's files hold no link from a set
to the abilities its bonuses fire. UESP makes the link: its
findSetBonusSkills.php matches every set bonus's text, figures replaced by #,
against the descriptions of the game's non-player abilities and writes the
set's name into minedSkills.setName (without "Perfected ", so a perfected
set's proc names the base set). This script takes that column in one trimmed
request and keys it by set id through the app's own set table; a setName that
is not a set ("CP:Cutting Defense", which UESP fixes by hand) is skipped and
counted.

Run after an ESO update (one request to UESP, about 5 MB; UESP asks heavy
users to go lightly, so do not loop it, and on a 403 or 429 stop):
    python scripts/generate_set_procs.py
or from a reply already saved:
    python scripts/generate_set_procs.py --from <minedSkills reply>.json
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
OUT_PATH = REPO_ROOT / "data" / "sets" / "proc_abilities.json"
EXPORT_URL = "https://esolog.uesp.net/exportJson.php?table=minedSkills&fields=id,setName"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
ATTRIBUTION = "Set proc data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
MIN_ROWS = 100000  # minedSkills has 150,000-odd rows; fewer means a bad reply
MIN_PROCS = 100  # several hundred abilities carry a set; fewer means a bad reply


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def set_procs(payload: dict, set_name_to_id: dict):
    """({ability id: {'set_id', 'set'}}, [setName values that are no set])."""
    rows = payload.get("minedSkills") if isinstance(payload, dict) else None
    procs, unknown = {}, []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ability_id = str(row.get("id", "")).strip()
        set_name = str(row.get("setName") or "").strip()
        if not ability_id.isdigit() or not set_name:
            continue
        set_id = set_name_to_id.get(set_name)
        if set_id is None:
            unknown.append(set_name)
            continue
        procs[ability_id] = {"set_id": set_id, "set": set_name}
    return procs, sorted(set(unknown))


def render(procs: dict, generated: str, source: str) -> str:
    lines = ["{",
             f' "generated": {json.dumps(generated)},',
             f' "source": {json.dumps(source)},',
             f' "attribution": {json.dumps(ATTRIBUTION)},',
             f' "count": {len(procs)},',
             ' "abilities": {']
    items = sorted(procs.items(), key=lambda kv: int(kv[0]))
    for n, (ability_id, data) in enumerate(items):
        comma = "," if n < len(items) - 1 else ""
        lines.append(f'  {json.dumps(ability_id)}: {json.dumps(data, ensure_ascii=False)}{comma}')
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from", dest="from_file", type=Path,
                        help="a saved minedSkills reply instead of fetching one")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)
    if args.from_file:
        text = args.from_file.read_text(encoding="utf-8")
        source = EXPORT_URL + f" (from {args.from_file.name})"
    else:
        text = fetch(EXPORT_URL)
        source = EXPORT_URL
    payload = json.loads(text)
    rows = payload.get("minedSkills") if isinstance(payload, dict) else None
    if not rows or len(rows) < MIN_ROWS:
        print(f"Only {len(rows or [])} rows in the reply; not writing", file=sys.stderr)
        return 1
    from gear_set_data import SET_NAME_TO_ID
    procs, unknown = set_procs(payload, SET_NAME_TO_ID)
    if len(procs) < MIN_PROCS:
        print(f"Only {len(procs)} abilities carry a known set; not writing", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(procs, datetime.now(timezone.utc).isoformat(timespec="seconds"), source),
                        encoding="utf-8")
    print(f"Wrote {args.out}: {len(procs)} abilities across "
          f"{len({p['set_id'] for p in procs.values()})} sets; "
          f"{len(unknown)} setName values that are no set: {', '.join(unknown[:8])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
