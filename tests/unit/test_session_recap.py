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
        text = sr.recap_text(self._night())
        self.assertEqual(text.splitlines(), [
            "Kyne's Aegis · Veteran · 2026-10-31 20:05 to 21:08 · 12 players",
            "Yandir the Butcher: kill in 1 pull, 1:22, 662k boss dps, no deaths",
            ("Lord Falgravn: 3 pulls, killed on pull 3, 50s between pulls; the kill 3:00, "
             "441k boss dps, 2 deaths"),
            "  First deaths: Grievous Pulse 1, Claw 1",
            "  Killers: Grievous Pulse 1, Claw 1; 100% by Lord Falgravn",
            "  Most time dead: @other 1:30, @me 30s",
            "Trash: 1 fight, 30s",
            "ⓘ 1 player with possible build issues",
            text.splitlines()[-1],
        ])
        self.assertIn("34", text.splitlines()[-1])

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
