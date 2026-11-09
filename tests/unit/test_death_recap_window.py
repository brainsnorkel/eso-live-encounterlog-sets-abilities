#!/usr/bin/env python3
"""The death recap window as a setting (issue #95): 1 to 10 seconds, 3 by
default since #133, held to that range from the config, read by the engine
when it is built, and written on each recap so the window names the seconds
it was built with."""

import json
import tempfile
import unittest
from pathlib import Path

from app_config import DEFAULTS, AppConfig
from app_startup import build_analyzer
from death_recap import (
    DEFAULT_WINDOW_S,
    KILLING_BLOW_GRACE_MS,
    LEGACY_WINDOW_MS,
    MAX_WINDOW_S,
    MIN_WINDOW_S,
    RECAP_WINDOW_MS,
    DeathRecapRecorder,
    recap_window_s,
)

BOSS = "70,287485/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _player(health, max_health=20000):
    return f"1,{health}/{max_health},26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _fields(result, hit, health, cast=900, overflow=0):
    """A COMBAT_EVENT's fields after the time and type: the boss on player 1."""
    return (f"{result},PHYSICAL,1,{hit},{overflow},{cast},12437,{BOSS},"
            f"{_player(health)}").split(",")


def _recorder(window_ms=None):
    names = {"70": "Test Boss", "1": "@tester"}
    kwargs = {} if window_ms is None else {"window_ms": window_ms}
    return DeathRecapRecorder(lambda uid: names.get(uid, ""),
                              lambda aid: ("Toppling Blow", "icon"), None, **kwargs)


class TestTheWindowValue(unittest.TestCase):

    def test_the_default_and_the_bounds(self):
        self.assertEqual((DEFAULT_WINDOW_S, MIN_WINDOW_S, MAX_WINDOW_S), (3, 1, 10))
        self.assertEqual(RECAP_WINDOW_MS, 3000)
        # A recap from before the setting still reads as the fixed five
        self.assertEqual(LEGACY_WINDOW_MS, 5000)
        self.assertEqual(DEFAULTS["death_recap"]["window_s"], DEFAULT_WINDOW_S)

    def test_a_config_value_is_held_to_the_bounds(self):
        for value, expected in ((None, 3), ("x", 3), (0, 1), (1, 1), (4, 4), (5, 5), ("7", 7),
                                (7.9, 7), (10, 10), (11, 10), (-3, 1)):
            with self.subTest(value=value):
                self.assertEqual(recap_window_s(value), expected)


class TestTheRecorderKeepsTheWindow(unittest.TestCase):

    def _death_after(self, recorder):
        """A hit 8 s before the death, one 2 s before, then the death."""
        recorder.record(12000, _fields("DAMAGE", 1000, 19000), "1")
        recorder.record(18000, _fields("DAMAGE", 3000, 16000), "1")
        return recorder.note_death("1", 20000, _fields("DIED", 0, 0, cast=901))

    def test_the_default_window_is_three_seconds(self):
        recap = self._death_after(_recorder())
        self.assertEqual(recap["window_ms"], 3000)
        self.assertEqual([row["offset_ms"] for row in recap["events"]], [-2000])

    def test_one_second_keeps_the_last_second_and_the_killing_blow(self):
        recorder = _recorder(window_ms=1000)
        recorder.record(18000, _fields("DAMAGE", 1000, 19000), "1")
        recorder.record(19500, _fields("DAMAGE", 3000, 16000), "1")
        recap = recorder.note_death("1", 20000, _fields("DIED", 0, 0, cast=901))
        # The killing blow, logged after the death within the grace
        recorder.record(20000 + KILLING_BLOW_GRACE_MS, _fields("DAMAGE", 16000, 0, cast=901), "1")
        self.assertEqual(recap["window_ms"], 1000)
        self.assertEqual([row["offset_ms"] for row in recap["events"]], [-500, KILLING_BLOW_GRACE_MS])

    def test_a_wider_window_keeps_the_older_hit(self):
        recap = self._death_after(_recorder(window_ms=10000))
        self.assertEqual(recap["window_ms"], 10000)
        self.assertEqual([row["offset_ms"] for row in recap["events"]], [-8000, -2000])

    def test_the_window_can_be_set_after_construction(self):
        # app_startup sets it on the analyzer's recorder before any line
        recorder = _recorder()
        recorder.window_ms = 9000
        recap = self._death_after(recorder)
        self.assertEqual(recap["window_ms"], 9000)
        self.assertEqual(len(recap["events"]), 2)


class TestTheSettingReachesTheEngine(unittest.TestCase):

    def test_build_analyzer_reads_the_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(path=Path(tmp) / "config.json")
            self.assertEqual(build_analyzer(config, []).death_recap_recorder.window_ms, 3000)
            config.set("death_recap.window_s", 8)
            self.assertEqual(build_analyzer(config, []).death_recap_recorder.window_ms, 8000)
            config.set("death_recap.window_s", 99)   # a hand-edited config file
            self.assertEqual(build_analyzer(config, []).death_recap_recorder.window_ms, 10000)

    def test_a_stored_five_is_kept_and_a_new_install_gets_three(self):
        # Issue #133, decision 1: the config cannot tell a saved default from
        # a chosen 5, so a stored value stays; only a config without the key
        # reads the new default
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"death_recap": {"window_s": 5}}), encoding="utf-8")
            self.assertEqual(AppConfig(path=path).get("death_recap.window_s"), 5)
            path.write_text(json.dumps({"update": {"channel": "beta"}}), encoding="utf-8")
            self.assertEqual(AppConfig(path=path).get("death_recap.window_s"), 3)


if __name__ == '__main__':
    unittest.main()
