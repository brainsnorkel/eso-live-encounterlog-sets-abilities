#!/usr/bin/env python3
"""The session recap (issue #171): one block per instance, one line per
boss's pulls in a row with what ended them, the trash, the build issues
as a count, the trial result, and Hide names."""

import unittest

import session_recap as sr
from fight_history import FightHistoryEntry


class _Mask:
    def text(self, name):
        name = str(name or "")
        return "@▒▒" if name.startswith("@") and name != "@me" else name


def _pull(outcome, health_left, boss, start_s, end_s, players=12):
    return {"boss": boss, "bosses": [boss], "outcome": outcome, "health_left": health_left,
            "health_start": 100.0, "health": {boss: [100.0, health_left]},
            "boss_died": outcome == "kill", "players": players, "dead_at_end": [],
            "local_dead_at_end": False, "start_s": start_s, "end_s": end_s,
            "zone": "1196|VETERAN", "continues": False, "cut": False, "went_on": False}


def _fight(boss, start, duration, pull=None, recaps=(), time_dead=None, zone="Kyne's Aegis",
           zone_id="1196", issues=False, result=None, boss_dps=0.0):
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = zone
    entry.zone_id = zone_id
    entry.difficulty = "VETERAN"
    entry.is_vet = True
    entry.timestamp = start
    entry.duration_s = duration
    entry.group_dps = 500000.0
    entry.group_boss_dps = boss_dps
    entry.dps_time_s = duration
    entry.boss_dps_time_s = duration if boss_dps else 0.0
    entry.pull = pull
    entry.death_recaps = list(recaps)
    entry.deaths = len(entry.death_recaps)
    entry.time_dead = time_dead or {}
    entry.trial_result = result
    entry.players = [{"name": "@me", "unit_id": "1", "build_issues": []},
                     {"name": "@other", "unit_id": "2",
                      "build_issues": [{"title": "x"}] if issues else []}]
    return entry


def _recap(unit_id, name, ms, ability, killer="Lord Falgravn"):
    return {"unit_id": unit_id, "name": name, "time_ms": ms, "ability": ability, "killer": killer}


class TestRecap(unittest.TestCase):

    def _night(self):
        return [
            _fight("Half-Giant Raider", "2026-10-31 20:05:00", 30.0),
            _fight("Yandir the Butcher", "2026-10-31 20:10:00", 82.0,
                   _pull("kill", 0.0, "Yandir the Butcher", 1000.0, 1082.0), boss_dps=662000.0),
            _fight("Lord Falgravn", "2026-10-31 21:00:00", 100.0,
                   _pull("wipe", 84.0, "Lord Falgravn", 4000.0, 4100.0),
                   [_recap("2", "@other", 5000, "Grievous Pulse")], time_dead={"2": 90_000},
                   issues=True),
            _fight("Lord Falgravn", "2026-10-31 21:02:30", 120.0,
                   _pull("wipe", 62.0, "Lord Falgravn", 4150.0, 4270.0),
                   [_recap("1", "@me", 3000, "Claw")], time_dead={"1": 30_000}),
            _fight("Lord Falgravn", "2026-10-31 21:05:00", 180.0,
                   _pull("kill", 0.0, "Lord Falgravn", 4320.0, 4500.0), boss_dps=441000.0,
                   result={'trial_id': 13, 'name': "Kyne's Aegis", 'is_vet': True,
                           'duration_ms': 3600000, 'score': 153117, 'vitality': 34,
                           'vitality_max': 36}),
        ]

    def test_a_night(self):
        from trial_result import result_text
        night = self._night()
        text = sr.recap_text(night)
        self.assertEqual(text.splitlines(), [
            "Kyne's Aegis · Veteran · 2026-10-31 20:05 to 21:08 · 12 players",
            "Yandir the Butcher: kill in 1 pull, 1:22, 662.0k boss dps, no deaths",
            # The deaths are the run's, before the kill's own time and dps
            ("Lord Falgravn: 3 pulls, killed on pull 3, 50s between pulls, 2 deaths; "
             "the kill 3:00, 441.0k boss dps"),
            "  First deaths: Grievous Pulse 1, Claw 1",
            "  Killers: Grievous Pulse 1, Claw 1; 100% by Lord Falgravn",
            "  Most time dead: @other 1:30, @me 30s",
            "Trash: 1 fight, 30s",
            "ⓘ 1 player with possible build issues",
            result_text(night[-1].trial_result),
        ])

    def test_a_kill_the_log_cut_in_two_is_one_pull_with_one_dps(self):
        first = _fight("Lord Falgravn", "2026-10-31 21:00:00", 120.0,
                       _pull("unseen", 40.0, "Lord Falgravn", 0.0, 120.0), boss_dps=400000.0)
        second = _fight("Lord Falgravn", "2026-10-31 21:02:10", 60.0,
                        _pull("kill", 0.0, "Lord Falgravn", 130.0, 190.0), boss_dps=700000.0)
        second.pull["continues"] = True
        text = sr.recap_text([first, second])
        # 120 s at 400k and 60 s at 700k: 3:00 at 500k
        self.assertIn("Lord Falgravn: kill in 1 pull, 3:00, 500.0k boss dps, no deaths", text)

    def test_a_boss_with_no_boss_figure_says_dps(self):
        text = sr.recap_text([_fight("Tho'at Replicanum", "2026-10-31 21:00:00", 90.0,
                                     _pull("kill", 0.0, "Tho'at Replicanum", 0.0, 90.0))])
        self.assertIn("kill in 1 pull, 1:30, 500.0k dps, no deaths", text)

    def test_players_with_no_name_are_counted_apart(self):
        fight = _fight("Lord Falgravn", "2026-10-31 21:00:00", 100.0)
        fight.players = [{"name": "anon", "unit_id": str(i), "build_issues": [{"title": "x"}]}
                         for i in (5, 6, 7)]
        self.assertIn("ⓘ 3 players with possible build issues", sr.recap_text([fight]))

    def test_the_span_skips_a_fight_with_no_clock(self):
        night = self._night()
        night[0].timestamp = "Unknown Time"
        self.assertTrue(sr.recap_text(night).startswith(
            "Kyne's Aegis · Veteran · 2026-10-31 20:10 to 21:08 · 12 players"))

    def test_hide_names(self):
        text = sr.recap_text(self._night(), _Mask())
        self.assertIn("Most time dead: @▒▒ 1:30, @me 30s", text)
        self.assertNotIn("@other", text)

    def test_one_pull_that_did_not_kill(self):
        text = sr.recap_text([_fight("Lord Falgravn", "2026-10-31 21:00:00", 100.0,
                                     _pull("wipe", 62.4, "Lord Falgravn", 0.0, 100.0))])
        self.assertIn("Lord Falgravn: 1 pull, wipe 62%, no deaths", text)

    def test_blocks_apart(self):
        night = self._night()
        night.append(_fight("Lokkestiiz", "2026-10-31 22:00:00", 200.0,
                            _pull("kill", 0.0, "Lokkestiiz", 9000.0, 9200.0), zone="Sunspire",
                            zone_id="1121", boss_dps=344000.0))
        blocks = sr.recap_text(night).split("\n\n")
        self.assertEqual(len(blocks), 2)
        self.assertTrue(blocks[1].startswith("Sunspire · Veteran · 2026-10-31 22:00 to 22:03"))

    def test_nothing_to_recap(self):
        self.assertEqual(sr.recap_text([]), "")


if __name__ == "__main__":
    unittest.main()
