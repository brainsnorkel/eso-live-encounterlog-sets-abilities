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
splitter wrote count once: every file is hashed first and only the largest
copy of each is read, so a truncated split never stands in for its complete
copy. Zipped splits (``*.log.zip``) are read too. The bars are judged with
the slots the engine builds (a Rampage shown as its morph), so the coverage
is the app's own.
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
from contextlib import contextmanager
from functools import lru_cache
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
from log_open import NoLogInZip, is_zip, log_members, log_size
from player_build import (
    ARMOR_SLOTS,
    WEAPON_SLOTS,
    _set_id,
    armor_weight,
    food_ids,
    weapon_type,
)

HEAD_BYTES = 256 * 1024
DEATHS = (b"DIED", b"KILLING_BLOW")
# A flag on an id the previous version saw in fewer sessions than this is weak
WEAK_SESSIONS = 3
# Form effects and casts that tell a werewolf's morph (werewolf.py), which
# the engine shows in place of a Rampage on the bar
FORM_EFFECT_BYTES = frozenset(i.encode() for i in werewolf.FORM_EFFECTS)
MORPH_CAST_BYTES = frozenset(i.encode() for i in {*werewolf.TRANSFORM_CASTS, *werewolf.STAND_INS})


@lru_cache(maxsize=1)
def tracked_groups() -> tuple:
    """(group, kind, ids) for every id the app depends on; kind is 'ability'
    (an effect, hit, cast or PLAYER_INFO id), 'set' (a worn set's id) or
    'monster' (a unit's monster id). Built once per process."""
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
    return tuple((name, kind, frozenset(str(i) for i in ids)) for name, kind, ids in groups)


@lru_cache(maxsize=1)
def _tracked_ids() -> tuple:
    """(ability ids, the same as bytes, set ids, monster ids as bytes), the
    union of tracked_groups by kind, built once per process."""
    groups = tracked_groups()

    def of(kind):
        return frozenset().union(*(ids for _name, k, ids in groups if k == kind))
    abilities = of("ability")
    return (abilities, frozenset(i.encode() for i in abilities), of("set"),
            frozenset(i.encode() for i in of("monster")))


@contextmanager
def open_binary(path: Path):
    """A binary stream of the log, or of the one log in a zipped split, by
    log_open's rules (a zip told by its content, its .log members); None for
    a zip that does not hold exactly one log. Closed on exit, zip included."""
    if is_zip(path):
        members = log_members(path)
        if len(members) != 1:
            yield None
            return
        with zipfile.ZipFile(path) as archive, archive.open(members[0]) as stream:
            yield stream
    else:
        with open(path, "rb") as stream:
            yield stream


def head_hash(path: Path) -> str | None:
    """A hash of the log's first 256 KB; None when *path* holds no single log."""
    with open_binary(path) as stream:
        return None if stream is None else hashlib.sha1(stream.read(HEAD_BYTES)).hexdigest()


def _csv(raw: bytes) -> list:
    return next(csv.reader(io.StringIO(raw.decode("utf-8", "replace"))))


class _Session:
    def __init__(self, version: str, data_version: str | None):
        self.version = version
        # None reads the bundle's version, as the app does
        self.tracker = data_staleness.DataCheckTracker(data_version=data_version)
        self.tracker.reset(version)
        # The players' morphs, for the slot the engine shows for a Rampage
        self.werewolf = werewolf.WerewolfTracker()
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
    ability_ids, ability_bytes, set_ids, monster_bytes = _tracked_ids()
    food = food_ids()
    parser = ESOLogParser()
    names, icons = {}, {}
    sessions = []
    session = None
    with open_binary(path) as stream:
        if stream is None:
            return []
        for raw in stream:
            c1 = raw.find(b",")
            if c1 < 0:
                continue
            c2 = raw.find(b",", c1 + 1)
            event = raw[c1 + 1:c2] if c2 > 0 else b""
            if event == b"EFFECT_CHANGED":
                if session is not None:
                    fields = raw.split(b",", 7)
                    ability = fields[5]
                    if ability in ability_bytes:
                        session.fires[ability.decode()] += 1
                    if ability in FORM_EFFECT_BYTES:
                        # on the target, or the source when the line says *
                        full = raw.split(b",")
                        target = full[6] if full[16].strip() == b"*" else full[16]
                        session.werewolf.note_effect(target.decode(), fields[2].decode(),
                                                     ability.decode(), int(fields[0]))
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
                    fields = raw.split(b",", 7)
                    if len(fields) > 6:
                        if fields[5] in ability_bytes:
                            session.fires[fields[5].decode()] += 1
                        if fields[5] in MORPH_CAST_BYTES:
                            session.werewolf.note_cast(fields[6].decode(), fields[5].decode(),
                                                       int(fields[0]))
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


def bar_slots(session, unit_id: str, bars: list, names: dict, icons: dict) -> list:
    """The slots the engine builds for a bar (ESOLogAnalyzer._bar_slots and
    _ability_slot): an id the log has not named is skipped, and a Rampage is
    shown as the morph it stands in for, with the morph's icon (the log's,
    else werewolf.SKILLS'). A scribed skill's icon needs nothing more: its
    slot takes the stem of the same ABILITY_INFO line (scribing.slot_fields)."""
    session.werewolf.note_bars(unit_id, bars)
    slots = []
    for ability in bars:
        morph = session.werewolf.stand_in_for(unit_id, ability)
        if morph:
            name, icon = werewolf.SKILLS.get(morph, ("", ""))
            slots.append({"id": morph, "name": names.get(morph) or name,
                          "icon": icons.get(morph) or icon})
        elif ability in names:
            slots.append({"id": ability, "name": names[ability], "icon": icons.get(ability, "")})
    return slots


def _note_player(session, info, names, icons, food, ability_ids, set_ids) -> None:
    bars = [str(a) for a in list(info.champion_points) + list(info.additional_data)]
    slots = bar_slots(session, str(info.unit_id), bars, names, icons)
    session.tracker.note_player(info.gear_data, slots)
    session.bars.update(bars)
    for item in info.gear_data:
        if len(item) < 7:
            continue
        slot, item_id, set_id = str(item[0]), str(item[1]), _set_id(item)
        if set_id:
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


def _hash(path: Path):
    """(path, head hash or None, the log's size, error or '') for one file."""
    try:
        digest = head_hash(path)
        return path, digest, log_size(path) if digest else 0, ""
    except (OSError, ValueError, zipfile.BadZipFile, NoLogInZip) as exc:
        return path, None, 0, repr(exc)


def pick_logs(hashed) -> tuple:
    """From (path, digest, size) of every log, one per digest: the largest
    copy, so a truncated split that shares its head with a complete copy
    never stands in for it (ties go to the later name). Returns (the logs
    kept, largest first, copies dropped)."""
    best = {}
    for path, digest, size in hashed:
        kept = best.get(digest)
        if kept is None or (size, str(path)) > (kept[1], str(kept[0])):
            best[digest] = (path, size)
    kept = sorted(best.values(), key=lambda pair: (pair[1], str(pair[0])), reverse=True)
    return [path for path, _size in kept], len(hashed) - len(best)


def _work(job):
    path, data_version = job
    try:
        return str(path), scan(path, data_version)
    except Exception as exc:  # noqa: BLE001 - one bad file does not stop the run
        return str(path), [{"error": repr(exc)}]


def collect(folder: Path, workers: int, data_version: str | None, limit: int = 0):
    """(sessions, files read, copies skipped, errors) over the folder. Every
    file is hashed first, cheaply; only the copy kept per hash is scanned."""
    paths = sorted(p for p in folder.iterdir()
                   if p.is_file() and (p.suffix.lower() == ".log" or p.name.lower().endswith(".log.zip")))
    if limit:
        paths = paths[-limit:]
    sessions, errors = [], []
    with Pool(max(1, workers)) as pool:
        hashed = list(pool.imap_unordered(_hash, paths))
        errors += [f"{path.name}: {error}" for path, _digest, _size, error in hashed if error]
        logs, copies = pick_logs([(path, digest, size) for path, digest, size, _error in hashed
                                  if digest])
        for path, found in pool.imap_unordered(_work, [(p, data_version) for p in logs]):
            for result in found:
                if "error" in result:
                    errors.append(f"{Path(path).name}: {result['error']}")
                else:
                    result["file"] = Path(path).name
                    sessions.append(result)
    sessions.sort(key=lambda s: s["file"])
    return sessions, len(logs), copies, errors


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
        flagged.sort(key=lambda f: (-f[1], f[0]))  # ties by id, so reruns agree
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
        for group, ability, n, share in sorted(flagged, key=lambda f: (-f[2], f[0], f[1])):
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
