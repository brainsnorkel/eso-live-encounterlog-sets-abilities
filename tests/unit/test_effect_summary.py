#!/usr/bin/env python3
"""Who applied an effect and who had it over a fight (issue #19)."""

import unittest

from effect_summary import UNKNOWN_SOURCE, matrix, summarise


def _iv(start, end, source, target, stacks=1):
    return {"start_ms": start * 1000, "end_ms": end * 1000,
            "source": source, "target": target, "stacks": stacks}


class TestSummarise(unittest.TestCase):

    def test_two_casters_overlapping_on_one_receiver(self):
        # @a 0-30 s, @b 20-50 s on @tank, in a 100 s fight
        s = summarise([_iv(0, 30, "@a", "@tank"), _iv(20, 50, "@b", "@tank")], 100_000)
        self.assertEqual(s["uptime_pct"], 50)
        self.assertEqual(s["sources"], [
            {"name": "@a", "uptime_pct": 30, "sole_pct": 20, "spans": 1},
            {"name": "@b", "uptime_pct": 30, "sole_pct": 20, "spans": 1}])
        self.assertEqual(s["targets"], [{"name": "@tank", "uptime_pct": 50, "spans": 2}])

    def test_one_caster_on_several_receivers(self):
        s = summarise([_iv(0, 40, "@heal", f"@p{i}") for i in range(3)]
                      + [_iv(50, 60, "@heal", "@p0")], 100_000)
        self.assertEqual(s["sources"], [{"name": "@heal", "uptime_pct": 50, "sole_pct": 50, "spans": 4}])
        self.assertEqual([(t["name"], t["uptime_pct"]) for t in s["targets"]],
                         [("@p0", 50), ("@p1", 40), ("@p2", 40)])
        # The receivers' union is the headline
        self.assertEqual(s["uptime_pct"], 50)

    def test_a_missing_caster_is_counted_not_dropped(self):
        s = summarise([_iv(0, 10, "", "Boss"), {"start_ms": 10_000, "end_ms": 20_000, "target": "Boss"},
                       _iv(20, 30, "unknown", "Boss"), _iv(30, 40, "@dd", "Boss")], 100_000)
        self.assertEqual([(l["name"], l["uptime_pct"], l["spans"]) for l in s["sources"]],
                         [(UNKNOWN_SOURCE, 30, 3), ("@dd", 10, 1)])

    def test_stacks_give_each_receivers_peak_and_time_at_it(self):
        s = summarise([_iv(0, 10, "@me", "@me", 1), _iv(10, 30, "@me", "@me", 3)],
                      100_000, stacks=True)
        self.assertEqual(s["targets"], [{"name": "@me", "uptime_pct": 30, "spans": 2,
                                         "max_stacks": 3, "at_max_pct": 20}])

    def test_empty_and_zero_length(self):
        s = summarise([_iv(5, 5, "@a", "@b")], 100_000)
        self.assertEqual((s["uptime_pct"], s["sources"], s["targets"]), (0, [], []))
        self.assertEqual(summarise([], 0)["uptime_pct"], 0)


class TestMatrix(unittest.TestCase):

    def test_only_with_several_casters_and_receivers(self):
        self.assertIsNone(matrix([_iv(0, 10, "@a", "@x"), _iv(0, 10, "@b", "@x")], 100_000))
        self.assertIsNone(matrix([_iv(0, 10, "@a", "@x"), _iv(0, 10, "@a", "@y")], 100_000))
        grid = matrix([_iv(0, 10, "@a", "@x"), _iv(0, 20, "@b", "@y")], 100_000)
        self.assertEqual(grid, {"@a": {"@x": 10}, "@b": {"@y": 20}})


if __name__ == '__main__':
    unittest.main()
