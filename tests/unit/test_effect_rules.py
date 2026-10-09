#!/usr/bin/env python3
"""Tracked effects (issue #10): the rule text anyone can paste, HyperTools
export strings, and the tracker's uptime and stack measurements."""

import unittest

from effect_rules import (
    DEFAULT_RULES,
    EffectTracker,
    Rule,
    decode_hypertools,
    hypertools_rules,
    parse_rules,
)


class TestRuleText(unittest.TestCase):

    def test_a_rule_per_line_with_comments_and_defaults(self):
        rules, errors = parse_rules(
            "# comment\n"
            "\n"
            "Off-Balance = 45902 62988, 39077 on boss\n"
            "Crux = 184220 on self stacks\n"
            "Minor Courage = 147417\n")
        self.assertEqual(errors, [])
        self.assertEqual(rules, [
            Rule("Off-Balance", frozenset({"45902", "62988", "39077"}), "boss", "uptime"),
            Rule("Crux", frozenset({"184220"}), "self", "stacks"),
            Rule("Minor Courage", frozenset({"147417"}), "group", "uptime"),
        ])

    def test_scope_words_work_without_on_and_in_any_order(self):
        rules, errors = parse_rules("Z'en = stacks 126597 enemies\n")
        self.assertEqual(errors, [])
        self.assertEqual(rules[0], Rule("Z'en", frozenset({"126597"}), "enemies", "stacks"))

    def test_bad_lines_are_reported_by_number_and_skipped(self):
        rules, errors = parse_rules(
            "Good = 1 on boss\n"
            "No equals sign\n"
            "= 2 on boss\n"
            "No ids = on boss\n"
            "Bad scope = 3 on mobs\n"
            "Stray word = 4 banana\n")
        self.assertEqual([r.name for r in rules], ["Good"])
        self.assertEqual([e.split(":")[0] for e in errors],
                         ["line 2", "line 3", "line 4", "line 5", "line 6"])
        self.assertIn("'banana'", errors[4])

    def test_the_bundled_examples_parse(self):
        rules, errors = parse_rules(DEFAULT_RULES)
        self.assertEqual(errors, [])
        self.assertEqual([r.name for r in rules], ["Off-Balance", "Touch of Z'en", "Crux"])
        self.assertIn("45902", rules[0].ids)
        self.assertEqual((rules[2].scope, rules[2].kind), ("self", "stacks"))


# A HyperTools export, as the addon's Transmission.lua writes it: a table of
# key/value records, scalars typed N, B or S
HT = ("$$Sname&$SMajor Resolve&$Starget&$SYourself&$Stype&$SIcon Tracker&"
      "$SIDs&$$N1&$N61694&$N2&$N61693&&"
      "$Sstacks&$$Sshow&$Bfalse&&"
      "$Sevents&$$N1&$$Stype&$SGet Effect Duration&$Sarguments&$$SIds&$$N1&$N61694&&&&&&")
HT_GROUP = ("$$Sname&$SBuffs on Groupmates&$Starget&$SGroup&$SIDs&$&"
            "$Schildren&$$SHealing Ward&$$Sname&$SHealing Ward&$SIDs&$$N1&$N86044&&&&&")


class TestHyperTools(unittest.TestCase):

    def test_decodes_the_addons_export_format(self):
        table = decode_hypertools(HT)
        self.assertEqual(table["name"], "Major Resolve")
        self.assertEqual(table["target"], "Yourself")
        self.assertEqual(table["IDs"], {1: 61694, 2: 61693})
        self.assertEqual(table["stacks"], {"show": False})
        self.assertEqual(table["events"][1]["arguments"]["Ids"], {1: 61694})

    def test_a_tracker_becomes_a_rule_with_its_ids_and_target(self):
        rules = hypertools_rules(HT)
        self.assertEqual(rules, [Rule("Major Resolve", frozenset({"61694", "61693"}), "self", "uptime")])

    def test_a_group_is_walked_and_children_inherit_its_target(self):
        rules = hypertools_rules(HT_GROUP)
        self.assertEqual(rules, [Rule("Healing Ward", frozenset({"86044"}), "group", "uptime")])

    def test_words_after_the_string_override_it(self):
        rules = hypertools_rules(HT + " on boss stacks")
        self.assertEqual((rules[0].scope, rules[0].kind), ("boss", "stacks"))

    def test_in_the_rule_text_and_its_errors(self):
        rules, errors = parse_rules("Crux = 184220 on self\n" + HT + "\n$garbage\n")
        self.assertEqual([r.name for r in rules], ["Crux", "Major Resolve"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("line 3:"))


def _tracker(text):
    rules, errors = parse_rules(text)
    assert not errors, errors
    return EffectTracker(rules)


class TestTracker(unittest.TestCase):

    def test_uptime_is_the_union_over_units_in_scope(self):
        t = _tracker("OB = 45902 62988 on boss\n")
        # Boss 70: 45902 for 10-20 s, 62988 for 15-25 s (overlap merges);
        # a mob and a player get the same ids and do not count
        t.record("GAINED", "45902", "70", "1", 10000, "boss")
        t.record("GAINED", "62988", "70", "1", 15000, "boss")
        t.record("FADED", "45902", "70", "1", 20000, "boss")
        t.record("FADED", "62988", "70", "1", 25000, "boss")
        t.record("GAINED", "45902", "71", "1", 30000, "enemy")
        t.record("GAINED", "45902", "1", "1", 30000, "self")
        [ob] = t.snapshot(0, 60000)
        self.assertEqual((ob["uptime_pct"], ob["text"]), (25.0, "OB:25%"))
        self.assertEqual([(iv["start_ms"], iv["end_ms"]) for iv in ob["intervals"]],
                         [(10000, 20000), (15000, 25000)])

    def test_stacks_are_the_mean_level_while_up_and_the_peak(self):
        t = _tracker("Crux = 184220 on self stacks\n")
        t.record("GAINED", "184220", "1", "1", 0, "self")
        t.record("UPDATED", "184220", "1", "2", 10000, "self")
        t.record("UPDATED", "184220", "1", "3", 20000, "self")
        t.record("FADED", "184220", "1", "0", 30000, "self")
        [crux] = t.snapshot(0, 40000)
        # 1 for 10 s, 2 for 10 s, 3 for 10 s: mean 2, peak 3, up 75% of the fight
        self.assertEqual((crux["avg_stacks"], crux["max_stacks"], crux["uptime_pct"]), (2.0, 3, 75.0))
        self.assertEqual(crux["text"], "Crux:2.0/3")
        self.assertEqual([iv["stacks"] for iv in crux["intervals"]], [1, 2, 3])

    def test_stacks_on_several_bosses_take_the_highest(self):
        t = _tracker("Z'en = 126597 on boss stacks\n")
        t.record("GAINED", "126597", "70", "5", 0, "boss")
        t.record("GAINED", "126597", "71", "2", 0, "boss")
        t.record("FADED", "126597", "70", "0", 10000, "boss")
        t.record("FADED", "126597", "71", "0", 20000, "boss")
        [zen] = t.snapshot(0, 20000)
        self.assertEqual((zen["avg_stacks"], zen["max_stacks"]), (3.5, 5))

    def test_scope_self_needs_the_local_player_and_group_takes_anyone(self):
        t = _tracker("Mine = 1 on self\nOurs = 1 on group\nPets = 1 on pets\n")
        t.record("GAINED", "1", "2", "1", 0, "group")
        t.record("GAINED", "1", "90", "1", 0, "pet")
        mine, ours, pets = t.snapshot(0, 10000)
        self.assertEqual((mine["uptime_pct"], ours["uptime_pct"], pets["uptime_pct"]), (0.0, 100.0, 100.0))
        self.assertEqual(mine["text"], "Mine:0%")

    def test_an_effect_from_before_the_pull_runs_into_the_fight_and_is_pruned_after(self):
        t = _tracker("Courage = 109966 on group\n")
        t.record("GAINED", "109966", "2", "1", 1000, "group")
        [c] = t.snapshot(5000, 15000)
        self.assertEqual(c["uptime_pct"], 100.0)
        t.record("FADED", "109966", "2", "1", 20000, "group")
        t.prune_before(25000)
        [c] = t.snapshot(25000, 35000)
        self.assertEqual(c["uptime_pct"], 0.0)

    def test_a_refresh_within_the_gap_is_one_span(self):
        t = _tracker("X = 5 on boss\n")
        t.record("GAINED", "5", "70", "1", 0, "boss")
        t.record("FADED", "5", "70", "1", 1000, "boss")
        t.record("GAINED", "5", "70", "1", 1030, "boss")
        t.record("FADED", "5", "70", "1", 2000, "boss")
        [x] = t.snapshot(0, 2000)
        self.assertEqual(len(x["intervals"]), 1)

    def test_an_empty_tracker_is_false_and_records_nothing(self):
        t = EffectTracker([])
        self.assertFalse(t)
        t.record("GAINED", "5", "70", "1", 0, "boss")
        self.assertEqual(t.snapshot(0, 1000), [])


if __name__ == '__main__':
    unittest.main()
