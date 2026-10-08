#!/usr/bin/env python3
"""The build window in the GUI (offscreen Qt): the link on a player's name,
its hover cue, the window's HTML, and the window itself."""

import copy
import html as html_lib
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
ICONS = ('ability_weapon_001', 'ability_mundusstones_003', 'ability_grimoire_support')
SKILL_URL = 'https://eso-hub.com/en/skills/weapon/two-handed/damage-ability'
SET_URLS = {'Slimecraw': 'https://eso-hub.com/en/sets/slimecraw',
            'Perfected Whorl of the Depths':
                'https://eso-hub.com/en/sets/perfected-whorl-of-the-depths'}


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _links(name):
    return SKILL_URL if name == 'Damage Ability' else None


def _entry():
    """The shared session's fight: @brainsnorkel (1), @dualwield (2), anon (3)."""
    return fights()[0]


def _player(entry, unit_id):
    return next(p for p in entry.players if p['unit_id'] == unit_id)


def _slot(n, icon='ability_weapon_001', name=None):
    return {'id': str(1000 + n), 'name': name or f'Skill {n}', 'icon': icon}


ARMOR = ('HEAD', 'SHOULDERS', 'CHEST', 'HAND', 'WAIST', 'LEGS', 'FEET')
WEAPONS = ('MAIN_HAND', 'OFF_HAND', 'BACKUP_MAIN', 'BACKUP_OFF')


def _item(slot, **fields):
    row = {'slot': slot, 'item_id': '1', 'set_id': '1', 'set': 'Alpha', 'mythic': False,
           'quality': 'LEGENDARY', 'trait': 'ARMOR_DIVINES', 'enchant': 'STAMINA',
           'enchant_quality': 'LEGENDARY', 'cp': True, 'level': 16, 'pieces': [5, 5],
           'weight': 'medium' if slot in ARMOR else '',
           'weapon_type': 'dagger' if slot in WEAPONS else ''}
    row.update(fields)
    return row


MUTED = '#5f6368'  # the light theme's secondary text, which slot labels use


def _slot_cell(label):
    return f"<td style='color:{MUTED}'>{label}</td>"


def _row_of(html, label, group=None):
    """The <tr> of the gear grid whose slot cell reads *label* (the first one
    after the *group* heading when given)."""
    start = html.index(f'>{group}</td>') if group else 0
    cell = html.index(_slot_cell(label), start)
    return html[html.rindex('<tr>', 0, cell):html.index('</tr>', cell)]


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class BuildGuiTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.icons_root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        for stem in ICONS:
            image = QImage(40, 40, QImage.Format_ARGB32)
            image.fill(QColor('red'))
            self.assertTrue(image.save(str(self.icons_root / f'{stem}.png')))

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        from gui.icon_cache import IconCache
        return IconCache(self.icons_root)

    def _window(self, entry=None, show=False):
        from app_config import AppConfig
        from gui.icon_cache import IconCache
        from gui.main_window import MainWindow
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.icons_root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        win.fight_view.icons = IconCache(self.icons_root)
        if show:
            win.resize(1080, 720)
            win.show()
            # Flush the worker's queued startup signals (its "waiting for
            # log" placeholder would replace the fight drawn below)
            _app.processEvents()
        if entry is not None:
            win._on_fight_completed(entry)
            win.history_list.setCurrentRow(0)
        return win

    def _point_on(self, view, text, offset=2):
        """Viewport point inside the first occurrence of *text*."""
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QTextCursor
        found = view.document().find(text)
        self.assertFalse(found.isNull(), text)
        inside = QTextCursor(view.document())
        inside.setPosition(found.selectionStart() + offset)
        return view.cursorRect(inside).center() + QPoint(2, 0)

    def _hover(self, view, text):
        from PySide6.QtTest import QTest
        # Qt drops a synthesized move to where the pointer already is, and an
        # earlier test's window may have left it on this very spot
        self._leave(view)
        QTest.mouseMove(view.viewport(), self._point_on(view, text))
        _app.processEvents()

    def _leave(self, view):
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        QTest.mouseMove(view.viewport(), QPoint(view.viewport().width() - 4,
                                                view.viewport().height() - 4))
        _app.processEvents()


class TestNameLink(BuildGuiTestCase):

    def test_every_listed_player_has_the_link_in_both_views(self):
        from gui.fight_render import render_html
        entry = _entry()
        for detailed in (True, False):
            html = render_html(entry, detailed=detailed)
            for unit, name in (('1', '@brainsnorkel'), ('2', '@dualwield'), ('3', 'anon')):
                self.assertIn(f'<b><a href="esolog:build/{unit}" '
                              f'style="text-decoration:none;color:#202124">{name}</a>', html)
            self.assertEqual(html.count('esolog:build/'), 3)

    def test_name_keeps_the_panes_text_color(self):
        from gui.fight_render import render_html
        entry = _entry()
        self.assertIn('color:#123456">@brainsnorkel</a>',
                      render_html(entry, detailed=True, text_color='#123456'))
        self.assertIn('color:#e8eaed">@brainsnorkel</a>',
                      render_html(entry, detailed=True, dark=True))

    def test_players_listed_only_under_also_died_have_no_link(self):
        from gui.fight_render import render_html
        entry = _entry()
        entry.deaths = 1
        entry.death_recaps = [{'unit_id': '77', 'name': '@passerby', 'time_ms': 61000,
                               'killer': 'Test Boss', 'ability': 'Tremor', 'ability_id': '9',
                               'icon': '', 'max_health': 18678, 'events': []}]
        html = render_html(entry, detailed=True)
        tail = html[html.rindex('</table>'):]
        self.assertIn('Also died:', tail)
        self.assertIn('@passerby', tail)
        self.assertIn('esolog:deaths/77', tail)
        self.assertNotIn('esolog:build/', tail)

    def test_hover_text_says_a_click_opens_the_build(self):
        from gui.fight_render import build_tooltips
        tips = build_tooltips(_entry())
        self.assertEqual(set(tips), {'esolog:build/1', 'esolog:build/2', 'esolog:build/3'})
        self.assertIn('<b>@brainsnorkel</b>', tips['esolog:build/1'])
        self.assertIn('Click for the full build', tips['esolog:build/1'])

    def test_names_are_escaped(self):
        from gui.fight_render import build_tooltips, render_html
        entry = _entry()
        _player(entry, '1')['name'] = '<i>@x</i>'
        self.assertIn('&lt;i&gt;@x&lt;/i&gt;</a>', render_html(entry, detailed=False))
        self.assertIn('<b>&lt;i&gt;@x&lt;/i&gt;</b>', build_tooltips(entry)['esolog:build/1'])

    def test_click_is_announced_and_other_links_behave_as_before(self):
        from PySide6.QtCore import QUrl
        from gui.fight_view import FightView
        opened, builds, recaps = [], [], []
        view = FightView(icons=self._cache(),
                         open_external=lambda url: opened.append(url.toString()) or True)
        view.build_requested.connect(builds.append)
        view.death_recap_requested.connect(recaps.append)
        for href in ('esolog:build/2', 'esolog:deaths/77', 'esolog:ability/99', SKILL_URL):
            view.anchorClicked.emit(QUrl(href))
        self.assertEqual((builds, recaps, opened), (['2'], ['77'], [SKILL_URL]))

    def test_search_still_finds_a_players_name(self):
        win = self._window(_entry())
        try:
            win.search_field.setText('@dualwield')
            self.assertEqual(win.search_count.text(), '1 match')
            selections = win.fight_view.extraSelections()
            self.assertEqual([s.cursor.selectedText() for s in selections], ['@dualwield'])
        finally:
            win.close()


class TestHoverCue(BuildGuiTestCase):

    def _cue(self, view):
        self.assertEqual(len(view._hover_selections), 1)
        return view._hover_selections[0]

    def test_pointer_over_a_name_underlines_it_in_the_link_color(self):
        from PySide6.QtCore import Qt
        from gui.fight_render import link_color
        win = self._window(_entry(), show=True)
        try:
            view = win.fight_view
            self.assertEqual((view.hovered_build_link, view.extraSelections()), ('', []))
            self._hover(view, '@dualwield')
            self.assertEqual(view.hovered_build_link, 'esolog:build/2')
            cue = self._cue(view)
            # Only the hovered name is restyled
            self.assertEqual(cue.cursor.selectedText(), '@dualwield')
            self.assertTrue(cue.format.fontUnderline())
            self.assertEqual(cue.format.foreground().color().name(), link_color(False))
            self.assertEqual(len(view.extraSelections()), 1)
            self.assertIn('Click for the full build', view.current_tooltip)
            self.assertEqual(view.viewport().cursor().shape(), Qt.PointingHandCursor)
        finally:
            win.close()

    def test_pointer_leaving_restores_the_name(self):
        win = self._window(_entry(), show=True)
        try:
            view = win.fight_view
            self._hover(view, '@brainsnorkel')
            self.assertEqual(view.hovered_build_link, 'esolog:build/1')
            self._leave(view)
            self.assertEqual((view.hovered_build_link, view._hover_selections,
                              view.extraSelections(), view.current_tooltip),
                             ('', [], [], ''))
        finally:
            win.close()

    def test_moving_to_another_name_moves_the_cue(self):
        win = self._window(_entry(), show=True)
        try:
            view = win.fight_view
            self._hover(view, '@brainsnorkel')
            self._hover(view, '@dualwield')
            self.assertEqual(self._cue(view).cursor.selectedText(), '@dualwield')
        finally:
            win.close()

    def test_search_highlights_stay_before_during_and_after(self):
        win = self._window(_entry(), show=True)
        try:
            view = win.fight_view
            win.search_field.setText('Warden')

            def highlighted():
                return [s.cursor.selectedText() for s in view.extraSelections()]

            self.assertEqual(highlighted(), ['Warden'])
            self._hover(view, '@dualwield')
            self.assertEqual(highlighted(), ['Warden', '@dualwield'])
            self._leave(view)
            self.assertEqual(highlighted(), ['Warden'])
            self.assertEqual(win.search_count.text(), '1 match')
        finally:
            win.close()

    def test_other_links_keep_their_hover_and_get_no_cue(self):
        from PySide6.QtCore import QUrl
        from ability_icons import esohub_set_url
        entry = _entry()
        entry.deaths = 1
        entry.death_recaps = [{'unit_id': '1', 'name': '@brainsnorkel', 'time_ms': 20000,
                               'killer': 'Test Boss', 'ability': 'Slap', 'ability_id': '9',
                               'icon': '', 'max_health': 18678, 'events': []}]
        win = self._window(entry)
        try:
            view = win.fight_view
            for href in ('esolog:ability/12345', esohub_set_url('Slimecraw'),
                         'esolog:deaths/1'):
                view.highlighted.emit(QUrl(href))
                self.assertTrue(view.current_tooltip, href)
                self.assertEqual((view.hovered_build_link, view._hover_selections),
                                 ('', []), href)
        finally:
            win.close()

    def test_a_fight_drawn_while_a_name_is_hovered_starts_clean(self):
        win = self._window(_entry(), show=True)
        try:
            view = win.fight_view
            self._hover(view, '@brainsnorkel')
            self.assertTrue(view._hover_selections)
            win._on_fight_completed(_entry())   # becomes the fight on screen
            self.assertEqual(win.history_list.currentRow(), 1)
            self.assertEqual((view.hovered_build_link, view._hover_selections,
                              view.extraSelections()), ('', [], []))
        finally:
            win.close()

    def test_cue_works_in_the_compact_view(self):
        win = self._window(_entry(), show=True)
        try:
            win.detail_action.setChecked(False)
            self._hover(win.fight_view, '@dualwield')
            self.assertEqual(self._cue(win.fight_view).cursor.selectedText(), '@dualwield')
        finally:
            win.close()

    def test_cue_color_follows_the_theme(self):
        from PySide6.QtGui import QColor, QPalette
        from gui.fight_render import link_color
        self.assertNotEqual(link_color(True), link_color(False))
        win = self._window(_entry(), show=True)
        try:
            palette = QPalette()
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.Window, QColor('#1e1e1e'))
                palette.setColor(group, QPalette.WindowText, QColor('#eeeeee'))
            win.setPalette(palette)
            win._on_theme_maybe_changed()
            _app.processEvents()
            self._hover(win.fight_view, '@dualwield')
            self.assertEqual(self._cue(win.fight_view).format.foreground().color().name(),
                             link_color(True))
        finally:
            win.close()


class TestBarIconSize(BuildGuiTestCase):

    def test_size_defaults_to_the_fight_views_and_can_be_given(self):
        from gui.fight_render import ICON_PX, _bar_html
        slots = [_slot(1)]
        small = _bar_html(slots, ['Skill 1'], self._cache(), None, html_lib.escape)
        self.assertIn(f'width="{ICON_PX}" height="{ICON_PX}"', small)
        large = _bar_html(slots, ['Skill 1'], self._cache(), None, html_lib.escape, 36)
        self.assertIn('width="36" height="36"', large)
        self.assertNotIn(f'width="{ICON_PX}"', large)


class TestBuildRender(BuildGuiTestCase):

    def _html(self, entry=None, unit='1', **kwargs):
        from gui.build_render import render_build_html
        kwargs.setdefault('icons', self._cache())
        kwargs.setdefault('links', _links)
        kwargs.setdefault('set_links', SET_URLS.get)
        return render_build_html(entry or _entry(), unit, **kwargs)

    def _with(self, unit='1', **fields):
        """The session's fight with *fields* replaced on one player."""
        entry = _entry()
        _player(entry, unit).update(copy.deepcopy(fields))
        return entry

    # ---- header ----

    def test_full_header(self):
        from gui.build_render import SNAPSHOT_NOTE, build_title
        from gui.fight_render import ROLE_NAMES
        entry = self._with(role='D')
        html = self._html(entry)
        self.assertEqual(ROLE_NAMES['D'], 'DPS')
        self.assertIn(">Pïque · High Elf Warden · CP 3224 · DPS</span>", html)
        for expected in ('>@brainsnorkel</span>', 'Test Boss', 'Scalecaller Peak', '[VET]',
                         str(entry.timestamp), SNAPSHOT_NOTE):
            self.assertIn(expected, html)
        self.assertEqual(build_title(entry, '1'), 'Build – @brainsnorkel')

    def test_anonymous_player_has_no_character_name(self):
        from gui.build_render import SNAPSHOT_NOTE
        html = self._html(self._with(unit='3', role='U'), unit='3')
        self.assertIn('>anon</span>', html)
        # No empty character part before race and class, and no word for a
        # role the engine could not tell
        self.assertIn(f"<span style='color:{MUTED}'>Argonian Arcanist · CP 467</span>", html)
        self.assertIn(SNAPSHOT_NOTE, html)

    def test_borrowed_skill_lines_show_as_in_the_fight_view(self):
        html = self._html(self._with(skill_lines=['Animal Companions', 'Herald of the Tome'],
                                     class_lines=['Animal Companions', 'Green Balance',
                                                  "Winter's Embrace"]))
        self.assertIn('Animal/Herald', html)
        stock = self._html(self._with(skill_lines=['Animal Companions'],
                                      class_lines=['Animal Companions']))
        self.assertNotIn('Animal', stock)

    def test_player_the_fight_does_not_list(self):
        from gui.build_render import NO_BUILD, build_title
        self.assertIn(NO_BUILD, self._html(unit='77'))
        self.assertEqual(build_title(_entry(), '77'), 'Build')

    # ---- bars ----

    def test_two_full_bars_front_above_back(self):
        six = [_slot(n) for n in range(6)]
        html = self._html(self._with(front_bar_slots=six, back_bar_slots=six,
                                     front_bar=[s['name'] for s in six],
                                     back_bar=[s['name'] for s in six]))
        self.assertLess(html.index('>Front</td>'), html.index('>Back</td>'))
        self.assertEqual(html.count('<img src="icon:ability_weapon_001" width="36" height="36"'),
                         12)
        # Each bar sets its ultimate apart
        self.assertEqual(html.count('&nbsp;&nbsp;&nbsp;<a href'), 2)

    def test_no_back_bar(self):
        html = self._html(self._with(back_bar_slots=[], back_bar=[]))
        self.assertIn('>Front</td>', html)
        self.assertNotIn('>Back</td>', html)

    def test_abilities_the_player_taunted_with_are_marked_as_in_the_fight_view(self):
        slots = [_slot(0), _slot(1, icon='ability_missing'), _slot(2)]
        slots[0]['taunt'] = slots[1]['taunt'] = True
        html = self._html(self._with(front_bar_slots=slots,
                                     front_bar=[s['name'] for s in slots]))
        self.assertIn('<img src="icon:ability_weapon_001?ring=7b1fa2" width="36"', html)
        self.assertIn("<span style='color:#7b1fa2'>Skill 1</span>", html)
        self.assertEqual(html.count('?ring='), 1)
        dark = self._html(self._with(front_bar_slots=slots,
                                     front_bar=[s['name'] for s in slots]), dark=True)
        self.assertIn('?ring=ce93d8"', dark)

    def test_ability_without_a_bundled_icon_shows_its_name(self):
        slots = [_slot(1), _slot(2, icon='ability_missing', name='Odd Skill')]
        html = self._html(self._with(front_bar_slots=slots, front_bar=['Skill 1', 'Odd Skill']))
        self.assertIn('<a href="esolog:ability/1002" style="text-decoration:none">Odd Skill</a>',
                      html)

    def test_bar_with_fewer_than_six_sets_none_apart(self):
        five = [_slot(n) for n in range(5)]
        html = self._html(self._with(front_bar_slots=five, back_bar_slots=[],
                                     front_bar=[s['name'] for s in five], back_bar=[]))
        self.assertEqual(html.count('<img src="icon:ability_weapon_001"'), 5)
        self.assertNotIn('&nbsp;&nbsp;&nbsp;<a href', html)

    def test_ability_links_to_its_esohub_page_when_known(self):
        html = self._html()
        self.assertIn(f'<a href="{SKILL_URL}" style="text-decoration:none">', html)
        unlinked = self._html(links=lambda name: None)
        self.assertIn('<a href="esolog:ability/12345"', unlinked)

    def test_scribed_skill_with_known_scripts(self):
        from gui.fight_render import anchor_tooltips
        banner = {'id': '217699', 'name': 'Shocking Banner', 'icon': 'ability_grimoire_support',
                  'scribed': True, 'grimoire': 'Banner Bearer',
                  'scripts': ['Shock Damage', 'Class Flourish', 'Heroism']}
        entry = self._with(front_bar_slots=[_slot(1), banner],
                           front_bar=['Skill 1', 'Shocking Banner'])
        html = self._html(entry)
        self.assertIn('>Shocking Banner</a> (Class Flourish / Heroism)', html)
        tip = anchor_tooltips(entry)['esolog:ability/217699#class-flourish.heroism']
        for part in ('Grimoire: Banner Bearer', 'Focus: Shock Damage',
                     'Signature: Class Flourish', 'Affix: Heroism'):
            self.assertIn(part, tip)

    def test_scribed_skill_whose_scripts_the_log_does_not_give(self):
        soul = {'id': '216802', 'name': 'Warding Soul', 'icon': 'ability_grimoire_soulmagic1',
                'scribed': True, 'grimoire': 'Wield Soul'}
        html = self._html(self._with(back_bar_slots=[soul], back_bar=['Warding Soul']))
        self.assertIn('>Warding Soul</a> (scripts not in log)', html)

    # ---- gear grid ----

    def test_complete_build_has_a_row_per_slot_under_four_groups(self):
        from player_build import SLOT_GROUPS, SLOT_LABELS
        slots = [slot for _group, group_slots in SLOT_GROUPS for slot in group_slots
                 if 'POISON' not in slot]
        html = self._html(self._with(gear=[_item(slot) for slot in slots]))
        positions = [html.index(f'>{group}</td>') for group, _slots in SLOT_GROUPS]
        self.assertEqual(positions, sorted(positions))
        grid = html[positions[0]:]
        self.assertEqual(grid.count('>Alpha<'), 14)
        for label in set(SLOT_LABELS.values()) - {'Poison'}:
            self.assertIn(f'>{label}</td>', grid)
        titles = ('Slot', 'Type', 'Set', 'Pcs', 'Quality', 'Trait', 'Enchant',
                  'Enchant quality')
        header = [html.index(f'>{title}</td>') for title in titles]
        self.assertEqual(header, sorted(header))

    def test_row_cells_are_weight_set_pieces_quality_trait_enchant_enchant_quality(self):
        from gui.build_render import COLUMNS, _QUALITY_COLORS
        row = _row_of(self._html(), 'Head')
        gold = _QUALITY_COLORS[False]['LEGENDARY']
        cells = [cell.split('>', 1)[1] for cell in row.split('<td')[2:]]
        self.assertEqual(len(cells), len(COLUMNS) - 1)
        self.assertEqual(cells[0], 'Medium</td>')
        self.assertTrue(cells[1].startswith(f'<a href="{SET_URLS["Slimecraw"]}"'))
        self.assertEqual(cells[2], '1</td>')                      # pieces
        self.assertEqual(cells[3], f"<span style='color:{gold}'>Legendary</span></td>")
        self.assertEqual(cells[4], 'Divines</td>')
        self.assertEqual(cells[5], 'Magicka</td>')
        self.assertEqual(cells[6], f"<span style='color:{gold}'>Legendary</span></td>")

    def test_slot_the_log_did_not_list_keeps_its_row_with_a_dash(self):
        from gui.build_render import DASH
        html = self._html()   # two staves: neither bar has an off hand
        for group in ('Front bar', 'Back bar'):
            row = _row_of(html, 'Off hand', group)
            # The dash stands where the set would
            self.assertIn(f"{_slot_cell('Off hand')}<td></td>"
                          f"<td><span style='color:{MUTED}'>{DASH}</span></td>", row)
            self.assertNotIn('Legendary', row)

    def test_item_that_belongs_to_no_set(self):
        from gui.build_render import DASH
        gear = [_item('WAIST', set='', set_id='', pieces=None, trait='ARMOR_STURDY')]
        row = _row_of(self._html(self._with(gear=gear)), 'Waist')
        self.assertIn(f">{DASH}</span></td><td align='center'></td>", row)
        for shown in ('Legendary', 'Sturdy', 'Stamina'):
            self.assertIn(shown, row)

    def test_set_the_bundled_data_does_not_know_is_plain_text(self):
        gear = [_item('WAIST', set='Set#4242', set_id='4242', pieces=[1, 1])]
        row = _row_of(self._html(self._with(gear=gear)), 'Waist')
        self.assertIn('<td>Set#4242</td>', row)
        self.assertNotIn('<a ', row)

    def test_costume_is_not_shown(self):
        self.assertNotIn('Costume', self._html(unit='2'))

    # ---- armor weight ----

    def _armor_heading(self, html):
        """The cells of the Armor group's heading row."""
        start = html.index('>Armor</td>')
        return html[html.rindex('<tr>', 0, start):html.index('</tr>', start)]

    def test_armor_rows_show_their_weight_after_the_slot(self):
        html = self._html()
        self.assertIn(f"{_slot_cell('Head')}<td>Medium</td>", _row_of(html, 'Head'))
        self.assertIn(f"{_slot_cell('Shoulders')}<td>Light</td>", _row_of(html, 'Shoulders'))
        gear = [_item('CHEST', weight='heavy')]
        self.assertIn(f"{_slot_cell('Chest')}<td>Heavy</td>",
                      _row_of(self._html(self._with(gear=gear)), 'Chest'))

    def test_jewelry_leaves_the_type_empty(self):
        html = self._html()
        for label in ('Neck', 'Ring 1', 'Ring 2'):
            self.assertIn(f"{_slot_cell(label)}<td></td><td>", _row_of(html, label))

    def test_weapon_rows_show_their_type_after_the_slot(self):
        # @brainsnorkel's real weapons: a lightning staff and an ice staff,
        # typed from the bundled table
        html = self._html()
        self.assertIn(f"{_slot_cell('Main hand')}<td>Lightning Staff</td>",
                      _row_of(html, 'Main hand', 'Front bar'))
        self.assertIn(f"{_slot_cell('Main hand')}<td>Ice Staff</td>",
                      _row_of(html, 'Main hand', 'Back bar'))
        gear = [_item('MAIN_HAND', weapon_type='greatsword'),
                _item('BACKUP_MAIN', weapon_type='sword'),
                _item('BACKUP_OFF', weapon_type='shield', trait='ARMOR_STURDY')]
        html = self._html(self._with(gear=gear))
        self.assertIn(f"{_slot_cell('Main hand')}<td>Greatsword</td>",
                      _row_of(html, 'Main hand', 'Front bar'))
        self.assertIn(f"{_slot_cell('Main hand')}<td>Sword</td>",
                      _row_of(html, 'Main hand', 'Back bar'))
        self.assertIn(f"{_slot_cell('Off hand')}<td>Shield</td>",
                      _row_of(html, 'Off hand', 'Back bar'))

    def test_weapon_of_unknown_type_shows_a_dash(self):
        from gui.build_render import DASH
        gear = [_item('MAIN_HAND', weapon_type=''), _item('OFF_HAND', weapon_type='wand')]
        html = self._html(self._with(gear=gear))
        for label in ('Main hand', 'Off hand'):
            self.assertIn(f"{_slot_cell(label)}<td><span style='color:{MUTED}'>{DASH}</span></td>",
                          _row_of(html, label, 'Front bar'))

    def test_armor_piece_of_unknown_weight_shows_a_dash(self):
        from gui.build_render import DASH
        gear = [_item('HEAD'), _item('CHEST', weight=''), _item('LEGS', weight='plate')]
        html = self._html(self._with(gear=gear))
        for label in ('Chest', 'Legs'):
            self.assertIn(f"{_slot_cell(label)}<td><span style='color:{MUTED}'>{DASH}</span></td>",
                          _row_of(html, label))
        self.assertIn('>1 medium, 2 unknown</td>', self._armor_heading(html))

    def test_row_from_before_weights_were_recorded_still_draws(self):
        row = _item('HEAD')
        del row['weight']
        self.assertIn('>Alpha<', _row_of(self._html(self._with(gear=[row])), 'Head'))

    def test_armor_heading_counts_the_weights_worn(self):
        from gui.build_render import COLUMNS
        heading = self._armor_heading(self._html())
        self.assertEqual(
            heading,
            f"<tr><td colspan='1' style='padding-top:7px;color:{MUTED};font-weight:bold'>"
            f"Armor</td><td colspan='{len(COLUMNS) - 1}' style='padding-top:7px;"
            f"color:{MUTED}'>6 medium, 1 light</td>")

    def test_weight_counts_put_the_most_worn_first(self):
        def tally(*weights):
            gear = [_item(slot, weight=weight) for slot, weight in zip(ARMOR, weights)]
            heading = self._armor_heading(self._html(self._with(gear=gear)))
            return heading[:-len('</td>')].rsplit('>', 1)[1]

        self.assertEqual(tally('heavy', 'light', 'medium', 'medium', 'medium', 'medium',
                               'medium'), '5 medium, 1 light, 1 heavy')
        self.assertEqual(tally(*['heavy'] * 7), '7 heavy')
        # Equal counts keep the order light, medium, heavy
        self.assertEqual(tally('heavy', 'heavy', 'heavy', 'light', 'light', 'light', 'medium'),
                         '3 light, 3 heavy, 1 medium')
        self.assertEqual(tally('light', 'heavy'), '1 light, 1 heavy')

    def test_no_armor_no_weight_count(self):
        from gui.build_render import COLUMNS
        heading = self._armor_heading(self._html(self._with(gear=[_item('MAIN_HAND')])))
        self.assertEqual(heading.count('<td'), 1)
        self.assertIn(f"colspan='{len(COLUMNS)}'", heading)

    # ---- item attributes ----

    def test_mythic_piece_reads_mythic_in_the_mythic_color(self):
        from gui.build_render import _QUALITY_COLORS
        row = _row_of(self._html(), 'Ring 2')
        self.assertIn('Shattered Paths Signet', row)
        self.assertIn(f"<span style='color:{_QUALITY_COLORS[False]['MYTHIC_OVERRIDE']}'>"
                      f"Mythic</span>", row)

    def test_internal_trait_name(self):
        gear = [_item('CHEST', trait='ARMOR_PROSPEROUS')]
        self.assertIn('<td>Invigorating</td>', _row_of(self._html(self._with(gear=gear)), 'Chest'))

    def test_epic_gear_with_a_legendary_enchant(self):
        from gui.build_render import _QUALITY_COLORS
        colors = _QUALITY_COLORS[False]
        gear = [_item('CHEST', quality='ARTIFACT', enchant_quality='LEGENDARY')]
        row = _row_of(self._html(self._with(gear=gear)), 'Chest')
        self.assertIn(f"<span style='color:{colors['ARTIFACT']}'>Epic</span>", row)
        self.assertIn(f"<span style='color:{colors['LEGENDARY']}'>Legendary</span>", row)

    def test_item_without_an_enchant(self):
        from gui.build_render import DASH
        gear = [_item('RING1', trait='JEWELRY_BLOODTHIRSTY', enchant='INVALID',
                      enchant_quality='')]
        row = _row_of(self._html(self._with(gear=gear)), 'Ring 1')
        self.assertTrue(row.endswith(f"<td>Bloodthirsty</td>"
                                     f"<td><span style='color:#5f6368'>{DASH}</span></td>"
                                     f"<td><span style='color:#5f6368'>{DASH}</span></td>"))

    def test_value_the_app_does_not_know_stays_readable(self):
        gear = [_item('MAIN_HAND', trait='WEAPON_NEW_TRAIT', enchant='BRAND_NEW_GLYPH',
                      quality='SHINY')]
        row = _row_of(self._html(self._with(gear=gear)), 'Main hand')
        for shown in ('<td>New Trait</td>', '<td>Brand New Glyph</td>', '<td>Shiny</td>'):
            self.assertIn(shown, row)

    def test_item_below_the_level_cap_shows_its_level(self):
        html = self._html(unit='2')
        self.assertIn("Superior</span> <span style='color:#5f6368'>CP150</span>",
                      _row_of(html, 'Ring 1'))
        self.assertNotIn('CP1', _row_of(html, 'Head'))

    # ---- set links ----

    def test_known_set_links_to_its_page_with_the_target_in_the_hover(self):
        from gui.fight_render import anchor_tooltips
        entry = _entry()
        url = SET_URLS['Perfected Whorl of the Depths']
        self.assertIn(f'<a href="{url}" style="text-decoration:none;color:#202124">'
                      f'Perfected Whorl of the Depths</a>', self._html(entry))
        tip = anchor_tooltips(entry, set_links=SET_URLS.get)[url]
        self.assertIn('<b>Perfected Whorl of the Depths</b>', tip)
        self.assertIn(url, tip)

    def test_set_without_a_page_is_plain_text(self):
        row = _row_of(self._html(), 'Chest')
        self.assertIn("<td>Aerie&#x27;s Cry</td>", row)
        self.assertNotIn('<a ', row)

    # ---- piece counts ----

    def test_counts_per_bar_for_a_set_the_back_bar_completes(self):
        from gui.build_render import PIECES_NOTE
        html = self._html()

        def pieces(label, group=None):
            return _row_of(html, label, group).split("<td align='center'>")[1].split('<')[0]

        # Whorl: three on the body, plus the back-bar staff as two
        self.assertEqual([pieces(slot) for slot in ('Shoulders', 'Neck', 'Ring 1')],
                         ['3/5', '3/5', '3/5'])
        self.assertEqual(pieces('Main hand', 'Back bar'), '5')
        # The same count on both bars is one number; a weapon shows its own bar
        self.assertEqual(pieces('Chest'), '5')
        self.assertEqual(pieces('Main hand', 'Front bar'), '2')
        self.assertIn(PIECES_NOTE, html)

    def test_no_back_bar_gives_single_numbers(self):
        gear = [_item('HEAD', pieces=[3, None]), _item('MAIN_HAND', pieces=[3, None]),
                _item('OFF_HAND', pieces=[3, None])]
        html = self._html(self._with(gear=gear))
        for label in ('Head', 'Main hand', 'Off hand'):
            self.assertIn("<td align='center'>3</td>", _row_of(html, label))

    # ---- poisons ----

    def test_poison_rows_sit_under_their_bar(self):
        from gui.build_render import _QUALITY_COLORS, POISON_NOTE
        html = self._html(unit='2')
        front = _row_of(html, 'Poison', 'Front bar')
        # Named in the set column, under the weapons' sets
        self.assertIn(f"{_slot_cell('Poison')}<td></td><td>Crown Lethal Poison</td>", front)
        self.assertIn(f"<span style='color:{_QUALITY_COLORS[False]['LEGENDARY']}'>Legendary</span>",
                      front)
        self.assertIn(POISON_NOTE, front)
        self.assertLess(html.index('>Back bar</td>'), html.index('Cloudy Hindering Poison IX'))
        self.assertIn('<td>Cloudy Hindering Poison IX</td>', _row_of(html, 'Poison', 'Back bar'))

    def test_unknown_poison_shows_its_item_id(self):
        gear = [_item('MAIN_HAND'),
                {'slot': 'POISON', 'item_id': '99999', 'name': 'Poison (item 99999)',
                 'quality': 'NORMAL', 'set': '', 'pieces': None}]
        self.assertIn('<td>Poison (item 99999)</td>',
                      _row_of(self._html(self._with(gear=gear)), 'Poison'))

    def test_no_poison_no_row(self):
        html = self._html()
        self.assertNotIn(_slot_cell('Poison'), html)
        # (the staff's Poison enchant is a different cell)
        self.assertIn('<td>Poison</td>', _row_of(html, 'Main hand', 'Front bar'))

    # ---- mundus and food ----

    def test_one_mundus_stone_with_its_icon(self):
        html = self._html()
        self.assertIn('Mundus</span>&nbsp; <img src="icon:ability_mundusstones_003" '
                      'width="18" height="18" style="vertical-align:middle">&nbsp;The Thief',
                      html)

    def test_two_mundus_stones(self):
        # The Atronach's icon is not in this cache: its name stands alone
        self.assertIn('Mundus</span>&nbsp; The Atronach, <img src="icon:ability_mundusstones_003"',
                      self._html(unit='3'))

    def test_translated_mundus_name_is_shown_as_logged(self):
        stone = [{'id': '13975', 'name': 'Segen: Der Dieb', 'icon': 'ability_mundusstones_003'}]
        self.assertIn('&nbsp;Segen: Der Dieb', self._html(self._with(mundus=stone)))

    def test_no_mundus_logged(self):
        from gui.build_render import NO_MUNDUS
        self.assertIn(f"Mundus</span>&nbsp; <span style='color:#5f6368'>{NO_MUNDUS}</span>",
                      self._html(self._with(mundus=[])))

    def test_food_and_drink(self):
        self.assertIn('Food</span>&nbsp; Increase Max Health &amp; Magicka', self._html())
        self.assertIn('Drink</span>&nbsp; Witchmother&#x27;s Potent Brew', self._html(unit='2'))

    def test_no_food_at_combat_start(self):
        from gui.build_render import NO_FOOD
        self.assertIn(f"Food</span>&nbsp; <span style='color:#5f6368'>{NO_FOOD}</span>",
                      self._html(unit='3'))

    def test_food_is_left_out_when_it_was_not_checked(self):
        entry = _entry()
        del _player(entry, '1')['food']
        html = self._html(entry)
        self.assertNotIn('Food</span>', html)
        self.assertIn('Mundus</span>', html)

    # ---- no gear, themes, escaping ----

    def test_player_without_logged_gear(self):
        from gui.build_render import NO_GEAR
        html = self._html(unit='3')
        self.assertIn(NO_GEAR, html)
        self.assertNotIn('Enchant quality', html)
        self.assertIn('>Front</td>', html)       # bars, mundus and food still show
        self.assertIn('Mundus</span>', html)

    def test_themes_use_different_colors(self):
        from gui.build_render import _QUALITY_COLORS
        light, dark = self._html(), self._html(dark=True)
        self.assertNotEqual(light, dark)
        self.assertIn(_QUALITY_COLORS[True]['LEGENDARY'], dark)
        self.assertNotIn(_QUALITY_COLORS[False]['LEGENDARY'], dark)
        self.assertIn('color:#e8eaed">Perfected Whorl of the Depths</a>', dark)

    def test_names_are_escaped(self):
        entry = self._with(name='<b>@x</b>', character='<i>C</i>',
                           gear=[_item('HEAD', set='A<u>B')],
                           mundus=[{'id': '1', 'name': '<s>M</s>', 'icon': ''}],
                           food={'id': '2', 'name': '<s>F</s>', 'kind': 'food'})
        entry.boss_name = '<b>Boss</b>'
        html = self._html(entry)
        for raw in ('<b>@x</b>', '<i>C</i>', 'A<u>B', '<s>M</s>', '<s>F</s>', '<b>Boss</b>'):
            self.assertNotIn(raw, html)
        self.assertIn('A&lt;u&gt;B', html)


class TestBuildWindow(BuildGuiTestCase):

    def test_real_mouse_click_on_a_name_opens_the_build(self):
        """End to end: a click on the rendered name, not an emitted signal."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(_entry(), show=True)
        try:
            self.assertIsNone(win._build_dialog)
            view = win.fight_view
            QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                             self._point_on(view, '@brainsnorkel'))
            _app.processEvents()
            dialog = win._build_dialog
            self.assertIsNotNone(dialog)
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.isModal())
            self.assertEqual(dialog.windowTitle(), 'Build – @brainsnorkel')
            text = dialog.view.toPlainText()
            for expected in ('Pïque', 'High Elf Warden', 'The Thief',
                             'Perfected Whorl of the Depths', 'Bloodthirsty', '3/5',
                             'Increase Max Health & Magicka', '6 medium, 1 light'):
                self.assertIn(expected, text)
        finally:
            win.close()

    def test_second_player_reuses_the_window(self):
        from PySide6.QtCore import QUrl
        win = self._window(_entry())
        try:
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/1'))
            dialog = win._build_dialog
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/2'))
            self.assertIs(win._build_dialog, dialog)
            self.assertEqual(dialog.windowTitle(), 'Build – @dualwield')
            text = dialog.view.toPlainText()
            self.assertIn('Crown Lethal Poison', text)
            self.assertNotIn('Perfected Whorl of the Depths', text)
        finally:
            win.close()

    def test_click_works_in_the_compact_view(self):
        from PySide6.QtCore import QUrl
        win = self._window(_entry())
        try:
            win.detail_action.setChecked(False)
            self.assertIn('esolog:build/3', win.fight_view._tooltips)
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/3'))
            self.assertEqual(win._build_dialog.windowTitle(), 'Build – anon')
        finally:
            win.close()

    def test_window_stays_on_the_fight_it_was_opened_for(self):
        from PySide6.QtCore import QUrl
        win = self._window(_entry())
        try:
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/1'))
            dialog = win._build_dialog
            shown = dialog.view.toHtml()
            # A new fight arrives and becomes the fight on screen
            later = _entry()
            later.boss_name = 'Another Boss'
            _player(later, '1')['gear'] = []
            win._on_fight_completed(later)
            self.assertEqual(win.history_list.currentRow(), 1)
            self.assertIn('Another Boss', win.fight_view.toPlainText())
            self.assertEqual(dialog.view.toHtml(), shown)
            self.assertEqual(dialog.windowTitle(), 'Build – @brainsnorkel')
            # Selecting the older fight again changes nothing either
            win.history_list.setCurrentRow(0)
            self.assertEqual(dialog.view.toHtml(), shown)
        finally:
            win.close()

    def test_build_opens_for_a_fight_of_a_reviewed_log(self):
        from PySide6.QtCore import QUrl
        win = self._window()
        try:
            win._on_review_loaded('old.log', [_entry()])
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/2'))
            self.assertIn('Cloudy Hindering Poison IX', win._build_dialog.view.toPlainText())
        finally:
            win.close()

    def test_hovering_an_ability_and_a_set_in_the_window_shows_their_text(self):
        from PySide6.QtCore import QUrl
        from ability_icons import esohub_set_url
        win = self._window(_entry())
        try:
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/1'))
            view = win._build_dialog.view
            view.highlighted.emit(QUrl('esolog:ability/12345'))
            self.assertIn('Damage Ability', view.current_tooltip)
            url = esohub_set_url('Slimecraw')
            self.assertIn(f'href="{url}"', view.toHtml())
            view.highlighted.emit(QUrl(url))
            self.assertIn('Slimecraw', view.current_tooltip)
            self.assertIn('Click to open on ESO-Hub', view.current_tooltip)
        finally:
            win.close()

    def test_set_link_opens_in_the_browser_and_not_as_a_build(self):
        from PySide6.QtCore import QUrl
        from ability_icons import esohub_set_url
        win = self._window(_entry())
        try:
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/1'))
            view = win._build_dialog.view
            opened = []
            view._open_external = lambda url: opened.append(url.toString()) or True
            view.anchorClicked.emit(QUrl(esohub_set_url('Slimecraw')))
            self.assertEqual(opened, [esohub_set_url('Slimecraw')])
        finally:
            win.close()

    def test_open_window_follows_a_theme_switch(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QColor, QPalette
        from gui.build_render import _QUALITY_COLORS
        win = self._window(_entry())
        try:
            win.fight_view.anchorClicked.emit(QUrl('esolog:build/1'))
            dialog = win._build_dialog
            self.assertIn(_QUALITY_COLORS[False]['LEGENDARY'], dialog.view.toHtml())

            palette = QPalette()
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.Window, QColor('#1e1e1e'))
                palette.setColor(group, QPalette.WindowText, QColor('#eeeeee'))
            win.setPalette(palette)
            win._on_theme_maybe_changed()
            self.assertIn(_QUALITY_COLORS[True]['LEGENDARY'], dialog.view.toHtml())
            self.assertNotIn(_QUALITY_COLORS[False]['LEGENDARY'], dialog.view.toHtml())
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
