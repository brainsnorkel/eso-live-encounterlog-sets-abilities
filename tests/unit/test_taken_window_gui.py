#!/usr/bin/env python3
"""The damage taken window in the GUI (offscreen Qt, issue #98): the shield
on a player's row and its hover text, the window's HTML (header figures,
kinds, damage by source, healing by healer, the small print, the empty
states, the Hide names mask), the links to it from the build and death
recap windows, and the window itself."""

import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights

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


def _ability(ability_id, name, damage, hits, max_hit, direct=None, dot=0, area=0, types=None,
             icon=''):
    direct = damage - dot if direct is None else direct
    return {'id': ability_id, 'name': name, 'icon': icon, 'damage': damage, 'hits': hits,
            'max': max_hit, 'direct': direct, 'dot': dot, 'fall': 0, 'area': area,
            'single': damage - area, 'types': types or {'physical': damage}}


def _heal(ability_id, name, landed, overheal, hits, hot=0, icon=''):
    return {'id': ability_id, 'name': name, 'icon': icon, 'landed': landed, 'overheal': overheal,
            'hits': hits, 'hot': hot, 'direct': landed - hot}


def _taken():
    """@tester's fight: 112,000 taken, 78,000 of it from Nahviintaas, 30,000
    from four Alkosh's Will, 4,000 from no unit; 60,000 absorbed; 25 of 45
    direct hits blocked, 3 dodged; 340,000 healed, 91% of all healing
    overheal, from @friend, @tester themselves and @friend's pet."""
    snap = _ability('1', 'Snap', 50000, 20, 4000, icon='taken_window_test')
    bite = _ability('2', 'Bite', 28000, 10, 5000)
    slash = _ability('3', 'Bloodletting Slash', 18000, 12, 2500, area=18000)
    bleed = _ability('4', 'Bleed', 12000, 40, 400, dot=12000, types={'bleed': 12000})
    fall = _ability('5', 'Falling', 4000, 2, 3000, types={'fall': 4000})
    fall['fall'], fall['direct'] = 4000, 0
    rr = _heal('10', 'Radiating Regeneration', 120000, 1400000, 300, hot=120000,
               icon='taken_window_test')
    prayer = _heal('11', 'Combat Prayer', 80000, 500000, 60)
    vigor = _heal('12', 'Echoing Vigor', 110000, 900000, 200, hot=110000)
    matriarch = _heal('13', 'Twilight Matriarch', 30000, 600000, 30)
    return {
        'total': 112000, 'direct': 100000, 'dot': 12000, 'fall': 4000, 'area': 18000,
        'single': 94000, 'martial': 108000, 'magical': 0, 'oblivion': 0, 'other': 4000,
        'types': {'physical': 96000, 'bleed': 12000, 'fall': 4000},
        'rules': {'cast': 18000, 'none': 94000}, 'blocked_through': 15000, 'absorbed': 60000,
        'avoided': 3, 'healed': 340000, 'heal_direct': 110000, 'heal_hot': 230000,
        'overheal': 3400000, 'heal_absorbed': 0, 'overkill': 0,
        'first_ms': 10000, 'last_ms': 90000,
        'abilities': [snap, bite, slash, bleed, fall], 'ability_count': 5,
        'results': {'DAMAGE': 20, 'BLOCKED_DAMAGE': 25, 'DOT_TICK': 40, 'FALL_DAMAGE': 2,
                    'DAMAGE_SHIELDED': 30, 'DODGED': 3, 'HOT_TICK': 500, 'HEAL': 90},
        'sources': [
            {'name': 'Nahviintaas', 'boss': True, 'unnamed': False, 'units': 1, 'damage': 78000,
             'hits': 30, 'max': 5000, 'abilities': [snap, bite]},
            {'name': "Alkosh's Will", 'boss': False, 'unnamed': False, 'units': 4, 'damage': 30000,
             'hits': 52, 'max': 2500, 'abilities': [slash, bleed]},
            {'name': '', 'boss': False, 'unnamed': True, 'units': 1, 'damage': 4000,
             'hits': 2, 'max': 3000, 'abilities': [fall]},
        ],
        'healers': [
            {'name': '@friend', 'self': False, 'pet': False, 'unnamed': False, 'landed': 200000,
             'overheal': 1900000, 'hits': 360, 'direct': 80000, 'hot': 120000,
             'abilities': [rr, prayer]},
            {'name': '@tester', 'self': True, 'pet': False, 'unnamed': False, 'landed': 110000,
             'overheal': 900000, 'hits': 200, 'direct': 0, 'hot': 110000, 'abilities': [vigor]},
            {'name': '@friend', 'self': False, 'pet': True, 'unnamed': False, 'landed': 30000,
             'overheal': 600000, 'hits': 30, 'direct': 30000, 'hot': 0, 'abilities': [matriarch]},
        ],
    }


def _cells_after(lines, label, count):
    """The *count* plain-text lines after *label*: a table row's cells, as
    QTextDocument writes each cell on a line of its own."""
    i = lines.index(label)
    return lines[i + 1:i + 1 + count]


def _player(unit_id, name, role='T', taken=None, companion=False):
    p = {'role': role, 'name': name, 'class_abbr': 'DK', 'class_name': 'Dragonknight',
         'is_local': name == '@tester',
         'dps': 5000.0, 'boss_dps': 4000.0, 'dmg_pct': 10.0, 'boss_pct': 9.0,
         'h': 40000, 'm': 20000, 's': 25000, 'unit_id': unit_id,
         'sets': [], 'all_sets': [], 'skill_lines': [], 'class_lines': [],
         'front_bar': [], 'back_bar': [], 'front_bar_slots': [], 'back_bar_slots': [],
         'damage': {}}
    if taken is not None:
        p['taken'] = taken
    if companion:
        p.update({'companion': True, 'owner_unit_id': '1', 'role': 'C', 'deaths': 0})
    return p


def _entry():
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = 'Nahviintaas'
    entry.zone_name = 'Sunspire'
    entry.is_vet = True
    entry.timestamp = '2026-09-23 21:12:04'
    entry.duration_s = 100.0
    entry.dps_time_s = 92.0
    entry.group_dps = 50000.0
    entry.group_boss_dps = 40000.0
    entry.players = [_player('1', '@tester', taken=_taken()),
                     _player('2', '@friend', role='H'),
                     _player('3', 'Bastian Hallix', companion=True)]
    return entry


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TakenWindowTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.icons_root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor('blue'))
        self.assertTrue(image.save(str(self.icons_root / 'taken_window_test.png')))

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        from gui.icon_cache import IconCache
        return IconCache(self.icons_root)


class TestShieldOnTheRow(TakenWindowTestCase):

    def test_every_player_row_carries_the_shield_but_a_companion_does_not(self):
        from gui.fight_render import link_color, render_html
        html = render_html(_entry(), detailed=False)
        link = link_color(False).lstrip('#')
        for unit_id in ('1', '2'):
            shield = re.search(rf'<a href="esolog:taken/{unit_id}"[^>]*>(.*?)</a>', html)
            self.assertIsNotNone(shield, unit_id)
            self.assertIn(f'glyph:taken?color={link}', shield.group(1))
        self.assertNotIn('esolog:taken/3', html)
        # The row's order: name, then the (i) and skull marks, then the shield
        row = html[html.index('esolog:build/1'):html.index('esolog:damage/1')]
        self.assertLess(row.index('@tester'), row.index('esolog:taken/1'))

    def test_hover_text_gives_the_fight_figures_and_what_a_click_does(self):
        from gui.fight_render import taken_tooltips
        tips = taken_tooltips(_entry())
        self.assertEqual(set(tips), {'esolog:taken/1', 'esolog:taken/2'})
        tip = tips['esolog:taken/1']
        for expected in ('<b>@tester</b>', '112,000 damage taken, 1,120 a second of the fight',
                         '340,000 healing received, 3,400 a second', '60,000 absorbed by shields',
                         'Click for the whole fight'):
            self.assertIn(expected, tip)
        # A player without a tally still has the shield and the click line
        self.assertNotIn('damage taken,', tips['esolog:taken/2'])
        self.assertIn('Click for the whole fight', tips['esolog:taken/2'])

    def test_the_mask_hides_the_name_in_the_hover_text(self):
        from gui.fight_render import taken_tooltips
        from gui.name_mask import NameMask
        tips = taken_tooltips(_entry(), names=NameMask(True, keep={'@tester'}, hidden={'@friend'}))
        self.assertIn('@tester', tips['esolog:taken/1'])
        self.assertNotIn('@friend', tips['esolog:taken/2'])

    def test_fight_view_announces_the_click(self):
        from PySide6.QtCore import QUrl

        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        try:
            seen = []
            view.taken_requested.connect(seen.append)
            view.anchorClicked.emit(QUrl('esolog:taken/1'))
            self.assertEqual(seen, ['1'])
        finally:
            view.close()


class TestTakenHtml(TakenWindowTestCase):

    def _text(self, entry=None, unit_id='1', **kw):
        from PySide6.QtGui import QTextDocument

        from gui.taken_render import render_taken_html
        doc = QTextDocument()
        doc.setHtml(render_taken_html(entry or _entry(), unit_id, **kw))
        return doc.toPlainText()

    def test_header_figures(self):
        text = self._text()
        for expected in ('@tester', 'Tank · Dragonknight', 'Nahviintaas · Sunspire [VET]',
                         '112,000 damage taken · 1,120 a second of the 1:40 fight',
                         'hits over 1:20, first to last',
                         '340,000 healing received · 3,400 a second',
                         '91% of all healing on this player was overheal',
                         'shields absorbed 60,000, 54% as much as reached health',
                         'blocked 25 of 45 direct hits', 'dodged or missed by 3'):
            self.assertIn(expected, text)

    def test_sections_in_order_with_the_recaps_kinds_block(self):
        text = self._text()
        kinds = text.index('Kinds of damage')
        sources = text.index('Damage by source')
        healers = text.index('Healing received')
        self.assertLess(kinds, sources)
        self.assertLess(sources, healers)
        # The recap's block: the total line, the three bars' sides, the
        # types, the mitigation line and the healing line
        block = text[kinds:sources]
        for expected in ('112,000 damage taken in this fight', 'direct', 'DoT', 'area',
                         'single target', 'Martial', 'Magical', 'physical 86%',
                         '15,000 got through while blocking', '60,000 absorbed by shields',
                         '3 hits avoided', 'healed 340,000', '3,400,000 overheal'):
            self.assertIn(expected, block, expected)

    def test_damage_by_source_groups_bosses_first_with_unit_counts_and_the_unnamed_unit(self):
        text = self._text()
        block = text[text.index('Damage by source'):text.index('Healing received')]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        self.assertEqual(lines[1:8], ['Source · ability', 'Damage', '%', 'Hits', 'Max', 'Avg', 'Kind'])
        # The source rows: name with its marks, damage, share, hits, max, average
        self.assertEqual(_cells_after(lines, 'Nahviintaas boss', 5),
                         ['78,000', '70%', '30', '5,000', '2,600'])
        self.assertEqual(_cells_after(lines, "Alkosh's Will ×4", 5),
                         ['30,000', '27%', '52', '2,500', '576'])
        self.assertEqual(_cells_after(lines, 'No unit named in the log', 5),
                         ['4,000', '4%', '2', '3,000', '2,000'])
        # Abilities under their source, with the kind words last
        self.assertEqual(_cells_after(lines, 'Snap', 6),
                         ['50,000', '45%', '20', '4,000', '2,500', 'direct · single target · physical'])
        self.assertEqual(_cells_after(lines, 'Bloodletting Slash', 6)[-1], 'direct · area · physical')
        self.assertEqual(_cells_after(lines, 'Bleed', 6)[-1], 'DoT · single target · bleed')
        self.assertEqual(_cells_after(lines, 'Falling', 6)[-1], 'fall')
        order = [lines.index(label) for label in (
            'Nahviintaas boss', 'Snap', 'Bite', "Alkosh's Will ×4", 'Bloodletting Slash', 'Bleed',
            'No unit named in the log', 'Falling')]
        self.assertEqual(order, sorted(order))

    def test_healing_by_healer_with_own_and_pet_marks_and_overheal_as_a_share(self):
        text = self._text()
        block = text[text.index('Healing received'):]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        self.assertEqual(lines[1:7], ['Healer · ability', 'Received', '%', 'Hits', 'Overheal', 'Kind'])
        # The healer rows: name with its mark, received, share of all received
        # healing, hits, the overheal as a share of that healer's healing
        self.assertEqual(_cells_after(lines, '@friend', 5),
                         ['200,000', '59%', '360', '90%', 'HoT 60% · direct 40%'])
        self.assertEqual(_cells_after(lines, '@tester own', 5), ['110,000', '32%', '200', '89%', 'HoT'])
        self.assertEqual(_cells_after(lines, '@friend pet', 5), ['30,000', '9%', '30', '95%', 'direct'])
        # Abilities under their healer
        self.assertEqual(_cells_after(lines, 'Radiating Regeneration', 5),
                         ['120,000', '35%', '300', '92%', 'HoT'])
        self.assertEqual(_cells_after(lines, 'Combat Prayer', 5)[3:], ['86%', 'direct'])
        order = [lines.index(label) for label in (
            '@friend', 'Radiating Regeneration', 'Combat Prayer', '@tester own', 'Echoing Vigor',
            '@friend pet', 'Twilight Matriarch')]
        self.assertEqual(order, sorted(order))
        # The amounts of overheal never appear: a share per row instead
        self.assertNotIn('1,400,000', block)
        self.assertNotIn('1,900,000', block)

    def test_small_print(self):
        text = self._text()
        self.assertIn('Per-second figures divide by the fight time', text)
        self.assertIn('What a block, armour or resistances prevented is not in the log', text)
        self.assertIn('Overheal is the part of a heal past full health', text)
        self.assertNotIn('classed by the skill table', text)
        entry = _entry()
        entry.players[0]['taken']['rules'] = {'table': 56000, 'cast': 56000}
        self.assertIn('50% of the damage classed by the skill table', self._text(entry))

    def test_empty_states(self):
        from gui.taken_render import (
            NO_DAMAGE_TAKEN,
            NO_HEALING,
            NO_PLAYER,
            NOT_RECORDED,
            render_taken_html,
        )
        entry = _entry()
        self.assertIn(NOT_RECORDED, render_taken_html(entry, '2'))
        self.assertIn(NO_PLAYER, render_taken_html(entry, '99'))
        taken = entry.players[0]['taken']
        taken.update({'total': 0, 'sources': [], 'abilities': [], 'ability_count': 0,
                      'healed': 0, 'overheal': 0, 'healers': []})
        text = self._text(entry)
        self.assertIn(NO_DAMAGE_TAKEN, text)
        self.assertIn(NO_HEALING, text)
        self.assertNotIn('a second of the', text)
        # An entry whose tally predates the by-source rows: the sections say so
        taken = _taken()
        del taken['sources']
        del taken['healers']
        del taken['results']
        entry.players[0]['taken'] = taken
        text = self._text(entry)
        self.assertEqual(text.count(NOT_RECORDED), 2)
        self.assertNotIn('blocked 25', text)

    def test_the_mask_hides_other_players_as_sources_and_healers(self):
        from gui.name_mask import NameMask
        from gui.taken_render import render_taken_html, taken_title
        mask = NameMask(True, keep={'@tester'}, hidden={'@friend'})
        entry = _entry()
        entry.players[0]['taken']['sources'].append(
            {'name': '@friend', 'boss': False, 'unnamed': False, 'units': 1, 'damage': 10,
             'hits': 1, 'max': 10, 'abilities': []})
        html = render_taken_html(entry, '1', names=mask)
        self.assertNotIn('@friend', html)
        self.assertIn('@tester', html)
        self.assertIn('Nahviintaas', html)
        self.assertEqual(taken_title(entry, '1', mask), 'Damage taken – @tester')
        self.assertEqual(taken_title(entry, '2', mask), f'Damage taken – {mask.text("@friend")}')
        self.assertNotIn('friend', taken_title(entry, '2', mask))

    def test_themes_differ_and_names_are_escaped(self):
        from gui.taken_render import render_taken_html
        entry = _entry()
        self.assertNotEqual(render_taken_html(entry, '1'), render_taken_html(entry, '1', dark=True))
        entry.players[0]['taken']['sources'][0]['name'] = 'A<i>'
        entry.players[0]['taken']['healers'][0]['abilities'][0]['name'] = 'B<i>'
        html = render_taken_html(entry, '1')
        self.assertIn('A&lt;i&gt;', html)
        self.assertIn('B&lt;i&gt;', html)

    def test_icons_are_drawn_when_the_cache_has_them(self):
        from gui.taken_render import render_taken_html
        html = render_taken_html(_entry(), '1', icons=self._cache())
        self.assertEqual(html.count('<img src="icon:taken_window_test"'), 2)


class TestLinksFromTheOtherWindows(TakenWindowTestCase):

    def test_the_build_windows_damage_dealt_heading_links_to_it(self):
        from gui.build_render import TAKEN_LINK, render_build_html
        entry = _entry()
        html = render_build_html(entry, '1')
        self.assertIn("href='esolog:taken/1'", html)
        self.assertIn(TAKEN_LINK, html)
        # Not for a companion, which has no tally
        self.assertNotIn('esolog:taken/3', render_build_html(entry, '3'))

    def test_the_recaps_fight_block_links_to_it(self):
        import html as html_module

        from gui.death_render import _THEMES, TAKEN_WINDOW_LINK, fight_block_html
        from gui.name_mask import NO_MASK
        html = fight_block_html(_entry().players[0], dict(_THEMES[False]), None,
                                html_module.escape, NO_MASK, 9.0)
        self.assertIn("href='esolog:taken/1'", html)
        self.assertIn(TAKEN_WINDOW_LINK, html)
        # The block itself is what it was: the title, the bars, the abilities
        self.assertIn('Damage taken this fight', html)
        for name in ('Snap', 'Bite', 'Bloodletting Slash', 'Bleed', 'Falling'):
            self.assertIn(name, html)


class TestTakenWindow(TakenWindowTestCase):

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

    def test_click_on_the_shield_opens_the_players_window(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            self.assertIsNone(win._taken_dialog)

            win.fight_view.anchorClicked.emit(QUrl('esolog:taken/1'))
            dialog = win._taken_dialog
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), 'Damage taken – @tester')
            text = dialog.view.toPlainText()
            for expected in ('112,000 damage taken', 'Damage by source', 'Nahviintaas',
                             'Healing received', 'Radiating Regeneration'):
                self.assertIn(expected, text)
            # The star links carry their hover text
            self.assertTrue(any('Warfare stars' in tip for tip in dialog.view._tooltips.values()))

            # Another player's shield reuses the window
            win.fight_view.anchorClicked.emit(QUrl('esolog:taken/2'))
            self.assertIs(win._taken_dialog, dialog)
            self.assertEqual(dialog.windowTitle(), 'Damage taken – @friend')
            self.assertIn('Damage kinds were not recorded', dialog.view.toPlainText())
        finally:
            win.close()

    def test_the_links_in_the_build_and_recap_windows_open_it(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win._show_build('1')
            win._build_dialog.view.anchorClicked.emit(QUrl('esolog:taken/1'))
            self.assertIsNotNone(win._taken_dialog)
            self.assertEqual(win._taken_dialog.windowTitle(), 'Damage taken – @tester')
            win._taken_dialog.close()
            win._show_death_recap('1')
            win._death_dialog.view.anchorClicked.emit(QUrl('esolog:taken/1'))
            self.assertTrue(win._taken_dialog.isVisible())
        finally:
            win.close()

    def test_open_window_follows_a_theme_switch_and_the_hide_names_switch(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:taken/1'))
            dialog = win._taken_dialog
            before = dialog.view.toHtml()
            dialog.refresh(not win._dark)
            self.assertNotEqual(before, dialog.view.toHtml())
            # Hide names: the other player's handle goes from the healers
            self.assertIn('@friend', dialog.view.toPlainText())
            win.hide_names_action.setChecked(True)
            self.assertNotIn('@friend', dialog.view.toPlainText())
            self.assertIn('@tester', dialog.view.toPlainText())
        finally:
            win.close()

    def test_window_from_the_engines_own_record(self):
        """End to end through the engine: the shared session's fight carries
        the by-source and by-healer rows for every player."""
        entry = fights()[0]
        for p in entry.players:
            if p.get('companion'):
                continue
            taken = p['taken']
            for key in ('sources', 'healers', 'results', 'abilities'):
                self.assertIn(key, taken, p['name'])
            for row in taken['abilities']:
                self.assertIn('max', row)
            self.assertEqual(sum(s['damage'] for s in taken['sources']), taken['total'])
            self.assertEqual(sum(h['landed'] for h in taken['healers']), taken['healed'])


if __name__ == '__main__':
    unittest.main()
