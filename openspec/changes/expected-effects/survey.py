"""Survey for issue #13 (python -I survey.py <src dir> <out.json>): per fight of a
fixed sample of the split logs, how many players, and which default rules were
seen at all. Read-only over D:/esologs/splits; summarise the JSON as design.md does."""
import json
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(SRC))

from esolog_tail import ESOLogAnalyzer, AnalyzerListener  # noqa: E402
from fight_history import FightHistory  # noqa: E402
from effect_rules import EffectTracker, parse_rules, DEFAULT_RULES  # noqa: E402

SPLITS = Path("D:/esologs/splits")
EVERY = 10
BUDGET = 1500 * 1024 * 1024

names = sorted(p.name for p in SPLITS.glob("*.log"))
sample, total = [], 0
for i, name in enumerate(names):
    if i % EVERY:
        continue
    size = (SPLITS / name).stat().st_size
    if total + size > BUDGET:
        continue
    sample.append(name)
    total += size
print(f"{len(sample)} logs, {total/1e6:.0f} MB", flush=True)


class Capture(AnalyzerListener):
    def __init__(self):
        self.fights = []

    def on_fight_completed(self, entry):
        self.fights.append(entry)

    def on_fight_updated(self, entry):
        pass

    def on_zone_changed(self, zone, difficulty):
        pass


rows = []
for name in sample:
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.effect_tracker = EffectTracker(parse_rules(DEFAULT_RULES)[0])
    analyzer.current_log_file = str(SPLITS / name)
    cap = Capture()
    analyzer.add_listener(cap)
    with open(SPLITS / name, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            entry = analyzer.log_parser.parse_line(line)
            if entry:
                analyzer.process_log_entry(entry)
    for e in cap.fights:
        rows.append({
            "log": name, "zone": e.zone_name, "boss": e.boss_name,
            "duration_s": e.duration_s, "players": len(e.players),
            "items": {t["name"]: {"uptime": t["uptime_pct"], "stacks": t["avg_stacks"],
                                  "reached": t["mobs_reached"], "units": t["units"]}
                      for t in e.tracked},
        })
    print(f"{name}: {len(cap.fights)} fights", flush=True)

OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(f"wrote {OUT} ({len(rows)} fights)")
