#!/usr/bin/env python3
"""
Generate data/items/armor_weights.json: the item ids of every light, medium
and heavy armor piece, for the Weight column of the build window's gear grid.

The encounter log gives an armor piece as an item id and never says how heavy
it is ([HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,...]). UESP's item
database lists every armor item with its armor type in one request (about
60,000 items, 5 MB). The ones of armor type 1, 2 and 3 (light, medium and
heavy) are kept here as three sorted lists of ids. The rest of that export,
jewelry among it, has no weight.

Checked against 48 logs of April to October 2026: all 905 item ids in their
armor slots had a weight in UESP's list. A piece from a set added to
the game after this file was built shows no weight until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_armor_weights.py
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "items" / "armor_weights.json"
ITEM_TYPE_ARMOR = 2
ARMOR_TYPES = {"1": "light", "2": "medium", "3": "heavy"}  # UESP's armorType
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=minedItemSummary"
              f"&type={ITEM_TYPE_ARMOR}&fields=itemId,armorType")
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
MIN_PER_WEIGHT = 10000  # the game has 17,000 to 21,000 of each; fewer means a bad response
IDS_PER_LINE = 16


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def armor_weights(payload: dict) -> dict:
    """{'light': [...], 'medium': [...], 'heavy': [...]}: the sorted item ids
    of each weight in UESP's armor export.

    Rows without a numeric id or without a weight are skipped.
    """
    rows = payload.get("minedItemSummary") if isinstance(payload, dict) else None
    found = {weight: set() for weight in ARMOR_TYPES.values()}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("itemId", "")).strip()
        weight = ARMOR_TYPES.get(str(row.get("armorType", "")).strip())
        if item_id.isdigit() and weight:
            found[weight].add(int(item_id))
    return {weight: sorted(ids) for weight, ids in found.items()}


def previous_weights(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {weight: set(data.get(weight) or []) for weight in ARMOR_TYPES.values()}


def _wrapped(ids: list) -> str:
    rows = [", ".join(str(i) for i in ids[start:start + IDS_PER_LINE])
            for start in range(0, len(ids), IDS_PER_LINE)]
    return "[\n  " + ",\n  ".join(rows) + "\n ]"


def render(weights: dict, generated: str) -> str:
    """The file's JSON, with the ids wrapped so a refresh diffs by line."""
    lists = ",\n".join(f" {json.dumps(weight)}: {_wrapped(weights[weight])}"
                       for weight in ARMOR_TYPES.values())
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps(EXPORT_URL)},\n'
            f' "count": {sum(len(ids) for ids in weights.values())},\n'
            f"{lists}\n"
            "}\n")


def write(path: Path, weights: dict) -> None:
    before = previous_weights(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(weights, generated), encoding="utf-8")
    total = sum(len(ids) for ids in weights.values())
    print(f"{path.relative_to(REPO_ROOT)}: {total} armor pieces with a weight")
    for weight, ids in weights.items():
        old = before.get(weight, set())
        print(f"  {weight}: {len(ids)} (+{len(set(ids) - old)} -{len(old - set(ids))} vs previous)")


def main() -> int:
    try:
        payload = json.loads(fetch(EXPORT_URL))
    except ValueError:
        sys.exit(f"{EXPORT_URL} did not return JSON; not overwriting")
    weights = armor_weights(payload)
    short = [f"{len(ids)} {weight}" for weight, ids in weights.items()
             if len(ids) < MIN_PER_WEIGHT]
    if short:
        sys.exit(f"only {', '.join(short)} armor pieces found in {EXPORT_URL}; not overwriting")
    write(OUT_PATH, weights)
    return 0


if __name__ == "__main__":
    sys.exit(main())
