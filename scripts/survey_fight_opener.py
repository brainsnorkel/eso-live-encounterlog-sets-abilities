#!/usr/bin/env python3
"""Survey who opens fights over a folder of encounter logs (issue #159).

It replays every log through the app's own engine (src/esolog_tail.py), so
it counts exactly what the fight pane's opener line would say, with none of
the caps the first survey had (12 monster actions before the line, 40
events after it, a 30 s window). Per kind of group it prints how fights
open: a player first, a monster first (with a player's cast already on its
way, or not), nobody, and of the player-first fights the taunts, the
openers before BEGIN_COMBAT, those at the memory's edge and the lines that
carry a time. A trial is a fight with 9 or more player rows, a dungeon 3 to
8, solo or duo fewer, an arena any fight in fight_opener.ARENA_ZONES.

usage: python scripts/survey_fight_opener.py <logs dir | log ...> [--workers N]
           [--margin MS] [--survey-rules] [--dump out.jsonl]

--margin sets the monster-first margin (fight_opener.OPENER_MONSTER_MARGIN_MS,
100 ms); --survey-rules turns off the dead-enemy drop and the list of
scripted mechanics, the first survey's rules, for comparing against it;
--dump writes one JSON line per fight (log, start, zone, players, opener,
monster_first). It reads the logs only.
"""
import contextlib
import io
import json
import os
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def replay(job):
    """The fights of one log: [{log, start, zone, players, opener,
    monster_first}], the last publish of a fight the game cut in two."""
    path, margin, survey_rules = job
    sys.path.insert(0, SRC)
    os.chdir(os.path.dirname(SRC))  # the engine reads data/ beside src/
    from esolog_tail import ESOLogAnalyzer, FightHistory
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.track_buff_timeline = False
    if margin is not None:
        analyzer.opener.margin_ms = margin
    if survey_rules:
        analyzer.opener.drop_gone = False
        analyzer.opener.scripted = False
    fights = {}
    publish = analyzer._publish_fight

    def recording_publish(zone_name=None, *args, **kwargs):
        start = analyzer.current_encounter.start_time
        result = publish(zone_name, *args, **kwargs)
        entry = analyzer._last_fight_entry
        if entry is not None:
            fights[start] = {
                "log": os.path.basename(path), "start": start, "zone": entry.zone_name,
                "players": sum(1 for p in entry.players if not p.get("companion")),
                "opener": entry.opener, "monster_first": entry.monster_first}
        return result

    analyzer._publish_fight = recording_publish
    with contextlib.redirect_stdout(io.StringIO()), \
            open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            entry = analyzer.log_parser.parse_line(line.rstrip("\n"))
            if entry is not None:
                analyzer.process_log_entry(entry)
    return list(fights.values())


def group_of(fight, arenas) -> str:
    if fight["zone"] in arenas:
        return "arena"
    if fight["players"] >= 9:
        return "trial"
    return "dungeon" if fight["players"] >= 3 else "solo or duo"


def report(fights, arenas, time_text) -> None:
    groups = ("all", "trial", "dungeon", "solo or duo", "arena")
    rows = {g: Counter() for g in groups}
    leads = []
    for fight in fights:
        opener, monster = fight["opener"], fight["monster_first"]
        for g in ("all", group_of(fight, arenas)):
            row = rows[g]
            row["fights"] += 1
            if monster:
                row["monster first"] += 1
                row["  a cast already on its way"] += bool(monster.get("in_flight"))
            elif opener:
                row["player first"] += 1
                row["  taunted"] += opener.get("kind") == "taunt"
                row["  before BEGIN_COMBAT"] += opener.get("time_ms", 0) < 0
                row["  at the memory's edge"] += bool(opener.get("edge"))
                row["  a time shown"] += bool(not opener.get("edge") and time_text(
                    opener.get("time_ms", 0), fight["zone"] in arenas))
            else:
                row["nobody"] += 1
        if opener and not monster and opener.get("time_ms", 0) < 0:
            leads.append(-opener["time_ms"])
    keys = ["fights", "player first", "  taunted", "  before BEGIN_COMBAT", "  at the memory's edge",
            "  a time shown", "monster first", "  a cast already on its way", "nobody"]
    print(f"{'':30}" + "".join(f"{g:>13}" for g in groups))
    for key in keys:
        cells = []
        for g in groups:
            n, total = rows[g][key], rows[g]["fights"]
            cells.append(f"{n:>7} {100 * n / total:4.1f}%" if key != "fights" and total
                         else f"{n:>13}")
        print(f"{key:30}" + "".join(cells))
    if leads:
        print(f"lead of a player-first opener before BEGIN_COMBAT: median {statistics.median(leads):.0f} ms, "
              f"{len(leads)} fights")


def main():
    args = sys.argv[1:]
    workers, margin, survey_rules, dump, paths = max(1, (os.cpu_count() or 2) - 2), None, False, None, []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--workers", "--margin", "--dump"):
            value = args[i + 1]
            if arg == "--workers":
                workers = int(value)
            elif arg == "--margin":
                margin = int(value)
            else:
                dump = value
            i += 2
            continue
        if arg == "--survey-rules":
            survey_rules = True
        elif os.path.isdir(arg):
            paths.extend(os.path.join(arg, name) for name in sorted(os.listdir(arg))
                         if name.endswith(".log"))
        else:
            paths.append(arg)
        i += 1
    if not paths:
        sys.exit(__doc__)
    sys.path.insert(0, SRC)
    from fight_opener import ARENA_ZONES, time_text
    paths.sort(key=lambda p: -os.path.getsize(p))  # the longest first, for the pool
    fights = []
    with ProcessPoolExecutor(workers) as pool:
        for log_fights in pool.map(replay, [(p, margin, survey_rules) for p in paths]):
            fights.extend(log_fights)
    if dump:
        with open(dump, "w", encoding="utf-8") as out:
            out.writelines(json.dumps(fight) + "\n" for fight in fights)
    print(f"{len(paths)} logs, {len(fights)} fights"
          + (", the first survey's rules" if survey_rules else ""))
    report(fights, ARENA_ZONES, time_text)


if __name__ == "__main__":
    main()
