#!/usr/bin/env python3
"""The fight list in blocks by instance (issue #129), offscreen: a header
naming the zone and difficulty above each block, fight rows without the
zone, the run's result in an inert row under the fight that completed it,
alternate blocks on a faint band, and the arrow keys stepping over the
inert rows."""

import os
import tempfile
import unittest
from pathlib import Path

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


RESULT = {'trial_id': 12, 'name': 'Sunspire', 'is_vet': True, 'duration_ms': 1351407,
          'score': 253117, 'vitality': 35, 'vitality_max': 36}


def _entry(boss, zone='Sunspire', zone_id='1121', difficulty='VETERAN', result=None):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = zone
    entry.zone_id = zone_id
    entry.difficulty = difficulty
    entry.is_vet = difficulty == 'VETERAN'
    entry.timestamp = '2026-10-21 21:50:00'
    entry.duration_s = 100.0
    entry.group_dps = 150000.0
    entry.trial_result = result
    entry.players = [{
        'role': 'D', 'name': '@me', 'class_abbr': 'NB', 'dps': 1000.0, 'dmg_pct': 100.0,
        'h': 20000, 'm': 30000, 's': 15000, 'unit_id': '1', 'sets': [], 'all_sets': [],
        'skill_lines': [], 'class_lines': [], 'front_bar': [], 'back_bar': [],
        'front_bar_slots': [], 'back_bar_slots': []}]
    return entry


class TestBlockRule(unittest.TestCase):

    def test_where_a_block_starts(self):
        from fight_blocks import starts_block
        first = _entry('Lokkestiiz')
        self.assertTrue(starts_block(None, first))
        # A wipe and a walk back in: same zone and difficulty, no result
        self.assertFalse(starts_block(first, _entry('Yolnahkriin')))
        self.assertTrue(starts_block(first, _entry('Yolnahkriin', difficulty='NORMAL')))
        self.assertTrue(starts_block(first, _entry('Iron Atronach', 'Craglorn', '888', 'NONE')))
        # A fresh run after a completed one, in the same zone
        self.assertTrue(starts_block(_entry('Nahviintaas', result=RESULT), _entry('Lokkestiiz')))

    def test_the_zone_id_tells_zones_of_one_name_apart(self):
        # A solo dungeon has its group dungeon's name
        from fight_blocks import starts_block
        self.assertTrue(starts_block(_entry('a', 'March of Sacrifices', '1055', 'NORMAL'),
                                     _entry('b', 'March of Sacrifices', '1592', 'NORMAL')))

    def test_header_text(self):
        from fight_blocks import header_text
        self.assertEqual(header_text(_entry('a')), 'Sunspire · Veteran')
        self.assertEqual(header_text(_entry('a', difficulty='NORMAL')), 'Sunspire · Normal')
        self.assertEqual(header_text(_entry('a', 'Craglorn', '888', 'NONE')), 'Craglorn')


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestFightList(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        from gui.fight_list import FightList
        self.list = FightList()
        self.fights = [_entry('Lokkestiiz'), _entry('Nahviintaas', result=RESULT),
                       _entry('Lokkestiiz'), _entry('Iron Atronach', 'Craglorn', '888', 'NONE')]
        for entry in self.fights:
            self.list.add_fight(entry)

    def tearDown(self):
        self.list.deleteLater()

    def _rows(self):
        from gui.fight_list import KIND_ROLE
        return [(self.list.item(row).data(KIND_ROLE), self.list.item(row).text())
                for row in range(self.list.count())]

    def test_rows(self):
        rows = self._rows()
        self.assertEqual([kind for kind, _ in rows], [
            'header', 'fight', 'fight', 'result', 'header', 'fight', 'header', 'fight'])
        self.assertEqual(rows[0][1], 'Sunspire · Veteran')
        self.assertEqual(rows[3][1], '✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31')
        self.assertEqual(rows[6][1], 'Craglorn')
        # The header names the zone, so the fight rows do not
        self.assertTrue(rows[1][1].startswith('Lokkestiiz · 1:40 · 150.0k gdps · '))
        for kind, text in rows:
            if kind == 'fight':
                self.assertNotIn('Sunspire', text)
                self.assertNotIn('Craglorn', text)

    def test_header_and_result_rows_are_inert(self):
        from PySide6.QtCore import Qt

        from gui.fight_list import ENTRY_ROLE
        for row, (kind, _) in enumerate(self._rows()):
            item = self.list.item(row)
            if kind == 'fight':
                self.assertTrue(item.flags() & Qt.ItemIsSelectable)
                self.assertIn(item.data(ENTRY_ROLE), self.fights)
            else:
                self.assertEqual(item.flags(), Qt.NoItemFlags)
                self.assertIsNone(item.data(ENTRY_ROLE))
        self.assertTrue(self.list.item(0).font().bold())

    def test_alternate_blocks_lie_on_a_band(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPalette

        from gui.fight_list import band_color
        palette = self.list.palette()
        band = band_color(palette.color(QPalette.Base), palette.color(QPalette.Text))
        styles = [self.list.item(row).background().style() for row in range(self.list.count())]
        self.assertEqual(styles, [Qt.NoBrush] * 4 + [Qt.SolidPattern] * 2 + [Qt.NoBrush] * 2)
        self.assertEqual(self.list.item(4).background().color(), band)
        self.assertNotEqual(band, palette.color(QPalette.Base))

    def test_the_band_follows_the_theme(self):
        from PySide6.QtGui import QColor, QPalette

        from gui.fight_list import band_color
        dark = QPalette(self.list.palette())
        dark.setColor(QPalette.Base, QColor('#1e1e1e'))
        dark.setColor(QPalette.Text, QColor('#ffffff'))
        self.list.setPalette(dark)
        self.assertEqual(self.list.item(4).background().color(),
                         band_color(QColor('#1e1e1e'), QColor('#ffffff')))
        # An inert row is not greyed out
        self.assertEqual(self.list.item(0).foreground().color(), QColor('#ffffff'))

    def test_fight_index_calls(self):
        self.assertEqual(self.list.fight_count(), 4)
        self.assertIs(self.list.entry_at(1), self.fights[0])
        self.assertIsNone(self.list.entry_at(0))
        self.assertEqual(self.list.row_of(self.fights[2]), 5)
        self.assertEqual(self.list.fight_item(2).text(), self.list.item(5).text())
        self.list.select_fight(-1)
        self.assertIs(self.list.current_entry(), self.fights[3])
        self.assertEqual(self.list.current_fight_index(), 3)

    def test_the_arrow_keys_step_over_the_inert_rows(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.list.show()
        self.list.select_fight(1)  # the run's last fight, above its result
        for expected in (2, 3):
            QTest.keyClick(self.list, Qt.Key_Down)
            self.assertEqual(self.list.current_fight_index(), expected)
        for expected in (2, 1):
            QTest.keyClick(self.list, Qt.Key_Up)
            self.assertEqual(self.list.current_fight_index(), expected)
        QTest.keyClick(self.list, Qt.Key_Home)
        self.assertEqual(self.list.current_fight_index(), 0)
        QTest.keyClick(self.list, Qt.Key_End)
        self.assertEqual(self.list.current_fight_index(), 3)

    def test_a_result_that_came_after_its_fight(self):
        from gui.fight_list import FightList
        listed = FightList()
        try:
            final = _entry('Nahviintaas')
            listed.add_fight(final)
            self.assertEqual(listed.count(), 2)
            final.trial_result = RESULT
            self.assertEqual(listed.update_fight(final), 1)
            self.assertEqual(listed.item(2).text(), '✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31')
            listed.update_fight(final)  # again: still one result row
            self.assertEqual(listed.count(), 3)
            # The next fight opens a block of its own
            listed.add_fight(_entry('Lokkestiiz'))
            self.assertEqual(listed.item(3).text(), 'Sunspire · Veteran')
            self.assertIsNone(listed.update_fight(_entry('not listed')))
        finally:
            listed.deleteLater()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestWindow(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        from app_config import AppConfig
        from gui.main_window import MainWindow
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        config = AppConfig(path=root / 'config.json')
        config.set('log_path', str(root / 'Encounter.log'))
        config.set('update.check_enabled', False)
        self.win = MainWindow(config)
        self.win.worker_thread.quit()
        self.win.worker_thread.wait(3000)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def test_live_fights_follow_and_the_final_fight_shows_the_result(self):
        from PySide6.QtGui import QGuiApplication
        self.win._on_fight_completed(_entry('Lokkestiiz'))
        final = _entry('Nahviintaas', result=RESULT)
        self.win._on_fight_completed(final)
        # The newest fight is current, not the result row under it
        self.assertIs(self.win.history_list.current_entry(), final)
        # The strip is the pane's first line (a table's text opens with a
        # line break)
        shown = self.win.fight_view.toPlainText().lstrip()
        self.assertTrue(shown.startswith('✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31'))
        self.win._copy_current()
        self.assertIn('Vitality 35/36', QGuiApplication.clipboard().text())
        self.win.history_list.select_fight(0)
        self.assertNotIn('Vitality', self.win.fight_view.toPlainText())

    def test_copy_session_copies_the_list_as_a_recap(self):
        from PySide6.QtGui import QGuiApplication
        self.win._copy_session()
        self.assertEqual(self.win.statusBar().currentMessage(), "No fights to copy")
        self.win._on_fight_completed(_entry('Lokkestiiz'))
        self.win._on_fight_completed(_entry('Nahviintaas', result=RESULT))
        self.win._copy_session()
        text = QGuiApplication.clipboard().text()
        self.assertTrue(text.startswith('Sunspire · Veteran · 2026-10-21 21:50 to 21:51'))
        self.assertIn('Trash: 2 fights, 3:20', text)
        self.assertIn('Vitality 35/36', text)
        self.assertTrue(self.win.statusBar().currentMessage().startswith(
            'Session recap copied to clipboard, '))
        self.assertEqual(self.win.copy_session_action.shortcut().toString(), 'Ctrl+Shift+C')

    def test_a_late_result_redraws_the_fight_on_screen(self):
        final = _entry('Nahviintaas')
        self.win._on_fight_completed(final)
        self.assertNotIn('Vitality', self.win.fight_view.toPlainText())
        final.trial_result = RESULT
        self.win._on_fight_updated(final)
        self.assertIn('Vitality 35/36', self.win.fight_view.toPlainText())
        self.assertEqual(self.win.history_list.count(), 3)

    def test_review_lists_blocks_and_picks_the_last_fight(self):
        fights = [_entry('Lokkestiiz', result=RESULT), _entry('Lokkestiiz')]
        self.win._on_review_loaded('review.log', fights)
        self.assertEqual(self.win.history_list.count(), 5)
        self.assertIs(self.win.history_list.current_entry(), fights[-1])


if __name__ == '__main__':
    unittest.main()
