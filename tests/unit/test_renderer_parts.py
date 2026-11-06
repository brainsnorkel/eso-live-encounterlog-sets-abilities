#!/usr/bin/env python3
"""The player pages in parts (issue #196, PR 3), for the window with a tab
for each, which names the player and the fight in a header of its own: the
build page's parts and facts line, the damage page with the kinds of damage
dealt, the damage taken page's two halves, the death recap without its
header or its fight block, and the links between them. Every part is a
slice of the page drawn whole, which stays as it was."""

import html
import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights

from tests.unit.test_damage_window_gui import _entry as _damage_entry
from tests.unit.test_death_recap_gui import _entry_with_deaths
from tests.unit.test_gui import FIXTURE_LOG, HAVE_QT, _ensure_app
from tests.unit.test_taken_window_gui import _entry as _taken_entry


def _golden_fights():
    """The golden fight log replayed, for players with resources."""
    import review_load
    from app_config import AppConfig
    from app_startup import build_analyzer
    with tempfile.TemporaryDirectory() as tmp:
        config = AppConfig(path=Path(tmp) / "config.json")
        return review_load.replay_log(build_analyzer(config, []), FIXTURE_LOG)[1]


class TestBuildParts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fights = fights() + _golden_fights()

    def _players(self):
        for entry in self.fights:
            for p in entry.players:
                yield entry, p

    def test_the_page_is_its_parts_and_the_damage_dealt_section(self):
        """The build part, then Damage dealt (which goes with the damage
        page), then the cap sections and Resources: the page drawn whole,
        in both themes."""
        from gui.build_render import (
            BUILD_PART,
            PEN_CRIT_PART,
            RESOURCES_PART,
            _damage_dealt_html,
            render_build_html,
        )
        from gui.fight_render import _theme
        checked = 0
        for entry, p in self._players():
            unit_id = p["unit_id"]
            for dark in (False, True):
                theme = _theme(dark)
                dealt = _damage_dealt_html(p, dark, dict(theme, text=theme["text"]), 9.0,
                                           html.escape)
                parts = (render_build_html(entry, unit_id, dark, part=BUILD_PART) + dealt
                         + render_build_html(entry, unit_id, dark, header=False, part=PEN_CRIT_PART)
                         + render_build_html(entry, unit_id, dark, header=False, part=RESOURCES_PART))
                self.assertEqual(parts, render_build_html(entry, unit_id, dark))
                checked += 1
        self.assertGreaterEqual(checked, 10)
        self.assertTrue(any(p.get("resources") for _entry, p in self._players()))

    def test_the_facts_line_in_place_of_the_header(self):
        """Under a header of its own the page begins with the facts line:
        race, class, champion points, role, borrowed lines and that the
        build is as logged at the fight's start; no name, no fight. The rest
        of the part is as it was."""
        from gui.build_render import BUILD_PART, SNAPSHOT_NOTE, render_build_html
        entry = fights()[0]
        p = next(p for p in entry.players if p["name"] == "@brainsnorkel")
        with_header = render_build_html(entry, p["unit_id"], part=BUILD_PART)
        without = render_build_html(entry, p["unit_id"], header=False, part=BUILD_PART)
        facts = without[:without.index("</p>") + len("</p>")]
        self.assertIn(SNAPSHOT_NOTE, facts)
        self.assertIn(f"CP {p['cp']}", facts)
        self.assertNotIn("@brainsnorkel", facts)
        self.assertNotIn(entry.boss_name, facts)
        self.assertNotIn("@brainsnorkel", without)
        self.assertTrue(with_header.endswith(without[len(facts):]))
        # The whole page under a header of its own begins with it too
        self.assertTrue(render_build_html(entry, p["unit_id"], header=False).startswith(facts))

    def test_a_companions_parts(self):
        """A companion's facts line says it is one, with its level; it has
        no part past its skills, which are its page but the kinds of its
        damage."""
        from gui.build_render import (
            BUILD_PART,
            PEN_CRIT_PART,
            RESOURCES_PART,
            render_build_html,
        )
        entry = _taken_entry()
        companion = entry.players[2]
        companion["level"] = 20
        without = render_build_html(entry, "3", header=False, part=BUILD_PART)
        self.assertTrue(without.startswith(
            "<p style='margin:0 0 2px 0;color:#5f6368'>Companion · level 20</p>"))
        self.assertNotIn("Bastian Hallix", without)
        whole = render_build_html(entry, "3")
        self.assertTrue(whole.startswith(render_build_html(entry, "3", part=BUILD_PART)))
        self.assertEqual(render_build_html(entry, "3", part=PEN_CRIT_PART), "")
        self.assertEqual(render_build_html(entry, "3", part=RESOURCES_PART), "")


class TestDamagePage(unittest.TestCase):

    def test_the_kinds_of_damage_dealt_under_the_tables(self):
        """dealt_kinds adds the build page's Damage dealt section after the
        tables, the note on dps time last; the rest is the page as it was."""
        from gui.build_render import DEALT_TITLE, _damage_dealt_html
        from gui.damage_render import DPS_TIME_NOTE, render_damage_html
        from gui.fight_render import _theme
        for entry in fights():
            for p in entry.players:
                plain = render_damage_html(entry, p["unit_id"])
                with_kinds = render_damage_html(entry, p["unit_id"], dealt_kinds=True)
                theme = _theme(False)
                dealt = _damage_dealt_html(p, False, dict(theme, text=theme["text"]), 9.0,
                                           html.escape)
                if DPS_TIME_NOTE not in plain:
                    self.assertEqual(with_kinds, plain)  # no damage: nothing to sort
                    continue
                note = plain.index("<p style='margin:10px 0 0 0;")
                self.assertEqual(with_kinds, plain[:note] + dealt + plain[note:])
                self.assertIn(f">{DEALT_TITLE} <span", with_kinds)

    def test_the_boss_damage_with_the_whole_fights_kinds(self):
        """The record keeps no boss kinds: on the boss damage page the
        section is the whole fight's, and its title says so."""
        from gui.build_render import DEALT_TITLE, DEALT_WHOLE_FIGHT_TITLE
        from gui.damage_render import render_damage_html
        entry = _damage_entry()
        kinds = next(p for p in fights()[0].players if p["name"] == "@brainsnorkel")["damage"]["kinds"]
        entry.players[0]["damage"]["kinds"] = kinds
        boss = render_damage_html(entry, "1", boss_only=True, dealt_kinds=True)
        # The title, then its link to the damage taken
        self.assertIn(f">{DEALT_WHOLE_FIGHT_TITLE} <span", boss)
        whole = render_damage_html(entry, "1", dealt_kinds=True)
        self.assertIn(f">{DEALT_TITLE} <span", whole)
        self.assertNotIn(DEALT_WHOLE_FIGHT_TITLE, whole)

    def test_without_its_header(self):
        from gui.damage_render import render_damage_html
        entry = _damage_entry()
        whole = render_damage_html(entry, "1")
        without = render_damage_html(entry, "1", header=False)
        self.assertNotIn("@tester", without)
        self.assertNotIn("Moonlit Cove", without)
        self.assertTrue(whole.endswith(without))


class TestTakenParts(unittest.TestCase):

    LINKED = re.compile(r"<a href='esolog:healing/1' style='text-decoration:none;color:#[0-9a-f]{6}'>"
                        r"healing received</a>")

    def _pages(self, dark=False):
        from gui.taken_render import HEALING_PART, TAKEN_PART, render_taken_html
        entry = _taken_entry()
        return (render_taken_html(entry, "1", dark, header=False),
                render_taken_html(entry, "1", dark, header=False, part=TAKEN_PART),
                render_taken_html(entry, "1", dark, header=False, part=HEALING_PART))

    def test_the_damage_half_links_its_healing_line_to_the_other(self):
        """The figures, the kinds and the sources, as on the whole page but
        for the words 'healing received', a link to the healing half, then
        the notes on damage."""
        from gui.taken_render import OVERHEAL_NOTE, PER_SECOND_NOTE, PREVENTED_NOTE
        for dark in (False, True):
            whole, taken, _healing = self._pages(dark)
            self.assertEqual(len(self.LINKED.findall(taken)), 1)
            plain = self.LINKED.sub("healing received", taken)
            healers = whole.index("<a name='healers'>")
            self.assertTrue(plain.startswith(whole[:healers]))
            self.assertNotIn("<a name='healers'>", taken)
            self.assertIn(html.escape(PER_SECOND_NOTE), taken)
            self.assertIn(html.escape(PREVENTED_NOTE), taken)
            self.assertNotIn(html.escape(OVERHEAL_NOTE), taken)

    def test_the_healing_half_is_its_line_then_the_table_by_healer(self):
        """The healing received line leads, then the table by healer as on
        the whole page, then the notes on healing."""
        from gui.taken_render import OVERHEAL_NOTE, PER_SECOND_NOTE, PREVENTED_NOTE
        whole, _taken, healing = self._pages()
        healers = whole.index("<a name='healers'>")
        notes = whole.index("<p style='margin:8px 0 1px 0;", healers)
        lead = healing[:healing.index("<a name='healers'>")]
        self.assertIn("healing received", lead)
        self.assertIn("340,000", lead)
        self.assertIn("91% of all healing on this player was overheal", lead)
        self.assertNotIn("damage taken", lead)
        self.assertIn(whole[healers:notes], healing)
        self.assertNotIn("<a name='sources'>", healing)
        self.assertNotIn(self.LINKED.pattern, healing)
        self.assertIn(html.escape(PER_SECOND_NOTE), healing)
        self.assertIn(html.escape(OVERHEAL_NOTE), healing)
        self.assertNotIn(html.escape(PREVENTED_NOTE), healing)

    def test_the_whole_page_is_as_it_was(self):
        """The page drawn whole has no healing link and every note."""
        from gui.taken_render import NOTES, render_taken_html
        entry = _taken_entry()
        page = render_taken_html(entry, "1")
        self.assertNotIn("esolog:healing/", page)
        for note in NOTES:
            self.assertIn(html.escape(note), page)
        self.assertTrue(page.endswith(render_taken_html(entry, "1", header=False)))


class TestRecapPage(unittest.TestCase):

    def test_without_its_header_or_its_fight_block(self):
        """Under a header of its own: no name and fight line; the fight
        block's place taken by a line linking to the player's damage taken.
        The deaths between are as on the whole page."""
        from gui.death_render import (
            FIGHT_BLOCK_TITLE,
            FIGHT_LINK_LEAD,
            FIGHT_LINK_TEXT,
            render_death_recap_html,
        )
        entry = _entry_with_deaths()
        whole = render_death_recap_html(entry, "1")
        page = render_death_recap_html(entry, "1", header=False, fight_block=False)
        self.assertNotIn("Sharpfang · Moonlit Cove", page)
        self.assertNotIn(FIGHT_BLOCK_TITLE, page)
        self.assertIn(f"{FIGHT_LINK_LEAD} <a href='esolog:taken/1'", page)
        self.assertIn(f"<b>{FIGHT_LINK_TEXT}</b></a>", page)
        first = whole.index("<p style='margin:14px 0 2px 0'><a name='death-1'>")
        block = whole.index(f"<b>{FIGHT_BLOCK_TITLE}</b>")
        block = whole.rindex("<p", 0, block)
        self.assertIn(whole[first:block], page)
        # A player who did not die keeps the line that says so
        self.assertIn("No deaths recorded", render_death_recap_html(entry, "2", header=False))

    def test_each_death_begins_with_an_anchor(self):
        from gui.death_render import death_anchor, render_death_recap_html
        page = render_death_recap_html(_entry_with_deaths(), "1")
        self.assertEqual([death_anchor(1), death_anchor(2)],
                         re.findall(r"<a name='(death-\d+)'></a>", page))
        self.assertLess(page.index("name='death-1'"), page.index("Death 1 of 2"))
        self.assertLess(page.index("name='death-2'"), page.index("Death 2 of 2"))


class TestLinks(unittest.TestCase):

    def test_the_healing_and_recap_hrefs(self):
        from gui.death_render import recap_from_href, recap_href, unit_from_href
        from gui.fight_render import healing_href, healing_unit_from_href
        self.assertEqual(healing_unit_from_href(healing_href("12")), "12")
        self.assertIsNone(healing_unit_from_href("esolog:taken/12"))
        self.assertEqual(recap_href("12", 3), "esolog:recap/12/3")
        self.assertEqual(recap_from_href(recap_href("12", 3)), ("12", 3))
        for bad in ("esolog:recap/12", "esolog:recap/12/0", "esolog:recap/12/x",
                    "esolog:recap//2", "esolog:deaths/12", ""):
            self.assertIsNone(recap_from_href(bad), bad)
        # Apart from the player's chip
        self.assertIsNone(unit_from_href(recap_href("12", 1)))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheViewsSignals(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def test_a_click_on_each_link_asks_for_its_page(self):
        """The healing line asks for the player's healing, a death's link
        for that death, the chip for the player's deaths as before."""
        from PySide6.QtCore import QUrl

        from gui.death_render import death_href, recap_href
        from gui.fight_render import healing_href
        from gui.fight_view import FightView
        view = FightView()
        asked = []
        view.healing_requested.connect(lambda unit: asked.append(("healing", unit)))
        view.recap_requested.connect(lambda unit, n: asked.append(("recap", unit, n)))
        view.death_recap_requested.connect(lambda unit: asked.append(("deaths", unit)))
        try:
            for href in (healing_href("4"), recap_href("4", 2), death_href("4")):
                view.anchorClicked.emit(QUrl(href))
            self.assertEqual(asked, [("healing", "4"), ("recap", "4", 2), ("deaths", "4")])
        finally:
            view.deleteLater()

    def test_a_death_scrolled_to_by_its_anchor(self):
        """The recap scrolls to a death by its anchor, as the page that
        lists the fight's deaths will open it."""
        from PySide6.QtWidgets import QApplication

        from gui.death_render import death_anchor, render_death_recap_html
        from gui.fight_view import FightView
        view = FightView()
        try:
            view.resize(500, 160)
            view.show()
            view.setHtml(render_death_recap_html(_entry_with_deaths(), "1"))
            QApplication.processEvents()
            bar = view.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            view.scrollToAnchor(death_anchor(2))
            second = bar.value()
            view.scrollToAnchor(death_anchor(1))
            self.assertLess(bar.value(), second)
        finally:
            view.close()
            view.deleteLater()


if __name__ == "__main__":
    unittest.main()
