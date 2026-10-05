#!/usr/bin/env python3
"""
Generate data/items/poisons_en.json: poison item id -> name, for the poison
rows of the build window.

The encounter log gives a slotted poison only as an item id
([POISON,79690,F,1,NONE,LEGENDARY,0,INVALID,F,0,NORMAL]). UESP's item
database names every poison (item type 30, about 50 items) in one request:

  "79690": {"name": "Crown Lethal Poison", "tiered": false}
  "76827": {"name": "Damage Health Poison", "tiered": true}

A poison whose strength scales with its solvent carries a tier numeral in its
name, "Damage Health Poison I" up to "IX". The numeral is dropped here and
marked with "tiered"; the app adds the one for the logged level
(player_build.poison_tier). A crafted poison's id identifies its primary
effect only: its other effects are not in the log.

Run after an ESO update that adds poisons (needs network access):
    python scripts/generate_poison_names.py
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "items" / "poisons_en.json"
ITEM_TYPE_POISON = 30
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=minedItemSummary"
              f"&type={ITEM_TYPE_POISON}&fields=itemId,name")
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
MIN_POISONS = 30  # the game has about 50; fewer means a bad response
TIER_RE = re.compile(r"^(.*\S) (I|II|III|IV|V|VI|VII|VIII|IX)$")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def poison_entries(payload: dict) -> dict:
    """item id -> {'name', 'tiered'} from UESP's minedItemSummary export.

    Rows without a numeric id or a name are skipped.
    """
    rows = payload.get("minedItemSummary") if isinstance(payload, dict) else None
    entries = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("itemId", "")).strip()
        name = str(row.get("name", "")).strip()
        if not item_id.isdigit() or not name:
            continue
        tiered = TIER_RE.match(name)
        entries[item_id] = {"name": tiered.group(1) if tiered else name,
                            "tiered": bool(tiered)}
    return entries


def previous_ids(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("poisons", {}))
    except ValueError:
        return set()


def write(path: Path, entries: dict) -> None:
    before = previous_ids(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": EXPORT_URL, "count": len(entries),
               "poisons": dict(sorted(entries.items(), key=lambda kv: int(kv[0])))}
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    added, removed = sorted(set(entries) - before), sorted(before - set(entries))
    print(f"{path.relative_to(REPO_ROOT)}: {len(entries)} poisons "
          f"(+{len(added)} -{len(removed)} vs previous)")
    for label, items in (("added", added), ("removed", removed)):
        if items:
            print(f"  {label}: {', '.join(items[:12])}{' ...' if len(items) > 12 else ''}")


def main() -> int:
    try:
        payload = json.loads(fetch(EXPORT_URL))
    except ValueError:
        sys.exit(f"{EXPORT_URL} did not return JSON; not overwriting")
    entries = poison_entries(payload)
    if len(entries) < MIN_POISONS:
        sys.exit(f"only {len(entries)} poisons found in {EXPORT_URL}; not overwriting")
    write(OUT_PATH, entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
