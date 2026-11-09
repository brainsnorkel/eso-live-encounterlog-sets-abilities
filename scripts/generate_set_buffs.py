#!/usr/bin/env python3
"""
Generate data/sets/set_buffs.json: the Major and Minor buffs a set's bonus
grants, by the ability id the encounter log writes for them, so the uptime
line can name the set behind a "Major Slayer" or a "Major Courage" (issue
#79, decision 5).

The log names a buff and never the set it came from, and the game's files
hold no link between the two. UESP's mined skills were the first plan:
findSetBonusSkills.php writes a set's name into minedSkills.setName by
matching the bonus text against ability descriptions. Checked on 2026-10-31
against 395 split logs, that column ties each set to the effect named after
the set ("Pillager's Profit", 184 of 216 sets worn), which the uptime line
already shows under the set's name, and misses the generic buffs: of 58
Major or Minor buffs the logs tie to one set, one was in UESP's table
(Roaring Opportunist got 135920, while its Major Slayer is 93109 and
135923). A generic buff's description never matches a bonus's text.

So this script reads split logs instead. Most sources write a Major or
Minor buff under an id of their own: Roaring Opportunist's Major Slayer is
135923, War Machine's 93442, Master Architect's 93120. Some ids are shared:
the wearers of all three also write 93109 (in 96%, 91% and 91% of their
sessions). Only an id that one set writes can name it. Per log session and player it
takes the sets the player had active (``piece_counts``, a perfected set and
its base counted together, as the game counts them) and every effect id the
player was the source of (EFFECT_CHANGED). A buff id is tied to a set when
all of these hold:

1. Its name ("Major Courage") is in that set's bonus text
   (data/sets/bonuses_en.json), on a bonus whose pieces the player wears.
   This drops the buffs that only ride along with what is worn beside the
   set: Jorvuld's Guidance wearers source Roaring Opportunist's Major Slayer
   in 86% of sessions, because the two are worn together.
2. At least WEARER_SHARE of the sessions wearing the set source it.
3. At most OTHER_SHARE of the sessions wearing no set that names the buff
   source it, so an id that something else writes too is not taken:
   Mender's Ward wearers source Major Vitality 61713 in 95% of sessions, but
   so do 3.8% of everyone else; the set's own 113653 is sourced by no one
   else. Every link that reads right sat at 0.7% or below. Leaving out every
   set that names the buff lets two sets share a buff name with their own
   ids (Spell Power Cure's Major Courage 66902, Olorime's 109994).
4. At least MIN_SESSIONS sessions wear the set.

An id that passes for two sets names neither and is left out (printed, not
written).

It knows only sets someone in the logs wore MIN_SESSIONS times, and reads
the bonus text of the bundled snapshot. Byte-identical copies of one split
(issue #85) are read once. The output holds ids and the game's names only,
nothing about the players.

Run after a patch, or when the logs hold more sets, then review the printed
table before committing the file:
    python scripts/generate_set_buffs.py                    # the app's split folder
    python scripts/generate_set_buffs.py --dir D:/esologs/splits
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
BONUSES_PATH = REPO_ROOT / "data" / "sets" / "bonuses_en.json"
OUT_PATH = REPO_ROOT / "data" / "sets" / "set_buffs.json"
BUFF_RE = re.compile(r"\b(?:Major|Minor) [A-Z][a-z]+\b")
PERFECTED = "Perfected "
WEARER_SHARE = 0.7  # of the sessions wearing the set that source the buff
OTHER_SHARE = 0.01  # of the sessions wearing no set that names the buff
MIN_SESSIONS = 5  # sessions wearing the set, for the shares to mean anything
METHOD = (f"named in the set's bonus text, sourced in at least {WEARER_SHARE:.0%} of the sessions "
          f"wearing the set and at most {OTHER_SHARE:.0%} of those wearing no set that names it, "
          f"from at least {MIN_SESSIONS} sessions (scripts/generate_set_buffs.py)")


def base_name(name: str) -> str:
    return name.removeprefix(PERFECTED)


def set_families(bonus_sets: dict):
    """({base set name: [set ids]}, {base set name: {buff name: pieces}},
    {set id: base set name}) from the bundled bonus text. A perfected set
    and its base set are one family; a buff's pieces are the fewest of any
    bonus line that names it."""
    ids, buffs, family_of = defaultdict(list), defaultdict(dict), {}
    for set_id, entry in bonus_sets.items():
        family = base_name(entry.get("name") or "")
        if not family:
            continue
        ids[family].append(str(set_id))
        family_of[str(set_id)] = family
        for bonus in entry.get("bonuses") or ():
            for name in BUFF_RE.findall(bonus.get("text") or ""):
                pieces = int(bonus.get("pieces") or 0)
                buffs[family][name] = min(buffs[family].get(name, pieces), pieces)
    return ({f: sorted(v, key=int) for f, v in ids.items()},
            {f: v for f, v in buffs.items() if v}, family_of)


def family_pieces(gear: dict, family_of: dict) -> dict:
    """{family: pieces active on the better bar} for one PLAYER_INFO's gear."""
    from player_build import piece_counts
    front, back = Counter(), Counter()
    for set_id, (on_front, on_back) in piece_counts(gear).items():
        family = family_of.get(set_id)
        if family:
            front[family] += on_front
            back[family] += on_back or 0
    return {f: max(front[f], back[f]) for f in set(front) | set(back)}


def read_sessions(lines, family_of: dict, names: dict):
    """[(worn, sourced)] per player per log session of one log: worn is
    {family: pieces} at the most any PLAYER_INFO of the session showed,
    sourced the effect ids the player was the source of. Fills *names*
    from ABILITY_INFO."""
    from eso_log_parser import ESOLogParser
    parser = ESOLogParser()
    sessions = []
    worn, sourced = defaultdict(dict), defaultdict(set)

    def close():
        sessions.extend((worn[unit], sourced[unit]) for unit in worn)

    for line in lines:
        head = line[:40]
        if ",EFFECT_CHANGED," in head:
            fields = line.split(",", 7)
            if len(fields) > 6:
                sourced[fields[6]].add(fields[5])
        elif ",ABILITY_INFO," in head:
            fields = line.split(",", 4)
            if len(fields) > 3:
                names.setdefault(fields[2], fields[3].strip('"'))
        elif ",PLAYER_INFO," in head:
            entry = parser.parse_line(line.rstrip("\r\n"))
            info = parser.parse_player_info(entry) if entry else None
            if info is None:
                continue
            gear = {item[0]: item for item in info.gear_data}
            seen = worn[info.unit_id]
            for family, pieces in family_pieces(gear, family_of).items():
                seen[family] = max(seen.get(family, 0), pieces)
        elif ",BEGIN_LOG," in head:
            close()
            worn, sourced = defaultdict(dict), defaultdict(set)
    close()
    return sessions


def tie_buffs(sessions, family_buffs: dict, names: dict):
    """({buff id: (family, buff name, sessions wearing, wearer share, other
    share)}, {buff id: [families]} for the ids two sets passed for)."""
    ids_named = defaultdict(set)
    for ability_id, name in names.items():
        ids_named[name].add(ability_id)
    naming = defaultdict(dict)  # buff name -> {family: pieces}
    for family, buffs in family_buffs.items():
        for name, pieces in buffs.items():
            naming[name][family] = pieces
    passed = defaultdict(list)
    for name, families in naming.items():
        ids = ids_named.get(name)
        if not ids:
            continue
        others = [sourced for worn, sourced in sessions
                  if not any(worn.get(f, 0) >= p for f, p in families.items())]
        other_share = {a: sum(a in s for s in others) / len(others) if others else 0.0 for a in ids}
        ids = [a for a in ids if other_share[a] <= OTHER_SHARE]
        for family, pieces in families.items():
            wearing = [sourced for worn, sourced in sessions if worn.get(family, 0) >= pieces]
            if len(wearing) < MIN_SESSIONS:
                continue
            for ability_id in ids:
                share = sum(ability_id in s for s in wearing) / len(wearing)
                if share >= WEARER_SHARE:
                    passed[ability_id].append((family, name, len(wearing), share, other_share[ability_id]))
    tied = {a: rows[0] for a, rows in passed.items() if len(rows) == 1}
    shared = {a: sorted(row[0] for row in rows) for a, rows in passed.items() if len(rows) > 1}
    return tied, shared


def render(tied: dict, family_ids: dict, generated: str, source: str) -> str:
    lines = ["{",
             f' "generated": {json.dumps(generated)},',
             f' "source": {json.dumps(source)},',
             f' "method": {json.dumps(METHOD)},',
             f' "count": {len(tied)},',
             ' "buffs": {']
    items = sorted(tied.items(), key=lambda kv: int(kv[0]))
    for n, (ability_id, (family, name, wearing, share, other)) in enumerate(items):
        row = {"name": name, "set": family, "set_ids": family_ids[family],
               "sessions": wearing, "wearers": round(share, 2), "others": round(other, 3)}
        comma = "," if n < len(items) - 1 else ""
        lines.append(f'  {json.dumps(ability_id)}: {json.dumps(row, ensure_ascii=False)}{comma}')
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def split_logs(folder: Path):
    """The split logs in *folder*, a byte-identical copy of another and the
    splitter's -temp.log of a session still being written left out."""
    from dedupe_splits import find_copies, split_key
    copies = {copy for _kept, found in find_copies(folder) for copy in found}
    return sorted(Path(entry.path) for entry in os.scandir(folder)
                  if entry.is_file() and split_key(entry.name) is not None
                  and Path(entry.path) not in copies)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, help="the split folder (default: the app's setting)")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)
    from dedupe_splits import config_split_dir
    folder = args.dir or config_split_dir()
    if folder is None or not folder.is_dir():
        print(f"No split folder: {folder}", file=sys.stderr)
        return 1
    bonus_sets = json.loads(BONUSES_PATH.read_text(encoding="utf-8"))["sets"]
    family_ids, family_buffs, family_of = set_families(bonus_sets)
    logs = split_logs(folder)
    names, sessions = {}, []
    for n, path in enumerate(logs, 1):
        with open(path, encoding="utf-8", errors="replace") as fh:
            sessions.extend(read_sessions(fh, family_of, names))
        print(f"\r{n}/{len(logs)} logs, {len(sessions)} player sessions", end="", file=sys.stderr)
    print(file=sys.stderr)
    if not sessions:
        print("No player sessions in those logs; not writing", file=sys.stderr)
        return 1
    tied, shared = tie_buffs(sessions, family_buffs, names)
    for ability_id, (family, name, wearing, share, other) in sorted(tied.items(), key=lambda kv: kv[1][:2]):
        print(f"{ability_id:>7} {name:22} {family:34} {wearing:5} sessions, "
              f"{share:.0%} of wearers, {other:.1%} of others")
    for ability_id, families in sorted(shared.items()):
        print(f"{ability_id:>7} {names.get(ability_id, '?'):22} left out, passed for {', '.join(families)}")
    source = f"{len(logs)} split logs, {len(sessions)} player sessions"
    args.out.write_text(render(tied, family_ids, datetime.now(timezone.utc).isoformat(timespec="seconds"), source),
                        encoding="utf-8")
    print(f"Wrote {args.out}: {len(tied)} buffs across {len({row[0] for row in tied.values()})} sets "
          f"from {source}; {len(shared)} left out as shared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
