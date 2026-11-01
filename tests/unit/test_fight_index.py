#!/usr/bin/env python3
"""The fight history across sessions (fight_index, issue #170): the line a
fight writes, the file, the comparison sets, a player's own history, the
run's best kill with this roster, and the backfill from split logs."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import fight_index as fi
from fight_history import FightHistoryEntry

ROSTER = [f"@p{i}" for i in range(12)]


class _Mask:
    def text(self, name):
        name = str(name or "")
        return "@▒▒" if name.startswith("@") and name != "@p0" else name


def _entry(start_s, outcome="kill", boss="Lord Falgravn", roster=ROSTER, version="eso.live.12.1",
           boss_dps=450_000.0, difficulty="VETERAN", rows=None):
    entry = FightHistoryEntry()
    entry.zone_id = "1196"
    entry.zone_name = "Kyne's Aegis"
    entry.difficulty = difficulty
    entry.game_version = version
    entry.duration_s = 180.0
    entry.dps_time_s = 178.0
    entry.group_dps = boss_dps * 1.2
    entry.group_boss_dps = boss_dps
    entry.deaths = 2
    entry.pull = {"boss": boss, "bosses": [boss], "outcome": outcome, "health_left": 0.0,
                  "players": len(roster), "start_s": start_s, "end_s": start_s + 180.0}
    entry.player_names = [{"name": h, "character": h[1:], "is_local": h == "@p0"} for h in roster]
    entry.players = rows if rows is not None else [
        {"name": h, "unit_id": str(i), "role": "D", "class_abbr": "NB",
         "boss_dps": boss_dps / len(roster) + i, "dps": boss_dps / len(roster)}
        for i, h in enumerate(roster)]
    entry.time_dead = {"3": 4_000}
    return entry


class TestLine(unittest.TestCase):

    def test_the_line_holds_the_figures_not_the_build(self):
        entry = _entry(1_000_000.0)
        entry.players.append({"name": "anon", "unit_id": "99", "role": "H", "class_abbr": "Templar",
                              "boss_dps": 10.0, "dps": 12.0})
        entry.players.append({"name": "@p0's Companion", "unit_id": "c1", "companion": True})
        line = fi.fight_line(entry, "0.29.0")
        self.assertEqual(line["key"], "1000000.000")
        self.assertEqual((line["boss"], line["outcome"], line["game"], line["app"]),
                         ("Lord Falgravn", "kill", "eso.live.12.1", "0.29.0"))
        self.assertEqual(line["handles"], sorted(ROSTER))
        self.assertEqual(line["local"], "@p0")
        self.assertEqual(len(line["rows"]), 13)  # the companion is left out
        self.assertEqual(line["rows"][-1]["handle"], "")  # anonymous: never matched
        self.assertEqual(line["rows"][3]["dead_ms"], 4_000)
        self.assertNotIn("gear", json.dumps(line))

    def test_no_pull_or_no_start_no_line(self):
        entry = _entry(1_000_000.0)
        entry.pull = None
        self.assertIsNone(fi.fight_line(entry))
        entry = _entry(1_000_000.0)
        entry.pull["start_s"] = None
        self.assertIsNone(fi.fight_line(entry))


class TestFile(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / fi.INDEX_NAME

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_line_is_written_once_and_an_update_appends(self):
        index = fi.FightIndex(self.path)
        line = fi.fight_line(_entry(1_000_000.0))
        self.assertTrue(index.add(line))
        self.assertFalse(index.add(dict(line)))  # a restart's replay: nothing new
        changed = dict(line, deaths=5)
        self.assertTrue(index.add(changed))
        self.assertEqual(len(self.path.read_text(encoding="utf-8").splitlines()), 2)
        again = fi.FightIndex(self.path)
        self.assertEqual(again.load(), 1)
        self.assertEqual(again.lines[line["key"]]["deaths"], 5)  # the last per key

    def test_a_bad_or_half_written_line_is_skipped(self):
        good = fi.fight_line(_entry(1_000_000.0))
        self.path.write_text(json.dumps(good) + "\nnot json\n" + json.dumps(good)[:40],
                             encoding="utf-8")
        index = fi.FightIndex(self.path)
        self.assertEqual(index.load(), 1)
        self.assertEqual(index.skipped, 2)

    def test_a_missing_file_is_an_empty_index(self):
        self.assertEqual(fi.FightIndex(self.path).load(), 0)

    def test_a_file_held_elsewhere_keeps_the_lines_for_the_next_write(self):
        self.path.mkdir()  # cannot be opened for appending, like a locked file
        index = fi.FightIndex(self.path)
        self.assertTrue(index.add(fi.fight_line(_entry(1_000_000.0))))
        self.assertEqual(index.pending(), 1)
        self.path.rmdir()
        index.add(fi.fight_line(_entry(2_000_000.0)))
        self.assertEqual(index.pending(), 0)
        self.assertEqual(fi.FightIndex(self.path).load(), 2)


class TestComparison(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index = fi.FightIndex(Path(self.tmp.name) / fi.INDEX_NAME)

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, *entries):
        for entry in entries:
            self.index.add(fi.fight_line(entry))

    def test_the_boss_wide_set_alone(self):
        strangers = [f"@s{i}" for i in range(12)]
        self._add(_entry(100.0, roster=strangers, boss_dps=400_000),
                  _entry(200.0, roster=strangers, boss_dps=500_000))
        found = fi.comparison(self.index, _entry(300.0, boss_dps=512_000))
        self.assertEqual(fi.comparison_text(found),
                         "Your Lord Falgravn kills: median 450k over 2, best 500k. This pull: 512k")

    def test_this_roster_on_this_version(self):
        strangers = [f"@s{i}" for i in range(12)]
        self._add(_entry(100.0, roster=strangers, boss_dps=300_000),
                  *[_entry(200.0 + i, boss_dps=470_000 + i) for i in range(3)])
        text = fi.comparison_text(fi.comparison(self.index, _entry(300.0, boss_dps=512_000)))
        self.assertIn("; with 8+ of this roster on 12.1: median 470k over 3", text)
        self.assertTrue(text.startswith("Your Lord Falgravn kills: median 470k over 4, best 470k"))

    def test_this_roster_on_any_version_when_the_version_leaves_too_few(self):
        strangers = [f"@s{i}" for i in range(12)]
        self._add(_entry(100.0, roster=strangers),
                  _entry(201.0, version="eso.live.11.3"), _entry(202.0, version="eso.live.12.0"),
                  _entry(203.0))
        text = fi.comparison_text(fi.comparison(self.index, _entry(300.0)))
        self.assertIn("; with 8+ of this roster: median", text)
        self.assertNotIn(" on 12.1", text)

    def test_only_earlier_kills_of_the_boss_at_the_difficulty(self):
        self._add(_entry(400.0),  # later
                  _entry(100.0, outcome="wipe"),
                  _entry(150.0, difficulty="NORMAL"),
                  _entry(160.0, boss="Captain Vrol"))
        self.assertIsNone(fi.comparison(self.index, _entry(300.0)))
        self.assertEqual(fi.comparison_text(None), "")

    def test_one_earlier_kill(self):
        self._add(_entry(100.0, roster=[f"@s{i}" for i in range(12)], boss_dps=441_000))
        # A fight with no boss figure is read by all its damage
        entry = _entry(300.0, boss_dps=0)
        entry.group_dps = 540_000.0
        self.assertEqual(fi.comparison_text(fi.comparison(self.index, entry)),
                         "Your earlier Lord Falgravn kill: 441k. This pull: 540k")


class TestPlayer(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index = fi.FightIndex(Path(self.tmp.name) / fi.INDEX_NAME)
        for start, dps in ((100.0, 300_000), (200.0, 360_000), (250.0, 420_000), (260.0, 480_000)):
            self.index.add(fi.fight_line(_entry(start, boss_dps=dps)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_last_three_kills_most_recent_first(self):
        entry = _entry(300.0)
        values = fi.player_history(self.index, entry, "@p2")
        self.assertEqual(len(values), 3)
        self.assertGreater(values[0], values[1])
        self.assertEqual(fi.player_history_text(entry, "@p2", values),
                         "@p2 on Lord Falgravn: 40k, 35k, 30k in their last three kills with you")
        self.assertTrue(fi.player_history_text(entry, "@p0", fi.player_history(
            self.index, entry, "@p0"), _Mask()).endswith("in your last three kills"))
        self.assertTrue(fi.player_history_text(entry, "@p2", values, _Mask()).startswith("@▒▒ on "))

    def test_an_anonymous_or_unknown_player_has_none(self):
        entry = _entry(300.0)
        self.assertEqual(fi.player_history(self.index, entry, "anon"), [])
        self.assertEqual(fi.player_history(self.index, entry, "@nobody"), [])
        self.assertEqual(fi.player_history_text(entry, "@nobody", []), "")

    def test_the_runs_best_kill_with_this_roster(self):
        run = [[_entry(300.0, outcome="wipe")], [_entry(400.0, outcome="wipe")]]
        self.assertEqual(fi.run_best_kill(self.index, run), 480_000)
        strangers = [[_entry(300.0, outcome="wipe", roster=[f"@s{i}" for i in range(12)])]]
        self.assertIsNone(fi.run_best_kill(self.index, strangers))


EPOCH = 1755729685851
_PLAYER = "22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _log(start_ms, boss_dies=True):
    boss = "287485/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
    lines = [
        f'5,BEGIN_LOG,{EPOCH + start_ms},15,"NA Megaserver","en","eso.live.12.1"',
        '1000,ZONE_CHANGED,1196,"Kyne\'s Aegis",VETERAN',
        '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@me",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
        '2500,UNIT_ADDED,70,MONSTER,F,0,105634,T,0,0,"Lord Falgravn","",0,50,160,0,HOSTILE,F',
        '10000,BEGIN_COMBAT',
        f'11000,COMBAT_EVENT,DAMAGE,PHYSICAL,0,1000,0,1,12437,1,{_PLAYER},70,{boss}',
    ]
    if boss_dies:
        lines.append(f'15000,COMBAT_EVENT,DIED_XP,PHYSICAL,0,32,0,2,217348,1,{_PLAYER},70,'
                     '0/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3')
    lines.append('16000,END_COMBAT')
    return "\n".join(lines) + "\n"


class TestBackfill(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.splits = root / "splits"
        self.splits.mkdir()
        (self.splits / "260101200000-Kyne's-Aegis-vet.log").write_text(_log(0), encoding="utf-8")
        (self.splits / "260102200000-Kyne's-Aegis-vet.log").write_text(_log(86_400_000),
                                                                        encoding="utf-8")
        # A byte-identical copy, as the old splitter made (issue #85)
        (self.splits / "260102200000-Kyne's-Aegis-vet-1.log").write_text(_log(86_400_000),
                                                                          encoding="utf-8")
        (self.splits / "260102200000-Kyne's-Aegis-vet-report.txt").write_text("x", encoding="utf-8")
        self.index = fi.FightIndex(root / fi.INDEX_NAME)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _analyzer():
        from esolog_tail import ESOLogAnalyzer, FightHistory
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        return analyzer

    def test_the_split_logs_through_the_engine_once(self):
        steps = []
        result = fi.backfill(self.splits, self.index, self._analyzer, "0.29.0",
                             progress=lambda label, done, total: steps.append((label, done, total)))
        self.assertEqual(result, {"logs": 2, "skipped": 1, "fights": 2, "left": 0})
        self.assertEqual(len(self.index), 2)
        line = next(iter(self.index.lines.values()))
        self.assertEqual((line["boss"], line["outcome"], line["game"]),
                         ("Lord Falgravn", "kill", "eso.live.12.1"))
        self.assertTrue(steps and steps[0][0].startswith("Fight history: log 1 of 3"))
        # Done is noted: the next build reads nothing
        again = fi.backfill(self.splits, fi.FightIndex(self.index.path), self._analyzer)
        self.assertEqual(again, {"logs": 0, "skipped": 0, "fights": 0, "left": 0})

    def test_only_the_splitters_files(self):
        self.assertTrue(fi.is_split_name("260113192924-Kyne's-Aegis-vet-14.log"))
        self.assertTrue(fi.is_split_name("260113192924-Kyne's-Aegis-vet.zip"))
        # A blank split folder is the log's own: never the live log or an archive
        self.assertFalse(fi.is_split_name("Encounter.log"))
        self.assertFalse(fi.is_split_name("20250929-Encounter.log"))
        self.assertFalse(fi.is_split_name("260102200000-Kyne's-Aegis-vet-report.txt"))

    def test_a_cancel_stops_and_the_next_build_carries_on(self):
        import review_load
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(review_load.ReviewCancelled):
            fi.backfill(self.splits, self.index, self._analyzer, cancel=cancel)
        result = fi.backfill(self.splits, self.index, self._analyzer)
        self.assertEqual(result["logs"], 2)


if __name__ == "__main__":
    unittest.main()
