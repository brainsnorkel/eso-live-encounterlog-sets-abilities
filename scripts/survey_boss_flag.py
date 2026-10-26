#!/usr/bin/env python3
"""Survey the game's boss flag over a folder of encounter logs (issue #67).

For every BEGIN_COMBAT..END_COMBAT span it finds the boss-flagged hostiles
the group hit (monster id, name, max health, damage taken, first and last
hit) and prints, per zone, each flagged monster id with its health as a
share of the largest flagged unit in the same fight: a unit well under a
tenth of its fight's boss is a candidate for boss_units.BOSS_FLAG_ADDS. It
is a raw scan of the lines, not the engine, so it reads a 30 GB folder in
minutes; field positions are those of the raw CSV line (UNIT_ADDED: unit
id, type, local, session id, monster id, boss flag, ..., name, ..., owner,
reaction; COMBAT_EVENT: the source unit state from field 9, the target's
from field 19, each starting with the unit id and its health).

usage: python scripts/survey_boss_flag.py <logs dir> [workers]
"""
import json
import os
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

DAMAGE_RESULTS = {"DAMAGE", "CRITICAL_DAMAGE", "DOT_TICK", "DOT_TICK_CRITICAL",
                  "BLOCKED_DAMAGE", "DAMAGE_SHIELDED"}


def scan(path):
    """The fights of one log: [{zone, dur, flagged: [{mid, name, max_hp, dmg,
    first, last}], unflagged_n}]."""
    zone = ""
    fights = []
    units = {}
    players = set()
    owners = {}
    cur = None

    def close():
        flagged = []
        unflagged = 0
        for uid, rec in cur["hits"].items():
            u = units.get(uid)
            if u is None:
                continue
            if u["boss"]:
                flagged.append({"mid": u["mid"], "name": u["name"], "max_hp": u["max_hp"],
                                "dmg": rec["dmg"], "first": rec["first"] - cur["begin"],
                                "last": rec["last"] - cur["begin"]})
            else:
                unflagged += 1
        fights.append({"zone": zone, "dur": cur["end"] - cur["begin"], "flagged": flagged,
                       "unflagged_n": unflagged})

    with open(path, "r", encoding="utf-8", errors="replace", buffering=1 << 20) as fh:
        for line in fh:
            i = line.find(",")
            if i < 0:
                continue
            j = line.find(",", i + 1)
            kind = line[i + 1:j] if j > 0 else line[i + 1:].strip()
            if kind == "COMBAT_EVENT":
                if cur is None:
                    continue
                f = line.rstrip("\n").split(",")
                if len(f) < 21 or f[2] not in DAMAGE_RESULTS:
                    continue
                src, tgt = f[9], f[19]
                if tgt == "*":
                    tgt = src
                u = units.get(tgt)
                if u is None or u["reaction"] != "HOSTILE":
                    continue
                if src not in players and owners.get(src) not in players:
                    continue
                try:
                    hit = int(f[5])
                    mx = int(f[20].split("/")[1])
                except (ValueError, IndexError):
                    continue
                u["max_hp"] = max(u["max_hp"], mx)
                ts = int(f[0])
                rec = cur["hits"].get(tgt)
                if rec is None:
                    rec = cur["hits"][tgt] = {"dmg": 0, "first": ts, "last": ts}
                rec["dmg"] += hit
                rec["last"] = ts
            elif kind == "UNIT_ADDED":
                f = line.rstrip("\n").split(",")
                if len(f) < 17:
                    continue
                uid = f[2]
                if f[3] == "PLAYER":
                    players.add(uid)
                    units.pop(uid, None)
                    continue
                if f[15] != "0":
                    owners[uid] = f[15]
                else:
                    owners.pop(uid, None)
                units[uid] = {"mid": f[6], "boss": f[7] == "T", "name": f[10].strip('"'),
                              "reaction": f[16], "max_hp": 0}
            elif kind == "UNIT_CHANGED":
                f = line.rstrip("\n").split(",")
                if len(f) > 11 and f[2] in units:
                    units[f[2]]["reaction"] = f[11]
            elif kind == "BEGIN_COMBAT":
                cur = {"begin": int(line[:i]), "hits": {}}
            elif kind in ("END_COMBAT", "END_LOG", "BEGIN_LOG"):
                if cur is not None:
                    cur["end"] = int(line[:i])
                    close()
                    cur = None
            elif kind == "ZONE_CHANGED":
                f = line.rstrip("\n").split(",")
                zone = f[3].strip('"') if len(f) > 3 else ""
    return fights


def main():
    folder = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    paths = sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".log"))
    paths.sort(key=os.path.getsize, reverse=True)
    fights = []
    seen = set()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for k, result in enumerate(pool.map(scan, paths), 1):
            for f in result:
                # The splitter can write a session twice: count a fight once
                key = json.dumps(f, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    fights.append(f)
            if k % 50 == 0:
                print(f"{k}/{len(paths)} logs", file=sys.stderr, flush=True)
    per_mid = defaultdict(lambda: {"fights": 0, "hp": [], "ratio": [], "span": [], "alone": 0})
    for f in fights:
        if not f["flagged"]:
            continue
        biggest = max(u["max_hp"] for u in f["flagged"])
        by_mid = {}
        for u in f["flagged"]:
            by_mid.setdefault((f["zone"], u["mid"], u["name"]), []).append(u)
        for key, us in by_mid.items():
            rec = per_mid[key]
            rec["fights"] += 1
            hp = max(u["max_hp"] for u in us)
            rec["hp"].append(hp)
            rec["ratio"].append(hp / biggest if biggest else 0)
            rec["span"].append(statistics.median((u["last"] - u["first"]) / 1000 for u in us))
            if len(by_mid) == 1:
                rec["alone"] += 1
    print(f"{len(paths)} logs, {len(fights)} fights, "
          f"{sum(1 for f in fights if f['flagged'])} that hit a boss-flagged unit\n")
    print("zone, monster id, name: fights, median max health, median and lowest share of the "
          "fight's largest flagged unit, median seconds hit, fights where it was the only "
          "flagged unit")
    for key in sorted(per_mid, key=lambda k: (k[0], -statistics.median(per_mid[k]["hp"]))):
        rec = per_mid[key]
        print(f"{key[0]:<28} {key[1]:>7} {key[2]:<36} n={rec['fights']:<4} "
              f"hp={statistics.median(rec['hp']):>12,.0f} share={statistics.median(rec['ratio']):.2f} "
              f"min={min(rec['ratio']):.2f} hit={statistics.median(rec['span']):>5.0f}s "
              f"alone={rec['alone']}")
    print("\nunder a tenth of the fight's largest flagged unit (BOSS_FLAG_ADDS candidates):")
    for key in sorted(per_mid):
        low = sum(1 for r in per_mid[key]["ratio"] if r < 0.10)
        if low:
            print(f"{key[0]:<28} {key[1]:>7} {key[2]:<36} in {low} of {per_mid[key]['fights']} fights")


if __name__ == "__main__":
    main()
