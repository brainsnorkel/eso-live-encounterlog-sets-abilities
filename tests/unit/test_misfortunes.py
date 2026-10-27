"""A solo dungeon run's Misfortunes (issue #70): the table, the icon
fallback, the engine's field and the fight pane's line."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from fight_history import FightHistoryEntry
from gui.fight_render import (
    MISFORTUNE_HREF,
    misfortunes_text,
    misfortunes_tooltips,
    render_html,
    render_plain_text,
)
from misfortunes import MISFORTUNES, run_misfortunes

ICONS = {"269749": "debuff_solodungeon_monster_warmwelcome",
         "300001": "debuff_solodungeon_player_somethingnew",
         "61744": "ability_buff_minor_berserk"}


def _run(ids):
    return run_misfortunes(ids, lambda i: ICONS.get(i, ""),
                           lambda i: {"300001": "Something New"}.get(i, ""))


class TestRunMisfortunes(unittest.TestCase):
    def test_known_ids_come_in_the_tables_order(self):
        # The Moon Hunter Keep run's PLAYER_INFO order differed between pulls
        self.assertEqual([name for name, _ in _run(["269792", "1", "269803", "269749"])],
                         ["Warm Welcome", "Revoke of Respite", "Alleviating Assault"])
        self.assertEqual([name for name, _ in _run(["269804", "269749", "269799"])],
                         ["Warm Welcome", "Weary Submission", "Pulled Punches"])

    def test_an_unknown_solo_dungeon_debuff_is_named_by_the_log(self):
        self.assertEqual(_run(["61744", "300001", "300001", "269749"]),
                         [MISFORTUNES["269749"], ("Something New", "")])

    def test_none_picked(self):
        self.assertEqual(_run(["61744", "1"]), [])


class TestFightPaneLine(unittest.TestCase):
    def _entry(self, misfortunes):
        entry = FightHistoryEntry()
        entry.zone_name = "Moon Hunter Keep"
        entry.boss_name = "Jailer Melitus"
        entry.misfortunes = misfortunes
        return entry

    def test_the_line_in_a_solo_dungeon(self):
        entry = self._entry([["Warm Welcome", "Enemies deal double damage"], ["Something New", ""]])
        self.assertEqual(misfortunes_text(entry), "Misfortunes: Warm Welcome · Something New")
        self.assertEqual(render_plain_text(entry).splitlines()[1],
                         "Misfortunes: Warm Welcome · Something New")
        page = render_html(entry, detailed=False)
        self.assertIn("Misfortunes: ", page)
        self.assertIn(f'href="{MISFORTUNE_HREF}0"', page)
        self.assertNotIn(f'href="{MISFORTUNE_HREF}1"', page)  # no text, no hover
        self.assertEqual(misfortunes_tooltips(entry),
                         {f"{MISFORTUNE_HREF}0": "<b>Warm Welcome</b><br>Enemies deal double damage"})

    def test_a_run_without_misfortunes_says_none(self):
        entry = self._entry([])
        self.assertEqual(misfortunes_text(entry), "Misfortunes: none")
        self.assertIn("Misfortunes: none", render_html(entry, detailed=False))

    def test_nothing_anywhere_else(self):
        entry = self._entry(None)
        self.assertEqual(misfortunes_text(entry), "")
        self.assertNotIn("Misfortunes", render_html(entry, detailed=False))
        self.assertNotIn("Misfortunes", render_plain_text(entry))
        self.assertEqual(misfortunes_tooltips(entry), {})


if __name__ == '__main__':
    unittest.main()
