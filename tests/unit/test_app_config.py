#!/usr/bin/env python3
"""The config file's tracked-effect rules: a fresh install starts with the
defaults, and a rules text saved by 0.8.0 or earlier, when the uptime
line's group buffs and taunt were built in, is given those items as rules
once, in front of the user's own."""

import json
import tempfile
import unittest
from pathlib import Path

from app_config import TRACKING_VERSION, AppConfig
from effect_rules import DEFAULT_RULES, UPTIME_LINE_RULES, Rule, parse_rules

LINE_ITEMS = ["Major Courage", "Major Force", "Major Slayer", "Powerful Assault",
              "Lucent Echoes", "Pearlescent Ward", "Taunt"]


class TestTrackingRulesUpgrade(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _stored(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return AppConfig(path=self.path)

    def test_a_fresh_config_has_the_defaults(self):
        config = AppConfig(path=self.path)
        self.assertEqual(config.get("tracking.rules"), DEFAULT_RULES)
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)

    def test_rules_saved_before_the_line_became_rules_gain_its_items_in_front(self):
        config = self._stored({"tracking": {"rules": "Mine = 1 on boss\n"}})
        self.assertEqual(config.get("tracking.rules"), UPTIME_LINE_RULES + "Mine = 1 on boss\n")
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)
        names = [rule.name for rule in parse_rules(config.get("tracking.rules"))[0]]
        self.assertEqual(names, LINE_ITEMS + ["Mine"])

    def test_a_rule_the_user_had_already_named_stays_theirs(self):
        config = self._stored({"tracking": {"rules": "Taunt = 38254 on boss\n"}})
        rules = parse_rules(config.get("tracking.rules"))[0]
        self.assertEqual(len(rules), 7)
        self.assertEqual([rule for rule in rules if rule.name == "Taunt"],
                         [Rule("Taunt", frozenset({"38254"}), "boss", "uptime")])

    def test_a_current_config_is_left_alone(self):
        config = self._stored({"tracking": {"rules": "Mine = 1 on boss\n", "version": TRACKING_VERSION}})
        self.assertEqual(config.get("tracking.rules"), "Mine = 1 on boss\n")

    def test_a_config_without_rules_is_left_alone(self):
        config = self._stored({"log_path": None})
        self.assertEqual(config.get("tracking.rules"), DEFAULT_RULES)
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)

    def test_saving_keeps_the_topped_up_text_and_the_version(self):
        config = self._stored({"tracking": {"rules": "Mine = 1 on boss\n"}})
        config.save()
        again = AppConfig(path=self.path)
        self.assertEqual(again.get("tracking.rules"), UPTIME_LINE_RULES + "Mine = 1 on boss\n")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["tracking"]["version"],
                         TRACKING_VERSION)


if __name__ == '__main__':
    unittest.main()
