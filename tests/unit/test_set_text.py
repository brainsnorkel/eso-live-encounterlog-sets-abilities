#!/usr/bin/env python3
"""A set's bonus text and the set behind a buff (set_text, issue #79)."""

import json
import re
import unittest
from pathlib import Path

import set_text

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

TABLE = {
    "1": {"name": "Plain Set", "bonuses": [
        {"pieces": 2, "text": "Adds 15-657 Critical Chance"},
        {"pieces": 3, "text": "Gain Minor Slayer, increasing damage done to monsters by 5%."},
        {"pieces": 5, "text": "Deals 100-4300 damage, up to once every 0.5 seconds."}]},
    "9": {"name": "Perfected Plain Set", "bonuses": [
        {"pieces": 2, "text": "Adds 15-657 Critical Chance"},
        {"pieces": 3, "text": "Gain Minor Slayer, increasing damage done to monsters by 5%."},
        {"pieces": 5, "text": "Adds 3-129 Weapon and Spell Damage", "perfected": True},
        {"pieces": 5, "text": "Deals 100-4300 damage, up to once every 0.5 seconds."}]},
}
BUFFS = {
    "66902": {"name": "Major Courage", "set": "Spell Power Cure"},
    "109994": {"name": "Major Courage", "set": "Vestment of Olorime"},
    "135923": {"name": "Major Slayer", "set": "Roaring Opportunist"},
}


class TestTopFigures(unittest.TestCase):

    def test_a_range_reads_as_its_top_value(self):
        self.assertEqual(set_text.top_figures("Adds 15-657 Critical Chance"),
                         "Adds 657 Critical Chance")
        self.assertEqual(set_text.top_figures("restore 263-11350 Magicka. Once every 45 seconds."),
                         "restore 11350 Magicka. Once every 45 seconds.")
        self.assertEqual(set_text.top_figures("Critical Healing by 0-15% for 10 seconds."),
                         "Critical Healing by 15% for 10 seconds.")
        self.assertEqual(set_text.top_figures("heal for 1-51 Health and restore 1-51 Stamina"),
                         "heal for 51 Health and restore 51 Stamina")

    def test_text_without_a_range_is_left_alone(self):
        for text in ("Gain Minor Slayer, increasing damage done to monsters by 5%.",
                     "up to once every 0.5 seconds", "Adds 4% Healing Taken", ""):
            self.assertEqual(set_text.top_figures(text), text)
        self.assertEqual(set_text.top_figures(None), "")

    def test_every_range_of_the_bundled_text_is_low_then_high(self):
        """What top_figures relies on: a dash between two figures in UESP's
        text is always a level range, the low value first. A duration or a
        distance written that way would be cut to its second figure."""
        sets = json.loads((REPO_ROOT / "data" / "sets" / "bonuses_en.json")
                          .read_text(encoding="utf-8"))["sets"]
        pair = re.compile(r"(\d[\d,]*(?:\.\d+)?)-(\d[\d,]*(?:\.\d+)?)")
        ranges = 0
        for set_id, entry in sets.items():
            for bonus in entry["bonuses"]:
                text = bonus["text"]
                for low, high in pair.findall(text):
                    ranges += 1
                    self.assertLess(float(low.replace(",", "")), float(high.replace(",", "")),
                                    (set_id, text))
                # Every range goes, and nothing but its low figure and dash
                self.assertEqual(set_text.top_figures(text), pair.sub(r"\2", text),
                                 (set_id, text))
        self.assertGreater(ranges, 1900)
        self.assertGreater(len(sets), 700)


class TestActiveLines(unittest.TestCase):

    def test_the_lines_at_or_below_the_piece_count(self):
        self.assertEqual(set_text.active_lines("1", 3, table=TABLE), [
            (2, "Adds 657 Critical Chance"),
            (3, "Gain Minor Slayer, increasing damage done to monsters by 5%.")])
        self.assertEqual(set_text.active_lines("1", 1, table=TABLE), [])
        self.assertEqual([n for n, _t in set_text.active_lines("1", 7, table=TABLE)], [2, 3, 5])

    def test_a_perfected_set_worn_whole_has_its_own_line(self):
        lines = set_text.active_lines("9", 5, table=TABLE)
        self.assertEqual([n for n, _t in lines], [2, 3, 5, 5])
        self.assertIn((5, "Adds 129 Weapon and Spell Damage"), lines)

    def test_both_versions_have_the_shared_lines_and_the_perfected_line_by_its_own_count(self):
        # Two perfected and three normal pieces: five of the set, two perfected
        lines = set_text.active_lines("9", 5, 2, table=TABLE)
        self.assertEqual([n for n, _t in lines], [2, 3, 5])
        self.assertNotIn((5, "Adds 129 Weapon and Spell Damage"), lines)
        # Five perfected and one normal: the perfected line too
        self.assertIn((5, "Adds 129 Weapon and Spell Damage"),
                      set_text.active_lines("9", 6, 5, table=TABLE))

    def test_a_set_without_text_has_no_lines(self):
        self.assertEqual(set_text.active_lines("404", 5, table=TABLE), [])
        self.assertEqual(set_text.active_lines("", 5, table=TABLE), [])

    def test_the_bundled_text(self):
        # Slivers of the Null Arca 767, its perfected version 772
        self.assertTrue(set_text.has_text("767"))
        self.assertFalse(set_text.has_text("0"))
        self.assertEqual(set_text.active_lines("767", 3), [
            (2, "Adds 657 Critical Chance"),
            (3, "Gain Minor Slayer, increasing damage done to monsters by 5%.")])
        self.assertIn((5, "Adds 129 Weapon and Spell Damage"), set_text.active_lines("772", 5))
        self.assertNotIn((5, "Adds 129 Weapon and Spell Damage"),
                         set_text.active_lines("772", 5, 2))

    def test_every_perfected_set_has_the_text_of_its_pair(self):
        """A set worn in both versions is read from the perfected version's
        entry (fight_render.set_hovers): it has to hold the normal one's
        lines, piece for piece, and its own beside them."""
        from player_build import perfected_pairs
        table = set_text.bonus_table()
        for perfected, normal in perfected_pairs().items():
            shared = [b["pieces"] for b in table[perfected]["bonuses"] if not b.get("perfected")]
            self.assertEqual(shared, [b["pieces"] for b in table[normal]["bonuses"]], perfected)
            self.assertTrue(any(b.get("perfected") for b in table[perfected]["bonuses"]),
                            perfected)


class TestSetBuffRecorder(unittest.TestCase):
    """Who had a set's own buff id up, and when (review of #220)."""

    def _recorder(self):
        return set_text.SetBuffRecorder(ids={"66902", "135923"})

    def test_a_buff_counts_in_every_window_it_was_up_in(self):
        rec = self._recorder()
        rec.record("GAINED", "66902", "7", "8", 1000)
        rec.record("FADED", "66902", "7", "8", 5000)
        self.assertEqual(rec.given_in(4000, 9000), {"7": {"66902"}})
        self.assertEqual(rec.given_in(0, 1000), {"7": {"66902"}})
        self.assertEqual(rec.given_in(6000, 9000), {})
        self.assertEqual(rec.given_in(0, 900), {})

    def test_an_open_buff_runs_on(self):
        rec = self._recorder()
        rec.record("UPDATED", "135923", "7", "*", 1000)  # never seen gained
        self.assertEqual(rec.given_in(50000, 60000), {"7": {"135923"}})
        rec.forget_unit("*", 2000)                       # the receiver is gone
        self.assertEqual(rec.given_in(50000, 60000), {})
        self.assertEqual(rec.given_in(1500, 1600), {"7": {"135923"}})

    def test_every_caster_of_a_shared_buff_and_no_unknown_one(self):
        rec = self._recorder()
        rec.record("GAINED", "66902", "7", "8", 1000)
        rec.record("UPDATED", "66902", "9", "8", 2000)   # another wearer refreshes it
        rec.record("FADED", "66902", "0", "8", 3000)
        self.assertEqual(rec.given_in(0, 9000), {"7": {"66902"}, "9": {"66902"}})
        rec.record("GAINED", "66902", "0", "10", 4000)   # no caster named
        rec.record("FADED", "66902", "0", "10", 5000)
        self.assertEqual(rec.given_in(3500, 9000), {})

    def test_other_ids_a_zone_change_pruning_and_a_reset(self):
        rec = self._recorder()
        rec.record("GAINED", "93109", "7", "8", 1000)    # the buff's own id, not the set's
        self.assertEqual(rec.given_in(0, 9000), {})
        rec.record("GAINED", "66902", "7", "8", 1000)
        rec.zone_changed(2000)
        self.assertEqual(rec.given_in(3000, 9000), {})
        rec.prune_before(2500)
        self.assertEqual(rec.given_in(0, 9000), {})
        rec.record("GAINED", "66902", "7", "8", 10000)
        rec.reset()
        self.assertEqual(rec.given_in(0, 99000), {})


class TestSetsBehind(unittest.TestCase):

    def test_the_sets_whose_id_of_the_rows_buff_a_caster_gave(self):
        given = ["66902", "135923"]
        self.assertEqual(set_text.sets_behind("Major Courage", given, BUFFS), ["Spell Power Cure"])
        self.assertEqual(set_text.sets_behind("major slayer", given, BUFFS),
                         ["Roaring Opportunist"])
        self.assertEqual(set_text.sets_behind("Major Courage", ["109994", "66902"], BUFFS),
                         ["Spell Power Cure", "Vestment of Olorime"])

    def test_a_row_that_is_no_buff_of_the_table_or_a_caster_who_gave_none(self):
        self.assertEqual(set_text.sets_behind("Lucent Echoes", ["66902"], BUFFS), [])
        self.assertEqual(set_text.sets_behind("Major Courage", [], BUFFS), [])
        self.assertEqual(set_text.sets_behind("Major Courage", ["1"], BUFFS), [])
        self.assertEqual(set_text.sets_behind("", ["66902"], BUFFS), [])

    def test_the_bundled_table(self):
        ids = set_text.buff_ids()
        self.assertIn("66902", ids)
        self.assertGreaterEqual(len(ids), 34)
        for ability_id, row in set_text.buff_table().items():
            self.assertTrue(ability_id.isdigit())
            self.assertRegex(row["name"], r"^(Major|Minor) ")
            self.assertTrue(row["set"])
        self.assertEqual(set_text.sets_behind("Major Slayer", ["135923", "93120"]),
                         ["Master Architect", "Roaring Opportunist"])


if __name__ == "__main__":
    unittest.main()
