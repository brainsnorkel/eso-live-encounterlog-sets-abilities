#!/usr/bin/env python3
"""Survey the Class Masteries the engine shows over a set of encounter logs
(issue #149), for generate_class_passives.MASTERIES_TAKEN.

Each log is replayed through the engine (src/), as the app reads it, and
every fight's rows of pure-class players are kept: class, role, the lines
and the masteries shown. A character is one handle and character name in a
log (an anonymous player one unit id and class, as the engine can tell no
more). It prints:

- how many rows show none, one, two or more masteries, by class, and how
  many of the rows with one are fights before the second showed later in
  the same log;
- the characters who never showed a second, by class, role and mastery;
- MASTERIES_TAKEN: for each class and role, how many characters were seen
  with each mastery among those that showed two, each character counted
  once, in the role of their longest log. Paste it into the generator and
  run that to rebuild the order.

It is the engine's whole replay, so a log takes seconds to a minute; the
logs run in parallel processes.

usage: python scripts/survey_masteries.py [--workers N] <log> [<log> ...]
"""
import argparse
import contextlib
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
ROLES = ("D", "H", "T")


def replay(path):
    """[(fight index, [row])] of one log, rows cut down to what the survey
    reads; a fight the engine announced again is kept once, as it ended."""
    sys.path.insert(0, str(SRC))
    from engine_events import AnalyzerListener
    from esolog_tail import ESOLogAnalyzer
    from fight_history import FightHistory

    entries = {}

    class Listener(AnalyzerListener):
        def on_fight_completed(self, entry):
            entries[id(entry)] = entry

    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.current_log_file = path
    analyzer.add_listener(Listener())
    # The engine prints each zone change to the console
    with open(path, "r", encoding="utf-8", errors="replace", buffering=1 << 20) as fh, \
            open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
        for line in fh:
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
    keep = ("name", "character", "unit_id", "class_name", "role", "skill_lines", "class_lines",
            "masteries")
    return [[{key: row.get(key) for key in keep} for row in entry.players
             if not row.get("companion")] for entry in entries.values()]


def characters(fights):
    """{character key: [row, one per fight in order]} for the pure-class
    players of one log's fights."""
    seen = defaultdict(list)
    for rows in fights:
        for row in rows:
            lines = set(row.get("skill_lines") or [])
            if not lines or lines != set(row.get("class_lines") or []):
                continue
            if row.get("name") == "anon":
                key = ("anon", f"{row.get('unit_id')}:{row.get('class_name')}")
            else:
                key = (row.get("name"), row.get("character"))
            seen[key].append(row)
    return seen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("logs", nargs="+")
    args = parser.parse_args(argv)
    logs = sorted(args.logs, key=lambda p: -os.path.getsize(p))

    by_class = defaultdict(Counter)   # class -> masteries shown on a row -> rows
    early = 0                         # rows with one where the log later shows two
    never = Counter()                 # (class, role, mastery) -> characters with one only
    pairs = {}                        # character -> (rows, class, role, two masteries)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for path, fights in zip(logs, pool.map(replay, logs)):
            for key, rows in characters(fights).items():
                if key[0] == "anon":
                    key = (path,) + key  # no telling one log's from another's
                union = []
                for row in rows:
                    union.extend(m for m in row.get("masteries") or [] if m not in union)
                for row in rows:
                    shown = len(row.get("masteries") or [])
                    by_class[row["class_name"]][min(shown, 3)] += 1
                    early += shown == 1 and len(union) >= 2
                role = Counter(row.get("role") for row in rows).most_common(1)[0][0]
                if len(union) == 1:
                    never[(rows[-1]["class_name"], role, union[0])] += 1
                elif len(union) == 2 and len(rows) > pairs.get(key, (0,))[0]:
                    pairs[key] = (len(rows), rows[-1]["class_name"], role, union)
            print(f"{Path(path).name}: {len(fights)} fights", file=sys.stderr)

    print("Pure-class rows by masteries shown (0, 1, 2, 3+):")
    for class_name in sorted(by_class):
        counts = by_class[class_name]
        total = sum(counts.values())
        print(f"  {class_name:13s} {total:6d} rows  {counts[0]:5d} {counts[1]:5d} "
              f"({counts[1] / total:.0%}) {counts[2]:6d} {counts[3]:3d}")
    print(f"  rows with one where the same log later shows two: {early}")
    print("Characters who never showed a second (class, role, mastery):")
    for (class_name, role, mastery), count in sorted(never.items()):
        print(f"  {class_name} {role} {mastery}: {count}")

    taken = defaultdict(lambda: {role: Counter() for role in ROLES})
    for _rows, class_name, role, union in pairs.values():
        if role in ROLES:
            taken[class_name][role].update(union)
    print(f"MASTERIES_TAKEN ({len(pairs)} characters with two) = {{")
    for class_name in sorted(taken):
        print(f"    {class_name!r}: {{")
        for role in ROLES:
            counts = ", ".join(f"{name!r}: {count}" for name, count in taken[class_name][role].most_common())
            print(f"        {role!r}: {{{counts}}},")
        print("    },")
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
