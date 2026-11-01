#!/usr/bin/env python3
"""Kill or wipe in the fight list, the pane and the copy (issues #168 and
#169), offscreen: the verdict on the row, 'Cut' and 'group went on', the
run row under a boss's pulls with its hover, the first-death line and the
time dead."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _pull(outcome, health_left, boss="Lord Falgravn", start_s=0.0, end_s=100.0,
          continues=False, cut=False, went_on=False):
    return {"boss": boss, "bosses": [boss], "outcome": outcome, "health_left": health_left,
            "health_start": 100.0, "health": {boss: [100.0, health_left]},
            "boss_died": outcome == "kill", "players": 12, "dead_at_end": [],
            "local_dead_at_end": outcome == "unseen", "start_s": start_s, "end_s": end_s,
            "zone": "1196|VETERAN", "continues": continues, "cut": cut, "went_on": went_on}


def _entry(boss, pull=None, recaps=(), time_dead=None, duration_s=100.0):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = "Kyne's Aegis"
    entry.zone_id = "1196"
    entry.difficulty = "VETERAN"
    entry.is_vet = True
    entry.timestamp = "2026-10-31 21:39:00"
    entry.duration_s = duration_s
    entry.group_dps = 441000.0
    entry.pull = pull
    entry.death_recaps = list(recaps)
    entry.deaths = len(entry.death_recaps)
    entry.time_dead = time_dead or {}
    entry.players = [
        {'role': 'D', 'name': '@me', 'class_abbr': 'NB', 'dps': 1000.0, 'dmg_pct': 50.0,
         'h': 20000, 'm': 30000, 's': 15000, 'unit_id': '1', 'sets': [], 'all_sets': [],
         'skill_lines': [], 'class_lines': [], 'front_bar': [], 'back_bar': [],
         'front_bar_slots': [], 'back_bar_slots': [], 'is_local': True},
        {'role': 'H', 'name': '@other', 'class_abbr': 'Templar', 'dps': 100.0, 'dmg_pct': 50.0,
         'h': 20000, 'm': 30000, 's': 15000, 'unit_id': '2', 'sets': [], 'all_sets': [],
         'skill_lines': [], 'class_lines': [], 'front_bar': [], 'back_bar': [],
         'front_bar_slots': [], 'back_bar_slots': []}]
    entry.player_names = [{'name': '@me', 'character': 'Me', 'is_local': True},
                          {'name': '@other', 'character': 'Other', 'is_local': False}]
    return entry


def _recap(unit_id, name, ms, ability="Grievous Pulse", killer="Lord Falgravn"):
    return {"unit_id": unit_id, "name": name, "time_ms": ms, "ability": ability,
            "killer": killer, "events": []}


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestFightListRuns(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        from gui.fight_list import FightList
        self.view = FightList()

    def tearDown(self):
        self.view.deleteLater()

    def _texts(self):
        return [self.view.item(row).text() for row in range(self.view.count())]

    def test_the_verdict_on_the_row_and_the_run_row_under_the_pulls(self):
        from gui.fight_list import KIND_ROLE, RUN
        self.view.add_fight(_entry("Yandir the Butcher", _pull("kill", 0.0, "Yandir the Butcher")))
        for i, health in enumerate((84.0, 62.0)):
            self.view.add_fight(_entry("Lord Falgravn", _pull("wipe", health, start_s=100.0 + i * 160,
                                                              end_s=212.0 + i * 160)))
        texts = self._texts()
        self.assertTrue(texts[1].startswith("Yandir the Butcher · Kill · "))
        self.assertTrue(texts[3].startswith("Lord Falgravn · Wipe 62% · "))
        self.assertEqual(texts[4], "Lord Falgravn: 2 pulls, best 62%, 48s between pulls")
        self.assertEqual(self.view.item(4).data(KIND_ROLE), RUN)
        # The run row moves down under the next pull, and says the kill
        row = self.view.add_fight(_entry("Lord Falgravn", _pull("kill", 0.0, start_s=420.0,
                                                                end_s=600.0)))
        texts = self._texts()
        self.assertEqual(row, 4)
        self.assertEqual(texts[5], "Lord Falgravn: 3 pulls, killed on pull 3, 48s between pulls")
        self.assertEqual(sum(1 for t in texts if "pulls" in t), 1)

    def test_a_run_row_is_inert(self):
        self.view.add_fight(_entry("Lord Falgravn", _pull("wipe", 84.0)))
        self.view.add_fight(_entry("Lord Falgravn", _pull("wipe", 62.0)))
        self.view.select_fight(0)
        self.assertEqual(self.view.fight_count(), 2)
        self.assertIsNone(self.view.entry_at(3))
        self.view.select_fight(-1)
        self.assertEqual(self.view.current_fight_index(), 1)

    def test_cut_and_group_went_on(self):
        # The flags the engine sets from the fights after (pull_outcome.mark_context)
        self.view.add_fight(_entry("Lord Falgravn", _pull("unseen", 63.0, cut=True)))
        self.view.add_fight(_entry("Lord Falgravn", _pull("unseen", 31.0, continues=True,
                                                          went_on=True)))
        self.view.add_fight(_entry("Captain Vrol", _pull("wipe", 90.0, "Captain Vrol")))
        texts = self._texts()
        self.assertIn("· Cut 63% ·", texts[1])
        self.assertIn("· Lost sight 31%, group went on ·", texts[2])

    def test_a_late_result_goes_under_the_run_row(self):
        from gui.fight_list import KIND_ROLE, RESULT, RUN
        self.view.add_fight(_entry("Lord Falgravn", _pull("wipe", 62.0)))
        last = _entry("Lord Falgravn", _pull("kill", 0.0))
        self.view.add_fight(last)
        last.trial_result = {'trial_id': 13, 'name': "Kyne's Aegis", 'is_vet': True,
                             'duration_ms': 1351407, 'score': 153117, 'vitality': 30,
                             'vitality_max': 36}
        self.view.update_fight(last)
        kinds = [self.view.item(row).data(KIND_ROLE) for row in range(self.view.count())]
        self.assertEqual(kinds[-2:], [RUN, RESULT])
        self.view.update_fight(last)
        kinds = [self.view.item(row).data(KIND_ROLE) for row in range(self.view.count())]
        self.assertEqual(kinds.count(RESULT), 1)

    def test_the_run_hover_and_hide_names(self):
        from gui.fight_list import RUN_ROLE, run_tooltip
        first = _entry("Lord Falgravn", _pull("wipe", 80.0),
                       [_recap("2", "@other", 5000)], time_dead={"2": 90_000})
        self.view.add_fight(first)
        self.view.add_fight(_entry("Lord Falgravn", _pull("wipe", 62.0),
                                   [_recap("1", "@me", 3000, "Claw")], time_dead={"1": 30_000}))
        run = self.view.item(3).data(RUN_ROLE)
        text = run_tooltip(run)
        self.assertIn("First deaths: Grievous Pulse 1, Claw 1", text)
        self.assertIn("Most time dead: @other 1:30, @me 30s", text)
        hidden = run_tooltip(run, hide_names=True)
        self.assertNotIn("@other", hidden)
        self.assertIn("@me 30s", hidden)

    def test_a_rebuild_gives_the_same_rows(self):
        entries = [_entry("Lord Falgravn", _pull("wipe", h)) for h in (84.0, 62.0)]
        for entry in entries:
            self.view.add_fight(entry)
        live = self._texts()
        self.view.set_fights(entries)
        self.assertEqual(self._texts(), live)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestPaneAndCopy(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def _wipe(self):
        return _entry("Lord Falgravn", _pull("wipe", 62.0),
                      [_recap("2", "@other", 102_000), _recap("1", "@me", 150_000, "Claw")],
                      time_dead={"2": 92_000, "1": 5_000}, duration_s=310.0)

    def test_the_copy(self):
        from gui.fight_render import render_plain_text
        text = render_plain_text(self._wipe())
        self.assertTrue(text.splitlines()[0].startswith("Lord Falgravn · Wipe 62% · 5:10 · "))
        self.assertIn("First death: @other to Grievous Pulse (Lord Falgravn) at 1:42 · 2 deaths"
                      " · the pull ended 3:28 later", text)
        self.assertIn("[H] @other Templar — ", text)
        self.assertIn(" · dead 1:32", text)

    def test_the_pane(self):
        from gui.fight_render import render_html
        page = render_html(self._wipe(), detailed=False)
        self.assertIn("Wipe 62% · 5:10", page)
        self.assertIn("First death: @other to Grievous Pulse", page)
        self.assertIn("dead 1:32", page)

    def test_hide_names_draws_the_stand_in_as_the_opener_line_does(self):
        from gui.fight_render import render_html, render_plain_text
        from gui.name_mask import NameMask
        entry = self._wipe()
        names = NameMask.for_entry(entry, True)
        page = render_html(entry, detailed=False, names=names)
        self.assertNotIn("@other", page)
        self.assertIn("First death: @<img", page)
        self.assertIn("First death: @▒▒▒▒▒ to Grievous Pulse", render_plain_text(entry, names=names))

    def test_the_pane_and_the_copy_say_cut_as_the_list_does(self):
        from gui.fight_render import render_html, render_plain_text
        entry = _entry("Lord Falgravn", _pull("unseen", 63.0, cut=True))
        self.assertIn("Cut 63% · ", render_html(entry, detailed=False))
        self.assertTrue(render_plain_text(entry).startswith("Lord Falgravn · Cut 63% · "))

    def test_the_death_hover(self):
        from gui.death_render import death_tooltips
        tips = death_tooltips(self._wipe())
        self.assertTrue(any("Dead for 1:32 of 5:10 (30%)" in tip for tip in tips.values()))


if __name__ == "__main__":
    unittest.main()
