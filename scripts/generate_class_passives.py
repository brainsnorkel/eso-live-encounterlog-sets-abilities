#!/usr/bin/env python3
"""
Generate data/skills/class_passives.json: every class skill line passive and
Class Mastery passive by game ability id, with its class, skill line, name
and rank, for the skill lines and masteries shown beside a player's class;
and the ids of the effects the masteries fire, by which a mastery is known
when it is not in the player's passive list.

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

The PLAYER_INFO list holds only the passives whose effect is always on. A
mastery that works by a proc (Unbound Potential, Abyssal Emergence, Wildfire
Embers, Bright Harbinger...) is never in it; it shows in the log as an
EFFECT_CHANGED the player is the source of, under one of a few effect ids
that carry the mastery's name. UESP's mined skill table lists those ids
(97 ids carry a mastery's name on the Update 51 client, the 35 passives
among them); the ones that are not the passives themselves are kept under
'mastery_effects'. Two monster abilities are also called Pound of Flesh and
target enemies; a mastery effect never does, so enemy-targeted rows are
left out.

Some masteries fire effects named after the buff they grant rather than
after themselves, with ids in the same block: Lead from the Front's Major
Berserk and Major Protection, Tundra's Maw's Major Brittle, Bountiful
Harvest's Major Heroism, Cutthroat's Focus's Cutthroat's Mockery.
SIGNATURE_EFFECTS maps those by hand, from 73 split logs of September and
October 2026 in which each id was sourced by one class alone (263306 and
263307 by Dragonknights 6,631 times and by no one else; 263825 by Wardens
14,207 times; 268257 by Wardens 128,405 times; 268259 by Nightblades 203
times) and whose durations match the masteries' text; the engine checks
the source's class as well. Nothing in UESP's tables ties them to their
mastery, so a new one has to be found the same way.

Run after an ESO update that adds a class or a skill line (two requests to
UESP, five seconds apart; UESP asks heavy users to go lightly, so do not
loop it):
    python scripts/generate_class_passives.py
or from replies already on disk, such as the ones the esobuild export keeps:
    python scripts/generate_class_passives.py --from build/esobuild-assets/sources/player_skills.json --mined build/esobuild-assets/sources/mined_skills.json
"""

import argparse
import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "skills" / "class_passives.json"
EXPORT_URL = ("https://esolog.uesp.net/exportJson.php?table=playerSkills"
              "&fields=id,name,classType,skillLine,baseAbilityId,rank,isPassive,skillType")
MINED_URL = ("https://esolog.uesp.net/exportJson.php?table=minedSkills"
             "&fields=id,name,isPassive,target")
ATTRIBUTION = "Skill data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
SKILL_TYPE_CLASS = "1"  # UESP's skillType for class skill lines
MASTERY_LINE = "Class Mastery"
# A class has three lines of four passives in two ranks, plus five masteries
PASSIVES_PER_CLASS = 3 * 4 * 2 + 5
MIN_MASTERY_EFFECTS = 40  # 60 on the Update 51 client; fewer means a short reply
CLASSES = ("Dragonknight", "Sorcerer", "Nightblade", "Warden", "Necromancer",
           "Templar", "Arcanist")
SECONDS_BETWEEN_REQUESTS = 5
# Effects a mastery fires under its buff's name, not its own (see the module
# docstring for how each was pinned to its mastery)
SIGNATURE_EFFECTS = {
    "263306": "Lead from the Front",   # Major Berserk, Dragonknights only
    "263307": "Lead from the Front",   # Major Protection, with it
    "263825": "Tundra's Maw",          # Major Brittle for 2.1 s, Wardens only
    "268257": "Bountiful Harvest",     # Major Heroism for 3 s, Wardens only
    "268259": "Cutthroat's Focus",     # Cutthroat's Mockery for 5 s, Nightblades only
}


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


def mastery_effects(payload: dict, passives: dict) -> dict:
    """{ability id: {'class', 'name'}} for every mined skill that carries a
    Class Mastery's name and is not one of the mastery passives themselves
    nor enemy-targeted (the Pound of Flesh monster abilities)."""
    rows = payload.get("minedSkills") if isinstance(payload, dict) else None
    masteries = {entry["name"]: entry["class"] for entry in passives.values()
                 if entry["line"] == MASTERY_LINE and entry["name"]}
    found = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ability_id = str(row.get("id", "")).strip()
        name = str(row.get("name") or "").strip()
        if not ability_id.isdigit() or ability_id in passives:
            continue
        mastery = SIGNATURE_EFFECTS.get(ability_id)
        if mastery and mastery in masteries:
            found[ability_id] = {"class": masteries[mastery], "name": mastery, "effect": name}
            continue
        if name not in masteries:
            continue
        if str(row.get("target") or "").strip().lower() == "enemy":
            continue
        found[ability_id] = {"class": masteries[name], "name": name}
    return dict(sorted(found.items(), key=lambda item: int(item[0])))


def per_class(passives: dict) -> Counter:
    return Counter(entry["class"] for entry in passives.values())


def render(passives: dict, effects: dict, generated: str) -> str:
    """The file's JSON, one entry per line so a refresh diffs by id."""
    def block(entries):
        return ",\n".join(f"  {json.dumps(ability_id)}: {json.dumps(entry)}"
                          for ability_id, entry in entries.items())
    return ("{\n"
            f' "generated": {json.dumps(generated)},\n'
            f' "source": {json.dumps([EXPORT_URL, MINED_URL])},\n'
            f' "attribution": {json.dumps(ATTRIBUTION)},\n'
            f' "count": {len(passives)},\n'
            ' "passives": {\n'
            f"{block(passives)}\n"
            " },\n"
            f' "mastery_effects_count": {len(effects)},\n'
            ' "mastery_effects": {\n'
            f"{block(effects)}\n"
            " }\n"
            "}\n")


def previous_ids(path: Path, key: str) -> set:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    return set((data.get(key) or {}).keys()) if isinstance(data, dict) else set()


def write(path: Path, passives: dict, effects: dict) -> None:
    before = previous_ids(path, "passives")
    before_effects = previous_ids(path, "mastery_effects")
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(render(passives, effects, generated), encoding="utf-8")
    now = set(passives)
    print(f"{path.relative_to(REPO_ROOT)}: {len(passives)} class passives "
          f"(+{len(now - before)} -{len(before - now)} vs previous)")
    counts = per_class(passives)
    for class_name in CLASSES:
        masteries = sum(1 for entry in passives.values()
                        if entry["class"] == class_name and entry["line"] == MASTERY_LINE)
        print(f"  {class_name}: {counts.get(class_name, 0)} ({masteries} masteries)")
    now_effects = set(effects)
    print(f"  mastery effects: {len(effects)} "
          f"(+{len(now_effects - before_effects)} -{len(before_effects - now_effects)} vs previous)")


def _load(source: Path, url: str) -> dict:
    try:
        return json.loads(source.read_text(encoding="utf-8") if source else fetch(url))
    except ValueError:
        sys.exit(f"{source or url} did not hold JSON; not overwriting")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--from", dest="source", type=Path,
                        help="a saved UESP playerSkills reply to read instead of fetching")
    parser.add_argument("--mined", type=Path,
                        help="a saved UESP minedSkills reply to read instead of fetching")
    args = parser.parse_args(argv)
    passives = class_passives(_load(args.source, EXPORT_URL))
    short = [f"{class_name} {per_class(passives).get(class_name, 0)}"
             for class_name in CLASSES
             if per_class(passives).get(class_name, 0) < PASSIVES_PER_CLASS]
    if short:
        sys.exit(f"fewer than {PASSIVES_PER_CLASS} passives for {', '.join(short)}; "
                 "not overwriting")
    if not args.mined and not args.source:
        time.sleep(SECONDS_BETWEEN_REQUESTS)
    effects = mastery_effects(_load(args.mined, MINED_URL), passives)
    if len(effects) < MIN_MASTERY_EFFECTS:
        sys.exit(f"only {len(effects)} mastery effects found; not overwriting")
    write(OUT_PATH, passives, effects)
    return 0


if __name__ == "__main__":
    sys.exit(main())
