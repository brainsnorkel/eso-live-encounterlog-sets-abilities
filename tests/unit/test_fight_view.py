#!/usr/bin/env python3
"""Ability-bar icons in the fight pane (offscreen Qt): rendering, the icon
cache, hover text, and external link routing."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

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


def _entry_with_bars():
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.zone_name = 'Coral Aerie'
    entry.timestamp = '2025-08-21 09:21:25'
    entry.players = [{
        'role': 'D', 'name': '@tester', 'class_abbr': 'NB', 'dps': 1000.0,
        'dmg_pct': 50.0, 'h': 20000, 'm': 30000, 's': 15000, 'unit_id': '1',
        'sets': [], 'all_sets': [(5, 'Deadly Strike')],
        'skill_lines': ['Assassination', 'Shadow', 'Siphoning'],
        'class_lines': ['Assassination', 'Shadow', 'Siphoning'],
        'front_bar': ['Biting Jabs', 'Unknown Thing'],
        'back_bar': [],
        'front_bar_slots': [
            {'id': '26792', 'name': 'Biting Jabs', 'icon': 'ability_test_001'},
            {'id': '99', 'name': 'Unknown Thing', 'icon': 'ability_missing'},
        ],
        'back_bar_slots': [],
    }]
    return entry


def _links(name):
    return ('https://eso-hub.com/en/skills/templar/aedric-spear/biting-jabs'
            if name == 'Biting Jabs' else None)


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class FightViewTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.icons_root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        self.assertTrue(image.save(str(self.icons_root / 'ability_test_001.png')))

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        from gui.icon_cache import IconCache
        return IconCache(self.icons_root)


class TestIconCache(FightViewTestCase):

    def test_loads_once_and_remembers_misses(self):
        cache = self._cache()
        self.assertTrue(cache.has('ability_test_001'))
        self.assertIs(cache.image('ability_test_001'), cache.image('ability_test_001'))
        self.assertEqual(cache.image('ability_test_001').width(), 40)
        self.assertFalse(cache.has('ability_missing'))
        self.assertFalse(cache.has(''))
        self.assertEqual(len(cache), 1)


class TestBarRendering(FightViewTestCase):

    def test_icons_replace_names_and_fall_back_to_text(self):
        from gui.fight_render import render_html
        html = render_html(_entry_with_bars(), detailed=True, icons=self._cache(), links=_links)
        self.assertIn('<img src="icon:ability_test_001"', html)
        self.assertNotIn('>Biting Jabs<', html)          # icon stands in for the name
        self.assertIn('Unknown Thing', html)             # no icon: name stays visible
        self.assertIn('href="https://eso-hub.com/en/skills/templar/aedric-spear/biting-jabs"', html)
        self.assertIn('href="esolog:ability/99"', html)  # hover anchor without a page

    def test_icon_bars_sit_side_by_side(self):
        """Bar 1 left of bar 2 on one line when both render as icons."""
        from gui.fight_render import BAR_DIVIDER, render_html
        entry = _entry_with_bars()
        player = entry.players[0]
        player['back_bar'] = ['Biting Jabs']
        player['back_bar_slots'] = [{'id': '26792', 'name': 'Biting Jabs', 'icon': 'ability_test_001'}]
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        self.assertEqual(html.count('<img '), 2)
        first_img, second_img = html.index('<img '), html.rindex('<img ')
        divider = html.index(BAR_DIVIDER)
        self.assertLess(first_img, divider)
        self.assertLess(divider, second_img)
        self.assertNotIn('<br>', html[first_img:second_img])  # same line
        # Text bars keep their own lines
        text_html = render_html(entry, detailed=True)
        self.assertNotIn(BAR_DIVIDER, text_html)
        self.assertIn('<td>Biting Jabs, Unknown Thing<br>Biting Jabs</td>', text_html)

    def test_set_names_link_to_esohub_pages(self):
        from gui.fight_render import anchor_tooltips, render_html, render_plain_text
        entry = _entry_with_bars()
        entry.players[0]['all_sets'] = [(5, 'Deadly Strike'), (2, 'Unknown Set'), (5, 'Arms of Relequen', True)]
        set_links = lambda n: {'Deadly Strike': 'https://eso-hub.com/en/sets/deadly-strike',  # noqa: E731
                               'Arms of Relequen': 'https://eso-hub.com/en/sets/perfected-arms-of-relequen'}.get(n)
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links, set_links=set_links)
        self.assertIn('5x <a href="https://eso-hub.com/en/sets/deadly-strike"', html)
        self.assertIn('>Deadly Strike</a>', html)
        self.assertIn('2x Unknown Set', html)       # no page known: plain text
        self.assertNotIn('<a href="esolog:set', html)
        self.assertIn('5x <a href="https://eso-hub.com/en/sets/perfected-arms-of-relequen"', html)
        self.assertNotIn('<i>', html)               # set list is not italic
        self.assertIn("<span style='font-size:6.75pt'>5x", html)  # 25% below the 9pt base
        tips = anchor_tooltips(entry, links=_links, set_links=set_links)
        self.assertIn('Deadly Strike', tips['https://eso-hub.com/en/sets/deadly-strike'])
        self.assertIn('eso-hub.com', tips['https://eso-hub.com/en/sets/deadly-strike'])
        # Without a set map the list is plain, and the clipboard copy never links
        self.assertIn('5x Deadly Strike, 2x Unknown Set, 5x Arms of Relequen',
                      render_html(entry, detailed=True))
        self.assertIn('5x Deadly Strike, 2x Unknown Set, 5x Arms of Relequen',
                      render_plain_text(entry))

    def test_name_row_bolds_major_resource_and_shows_subclass_lines(self):
        from gui.fight_render import render_html
        entry = _entry_with_bars()
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        self.assertIn('H 20.0k · <b>M 30.0k</b> · S 15.0k', html)
        # A stock Nightblade: the class abbreviation says it all
        self.assertNotIn('Assassination/Shadow/Siphoning', html)
        self.assertNotIn('Assassination / Shadow', html)  # and never inside the card
        # Subclassed: lines appear beside the class, first words, no spaces around /
        entry.players[0]['skill_lines'] = ['Assassination', 'Shadow', 'Herald of the Tome']
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        name_row = html[html.index('@tester'):html.index('<td align=')]
        self.assertIn("NB</span> <span style='color:", name_row)
        self.assertIn('Assassination/Shadow/Herald</span>', name_row)
        self.assertEqual(html.count('Assassination/Shadow/Herald'), 1)
        # Compact view carries it too, and the plain copy keeps full names
        self.assertIn('Assassination/Shadow/Herald', render_html(entry, detailed=False))
        from gui.fight_render import render_plain_text
        self.assertIn('Assassination/Shadow/Herald of the Tome', render_plain_text(entry))
        # Unknown class: lines are shown rather than hidden
        entry.players[0]['class_lines'] = []
        entry.players[0]['skill_lines'] = ["Dawn's Wrath", 'Bone Tyrant']
        self.assertIn('Dawn/Bone', render_html(entry, detailed=False))

    def test_without_icon_cache_bars_stay_text(self):
        from gui.fight_render import render_html, render_plain_text
        entry = _entry_with_bars()
        html = render_html(entry, detailed=True)
        self.assertNotIn('<img', html)
        self.assertIn('Biting Jabs, Unknown Thing', html)
        self.assertIn('Biting Jabs, Unknown Thing', render_plain_text(entry))

    def test_anchor_tooltips_name_every_slot_and_link(self):
        from gui.fight_render import anchor_tooltips
        tips = anchor_tooltips(_entry_with_bars(), links=_links)
        linked = tips['https://eso-hub.com/en/skills/templar/aedric-spear/biting-jabs']
        self.assertIn('Biting Jabs', linked)
        self.assertIn('eso-hub.com', linked)
        unlinked = tips['esolog:ability/99']
        self.assertIn('Unknown Thing', unlinked)
        self.assertNotIn('eso-hub.com', unlinked)


class TestFightViewWidget(FightViewTestCase):

    def test_serves_icons_and_never_navigates(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        self.assertFalse(view.openLinks())
        image = view.loadResource(QTextDocument.ImageResource, QUrl('icon:ability_test_001'))
        self.assertEqual(image.width(), 40)
        from gui.fight_render import render_html
        view.resize(400, 200)
        view.show()
        _app.processEvents()
        view.setHtml(render_html(_entry_with_bars(), detailed=True, icons=view.icons, links=_links))
        self.assertIn('@tester', view.toPlainText())
        # The document resolves icon: URLs through the view's loadResource
        resource = view.document().resource(QTextDocument.ImageResource, QUrl('icon:ability_test_001'))
        self.assertEqual(resource.width(), 40)
        # ...and the laid-out page really draws the (red) icon
        from PySide6.QtGui import QColor, QImage, QPainter
        _app.processEvents()
        out = QImage(400, 200, QImage.Format_ARGB32)
        out.fill(QColor('white'))
        painter = QPainter(out)
        view.document().drawContents(painter)
        painter.end()
        reds = sum(1 for x in range(400) for y in range(200)
                   if out.pixelColor(x, y).red() > 200 and out.pixelColor(x, y).green() < 60)
        self.assertGreater(reds, 50)

    def test_external_links_open_outside_and_hover_shows_name(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QToolTip
        from gui.fight_view import FightView
        opened = []
        view = FightView(icons=self._cache(), open_external=lambda url: opened.append(url.toString()) or True)
        view.anchorClicked.emit(QUrl('https://eso-hub.com/en/skills/x/y/z'))
        view.anchorClicked.emit(QUrl('esolog:ability/99'))
        self.assertEqual(opened, ['https://eso-hub.com/en/skills/x/y/z'])
        view.set_tooltips({'esolog:ability/99': '<b>Unknown Thing</b>'})
        view.highlighted.emit(QUrl('esolog:ability/99'))
        self.assertEqual(view.current_tooltip, '<b>Unknown Thing</b>')
        self.assertEqual(QToolTip.text(), '<b>Unknown Thing</b>')
        # Leaving the anchor hides the tip (Qt fades it on a timer, so check
        # the view's own state rather than QToolTip.text())
        view.highlighted.emit(QUrl())
        self.assertEqual(view.current_tooltip, '')
        view.highlighted.emit(QUrl('esolog:ability/unknown'))
        self.assertEqual(view.current_tooltip, '')

    def test_scribed_skill_anchors_differ_by_scripts(self):
        """Two players' Shocking Banners share a page but not their hover."""
        from PySide6.QtCore import QUrl
        from gui.fight_render import anchor_tooltips, render_html
        from gui.fight_view import FightView
        entry = _entry_with_bars()
        page = 'https://eso-hub.com/en/scribing/combination/93/shocking-banner'
        for name, affix in (('@tester', 'Heroism'), ('@other', 'Berserk')):
            entry.players.append(dict(entry.players[0], name=name, front_bar=['Shocking Banner'],
                                      front_bar_slots=[{
                                          'id': '217699', 'name': 'Shocking Banner', 'scribed': True,
                                          'icon': 'ability_test_001', 'grimoire': 'Banner Bearer',
                                          'scripts': ['Shock Damage', 'Class Flourish', affix]}]))
        links = lambda name: page if name == 'Shocking Banner' else None  # noqa: E731
        opened = []
        view = FightView(icons=self._cache(), open_external=lambda url: opened.append(url.toString()) or True)
        view.set_tooltips(anchor_tooltips(entry, links=links))
        view.setHtml(render_html(entry, detailed=True, icons=view.icons, links=links))
        # The anchors survive Qt's URL handling as written, so each finds its text
        hrefs = [f'{page}#class-flourish.heroism', f'{page}#class-flourish.berserk']
        for href, affix in zip(hrefs, ('Heroism', 'Berserk')):
            self.assertIn(f'href="{href}"', render_html(entry, detailed=True, links=links))
            view.highlighted.emit(QUrl(href))
            self.assertIn(f'Affix: {affix}', view.current_tooltip)
        view.anchorClicked.emit(QUrl(hrefs[0]))
        self.assertEqual(opened, [hrefs[0]])


class TestSearchFindsAbilityIcons(FightViewTestCase):
    """Ctrl+F matches an icon by the ability name behind it."""

    def _view_with_bars(self):
        from gui.fight_render import anchor_names, render_html
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        view.resize(480, 320)  # tall enough that the bar row is inside the viewport
        view.show()
        _app.processEvents()
        entry = _entry_with_bars()
        view.set_anchor_names(anchor_names(entry, links=_links))
        view.setHtml(render_html(entry, detailed=True, icons=view.icons, links=_links))
        _app.processEvents()
        return view

    def test_anchor_matches_select_icons_by_name(self):
        view = self._view_with_bars()
        hits = view.anchor_matches('JABS')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].selectedText(), '￼')  # the icon's object character
        # A slot shown as text is found by QTextDocument.find, never duplicated here
        self.assertEqual(view.anchor_matches('unknown'), [])
        self.assertEqual(view.anchor_matches(''), [])
        self.assertEqual(view.anchor_matches('zzz'), [])

    def test_icon_highlight_is_visible(self):
        """An extra selection over the icon tints the icon itself."""
        from PySide6.QtGui import QColor, QTextCharFormat
        from PySide6.QtWidgets import QTextEdit
        view = self._view_with_bars()

        def pure_red_pixels():
            image = view.grab().toImage()
            return sum(1 for x in range(image.width()) for y in range(image.height())
                       if (c := image.pixelColor(x, y)).red() > 200 and c.green() < 60 and c.blue() < 60)

        before = pure_red_pixels()
        self.assertGreater(before, 100)
        highlight = QTextCharFormat()
        highlight.setBackground(QColor('#ffd54f'))
        highlight.setForeground(QColor('#000000'))
        selections = []
        for cursor in view.anchor_matches('jabs'):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight
            selections.append(selection)
        view.setExtraSelections(selections)
        _app.processEvents()
        self.assertLess(pure_red_pixels(), before * 0.5)

    def test_window_search_counts_and_cycles_icon_matches(self):
        from app_config import AppConfig
        from gui.icon_cache import IconCache
        from gui.main_window import MainWindow
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.icons_root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            win.fight_view.icons = IconCache(self.icons_root)
            win._on_fight_completed(_entry_with_bars())
            win.history_list.setCurrentRow(0)
            self.assertNotIn('Biting Jabs', win.fight_view.toPlainText())

            win.search_field.setText('jabs')
            selections = win.fight_view.extraSelections()
            self.assertEqual(len(selections), 1)
            self.assertEqual(selections[0].cursor.selectedText(), '￼')
            self.assertIn('1 match', win.search_count.text())

            # Text and icon matches combine ("Unknown Thing" text + Biting Jabs icon)
            win.search_field.setText('ing')
            matches = win._search_matches()
            self.assertEqual(len(matches), 2)
            self.assertEqual([m.selectedText() for m in matches], ['￼', 'ing'])
            self.assertIn('2 matches', win.search_count.text())
            first = win.fight_view.textCursor().position()
            win._goto_next_match()
            self.assertGreater(win.fight_view.textCursor().position(), first)

            win.search_field.clear()
            self.assertEqual(win.fight_view.extraSelections(), [])
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
