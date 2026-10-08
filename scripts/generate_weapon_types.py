#!/usr/bin/env python3
"""
Generate data/items/weapon_types.json: the item ids of every weapon and
shield, one sorted list per type, for the Type column of the build window's
gear grid and for the healer role's restoration staff check.

The encounter log gives a weapon as an item id and never names its type
([MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,...]). UESP's item
database lists every weapon and shield with its type in one request (about
63,000 items, 2.5 MB). Each type's ids are kept here under the name the game
uses for the type (an inferno staff, a battle axe, a shield).

Checked against 20 logs of October 2026: all 174 weapon ids in them were in
UESP's list. A weapon from a set added to the game after this file was built
shows a dash in the build window until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_weapon_types.py
A reply from UESP already saved to disk can be used instead of fetching it
again (UESP asks for sparing use of its export):
    python scripts/generate_weapon_types.py --from <saved reply>.json
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "items" / "weapon_types.json"
ITEM_TYPE_WEAPON = 1
# UESP's weaponType (the game's WEAPONTYPE constants) -> the table's key.
# 7 is a prop and 10 a rune; neither is equipment the log can list.
WEAPON_TYPES = {
    "1": "axe", "2": "mace", "3": "sword", "4": "greatsword", "5": "battle_axe",
    "6": "maul", "8": "bow", "9": "restoration_staff", "11": "dagger",
    "12": "inferno_staff", "13": "ice_staff", "14": "shield", "15": "lightning_staff",
}
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=minedItemSummary"
              f"&type={ITEM_TYPE_WEAPON}&fields=itemId,weaponType")
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
MIN_PER_TYPE = 3000  # the game has 4,700 to 4,950 of each; fewer means a bad response
IDS_PER_LINE = 16


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def weapon_types(payload: dict) -> dict:
    """{'axe': [...], 'mace': [...], ...}: the sorted item ids of each weapon
    type in UESP's weapon export, every type present even when empty.

    Rows without a numeric id or of a type the table does not keep are
    skipped.
    """
    rows = payload.get("minedItemSummary") if isinstance(payload, dict) else None
    found = {kind: set() for kind in WEAPON_TYPES.values()}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("itemId", "")).strip()
        kind = WEAPON_TYPES.get(str(row.get("weaponType", "")).strip())
        if item_id.isdigit() and kind:
            found[kind].add(int(item_id))
    return {kind: sorted(ids) for kind, ids in found.items()}


def previous_types(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {kind: set(data.get(kind) or []) for kind in WEAPON_TYPES.values()}


def _wrapped(ids: list) -> str:
    rows = [", ".join(str(i) for i in ids[start:start + IDS_PER_LINE])
            for start in range(0, len(ids), IDS_PER_LINE)]
    return "[\n  " + ",\n  ".join(rows) + "\n ]"


def render(types: dict, generated: str) -> str:
    """The file's JSON, with the ids wrapped so a refresh diffs by line."""
    lists = ",\n".join(f" {json.dumps(kind)}: {_wrapped(types[kind])}"
                       for kind in WEAPON_TYPES.values())
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps(EXPORT_URL)},\n'
            f' "count": {sum(len(ids) for ids in types.values())},\n'
            f"{lists}\n"
            "}\n")


def write(path: Path, types: dict) -> None:
    before = previous_types(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(types, generated), encoding="utf-8")
    total = sum(len(ids) for ids in types.values())
    print(f"{path.relative_to(REPO_ROOT)}: {total} weapons and shields with a type")
    for kind, ids in types.items():
        old = before.get(kind, set())
        print(f"  {kind}: {len(ids)} (+{len(set(ids) - old)} -{len(old - set(ids))} vs previous)")


def load_payload(argv: list) -> tuple:
    """(payload, where it came from) from the command line: a saved reply
    after --from, else UESP's export."""
    if len(argv) == 2 and argv[0] == "--from":
        source = argv[1]
        text = Path(source).read_text(encoding="utf-8")
    elif argv:
        sys.exit(f"usage: {Path(sys.argv[0]).name} [--from <saved reply>.json]")
    else:
        source = EXPORT_URL
        text = fetch(EXPORT_URL)
    try:
        return json.loads(text), source
    except ValueError:
        sys.exit(f"{source} did not hold JSON; not overwriting")


def main(argv=None) -> int:
    payload, source = load_payload(sys.argv[1:] if argv is None else argv)
    types = weapon_types(payload)
    short = [f"{len(ids)} {kind}" for kind, ids in types.items() if len(ids) < MIN_PER_TYPE]
    if short:
        sys.exit(f"only {', '.join(short)} found in {source}; not overwriting")
    write(OUT_PATH, types)
    return 0


if __name__ == "__main__":
    sys.exit(main())
