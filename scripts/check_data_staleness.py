#!/usr/bin/env python3
"""
Check the bundled game data against a folder of encounter logs, game
version by game version (issue #173). Run it after a game update, before
the data refresh, to see what the update broke; it changes nothing.

    python scripts/check_data_staleness.py                (the app's split folder)
    python scripts/check_data_staleness.py --dir D:/esologs/splits --workers 12
    python scripts/check_data_staleness.py --data-version eso.live.12.0   (what if)

Two reports, by the game version each logging session's BEGIN_LOG names:

1. **Coverage**: the set ids, armor and weapon item ids, abilities on
   players' bars, killing abilities and set names the logs name, and how
   many of them the bundle does not know (the app's own rules, from
   src/data_staleness.py: a plain low-level item such as a new character's
   Soul-Shriven clothes is left out, and its count shown apart). It also
   says in how many sessions the app's status line would have spoken, with
   the bundle's version or the one --data-version names, and lists the
   food hint: effects with a food-style icon (the prefixes
   scripts/generate_food_buffs.py uses) on a player with no listed food. The
   app does not count food, since that test is only a hint; monsters'
   icons are listed here for the same reason (the bundle carries the player
   skills' and the death_recap_ icons only).
2. **Fires**: every ability id the app depends on (the default tracked
   effects, the penetration and critical damage rules, the build-issue
   rules' ids and sets, class passives and mastery effects, werewolf,
   companion and Fatecarver ids, the cast kinds' ids) and the companions'
   and boss-flag adds' monster ids, with the sessions of each version it
   appeared in (an effect, a hit, a cast, a PLAYER_INFO line, a unit). An id
   that appeared on the previous version and in none of the newest
   version's sessions is flagged: the game may have renumbered it. A flag on
   an id the previous version saw in few sessions is weak; the share says so.

Logs are told apart by a hash of their first 256 KB, so the copies the old
splitter wrote count once. Zipped splits (``*.log.zip``) are read too.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_food_buffs import FOOD_ICON_PREFIXES

import boss_units
import build_issues
import casts
import companions
import data_staleness
import pen_crit
import resources
import werewolf
from ability_icons import icon_stem
from effect_rules import DEFAULT_RULES, parse_rules
from eso_log_parser import ESOLogParser
from player_build import (
    ARMOR_SLOTS,
    WEAPON_SLOTS,
    armor_weight,
    food_ids,
    weapon_type,
)

HEAD_BYTES = 256 * 1024
DEATHS = (b"DIED", b"KILLING_BLOW")
# A flag on an id the previous version saw in fewer sessions than this is weak
WEAK_SESSIONS = 3


def tracked_groups() -> list:
    """(group, kind, ids) for every id the app depends on; kind is 'ability'
    (an effect, hit, cast or PLAYER_INFO id), 'set' (a worn set's id) or
    'monster' (a unit's monster id)."""
    groups = []
    rules, _errors = parse_rules(DEFAULT_RULES)
    groups += [(f"Tracked effect: {rule.name}", "ability", rule.ids) for rule in rules]
    groups += [(f"Penetration and crit: {rule.name}", "ability", rule.ids)
               for rule in pen_crit.tracker_rules()]
    groups += [
        ("Build issues: taunts", "ability", build_issues.TAUNT_SKILL_IDS),
        ("Build issues: pulls", "ability", build_issues.PULL_SKILL_IDS),
        ("Build issues: Destructive Clench", "ability", build_issues.CLENCH_SKILL_IDS),
        ("Build issues: Elemental Drain", "ability", build_issues.ELEMENTAL_DRAIN_IDS),
        ("Build issues: proc set effects", "ability", build_issues.PROC_EFFECT_IDS),
        ("Build issues: sets (Minor Slayer, group, proc, Oakensoul)", "set",
         set(build_issues.SLAYER_SETS) | set(build_issues.GROUP_SETS)
         | set(build_issues.PROC_SETS) | {build_issues.OAKENSOUL_SET_ID}),
    ]
    try:
        passives = json.loads((ROOT / "data" / "skills" / "class_passives.json")
                              .read_text(encoding="utf-8"))
        groups += [("Class passives", "ability", set(passives.get("passives") or {})),
                   ("Class Mastery effects", "ability", set(passives.get("mastery_effects") or {}))]
    except (OSError, ValueError):
        pass
    groups += [
        ("Werewolf", "ability", werewolf.CAST_IDS | werewolf.EFFECT_IDS),
        ("Companion ultimates", "ability", set(companions.ULTIMATES)),
        ("Companions", "monster", set(companions.COMPANION_MONSTER_IDS)),
        ("Fatecarver channel", "ability", set(casts.CHANNEL_EFFECTS) | set(resources.CHANNEL_TICKS)),
        ("Casts: light and heavy attacks", "ability", casts.LIGHT_ATTACKS | casts.HEAVY_ATTACKS),
        ("Casts: bash, swap, dodge, break free", "ability",
         casts.BASHES | casts.SWAPS | casts.DODGES | casts.BREAK_FREE),
        ("Casts: synergies", "ability", casts.SYNERGIES),
        ("Casts: potions", "ability", casts.POTIONS),
        ("Boss flag adds", "monster", set(boss_units.BOSS_FLAG_ADDS)),
    ]
    return [(name, kind, frozenset(str(i) for i in ids)) for name, kind, ids in groups]


def open_binary(path: Path):
    """A binary stream of the log, or of the one log in a zipped split."""
    if zipfile.is_zipfile(path):
        zf = zipfile.ZipFile(path)
        members = [i.filename for i in zf.infolist() if i.filename.lower().endswith(".log")]
        if len(members) != 1:
            zf.close()
            return None
        return zf.open(members[0])
    return open(path, "rb")


def head_hash(path: Path) -> str | None:
    stream = open_binary(path)
    if stream is None:
        return None
    with stream:
        return hashlib.sha1(stream.read(HEAD_BYTES)).hexdigest()


def _csv(raw: bytes) -> list:
    return next(csv.reader(io.StringIO(raw.decode("utf-8", "replace"))))


class _Session:
    def __init__(self, version: str, data_version: str | None):
        self.version = version
        self.tracker = data_staleness.DataCheckTracker(data_version=data_version) \
            if data_version is not None else data_staleness.DataCheckTracker()
        self.tracker.reset(version)
        self.sets, self.armor, self.weapons, self.bars = set(), set(), set(), set()
        self.armor_unknown_all, self.weapons_unknown_all = set(), set()
        self.killers = {}
        self.food_hint = Counter()
        self.fires = Counter()

    def result(self) -> dict:
        check = self.tracker.check()
        return {"version": self.version, "speaks": not check.clear,
                "status": data_staleness.status_text(check),
                "unknown_sets": list(check.unknown_sets),
                "unknown_armor": list(check.unknown_armor),
                "unknown_weapons": list(check.unknown_weapons),
                "missing_icons": [list(x) for x in check.missing_icons],
                "unlinked_sets": list(check.unlinked_sets),
                "sets": sorted(self.sets), "armor": sorted(self.armor),
                "weapons": sorted(self.weapons), "bars": sorted(self.bars),
                "armor_unknown_all": sorted(self.armor_unknown_all),
                "weapons_unknown_all": sorted(self.weapons_unknown_all),
                "killers": self.killers,
                "food_hint": [[*k, n] for k, n in self.food_hint.items()],
                "fires": dict(self.fires)}


def scan(path: Path, data_version: str | None) -> list:
    """Every logging session of *path*, as the dict _Session.result makes."""
    groups = tracked_groups()
    ability_ids = frozenset().union(*(ids for _n, kind, ids in groups if kind == "ability"))
    set_ids = frozenset().union(*(ids for _n, kind, ids in groups if kind == "set"))
    monster_ids = frozenset().union(*(ids for _n, kind, ids in groups if kind == "monster"))
    ability_bytes = {i.encode() for i in ability_ids}
    monster_bytes = {i.encode() for i in monster_ids}
    food = food_ids()
    parser = ESOLogParser()
    names, icons = {}, {}
    sessions = []
    session = None
    stream = open_binary(path)
    if stream is None:
        return []
    with stream:
        for raw in stream:
            c1 = raw.find(b",")
            if c1 < 0:
                continue
            c2 = raw.find(b",", c1 + 1)
            event = raw[c1 + 1:c2] if c2 > 0 else b""
            if event == b"EFFECT_CHANGED":
                if session is not None:
                    ability = raw.split(b",", 6)[5]
                    if ability in ability_bytes:
                        session.fires[ability.decode()] += 1
            elif event == b"COMBAT_EVENT":
                if session is not None:
                    fields = raw.split(b",", 9)
                    if len(fields) > 8:
                        ability = fields[8]
                        if ability in ability_bytes:
                            session.fires[ability.decode()] += 1
                        if fields[2] in DEATHS:
                            session.killers[ability.decode()] = icons.get(ability.decode(), "")
            elif event == b"BEGIN_CAST":
                if session is not None:
                    fields = raw.split(b",", 6)
                    if len(fields) > 5 and fields[5] in ability_bytes:
                        session.fires[fields[5].decode()] += 1
            elif event == b"UNIT_ADDED":
                if session is not None:
                    fields = raw.split(b",", 7)
                    if len(fields) > 6 and fields[6] in monster_bytes:
                        session.fires[fields[6].decode()] += 1
            elif event == b"ABILITY_INFO":
                fields = _csv(raw)
                if len(fields) > 4:
                    names[fields[2]] = fields[3]
                    icons[fields[2]] = icon_stem(fields[4])
            elif event == b"PLAYER_INFO":
                if session is None:
                    session = _Session("", data_version)
                    sessions.append(session)
                entry = parser.parse_line(raw.decode("utf-8", "replace").rstrip("\r\n"))
                info = parser.parse_player_info(entry) if entry is not None else None
                if info is None:
                    continue
                _note_player(session, info, names, icons, food, ability_ids, set_ids)
            elif event == b"BEGIN_LOG":
                fields = raw.decode("utf-8", "replace").strip().replace('"', "").split(",")
                session = _Session(fields[6].strip() if len(fields) > 6 else "", data_version)
                sessions.append(session)
    return [s.result() for s in sessions]


def _note_player(session, info, names, icons, food, ability_ids, set_ids) -> None:
    bars = [str(a) for a in list(info.champion_points) + list(info.additional_data)]
    slots = [{"id": a, "name": names[a], "icon": icons.get(a, "")} for a in bars if a in names]
    session.tracker.note_player(info.gear_data, slots)
    session.bars.update(bars)
    for item in info.gear_data:
        if len(item) < 7:
            continue
        slot, item_id, set_id = str(item[0]), str(item[1]), str(item[6])
        if set_id not in ("", "0", "nan"):
            session.sets.add(set_id)
            if set_id in set_ids:
                session.fires[set_id] += 1
        if slot in ARMOR_SLOTS:
            session.armor.add(item_id)
            if not armor_weight(item_id):
                session.armor_unknown_all.add(item_id)
        elif slot in WEAPON_SLOTS:
            session.weapons.add(item_id)
            if not weapon_type(item_id):
                session.weapons_unknown_all.add(item_id)
    effects = [str(e) for e in info.ability_ids]
    for ability in effects + bars:
        if ability in ability_ids:
            session.fires[ability] += 1
    if not any(e in food for e in effects):
        for effect in effects:
            stem = icons.get(effect, "")
            if effect not in food and stem.startswith(FOOD_ICON_PREFIXES):
                session.food_hint[(effect, names.get(effect, ""), stem)] += 1


def _work(job):
    path, data_version = job
    digest = head_hash(path)
    if digest is None:
        return str(path), None, []
    try:
        return str(path), digest, scan(path, data_version)
    except Exception as exc:  # noqa: BLE001 - one bad file does not stop the run
        return str(path), digest, [{"error": repr(exc)}]


def collect(folder: Path, workers: int, data_version: str | None, limit: int = 0):
    """(sessions, files read, copies skipped, errors) over the folder."""
    paths = sorted(p for p in folder.iterdir()
                   if p.is_file() and (p.suffix.lower() == ".log" or p.name.lower().endswith(".log.zip")))
    if limit:
        paths = paths[-limit:]
    paths.sort(key=lambda p: p.stat().st_size, reverse=True)
    seen, sessions, errors = set(), [], []
    copies = 0
    with Pool(max(1, workers)) as pool:
        for path, digest, found in pool.imap_unordered(_work, [(p, data_version) for p in paths]):
            if digest is None:
                continue
            if digest in seen:
                copies += 1
                continue
            seen.add(digest)
            for result in found:
                if "error" in result:
                    errors.append(f"{Path(path).name}: {result['error']}")
                else:
                    result["file"] = Path(path).name
                    sessions.append(result)
    return sessions, len(seen), copies, errors


def _version_key(version: str):
    return data_staleness.parse_game_version(version) or (-1, -1)


def coverage(sessions: list) -> dict:
    """Per game version: the counts of the coverage report."""
    by_version = defaultdict(list)
    for s in sessions:
        by_version[s["version"]].append(s)
    stems = data_staleness.bundled_icon_stems()
    report = {}
    for version in sorted(by_version, key=_version_key):
        group = by_version[version]

        def union(key, group=group):
            return set().union(*(set(s[key]) for s in group))
        killers = {}
        for s in group:
            killers.update(s["killers"])
        food = Counter()
        for s in group:
            for effect, name, stem, n in s["food_hint"]:
                food[(effect, name, stem)] += n
        report[version or "(none)"] = {
            "sessions": len(group),
            "speaks": sum(1 for s in group if s["speaks"]),
            "status_lines": Counter(s["status"] for s in group if s["speaks"]).most_common(5),
            "sets": len(union("sets")), "sets_unknown": sorted(union("unknown_sets")),
            "armor": len(union("armor")), "armor_unknown": sorted(union("unknown_armor")),
            "armor_left_out": sorted(union("armor_unknown_all") - union("unknown_armor")),
            "weapons": len(union("weapons")), "weapons_unknown": sorted(union("unknown_weapons")),
            "weapons_left_out": sorted(union("weapons_unknown_all") - union("unknown_weapons")),
            "bars": len(union("bars")),
            "bar_icons_missing": sorted({tuple(x) for s in group for x in s["missing_icons"]}),
            "killers": len(killers),
            "killer_icons_missing": sorted(a for a, stem in killers.items() if stem and stem not in stems),
            "unlinked_sets": sorted(union("unlinked_sets")),
            "food_hint": [[*k, n] for k, n in food.most_common(10)],
        }
    return report


def fires(sessions: list) -> dict:
    """{'versions', 'previous', 'newest', 'sessions' (per version), 'groups':
    [{group, kind, ids, fired_newest, flagged: [(id, sessions on previous,
    share)]}]}."""
    by_version = defaultdict(list)
    for s in sessions:
        if s["version"]:
            by_version[s["version"]].append(s)
    versions = sorted(by_version, key=_version_key)
    out = {"versions": versions, "sessions": {v: len(by_version[v]) for v in versions},
           "groups": [], "previous": versions[-2] if len(versions) > 1 else "",
           "newest": versions[-1] if versions else ""}
    if len(versions) < 2:
        return out
    previous, newest = versions[-2], versions[-1]

    def seen_in(version):
        counts = Counter()
        for s in by_version[version]:
            counts.update(set(s["fires"]))
        return counts
    seen_previous, seen_newest = seen_in(previous), seen_in(newest)
    for name, kind, ids in tracked_groups():
        flagged = [(i, seen_previous[i], seen_previous[i] / len(by_version[previous]))
                   for i in ids if seen_previous[i] and not seen_newest[i]]
        flagged.sort(key=lambda f: -f[1])
        out["groups"].append({"group": name, "kind": kind, "ids": len(ids),
                              "fired_previous": sum(1 for i in ids if seen_previous[i]),
                              "fired_newest": sum(1 for i in ids if seen_newest[i]),
                              "flagged": flagged})
    return out


def print_report(cov: dict, fire: dict, files: int, copies: int, errors: list,
                 data_version: str) -> None:
    print(f"# Game data check: {files} logs ({copies} copies skipped), "
          f"data built for {data_staleness.short_version(data_version) or '(no version)'}")
    for error in errors:
        print(f"  error: {error}")
    print("\n## Coverage by game version\n")
    print("| Version | Sessions | Line shown | Set ids / unknown | Armor ids / unknown "
          "(left out) | Weapon ids / unknown (left out) | Bar abilities / icon missing "
          "| Killing abilities / icon missing | Sets with no link |")
    print("|---|---|---|---|---|---|---|---|---|")
    for version, r in cov.items():
        print(f"| {version} | {r['sessions']} | {r['speaks']} | {r['sets']} / {len(r['sets_unknown'])} "
              f"| {r['armor']} / {len(r['armor_unknown'])} ({len(r['armor_left_out'])}) "
              f"| {r['weapons']} / {len(r['weapons_unknown'])} ({len(r['weapons_left_out'])}) "
              f"| {r['bars']} / {len(r['bar_icons_missing'])} "
              f"| {r['killers']} / {len(r['killer_icons_missing'])} | {len(r['unlinked_sets'])} |")
    for version, r in cov.items():
        details = []
        if r["sets_unknown"]:
            details.append(f"unknown sets {', '.join(r['sets_unknown'][:10])}")
        if r["armor_unknown"] or r["weapons_unknown"]:
            details.append(f"unknown items {', '.join((r['armor_unknown'] + r['weapons_unknown'])[:10])}")
        if r["armor_left_out"] or r["weapons_left_out"]:
            details.append("left out (plain low-level) "
                           f"{', '.join((r['armor_left_out'] + r['weapons_left_out'])[:10])}")
        if r["bar_icons_missing"]:
            details.append("bar icons missing " + ", ".join(
                f"{name} ({aid})" for aid, name in r["bar_icons_missing"][:10]))
        if r["unlinked_sets"]:
            details.append(f"no ESO-Hub link {', '.join(r['unlinked_sets'][:10])}")
        if r["status_lines"]:
            details.append("status lines " + "; ".join(f"{t!r} x{n}" for t, n in r["status_lines"]))
        if r["food_hint"]:
            details.append("food hint " + "; ".join(
                f"{e} {name} ({stem}) x{n}" for e, name, stem, n in r["food_hint"]))
        if details:
            print(f"\n{version}:")
            for line in details:
                print(f"- {line}")
    print("\n## Ids the app depends on, by game version\n")
    if not fire["previous"]:
        print("One game version only: nothing to compare.")
        return
    previous, newest = fire["previous"], fire["newest"]
    print(f"Previous {previous}: {fire['sessions'][previous]} sessions; "
          f"newest {newest}: {fire['sessions'][newest]} sessions.\n")
    print(f"| Group | Ids | Seen on {data_staleness.short_version(previous)} "
          f"| Seen on {data_staleness.short_version(newest)} | Flagged |")
    print("|---|---|---|---|---|")
    for g in fire["groups"]:
        print(f"| {g['group']} | {g['ids']} | {g['fired_previous']} | {g['fired_newest']} "
              f"| {len(g['flagged'])} |")
    flagged = [(g["group"], *f) for g in fire["groups"] for f in g["flagged"]]
    if flagged:
        print(f"\nFlagged: seen on {previous}, in no session of {newest} "
              f"(weak below {WEAK_SESSIONS} sessions):\n")
        for group, ability, n, share in sorted(flagged, key=lambda f: -f[2]):
            weak = " (weak)" if n < WEAK_SESSIONS else ""
            print(f"- {group}: {ability}, {n} sessions ({100 * share:.0f}%){weak}")
    else:
        print("\nNothing flagged.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, help="a folder of logs (default: the app's split folder)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--data-version", default=None,
                        help="judge against this version instead of data/version.json's")
    parser.add_argument("--limit", type=int, default=0, help="only the newest N files")
    parser.add_argument("--json", type=Path, help="also write the full results here")
    args = parser.parse_args(argv)
    folder = args.dir
    if folder is None:
        from dedupe_splits import config_split_dir
        folder = config_split_dir()
    if folder is None or not folder.is_dir():
        print(f"No folder of logs: {folder}", file=sys.stderr)
        return 1
    data_version = args.data_version
    shown_version = data_version if data_version is not None else \
        str(data_staleness.bundle_version().get("game_version") or "")
    sessions, files, copies, errors = collect(folder, args.workers, data_version, args.limit)
    cov, fire = coverage(sessions), fires(sessions)
    print_report(cov, fire, files, copies, errors, shown_version)
    if args.json:
        args.json.write_text(json.dumps({"coverage": cov, "fires": fire}, indent=1, default=list),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
