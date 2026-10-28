#!/usr/bin/env python3
"""The damage window in the GUI (offscreen Qt): the link on a player's dps
figure, its hover text, the shares beside the dps figures, the window's
HTML, and the window itself."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights  # noqa: E402

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


def _row(name, damage, hits, crits=0, pet=False, icon='', max_hit=None, shielded=0):
    return {'id': '1', 'name': name, 'icon': icon, 'pet': pet, 'damage': damage,
            'hits': hits, 'crits': crits, 'blocked': 0, 'shielded': shielded, 'ticks': 0,
            'max': max_hit if max_hit is not None else damage, 'min': 1}


def _window(first_ms, last_ms, origin_ms=10000):
    return {'first_ms': first_ms, 'last_ms': last_ms, 'span_ms': last_ms - first_ms,
            'first_s': (first_ms - origin_ms) / 1000.0, 'last_s': (last_ms - origin_ms) / 1000.0}


def _damage():
    """@tester's record: 900,000 in a 90 s span, 600,000 of it to the boss."""
    return {
        'total': 900000, 'boss': 600000,
        'window': _window(11000, 101000), 'boss_window': _window(11000, 71000),
        'abilities': [
            _row('Biting Jabs', 500000, 100, crits=60, icon='damage_window_test', max_hit=9000),
            _row('Volatile Familiar', 250000, 50, pet=True),
            _row('Wall of Elements', 150000, 300, crits=100, shielded=5000),
        ],
        'boss_abilities': [
            _row('Biting Jabs', 400000, 80, crits=50, icon='damage_window_test', max_hit=9000),
            _row('Volatile Familiar', 200000, 40, pet=True),
        ],
        'targets': [
            {'unit_id': '70', 'name': 'Sharpfang', 'boss': True, 'damage': 600000, 'hits': 120,
             **_window(11000, 71000)},
            {'unit_id': '71', 'name': 'Ravenous Hound', 'boss': False, 'damage': 300000,
             'hits': 330, **_window(71000, 101000)},
        ],
    }


def _player(unit_id, name, damage=None, boss_pct=66.7, dmg_pct=62.9):
    return {'role': 'D', 'name': name, 'class_abbr': 'Templar', 'class_name': 'Templar',
            'dps': 10000.0, 'boss_dps': 10000.0, 'dmg_pct': dmg_pct, 'boss_pct': boss_pct,
            'h': 20000, 'm': 30000, 's': 15000, 'unit_id': unit_id,
            'sets': [], 'all_sets': [], 'skill_lines': [], 'class_lines': [],
            'front_bar': [], 'back_bar': [], 'front_bar_slots': [], 'back_bar_slots': [],
            'damage': damage if damage is not None else _damage()}


def _entry(boss=True):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = 'Sharpfang'
    entry.zone_name = 'Moonlit Cove'
    entry.is_vet = True
    entry.timestamp = '2026-10-03 16:54:04'
    entry.duration_s = 100.0
    entry.dps_time_s = 92.0
    entry.group_dps = 16000.0
    entry.group_boss_dps = 15000.0 if boss else 0.0
    entry.players = [_player('1', '@tester'), _player('2', '@friend', damage={})]
    return entry


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class DamageWindowTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.icons_root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        self.assertTrue(image.save(str(self.icons_root / 'damage_window_test.png')))

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        from gui.icon_cache import IconCache
        return IconCache(self.icons_root)


class TestDpsFigureInFightView(DamageWindowTestCase):

    def test_dps_figure_is_a_link_and_shares_read_boss_over_total(self):
        from gui.fight_render import render_html, render_plain_text
        html = render_html(_entry(), detailed=False)
        self.assertIn('href="esolog:damage/1"', html)
        # The figure, then the breakdown glyph, inside the anchor
        self.assertIn('>10.0k / 10.0k&nbsp;<img src="glyph:breakdown?', html)
        self.assertIn('66.7% / 62.9%', html)
        self.assertIn('— 10.0k / 10.0k (66.7% / 62.9%)', render_plain_text(_entry()))
        # A fight without a boss keeps the single figures
        html = render_html(_entry(boss=False), detailed=False)
        self.assertIn('>10.0k&nbsp;<img src="glyph:breakdown?', html)
        self.assertIn('>62.9%<', html)
        self.assertNotIn('66.7%', html)
        self.assertIn('— 10.0k (62.9%)', render_plain_text(_entry(boss=False)))

    def test_header_shows_the_dps_time_when_it_differs(self):
        from gui.fight_render import render_html
        self.assertIn('1:40 (dps time 1:32)', render_html(_entry(), detailed=False))
        same = _entry()
        same.dps_time_s = 100.0
        self.assertNotIn('dps time', render_html(same, detailed=False))

    def test_hover_text_gives_the_dps_time_and_the_whole_fight_figures(self):
        from gui.fight_render import damage_tooltips
        tips = damage_tooltips(_entry())
        tip = tips['esolog:damage/1']
        self.assertIn('<b>@tester</b>', tip)
        self.assertIn('900,000 damage in 1:30 dps time (first hit to last) of a 1:40 fight', tip)
        self.assertIn('600,000 to the bosses in 1:00', tip)
        # Over the whole fight: boss 6,000 and total 9,000 per second
        self.assertIn('Over the whole fight: 6.0k / 9.0k', tip)
        self.assertIn('Click for the damage breakdown', tip)
        # A player without a record still gets the click hint
        self.assertIn('Click for the damage breakdown', tips['esolog:damage/2'])
        self.assertNotIn('dps time', tips['esolog:damage/2'])

    def test_fight_view_announces_the_click_and_cues_the_hover(self):
        from PySide6.QtCore import QUrl
        from gui.fight_render import render_html
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        clicked = []
        view.damage_requested.connect(clicked.append)
        view.setHtml(render_html(_entry(), detailed=False))
        view.anchorClicked.emit(QUrl('esolog:damage/1'))
        self.assertEqual(clicked, ['1'])
        view.highlighted.emit(QUrl('esolog:damage/1'))
        self.assertEqual(view.hovered_build_link, 'esolog:damage/1')
        self.assertTrue(view.extraSelections())


class TestDamageWindowHtml(DamageWindowTestCase):

    def test_abilities_largest_first_with_their_figures(self):
        from gui.damage_render import render_damage_html
        html = render_damage_html(_entry(), '1', icons=self._cache())
        for expected in ('>@tester</span>', 'DPS · Templar', 'Sharpfang', 'Moonlit Cove', '[VET]'):
            self.assertIn(expected, html)
        # Totals over the dps time: 900,000 in 1:30.0 is 10,000 a second
        self.assertIn('<b>900,000</b> damage in <b>1:30.0</b> dps time', html)
        self.assertIn('<b>10.0k</b> dps · 62.9% of the group\'s damage', html)
        self.assertIn('first hit 1.0 s after the pull, last hit 1:31 into the 1:40 fight', html)
        self.assertIn('over the whole fight 9.0k dps', html)
        jabs = html.index('Biting Jabs')
        familiar = html.index('Volatile Familiar')
        wall = html.index('Wall of Elements')
        self.assertLess(jabs, familiar)
        self.assertLess(familiar, wall)
        row = html[jabs:html.index('</tr>', jabs)]
        # damage, share, hits, crit %, max, average, dps
        for cell in ('500,000', '55.6%', '>100<', '60%', '9,000', '5,000', '5.6k'):
            self.assertIn(cell, row)
        self.assertIn('<img src="icon:damage_window_test"', html[:jabs + 1])
        self.assertIn('Volatile Familiar <span', html)
        self.assertIn('(pet)', html)
        # Targets with their own spans: the hound's 300,000 over 30 s
        self.assertIn('Targets', html)
        hound = html[html.index('Ravenous Hound'):]
        hound = hound[:hound.index('</tr>')]
        for cell in ('300,000', '33.3%', '>330<', '30.0s', '10.0k'):
            self.assertIn(cell, hound)
        self.assertIn('<b>Sharpfang</b>', html)

    def test_boss_only_view(self):
        from gui.damage_render import render_damage_html
        html = render_damage_html(_entry(), '1', boss_only=True)
        self.assertIn('<b>600,000</b> damage to the bosses in <b>1:00.0</b> dps time', html)
        self.assertIn("66.7% of the group's boss damage", html)
        self.assertNotIn('Wall of Elements', html)
        self.assertNotIn('Ravenous Hound', html)
        self.assertIn('Sharpfang', html)
        # Shares are of the boss damage: 400,000 of 600,000
        self.assertIn('66.7%', html[html.index('Biting Jabs'):])

    def test_players_without_damage_or_record(self):
        from gui.damage_render import NO_BOSS_DAMAGE, NO_DAMAGE, NO_RECORD, render_damage_html
        self.assertIn(NO_RECORD, render_damage_html(_entry(), '2'))
        self.assertIn(NO_RECORD, render_damage_html(_entry(), '99'))
        empty = _entry()
        empty.players[0]['damage'] = {'total': 0, 'boss': 0, 'window': {}, 'boss_window': {},
                                      'abilities': [], 'boss_abilities': [], 'targets': []}
        self.assertIn(NO_DAMAGE, render_damage_html(empty, '1'))
        no_boss = _entry()
        no_boss.players[0]['damage']['boss'] = 0
        self.assertIn(NO_BOSS_DAMAGE, render_damage_html(no_boss, '1', boss_only=True))

    def test_themes_use_different_colors_and_names_are_escaped(self):
        from gui.damage_render import render_damage_html
        light = render_damage_html(_entry(), '1')
        dark = render_damage_html(_entry(), '1', dark=True)
        self.assertNotEqual(light, dark)
        entry = _entry()
        entry.players[0]['damage']['abilities'][0]['name'] = 'A<i>'
        self.assertIn('A&lt;i&gt;', render_damage_html(entry, '1'))


class TestDamageWindow(DamageWindowTestCase):

    def _main_window(self):
        from app_config import AppConfig
        from gui.icon_cache import IconCache
        from gui.main_window import MainWindow
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.icons_root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        win.fight_view.icons = IconCache(self.icons_root)
        return win

    def test_click_on_the_dps_figure_opens_the_players_window(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            self.assertIsNone(win._damage_dialog)

            win.fight_view.anchorClicked.emit(QUrl('esolog:damage/1'))
            dialog = win._damage_dialog
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), 'Damage – @tester')
            text = dialog.view.toPlainText()
            for expected in ('Biting Jabs', 'Volatile Familiar (pet)', 'Wall of Elements',
                             'Ravenous Hound', 'Targets'):
                self.assertIn(expected, text)
            # The boss switch shows, and narrows the window to the bosses
            self.assertTrue(dialog.boss_only.isVisibleTo(dialog))
            dialog.boss_only.setChecked(True)
            text = dialog.view.toPlainText()
            self.assertIn('damage to the bosses', text)
            self.assertNotIn('Wall of Elements', text)

            # Another player's figure reuses the window; without boss damage
            # the switch goes away and is off
            win.fight_view.anchorClicked.emit(QUrl('esolog:damage/2'))
            self.assertIs(win._damage_dialog, dialog)
            self.assertEqual(dialog.windowTitle(), 'Damage – @friend')
            self.assertFalse(dialog.boss_only.isVisibleTo(dialog))
            self.assertFalse(dialog.boss_only.isChecked())
            self.assertIn('No damage record', dialog.view.toPlainText())
        finally:
            win.close()

    def test_window_from_the_engines_own_record(self):
        """End to end through the engine: the shared session's one fight."""
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            entry = fights()[0]
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:damage/1'))
            dialog = win._damage_dialog
            self.assertEqual(dialog.windowTitle(), 'Damage – @brainsnorkel')
            text = dialog.view.toPlainText()
            # One hit of 90,000: its own value per second, all of it Damage
            # Ability on the Test Boss, which is not flagged as a boss
            self.assertIn('90,000 damage in 1.0s dps time', text)
            self.assertIn('90.0k dps', text)
            self.assertIn('Damage Ability', text)
            self.assertIn('Test Boss', text)
            self.assertFalse(dialog.boss_only.isVisibleTo(dialog))
        finally:
            win.close()

    def test_open_window_follows_a_theme_switch(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:damage/1'))
            dialog = win._damage_dialog
            before = dialog.view.toHtml()
            dialog.refresh(not win._dark)
            self.assertNotEqual(dialog.view.toHtml(), before)
            self.assertIn('Biting Jabs', dialog.view.toPlainText())
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
