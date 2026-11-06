#!/usr/bin/env python3
"""Ability-bar icons in the fight pane (offscreen Qt): rendering, the icon
cache, hover text, and external link routing."""

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

    def test_abilities_the_player_taunted_with_are_ringed_or_purple(self):
        from gui.fight_render import render_html
        entry = _entry_with_bars()
        slots = entry.players[0]['front_bar_slots']
        slots[0]['taunt'] = True   # has an icon: ringed in the taunt color
        slots[1]['taunt'] = True   # no icon: its name in that color
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        self.assertIn('<img src="icon:ability_test_001?ring=7b1fa2"', html)
        self.assertIn("<span style='color:#7b1fa2;font-weight:bold'>Unknown Thing</span>", html)
        dark = render_html(entry, detailed=True, dark=True, icons=self._cache(), links=_links)
        self.assertIn('<img src="icon:ability_test_001?ring=ce93d8"', dark)
        self.assertIn("<span style='color:#ce93d8;font-weight:bold'>Unknown Thing</span>", dark)
        # Without an icon cache the bar is text, the taunting names colored
        text = render_html(entry, detailed=True, links=_links)
        self.assertIn("<span style='color:#7b1fa2;font-weight:bold'>Biting Jabs</span>, "
                      "<span style='color:#7b1fa2;font-weight:bold'>Unknown Thing</span>", text)
        # Nothing marked: no ring and no color
        plain = render_html(_entry_with_bars(), detailed=True, icons=self._cache(), links=_links)
        self.assertNotIn('?ring=', plain)
        self.assertNotIn('#7b1fa2', plain)
        self.assertNotIn('<span', render_html(_entry_with_bars(), detailed=True, links=_links)
                         .split('Biting Jabs')[0][-40:])

    def test_icon_bars_sit_side_by_side(self):
        """Bar 1 left of bar 2 on one line when both render as icons."""
        from gui.fight_render import BAR_DIVIDER, render_html
        entry = _entry_with_bars()
        player = entry.players[0]
        player['back_bar'] = ['Biting Jabs']
        player['back_bar_slots'] = [{'id': '26792', 'name': 'Biting Jabs', 'icon': 'ability_test_001'}]
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        # Two ability icons (the dps figure's link glyph is an image too)
        icon = '<img src="icon:'
        self.assertEqual(html.count(icon), 2)
        first_img, second_img = html.index(icon), html.rindex(icon)
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
        # Subclassed: only the borrowed line appears beside the class, its
        # first word after a plus sign
        entry.players[0]['skill_lines'] = ['Assassination', 'Shadow', 'Herald of the Tome']
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        name_row = html[html.index('@tester'):html.index('<td align=')]
        self.assertIn("NB</span> <span style='color:", name_row)
        self.assertIn('+Herald</span>', name_row)
        self.assertNotIn('Assassination', name_row)
        self.assertEqual(html.count('+Herald'), 1)
        # Compact view carries it too, and the plain copy keeps full names
        self.assertIn('+Herald', render_html(entry, detailed=False))
        from gui.fight_render import render_plain_text
        self.assertIn('+Herald of the Tome', render_plain_text(entry))
        self.assertNotIn('Assassination/Shadow', render_plain_text(entry))
        # Two borrowed lines, each with its own plus sign
        entry.players[0]['skill_lines'] = ['Assassination', 'Animal Companions', 'Herald of the Tome']
        self.assertIn('+Animal +Herald', render_html(entry, detailed=False))
        # Class Mastery passives: a pure-class build names them after the
        # class, with a colon ("NB: An Eye for Exploitation, Above and Beyond")
        entry.players[0]['skill_lines'] = ['Assassination', 'Shadow', 'Siphoning']
        entry.players[0]['masteries'] = ['An Eye for Exploitation', 'Above and Beyond']
        html = render_html(entry, detailed=True, icons=self._cache(), links=_links)
        self.assertIn("NB:</span> <span style='color:", html)
        self.assertIn('An Eye for Exploitation, Above and Beyond</span>', html)
        self.assertIn('      An Eye for Exploitation, Above and Beyond', render_plain_text(entry))
        self.assertIn('NB:', render_html(entry, detailed=False))
        # A subclassed build cannot have one; the borrowed lines win the place
        entry.players[0]['skill_lines'] = ['Assassination', 'Shadow', 'Herald of the Tome']
        self.assertIn('NB</span>', render_html(entry, detailed=False))
        self.assertIn('+Herald', render_html(entry, detailed=False))
        entry.players[0]['skill_lines'] = ['Assassination', 'Shadow', 'Siphoning']
        entry.players[0]['masteries'] = []
        self.assertNotIn('NB:', render_html(entry, detailed=False))
        self.assertNotIn('Exploitation', render_plain_text(entry))
        # Unknown class: every line is shown rather than hidden
        entry.players[0]['class_lines'] = []
        entry.players[0]['skill_lines'] = ["Dawn's Wrath", 'Bone Tyrant']
        self.assertIn('Dawn/Bone', render_html(entry, detailed=False))

    def test_a_lone_mastery_is_followed_by_a_question_mark(self):
        """Issue #149: one Class Mastery shown means a second is likely."""
        from gui.fight_render import mastery_tooltips, render_html, render_plain_text
        entry = _entry_with_bars()
        p = entry.players[0]
        p.update(class_name='Nightblade', masteries=['An Eye for Exploitation'])
        cue = (', <a href="esolog:mastery/1" style="text-decoration:none;color:')
        for detailed in (True, False):
            html = render_html(entry, detailed=detailed, icons=self._cache(), links=_links)
            self.assertIn('An Eye for Exploitation' + cue, html)
            self.assertIn('>?</a></span>', html)
        # The hover: the class's other four, a damage dealer's order
        tip = mastery_tooltips(entry)['esolog:mastery/1']
        self.assertIn('<b>Second Class Mastery not seen</b>', tip)
        self.assertIn('Likeliest for a Nightblade DPS:', tip)
        self.assertLess(tip.index('Above and Beyond'), tip.index('Share the Spoils'))
        self.assertNotIn('An Eye for Exploitation', tip)
        self.assertIn('Click for the full build', tip)
        self.assertIn('      An Eye for Exploitation, ? · second not seen, most likely Above and Beyond, '
                      "Cutthroat's Focus, Share the Spoils or Nocturnal Inspiration",
                      render_plain_text(entry))
        # A healer's order; Bastion of Light marked
        p.update(class_name='Templar', role='H', masteries=['Devout Guardian'],
                 skill_lines=["Aedric Spear", "Dawn's Wrath", 'Restoring Light'],
                 class_lines=["Aedric Spear", "Dawn's Wrath", 'Restoring Light'])
        tip = mastery_tooltips(entry)['esolog:mastery/1']
        self.assertIn('Likeliest for a Templar healer:', tip)
        self.assertIn('&nbsp;&nbsp;Bright Harbinger<br>', tip)
        self.assertIn('Bastion of Light (never shows in the log)<br>', tip)
        arcanist = ['Herald of the Tome', 'Soldier of Apocrypha', 'Curative Runeforms']
        other = _entry_with_bars()
        other.players[0].update(class_name='Arcanist', role='D', masteries=['Unbound Potential'],
                                skill_lines=arcanist, class_lines=arcanist)
        self.assertIn('Likeliest for an Arcanist DPS:', mastery_tooltips(other)['esolog:mastery/1'])
        # No mark: two shown, none, a borrowed line, an unknown class, a companion
        for fields in ({'masteries': ['Devout Guardian', 'Bright Harbinger']}, {'masteries': []},
                       {'skill_lines': ["Aedric Spear", "Dawn's Wrath", 'Herald of the Tome']},
                       {'class_lines': []}, {'companion': True}):
            other = _entry_with_bars()
            other.players[0].update(dict(p, **fields))
            self.assertNotIn('esolog:mastery/', render_html(other, detailed=False), fields)
            self.assertEqual(mastery_tooltips(other), {}, fields)
            self.assertNotIn('second not seen', render_plain_text(other), fields)

    def test_without_icon_cache_bars_stay_text(self):
        from gui.fight_render import render_html, render_plain_text
        entry = _entry_with_bars()
        html = render_html(entry, detailed=True)
        self.assertNotIn('<img src="icon:', html)
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

    def test_serves_a_ringed_icon_for_a_taunting_ability(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        ringed = view.loadResource(QTextDocument.ImageResource,
                                   QUrl('icon:ability_test_001?ring=7b1fa2'))
        self.assertEqual((ringed.width(), ringed.height()), (40, 40))
        self.assertEqual(ringed.pixelColor(1, 1).name(), '#7b1fa2')    # the ring, inside the edge
        self.assertEqual(ringed.pixelColor(38, 38).name(), '#7b1fa2')
        self.assertEqual(ringed.pixelColor(20, 20).name(), '#ff0000')  # the icon itself
        # The base icon is untouched, and a ring the URL does not spell as
        # a color is ignored
        for url in ('icon:ability_test_001', 'icon:ability_test_001?ring=purple'):
            image = view.loadResource(QTextDocument.ImageResource, QUrl(url))
            self.assertEqual(image.pixelColor(1, 1).name(), '#ff0000', url)
        # Drawn once per color, then served again
        again = view.loadResource(QTextDocument.ImageResource,
                                  QUrl('icon:ability_test_001?ring=7b1fa2'))
        self.assertIs(ringed, again)
        other = view.loadResource(QTextDocument.ImageResource,
                                  QUrl('icon:ability_test_001?ring=ce93d8'))
        self.assertEqual(other.pixelColor(1, 1).name(), '#ce93d8')
        # An icon the cache lacks stays missing, ring or not
        self.assertFalse(view.icons.has('ability_missing'))
        self.assertIsNone(view.icons.image('ability_missing', ring='#7b1fa2'))

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

    def test_the_lone_mastery_mark_opens_the_build_and_underlines(self):
        from PySide6.QtCore import QUrl
        from gui.fight_render import mastery_tooltips, render_html
        from gui.fight_view import FightView
        entry = _entry_with_bars()
        entry.players[0].update(class_name='Nightblade', masteries=['An Eye for Exploitation'])
        view = FightView(icons=self._cache())
        requested = []
        view.build_requested.connect(requested.append)
        view.set_tooltips(mastery_tooltips(entry))
        view.setHtml(render_html(entry, detailed=False))
        view.highlighted.emit(QUrl('esolog:mastery/1'))
        self.assertIn('Second Class Mastery not seen', view.current_tooltip)
        self.assertEqual(view.hovered_build_link, 'esolog:mastery/1')
        view.anchorClicked.emit(QUrl('esolog:mastery/1'))
        self.assertEqual(requested, ['1'])

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


class TestStepsAfterLayout(FightViewTestCase):
    """restore_scroll and the build window's scroll to an anchor act again
    once the page is laid out, on a timer the view owns (issue #196). Where
    the anchor's step lands is tested on the build window's headings
    (test_build_window_gui)."""

    def _deleted_before_the_step(self, make):
        """Delete the window *make* returns, with its view (the two may be
        one), before the step after layout runs, then run the event loop.
        Returns whether the view's Python wrapper outlived the deletion
        (freeing it needs no garbage collector once nothing holds it, and
        conftest keeps the collector off) and what Qt's callbacks raised,
        which PySide only prints."""
        import sys
        import weakref

        from PySide6.QtCore import QCoreApplication, QEvent
        errors = []
        hook = sys.excepthook
        sys.excepthook = lambda kind, value, tb: errors.append(value)
        try:
            window, view = make()
            freed = weakref.ref(view)
            window.deleteLater()
            del window, view
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            alive = freed() is not None
            _app.processEvents()  # when the step would run
        finally:
            sys.excepthook = hook
        return alive, errors

    def test_a_view_deleted_before_its_scroll_is_put_back_is_freed_quietly(self):
        from gui.fight_view import FightView

        def make():
            view = FightView(icons=self._cache())
            view.setHtml('<p>a line of the page</p>' * 300)
            view.restore_scroll(120)
            return view, view
        self.assertEqual(self._deleted_before_the_step(make), (False, []))

    def test_a_player_window_deleted_before_its_anchor_scroll_is_freed_quietly(self):
        """The player window opened at one death scrolls its Deaths page to
        that death's anchor after layout (issue #196): deleted before the
        step runs, with its page, it is freed and raises nothing."""
        from gui.player_window import DEATHS_TAB, PlayerWindow
        from tests.unit.test_death_recap_gui import _entry_with_deaths

        def make():
            window = PlayerWindow(icons=self._cache())
            window.open(_entry_with_deaths(), '1', DEATHS_TAB, dark=False, death=2)
            window.hide()
            return window, window.view(DEATHS_TAB)
        self.assertEqual(self._deleted_before_the_step(make), (False, []))

    def test_the_step_runs_once_laid_out_and_only_for_its_page(self):
        from PySide6.QtWidgets import QApplication

        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        try:
            view.resize(300, 200)
            view.show()
            QApplication.processEvents()
            view.setHtml('<p>a line of the page</p>' * 300)
            view.restore_scroll(400)
            self.assertEqual(view.verticalScrollBar().value(), 400)
            # Moved before the loop runs, the bar goes back: the step, not
            # restore_scroll's own setValue, has the last word
            view.verticalScrollBar().setValue(0)
            QApplication.processEvents()
            self.assertEqual(view.verticalScrollBar().value(), 400)
            # A new page opens at its top: the step still pending was for
            # the page it replaced
            view.restore_scroll(250)
            view.setHtml('<p>a line of another page</p>' * 300)
            QApplication.processEvents()
            self.assertEqual(view.verticalScrollBar().value(), 0)
        finally:
            view.close()
            view.deleteLater()

    def test_a_redraw_before_the_step_runs_keeps_the_steps_place(self):
        """A second redraw in the same pass, two fight updates say, finds
        the bar not yet where the step after the first will put it (a page
        Qt lays out in parts leaves it short until then): keeping_place
        takes the step's scroll or anchor, not the bar's position."""
        from PySide6.QtWidgets import QApplication

        from gui.fight_view import FightView
        lines = '<p>a line of the page</p>' * 150
        page = f'{lines}<p><a name="there"></a>the heading</p>{lines}'
        view = FightView(icons=self._cache())
        try:
            view.resize(300, 200)
            view.show()
            view.setHtml(page)
            QApplication.processEvents()
            bar = view.verticalScrollBar()
            bar.setValue(400)
            with view.keeping_place():
                view.setHtml(page)
            bar.setValue(0)
            with view.keeping_place():
                view.setHtml(page)
            QApplication.processEvents()
            self.assertEqual(bar.value(), 400)

            # The same for a page just opened at an anchor
            view.setHtml(page)
            view.open_at_anchor('there')
            QApplication.processEvents()
            at_anchor = bar.value()
            self.assertGreater(at_anchor, 400)
            view.setHtml(page)
            view.open_at_anchor('there')
            bar.setValue(0)
            with view.keeping_place():
                view.setHtml(page)
            QApplication.processEvents()
            self.assertEqual(bar.value(), at_anchor)
        finally:
            view.close()
            view.deleteLater()

    @staticmethod
    def _until_laid_out(bar, whole):
        """Run the event loop until the bar has the page's whole range,
        *whole* (Qt's layout ticks, the view's step and hold), and a pass
        more."""
        import time
        deadline = time.monotonic() + 5
        while bar.maximum() != whole and time.monotonic() < deadline:
            _app.processEvents()
        _app.processEvents()

    def test_a_page_laid_out_in_parts_lands_where_it_was_kept(self):
        """A page taller for its length at its end than at its start (long
        paragraphs, then short lines): Qt lays it out in parts, on its ticks
        after setHtml, and until then the bar's range is an estimate from
        the part laid out, short of the page's. The scroll put back stopped
        at it, thousands of pixels short; it is held until the bar gets
        there (issue #196). The reader scrolling just after a redraw is
        left where they scrolled to."""
        from PySide6.QtWidgets import QAbstractSlider

        from gui.fight_view import FightView
        page = ('<p>' + 'word ' * 400 + '</p>') * 10 + '<p>x</p>' * 800
        view = FightView(icons=self._cache())
        try:
            view.resize(300, 300)
            view.show()
            view.setHtml(page)
            view.document().size()  # laid out whole, for the bar's whole range
            _app.processEvents()
            bar = view.verticalScrollBar()
            whole = bar.maximum()
            kept = whole * 9 // 10
            bar.setValue(kept)
            with view.keeping_place():
                view.setHtml(page)
            self.assertLess(bar.maximum(), kept)  # the estimate
            self._until_laid_out(bar, whole)
            self.assertEqual(bar.value(), kept)

            with view.keeping_place():
                view.setHtml(page)
            bar.triggerAction(QAbstractSlider.SliderToMinimum)
            self._until_laid_out(bar, whole)
            self.assertEqual(bar.value(), 0)
        finally:
            view.close()
            view.deleteLater()

    def test_a_redraw_while_the_place_is_held_puts_the_page_there(self):
        """While the place is held the bar can be short of it, the page's
        range not yet grown to it or the page drawn shorter: a redraw then,
        a second fight update say, puts the page where it is held, not
        where the bar is meanwhile (keeping_place). Here the fight is drawn
        shorter than where the reader was, the bar stopping at its end, and
        then as long again."""
        from gui.fight_view import FightView
        line = '<p>a line of the page</p>'
        view = FightView(icons=self._cache())
        try:
            view.resize(300, 200)
            view.show()
            view.setHtml(line * 300)
            _app.processEvents()
            bar = view.verticalScrollBar()
            kept = bar.maximum() - 50
            bar.setValue(kept)
            with view.keeping_place():
                view.setHtml(line * 100)
            _app.processEvents()  # the step has run
            self.assertLess(bar.value(), kept)
            with view.keeping_place():
                view.setHtml(line * 300)
            _app.processEvents()
            self.assertEqual(bar.value(), kept)
        finally:
            view.close()
            view.deleteLater()

    def test_tab_ends_the_hold(self):
        """The fight is drawn shorter than where the reader was, so the
        place is held to the end of HOLD_MS. Tab moves the page to the link
        at its top, which the bar does not report: the hold ends there, and
        a change of the bar's range leaves the page where Tab took it
        (issue #199). It put the page back at the place still held."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.fight_view import FightView
        line = '<p>a line of the page</p>'
        link = "<p><a href='esolog:issues/1'>(i) of 1</a></p>"
        view = FightView(icons=self._cache())
        try:
            view.resize(300, 200)
            view.show()
            view.setHtml(link + line * 300)
            _app.processEvents()
            bar = view.verticalScrollBar()
            bar.setValue(bar.maximum())
            with view.keeping_place():
                view.setHtml(link + line * 100)
            _app.processEvents()
            self.assertTrue(view._hold.isActive())
            view.setFocus()
            QTest.keyClick(view, Qt.Key_Tab)
            place = bar.value()
            self.assertLess(place, 50)  # at the link, at the page's top
            view.resize(300, 180)  # the bar's range changes
            _app.processEvents()
            self.assertEqual(bar.value(), place)
        finally:
            view.close()
            view.deleteLater()


class TestEnterOnALink(FightViewTestCase):

    def test_a_link_ending_a_wrapped_line_is_placed_on_its_line(self):
        """Enter on a link that ends a wrapped line: keyboard_link_rect is
        at the link, its left edge and its line. Joined with the cursor at
        the link's end, which is on the next line, it took that line's left
        margin and bottom, and the (i) popup opened there (issue #196)."""
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QTextCursor
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        asked = []

        def note(unit_id):
            asked.append((unit_id, view.keyboard_link_rect()))
        view.issues_requested.connect(note)
        try:
            view.resize(300, 300)
            view.show()
            view.activateWindow()
            QApplication.processEvents()
            # A line may break between any two ideographs: the count before
            # the link that makes it the first line's last character
            for n in range(1, 200):
                view.setHtml(f"<p>{'文' * n}<a href='esolog:issues/2'>中</a>{'文' * 60}</p>")
                start, end = QTextCursor(view.document()), QTextCursor(view.document())
                start.setPosition(n)
                end.setPosition(n + 1)
                if view.cursorRect(end).top() > view.cursorRect(start).top():
                    break
            else:
                self.fail('no count of ideographs ends the first line with the link')
            mark = view.cursorRect(start)
            view.setFocus()
            QTest.keyClick(view, Qt.Key_Tab)
            self.assertEqual(view.textCursor().selectionStart(), n)
            QTest.keyClick(view, Qt.Key_Return)
            self.assertEqual(asked, [('2', QRect(view.viewport().mapToGlobal(mark.topLeft()),
                                                 mark.size()))])
        finally:
            view.issues_requested.disconnect(note)
            view.close()
            view.deleteLater()


class TestALinkReachedWithTab(FightViewTestCase):
    """The fight on screen can change while the reader tabs through its
    links, the (i) marks say: the redraw in place gives the link they had
    reached Tab's focus back (FightView.keeping_place, issue #196). It left
    nothing selected, so Enter did nothing and the next Tab went back to
    the page's first link."""

    PAGE = ("<p><a href='esolog:build/1'>a name</a> wears "
            "<a href='https://eso-hub.com/en/sets/x'>a set</a> and "
            "<a href='https://eso-hub.com/en/sets/x'>the set again</a></p>"
            + "<p>a line of the page</p>" * 30
            + "<p><a href='esolog:issues/2'>(i) of 2</a> "
            "<a href='esolog:issues/3'>(i) of 3</a></p>"
            + "<p>a line of the page</p>" * 30)
    # Two ability bars as the pane's build card and the build window draw
    # them: tables whose first cell begins with the bar's first ability
    FRONT = ("<table><tr><td><a href='esolog:ability/1'>one</a>&nbsp;"
             "<a href='esolog:ability/2'>two</a></td></tr></table>")
    BACK = ("<table><tr><td><a href='esolog:ability/3'>three</a>&nbsp;"
            "<a href='esolog:ability/4'>four</a></td></tr></table>")
    LINES = "<p>a line of the page</p>" * 30

    def setUp(self):
        super().setUp()
        from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

        from gui.fight_view import FightView
        # A field after the view: where Tab goes from the page's last link
        self.host = QWidget()
        layout = QVBoxLayout(self.host)
        self.view = FightView(icons=self._cache())
        layout.addWidget(self.view)
        layout.addWidget(QLineEdit())
        self.host.resize(400, 300)
        self.host.show()
        self.host.activateWindow()
        _app.processEvents()

    def tearDown(self):
        self.host.close()
        self.host.deleteLater()
        super().tearDown()

    def _tab(self, times):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.view.setFocus()
        for _ in range(times):
            QTest.keyClick(self.view, Qt.Key_Tab)

    def _redraw(self, page):
        with self.view.keeping_place():
            self.view.setHtml(page)
        _app.processEvents()

    def _selected(self):
        cursor = self.view.textCursor()
        return cursor.selectedText() if cursor.hasSelection() else None

    def test_the_link_has_tabs_frame_again_and_the_next_tab_goes_on(self):
        """Tabbed to an (i) and scrolled on a little, the reader sees the
        page redrawn: the (i) has Tab's dotted frame again, painted as Tab
        painted it (the viewport the same to the pixel, the scroll where the
        reader had it), rather than the highlight of selected text; Enter
        opens it, the next Tab goes on to the next (i), and the focus never
        leaves the page."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        opened = []
        self.view.anchorClicked.connect(lambda url: opened.append(url.toString()))
        self.view.setHtml(self.PAGE)
        self._tab(4)
        self.assertEqual(self._selected(), '(i) of 2')
        bar = self.view.verticalScrollBar()
        self.assertGreater(bar.value(), 0)
        bar.setValue(bar.value() + 20)  # the (i) still in view
        _app.processEvents()
        place = bar.value()
        framed = self.view.viewport().grab().toImage()
        self._redraw(self.PAGE)
        self.assertEqual(self._selected(), '(i) of 2')
        self.assertEqual(bar.value(), place)
        self.assertEqual(self.view.viewport().grab().toImage(), framed)
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(opened, ['esolog:issues/2'])
        QTest.keyClick(self.view, Qt.Key_Tab)
        self.assertEqual(self._selected(), '(i) of 3')
        self.assertIs(QApplication.focusWidget(), self.view)

    def test_the_link_is_known_by_its_place_among_the_links_to_its_href(self):
        """One href on several links (an ESO-Hub set link on each player who
        wears the set): the second is kept as the second, text added before
        it or not. A player's own (i), moved up the page by the fight ranking
        the players anew, is kept too. A link the page no longer has leaves
        nothing selected, and the focus on the page."""
        from PySide6.QtWidgets import QApplication
        self.view.setHtml(self.PAGE)
        self._tab(3)
        self.assertEqual(self._selected(), 'the set again')
        self._redraw(self.PAGE.replace("<p><a href='esolog:build/1'>",
                                       "<p>new words <a href='esolog:build/1'>"))
        self.assertEqual(self._selected(), 'the set again')

        self.view.setHtml(self.PAGE)
        self._tab(5)
        self.assertEqual(self._selected(), '(i) of 3')
        moved = ("<p><a href='esolog:issues/3'>(i) of 3</a></p>"
                 + self.PAGE.replace(" <a href='esolog:issues/3'>(i) of 3</a>", ""))
        self._redraw(moved)
        self.assertEqual(self._selected(), '(i) of 3')
        self.assertEqual(self.view.textCursor().selectionStart(), 0)

        self._redraw(self.PAGE.replace(" <a href='esolog:issues/3'>(i) of 3</a>", ""))
        self.assertIsNone(self._selected())
        self.assertIs(QApplication.focusWidget(), self.view)

    def test_a_link_that_begins_a_tables_first_cell(self):
        """A bar's first ability, after the player's name, begins its
        table's first cell: after the redraw it has Tab's focus again,
        Enter opens it and the next Tab goes on to the next ability (issue
        #196). The step taken from a selection of the character before it,
        which QTextCursor widened over the whole table, framed the set link
        after the table."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        opened = []
        self.view.anchorClicked.connect(lambda url: opened.append(url.toString()))
        page = ("<p><a href='esolog:build/1'>a name</a></p>" + self.FRONT
                + "<p><a href='https://eso-hub.com/en/sets/x'>a set</a></p>" + self.LINES)
        self.view.setHtml(page)
        self._tab(2)
        self.assertEqual(self._selected(), 'one')
        self._redraw(page)
        self.assertEqual(self._selected(), 'one')
        QTest.keyClick(self.view, Qt.Key_Return)
        self.assertEqual(opened, ['esolog:ability/1'])
        QTest.keyClick(self.view, Qt.Key_Tab)
        self.assertEqual(self._selected(), 'two')

    def test_a_link_that_begins_a_tables_first_cell_with_none_after_it(self):
        """The same with no link after the table: the focus stays on the
        page, on that link. Tab's step found no link after the table and
        moved the focus on to the field below the page."""
        from PySide6.QtWidgets import QApplication
        page = "<p><a href='esolog:build/1'>a name</a></p>" + self.FRONT + self.LINES
        self.view.setHtml(page)
        self._tab(2)
        self.assertEqual(self._selected(), 'one')
        self._redraw(page)
        self.assertIs(QApplication.focusWidget(), self.view)
        self.assertEqual(self._selected(), 'one')

    def test_the_pages_first_link(self):
        """The page's first link has no link before it to take Tab's step
        from: the step is taken from no selection, from which Tab starts at
        the page's start. As in the build window, that link begins the front
        bar's table, the back bar's following it; the step taken from a
        selection of the character before it framed the back bar's first
        ability."""
        from PySide6.QtWidgets import QApplication
        page = "<p>a build</p>" + self.FRONT + self.BACK + self.LINES
        self.view.setHtml(page)
        self._tab(1)
        self.assertEqual(self._selected(), 'one')
        self._redraw(page)
        self.assertIs(QApplication.focusWidget(), self.view)
        self.assertEqual(self._selected(), 'one')

    def test_the_pages_links_are_the_ones_tab_reaches(self):
        """The view reads the page's links as Tab's search does, since the
        step it takes after a redraw finds the link after the one it starts
        from: links side by side, an icon in a link, the bars' tables, an
        anchor with a name alone, which is no link, and a link whose href is
        empty, which is one. setHtml never makes that last; it is written
        here in code."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QTextCharFormat, QTextCursor
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        self.view.setHtml("<p><a name='top'>a heading</a> <a href='esolog:build/1'>a name</a>"
                          "<a href='esolog:damage/1'>1.0k</a> <a href='esolog:issues/1'>"
                          "<img src='icon:ability_test_001'></a></p>" + self.FRONT + self.BACK)
        empty = QTextCharFormat()
        empty.setAnchor(True)
        empty.setAnchorHref('')
        cursor = QTextCursor(self.view.document())
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock()
        cursor.insertText('an empty href', empty)
        cursor.insertText(' then a line', QTextCharFormat())
        reached = []
        self.view.setFocus()
        while True:
            QTest.keyClick(self.view, Qt.Key_Tab)
            selected = self.view.textCursor()
            if QApplication.focusWidget() is not self.view or not selected.hasSelection():
                break
            reached.append((selected.selectionStart(), selected.selectionEnd()))
        self.assertEqual(len(reached), 8)
        self.assertEqual(reached, [(start, end) for _href, start, end in self.view._links()])

    def _moved_down(self):
        """The page with ten rows more above the first (i), as an update
        that ranks its player lower adds them."""
        return self.PAGE.replace("<p><a href='esolog:issues/2'>",
                                 "<p>a line of the page</p>" * 10 + "<p><a href='esolog:issues/2'>")

    def test_a_link_on_the_screen_stays_where_it_was_on_it(self):
        """The fight on screen changes in place and moves the link the
        reader reached with Tab down the page: the link stays where it was
        on the screen, with Tab's focus, and the page moves under it (issue
        #199). Kept by the bar's position, it went out of sight with its
        focus frame, and Enter opened a link the reader could not see."""
        self.view.setHtml(self.PAGE)
        self._tab(4)
        self.assertEqual(self._selected(), '(i) of 2')
        top = self.view.link_top()
        self.assertIsNotNone(top)
        bar = self.view.verticalScrollBar()
        scroll = bar.value()
        self._redraw(self._moved_down())
        self.assertEqual(self._selected(), '(i) of 2')
        self.assertEqual(self.view.link_top(), top)
        self.assertGreater(bar.value(), scroll)

    def test_a_link_scrolled_out_of_view_leaves_the_page_where_the_reader_put_it(self):
        """The reader has scrolled the link they reached with Tab out of
        view when the fight moves it: the page stays at their scroll, the
        link keeping Tab's focus (issue #199)."""
        self.view.setHtml(self.PAGE)
        self._tab(4)
        bar = self.view.verticalScrollBar()
        bar.setValue(0)
        _app.processEvents()
        self.assertIsNone(self.view.link_top())  # below the screen
        self._redraw(self._moved_down())
        self.assertEqual(self._selected(), '(i) of 2')
        self.assertEqual(bar.value(), 0)

    def _click(self, href):
        """A click with the mouse in the middle of the link to *href*."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QTextCursor
        from PySide6.QtTest import QTest
        _href, start, end = next(link for link in self.view._links() if link[0] == href)
        cursor = QTextCursor(self.view.document())
        cursor.setPosition(start)
        left = self.view.cursorRect(cursor)
        cursor.setPosition(end)
        right = self.view.cursorRect(cursor)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.NoModifier,
                         QPoint((left.left() + right.left()) // 2, left.center().y()))
        _app.processEvents()

    def test_a_link_clicked_is_not_one_reached_with_tab(self):
        """Qt selects a link clicked with the mouse as Tab selects one, and
        the selection stays when the window the link opens takes the focus.
        It is not a link reached with Tab: a redraw that moves it down the
        page leaves the page where the reader had it, at its top (issue
        #202). Taken for one, it was kept where it was on the screen, and
        the page scrolled down after it. Tab from it goes on to the next
        link, which is one."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.view.setHtml(self.PAGE)
        self.view.setFocus()
        bar = self.view.verticalScrollBar()
        self._click('esolog:build/1')
        self.assertEqual(self._selected(), 'a name')
        self.assertIsNone(self.view.link_top())
        self._redraw("<p>a line of the page</p>" * 30 + self.PAGE)
        self.assertEqual(bar.value(), 0)
        self.assertIsNone(self._selected())

        self.view.setHtml(self.PAGE)
        self._click('esolog:build/1')
        QTest.keyClick(self.view, Qt.Key_Tab)
        self.assertEqual(self._selected(), 'a set')
        self.assertIsNotNone(self.view.link_top())
        self._redraw(self.PAGE.replace("<p><a href='esolog:build/1'>",
                                       "<p>new words <a href='esolog:build/1'>"))
        self.assertEqual(self._selected(), 'a set')


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
            win.history_list.select_fight(0)
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


class TestTauntPulse(FightViewTestCase):
    """The taunt ring pulses (issue #12): the cache draws the ring at phases
    of a glow, and the view steps the page's ringed icons through them."""

    def test_the_ring_is_wide_outlined_and_brighter_mid_glow(self):
        cache = self._cache()
        rest = cache.image('ability_test_001', ring='#7b1fa2')
        mid = cache.image('ability_test_001', ring='#7b1fa2', phase=0.5)
        # Dark hairline on the edge, the ring from the next pixel for a
        # fifth of the icon, the icon untouched inside
        self.assertLess(rest.pixelColor(0, 0).lightness(), 60)
        self.assertEqual(rest.pixelColor(1, 1).name(), '#7b1fa2')
        self.assertEqual(rest.pixelColor(4, 4).name(), '#7b1fa2')
        self.assertEqual(rest.pixelColor(20, 20).name(), '#ff0000')
        self.assertEqual(mid.pixelColor(20, 20).name(), '#ff0000')
        self.assertGreater(mid.pixelColor(1, 1).lightness(), rest.pixelColor(1, 1).lightness())
        # A full cycle is the resting image again, drawn once
        self.assertIs(cache.image('ability_test_001', ring='#7b1fa2', phase=1.0), rest)
        self.assertIs(cache.image('ability_test_001', ring='#7b1fa2', phase=0.5), mid)

    def test_the_view_pulses_only_while_a_ringed_icon_is_on_the_page(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        view.resize(300, 100)
        view.show()
        url = QUrl('icon:ability_test_001?ring=7b1fa2')
        view.setHtml('<p><img src="icon:ability_test_001?ring=7b1fa2" width="40" height="40"></p>')
        # Laying the page out loads the icon
        out = QImage(300, 100, QImage.Format_ARGB32)
        painter = QPainter(out)
        view.document().drawContents(painter)
        painter.end()
        self.assertEqual(list(view._ring_urls), [url.toString()])
        self.assertTrue(view._pulse.isActive())
        at_rest = view.document().resource(QTextDocument.ImageResource, url)
        self.assertEqual(QImage(at_rest).pixelColor(1, 1).name(), '#7b1fa2')
        # One step on: the page's image for that URL is the brighter one
        view._pulse_step()
        stepped = QImage(view.document().resource(QTextDocument.ImageResource, url))
        self.assertGreater(stepped.pixelColor(1, 1).lightness(), QColor('#7b1fa2').lightness())
        self.assertEqual(stepped.pixelColor(20, 20).name(), '#ff0000')
        # A page without a ring stops the pulse
        view.setHtml('<p>nothing ringed</p>')
        self.assertEqual(view._ring_urls, {})
        self.assertFalse(view._pulse.isActive())
        view._pulse_step()
        self.assertFalse(view._pulse.isActive())
        view.close()


class TestLinkGlyphs(FightViewTestCase):
    """The glyphs that say the dps figures can be clicked (issue #34)."""

    def test_dps_figures_carry_a_glyph_inside_their_anchor_in_both_themes(self):
        import re

        from gui.fight_render import (
            link_color,
            muted_color,
            render_html,
            render_plain_text,
        )
        entry = _entry_with_bars()
        entry.group_dps = 1000.0
        for dark in (False, True):
            html = render_html(entry, detailed=False, dark=dark)
            link = link_color(dark).lstrip('#')
            muted = muted_color(dark).lstrip('#')
            # The header's figure, its unit, then the graph glyph in the
            # link colour, all inside the anchor
            header = re.search(r'<a href="esolog:graph/"[^>]*>(.*?)</a>', html).group(1)
            self.assertTrue(header.endswith(
                f'gdps&nbsp;<img src="glyph:graph?color={link}&amp;px=13" '
                f'alt="DPS graph" style="vertical-align:middle">'), header)
            self.assertTrue(header.startswith('1.0k gdps'), header)
            # A player's figure, then the breakdown glyph in the muted colour
            row = re.search(r'<a href="esolog:damage/1"[^>]*>(.*?)</a>', html).group(1)
            self.assertEqual(row, f'1.0k&nbsp;<img src="glyph:breakdown?color={muted}'
                                  f'&amp;px=13" alt="damage breakdown" style="vertical-align:middle">')
            # After the player's name, the shield that opens their damage
            # taken window (issue #98), in the link colour, the whole anchor
            shield = re.search(r'<a href="esolog:taken/1"[^>]*>(.*?)</a>', html).group(1)
            self.assertEqual(shield, f'<img src="glyph:taken?color={link}&amp;px=13" '
                                     f'alt="damage taken" style="vertical-align:middle">')
            self.assertEqual(html.count('glyph:'), 3)
        # The names keep their plain look, and copied text has no glyph
        self.assertIn('color:#202124">@tester</a>', render_html(entry, detailed=False))
        self.assertNotIn('glyph', render_plain_text(entry))
        # The glyph follows the pane's font size
        self.assertIn('&amp;px=18"', render_html(entry, detailed=False, base_pt=12.0))
        # A fight without damage has no graph to open: no link, no glyph
        entry.group_dps = 0.0
        html = render_html(entry, detailed=False)
        self.assertNotIn('esolog:graph/', html)
        self.assertNotIn('glyph:graph', html)
        self.assertIn(' · 0 gdps · ', html)

    def test_glyph_images_are_drawn_in_the_asked_colour_and_size(self):
        from gui.glyphs import glyph_image
        for kind in ('graph', 'breakdown'):
            image = glyph_image(kind, '#1a73e8', 13)
            self.assertEqual((image.width(), image.height()), (13, 13))
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)  # a transparent corner
            solid = {image.pixelColor(x, y).name() for x in range(13) for y in range(13)
                     if image.pixelColor(x, y).alpha() == 255}
            self.assertEqual(solid, {'#1a73e8'}, kind)
            self.assertIs(glyph_image(kind, '#1a73e8', 13), image)  # drawn once
        # On a scaled display the image has more pixels and the same logical size
        hidpi = glyph_image('graph', '#1a73e8', 13, dpr=2.0)
        self.assertEqual((hidpi.width(), hidpi.devicePixelRatio()), (26, 2.0))
        self.assertIsNone(glyph_image('sparkle', '#1a73e8', 13))
        self.assertIsNone(glyph_image('graph', 'no-such-colour', 13))
        self.assertIsNone(glyph_image('graph', '#1a73e8', 0))

    def test_the_view_serves_glyphs_and_the_page_draws_them(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument

        from gui.fight_render import render_html
        from gui.fight_view import FightView
        view = FightView(icons=self._cache())
        image = view.loadResource(QTextDocument.ImageResource,
                                  QUrl('glyph:graph?color=1a73e8&px=13'))
        self.assertEqual(image.width(), 13)
        for bad in ('glyph:graph?color=blue&px=13', 'glyph:graph?px=13',
                    'glyph:graph?color=1a73e8&px=x', 'glyph:graph?color=1a73e8',
                    'glyph:sparkle?color=1a73e8&px=13'):
            served = view.loadResource(QTextDocument.ImageResource, QUrl(bad))
            self.assertFalse(isinstance(served, QImage) and not served.isNull(), bad)
        entry = _entry_with_bars()
        entry.group_dps = 1000.0
        view.resize(520, 120)
        view.show()
        _app.processEvents()
        for dark in (False, True):
            view.setHtml(render_html(entry, detailed=False, dark=dark))
            _app.processEvents()
            self.assertFalse(view.grab().isNull())
        view.setHtml(render_html(entry, detailed=False))
        _app.processEvents()
        # The document resolves both glyph URLs through the view
        for url in ('glyph:graph?color=1a73e8&px=13', 'glyph:breakdown?color=5f6368&px=13'):
            self.assertEqual(QImage(view.document().resource(
                QTextDocument.ImageResource, QUrl(url))).width(), 13)
        # ...and the laid-out page really draws the link-coloured graph glyph
        out = QImage(520, 120, QImage.Format_ARGB32)
        out.fill(QColor('white'))
        painter = QPainter(out)
        view.document().drawContents(painter)
        painter.end()
        blues = sum(1 for x in range(520) for y in range(120)
                    if out.pixelColor(x, y).blue() > 180 and out.pixelColor(x, y).red() < 90)
        self.assertGreater(blues, 8)
        view.close()


if __name__ == '__main__':
    unittest.main()
