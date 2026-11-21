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
from effect_rules import (
    BOSS_DEBUFFS_COMMENT,
    CATALYST_RULE,
    DEFAULT_RULES,
    MAJOR_BREACH_RULE,
    UPTIME_LINE_RULES,
    Rule,
    parse_rules,
)

LINE_ITEMS = ["Major Courage", "Major Force", "Major Slayer", "Powerful Assault",
              "Lucent Echoes", "Pearlescent Ward", "Taunt"]
# What version 6 adds at the end of a saved text that has neither line nor
# the default boss-debuff comment (issue #243)
ADDED_IN_6 = MAJOR_BREACH_RULE + "\n" + CATALYST_RULE + "\n"


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
        self.assertEqual(config.get("tracking.rules"),
                         UPTIME_LINE_RULES + "Mine = 1 on boss\n" + ADDED_IN_6)
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)
        names = [rule.name for rule in parse_rules(config.get("tracking.rules"))[0]]
        self.assertEqual(names, LINE_ITEMS + ["Mine", "Major Breach", "Elemental Catalyst"])

    def test_a_rule_the_user_had_already_named_stays_theirs(self):
        config = self._stored({"tracking": {"rules": "Taunt = 38254 on boss\n"}})
        rules = parse_rules(config.get("tracking.rules"))[0]
        self.assertEqual(len(rules), 9)
        # Their ids, scope and measurement; the taunt's expected words added
        self.assertEqual([rule for rule in rules if rule.name == "Taunt"],
                         [Rule("Taunt", frozenset({"38254"}), "boss", "uptime",
                               frozenset({"small", "large"}))])

    def test_a_version_2_text_gains_expected_words_and_zen_counts_dots(self):
        """Issue #13 and #27: the expected defaults get their words by name
        (Powerful Assault, not expected since #48, gets none), Touch of
        Z'en's stacks become dots; a renamed or already-flagged line, and
        every other line, stays as written."""
        text = ("# my rules\n"
                "Major Courage = 109966 on group\n"
                "Powerful Assault = 61771 on group\n"
                "Taunt  =  38254 on boss each\n"
                "Touch of Z'en = 126597 on boss stacks\n"
                "Courage = 109966 on group\n"
                "Major Force = 61747 on group expected all\n"
                "Mine = 1 on boss\n")
        config = self._stored({"tracking": {"rules": text, "version": 2}})
        self.assertEqual(config.get("tracking.rules"),
                         "# my rules\n"
                         "Major Courage = 109966 on group expected large\n"
                         "Powerful Assault = 61771 on group\n"
                         "Taunt  =  38254 on boss each expected small large\n"
                         "Touch of Z'en = 126597 on boss dots\n"
                         "Courage = 109966 on group\n"
                         "Major Force = 61747 on group expected all\n"
                         "Mine = 1 on boss\n" + ADDED_IN_6)
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)
        # Already at version 3, and nothing for version 4 to take off: only
        # version 6's lines are added
        config = self._stored({"tracking": {"rules": text, "version": 3}})
        self.assertEqual(config.get("tracking.rules"), text + ADDED_IN_6)

    def test_a_version_3_text_loses_powerful_assaults_expected_large(self):
        """Issue #48: Powerful Assault is no longer expected, so the words
        version 3 put on its line come off again, in the user's own
        spelling of the line; a line with its own sizes, a renamed line, a
        comment and every other line stay as written."""
        text = ("Powerful Assault = 61771 on group expected large\n"
                "powerful assault = expected Large 61771 61772 group\n"
                "Powerful Assault = 61771 on group expected all\n"
                "Powerful Assault = 61771 on group expected small large\n"
                "PA = 61771 on group expected large\n"
                "Major Courage = 109966 on group expected large\n"
                "# Powerful Assault = 61771 on group expected large\n")
        config = self._stored({"tracking": {"rules": text, "version": 3}})
        self.assertEqual(config.get("tracking.rules"),
                         "Powerful Assault = 61771 on group\n"
                         "powerful assault = 61771 61772 group\n"
                         "Powerful Assault = 61771 on group expected all\n"
                         "Powerful Assault = 61771 on group expected small large\n"
                         "PA = 61771 on group expected large\n"
                         "Major Courage = 109966 on group expected large\n"
                         "# Powerful Assault = 61771 on group expected large\n" + ADDED_IN_6)
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)
        # Already at version 4: nothing taken off, whatever it says
        config = self._stored({"tracking": {"rules": text, "version": 4}})
        self.assertEqual(config.get("tracking.rules"), text + ADDED_IN_6)
        # A text from before version 3 is not given the words it would lose
        config = self._stored({"tracking": {"rules": "Powerful Assault = 61771 on group\n"}})
        self.assertNotIn("Powerful Assault = 61771 on group expected", config.get("tracking.rules"))
        self.assertEqual(config.get("tracking.version"), TRACKING_VERSION)

    def test_a_version_5_text_gains_major_breach_and_catalyst(self):
        """Issue #243: the default text as a 0.13 install saved it, without
        Elemental Catalyst, has Major Breach put first among its boss
        debuffs and Catalyst after it; the next Save keeps both, and a line
        deleted after that stays deleted."""
        text = (UPTIME_LINE_RULES + BOSS_DEBUFFS_COMMENT + "\n"
                "Off-Balance   = 45902 on boss\n"
                "Alkosh        = 76667 on boss\n")
        config = self._stored({"tracking": {"rules": text, "version": 5}})
        upgraded = (UPTIME_LINE_RULES + BOSS_DEBUFFS_COMMENT + "\n" + ADDED_IN_6
                    + "Off-Balance   = 45902 on boss\n"
                    "Alkosh        = 76667 on boss\n")
        self.assertEqual(config.get("tracking.rules"), upgraded)
        config.save()
        again = AppConfig(path=self.path)
        self.assertEqual(again.get("tracking.rules"), upgraded)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["tracking"]["version"], 6)
        again.set("tracking.rules", upgraded.replace(MAJOR_BREACH_RULE + "\n", ""))
        again.save()
        self.assertNotIn("Major Breach", AppConfig(path=self.path).get("tracking.rules"))

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
        self.assertEqual(again.get("tracking.rules"),
                         UPTIME_LINE_RULES + "Mine = 1 on boss\n" + ADDED_IN_6)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["tracking"]["version"],
                         TRACKING_VERSION)


if __name__ == '__main__':
    unittest.main()
