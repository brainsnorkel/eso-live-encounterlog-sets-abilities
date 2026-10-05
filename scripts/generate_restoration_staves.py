#!/usr/bin/env python3
"""
Generate data/items/restoration_staves.json: the item ids of every
restoration staff, for the role heuristic (a healer has magicka as their
largest pool and a restoration staff equipped).

The encounter log gives a weapon as an item id and never names its type
([MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,...]). UESP's item
database lists every weapon with its type in one request (about 63,000
weapons, 4.5 MB); the ones of weapon type 9, the game's healing staff, are
kept here as a sorted list of ids.

Checked against 36 logs of October 2026: all 246 weapon ids in them were in
UESP's list. A staff from a set added to the game after this file was built
is not recognised until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_restoration_staves.py
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "items" / "restoration_staves.json"
ITEM_TYPE_WEAPON = 1
WEAPON_TYPE_RESTORATION_STAFF = "9"
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=minedItemSummary"
              f"&type={ITEM_TYPE_WEAPON}&fields=itemId,weaponType")
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
MIN_STAVES = 3000  # the game has about 4,800; fewer means a bad response
IDS_PER_LINE = 16


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def restoration_staff_ids(payload: dict) -> list:
    """Sorted item ids of the restoration staves in UESP's weapon export.

    Rows without a numeric id are skipped.
    """
    rows = payload.get("minedItemSummary") if isinstance(payload, dict) else None
    ids = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("itemId", "")).strip()
        if item_id.isdigit() and str(row.get("weaponType", "")).strip() == WEAPON_TYPE_RESTORATION_STAFF:
            ids.add(int(item_id))
    return sorted(ids)


def previous_ids(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("ids", []))
    except ValueError:
        return set()


def render(ids: list, generated: str) -> str:
    """The file's JSON, with the ids wrapped so a refresh diffs by line."""
    rows = [", ".join(str(i) for i in ids[start:start + IDS_PER_LINE])
            for start in range(0, len(ids), IDS_PER_LINE)]
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps(EXPORT_URL)},\n'
            f' "count": {len(ids)},\n'
            ' "ids": [\n  ' + ",\n  ".join(rows) + "\n ]\n"
            "}\n")


def write(path: Path, ids: list) -> None:
    before = previous_ids(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(ids, generated), encoding="utf-8")
    added, removed = sorted(set(ids) - before), sorted(before - set(ids))
    print(f"{path.relative_to(REPO_ROOT)}: {len(ids)} restoration staves "
          f"(+{len(added)} -{len(removed)} vs previous)")
    for label, items in (("added", added), ("removed", removed)):
        if items:
            shown = ", ".join(str(i) for i in items[:12])
            print(f"  {label}: {shown}{' ...' if len(items) > 12 else ''}")


def main() -> int:
    try:
        payload = json.loads(fetch(EXPORT_URL))
    except ValueError:
        sys.exit(f"{EXPORT_URL} did not return JSON; not overwriting")
    ids = restoration_staff_ids(payload)
    if len(ids) < MIN_STAVES:
        sys.exit(f"only {len(ids)} restoration staves found in {EXPORT_URL}; not overwriting")
    write(OUT_PATH, ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
