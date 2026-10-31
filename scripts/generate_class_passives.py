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
EFFECT_CHANGED the player is the source of, or as a POWER_ENERGIZE when it
gives resources (Conservation of Energy, Share the Spoils, Nocturnal
Inspiration), under one of a few ids that carry the mastery's name.
UESP's mined skill table lists those ids
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

Devout Guardian's shield is called Hold the Line (103 split logs of
September and October 2026): 263619 is a 6-second effect gained by
a Templar on themselves (5,989 times, seven named Templars and some
anonymous ones, never another class), put on
cooldown after it fires and absorbing hits, and 263621 the Ultimate the
same Templars gain when it breaks (1,803 POWER_ENERGIZE lines, Templars
only), as the mastery's text says. Other classes appear on 263619 only as
the source of a hit the Templar's shield absorbed, which the engine does
not read. No Templar who gained it showed two other masteries in the same
session (the game allows two).

A character takes two masteries, and the log often shows one: a proc
mastery only once it has fired, Bastion of Light never. Where one shows,
the app lists the class's others as the likely second, in the order
players of that role take them ('mastery_order', by class and role: D, H
or T). The order comes from MASTERIES_TAKEN, how many characters of each
role were seen with each mastery among those that showed two, counted by
scripts/survey_masteries.py over 103 split logs of September and October
2026 (313 characters, each once, in the role of their longest log): by the
role's count, then the class's count over all roles, then by name. A
mastery the log never names (NEVER_LOGGED) cannot be counted and goes
last; the app marks it. The counts are the groups of one player's logs,
and a healer or tank cell of one or two characters says little; an order
from them is still better than none (issue #149).

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
# docstring for how each was pinned to its mastery). An id may be a gained
# effect or a resource gain (POWER_ENERGIZE), whichever the log writes: the
# engine reads a mastery from both
SIGNATURE_EFFECTS = {
    "263306": "Lead from the Front",   # Major Berserk, Dragonknights only
    "263307": "Lead from the Front",   # Major Protection, with it
    "263825": "Tundra's Maw",          # Major Brittle for 2.1 s, Wardens only
    "268257": "Bountiful Harvest",     # Major Heroism for 3 s, Wardens only
    "268259": "Cutthroat's Focus",     # Cutthroat's Mockery for 5 s, Nightblades only
    "263619": "Devout Guardian",       # Hold the Line, a 6 s shield, Templars only
    "263621": "Devout Guardian",       # Hold the Line, Ultimate when the shield breaks
}
ROLES = ("D", "H", "T")  # damage dealer, healer, tank: the fight entry's roles
# Characters of each role seen with each mastery, among those whose two
# masteries both showed (scripts/survey_masteries.py; see the module
# docstring). A mastery missing from a role was not seen in it
MASTERIES_TAKEN = {
    "Dragonknight": {
        "D": {"Wildfire Embers": 21, "Inexorable Descent": 17, "Lead from the Front": 5,
              "Resolute Defense": 2, "Booming Voice": 1},
        "H": {},
        "T": {"Lead from the Front": 16, "Resolute Defense": 15, "Inexorable Descent": 10,
              "Wildfire Embers": 6, "Booming Voice": 5},
    },
    "Sorcerer": {
        "D": {"Font of Power": 26, "Static Reverberation": 19, "Calculated Defense": 9,
              "Conservation of Energy": 4},
        "H": {"Conservation of Energy": 1, "Sphere of Influence": 1},
        "T": {"Calculated Defense": 13, "Conservation of Energy": 9, "Sphere of Influence": 3,
              "Font of Power": 2, "Static Reverberation": 1},
    },
    "Nightblade": {
        "D": {"Above and Beyond": 50, "An Eye for Exploitation": 49, "Cutthroat's Focus": 1},
        "H": {"Nocturnal Inspiration": 1, "Share the Spoils": 1},
        "T": {"Cutthroat's Focus": 3, "An Eye for Exploitation": 2, "Share the Spoils": 2,
              "Above and Beyond": 1},
    },
    "Warden": {
        "D": {"Wild Adaptation": 11, "Glacial Obstinance": 9, "Tundra's Maw": 4,
              "Bountiful Harvest": 1, "Green-Keeper's Hide": 1},
        "H": {"Bountiful Harvest": 19, "Tundra's Maw": 19},
        "T": {"Tundra's Maw": 4, "Bountiful Harvest": 2, "Wild Adaptation": 2},
    },
    "Necromancer": {
        "D": {"Cycle Unending": 16, "Nothing Wasted": 15, "Malevolent Promise": 1},
        "H": {"Malevolent Promise": 1, "Veil's Forfeit": 1},
        "T": {"Nothing Wasted": 7, "Cycle Unending": 5, "Pound of Flesh": 3, "Veil's Forfeit": 2,
              "Malevolent Promise": 1},
    },
    "Templar": {
        "D": {"Bright Harbinger": 12, "Judgment's Brand": 12},
        "H": {"Bright Harbinger": 5, "Devout Guardian": 4, "Judgment's Brand": 1},
        "T": {"Bright Harbinger": 8, "Judgment's Brand": 5, "Devout Guardian": 4,
              "Steadfast Candescence": 1},
    },
    "Arcanist": {
        "D": {"Unbound Potential": 62, "Abyssal Emergence": 35, "Fate Realigned": 27,
              "Ink-Scribe's Verve": 2},
        "H": {"Ink-Scribe's Verve": 12, "Erudite's Rigor": 8, "Fate Realigned": 2,
              "Abyssal Emergence": 1, "Unbound Potential": 1},
        "T": {"Fate Realigned": 2, "Unbound Potential": 2},
    },
}
# Masteries nothing in the log names (Bastion of Light heals through Sacred
# Ground and gives Ultimate, and no line of the survey logs carries it):
# last in every order, marked by the app
NEVER_LOGGED = ("Bastion of Light",)


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


def mastery_order(passives: dict) -> dict:
    """{class: {role: [the class's masteries, the likeliest first]}} for
    every class with masteries in *passives*: by the role's count in
    MASTERIES_TAKEN, then the class's count over all roles, then by name; a
    mastery in NEVER_LOGGED last."""
    names = {}
    for entry in passives.values():
        if entry["line"] == MASTERY_LINE and entry["name"]:
            names.setdefault(entry["class"], set()).add(entry["name"])
    order = {}
    for class_name in sorted(names, key=lambda c: (CLASSES.index(c) if c in CLASSES else len(CLASSES), c)):
        taken = MASTERIES_TAKEN.get(class_name, {})
        overall = Counter()
        for counts in taken.values():
            overall.update(counts)
        order[class_name] = {}
        for role in ROLES:
            counts = taken.get(role, {})
            order[class_name][role] = sorted(names[class_name], key=lambda name: (
                name in NEVER_LOGGED, -counts.get(name, 0), -overall[name], name))
    return order


def render(passives: dict, effects: dict, generated: str) -> str:
    """The file's JSON, one entry per line so a refresh diffs by id."""
    def block(entries):
        return ",\n".join(f"  {json.dumps(ability_id)}: {json.dumps(entry)}"
                          for ability_id, entry in entries.items())
    never = sorted({entry["name"] for entry in passives.values()
                    if entry["line"] == MASTERY_LINE and entry["name"] in NEVER_LOGGED})
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
            " },\n"
            ' "mastery_order": {\n'
            f"{block(mastery_order(passives))}\n"
            " },\n"
            f' "masteries_never_logged": {json.dumps(never)}\n'
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
    unknown = unknown_taken(passives)
    if unknown:
        print(f"  MASTERIES_TAKEN names no mastery of its class: {', '.join(unknown)}")


def unknown_taken(passives: dict) -> list:
    """'Class: name' for each mastery MASTERIES_TAKEN or NEVER_LOGGED names
    that *passives* does not hold for that class (a rename in a patch)."""
    held = {(entry["class"], entry["name"]) for entry in passives.values()
            if entry["line"] == MASTERY_LINE}
    names = {name for _class, name in held}
    missing = sorted({f"{class_name}: {name}" for class_name, roles in MASTERIES_TAKEN.items()
                      for counts in roles.values() for name in counts
                      if (class_name, name) not in held})
    missing.extend(f"?: {name}" for name in NEVER_LOGGED if name not in names)
    return missing


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
