#!/usr/bin/env python3
"""The Events tab (issue #214, gui.events_tab), offscreen: the table's
columns and rows from a fight replayed through the engine, the summary
line, the five categories shown at first and More's three, Show's last 60
seconds, the search filtering the rows and counting them, Enter and a
double-click on a death's row opening its recap, Hide names in Who and
Detail, a fight update keeping the row selected and the scroll, the tab
after Deaths with Alt+V, its Tab order, and the Find button the tab bar's
corner holds at a large text size."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app

_app = None


def _fight():
    """A fresh entry of the fight test_fight_events replays: a taunt swap,
    the boss's health, a cast at @first that @second interrupts, a big hit
    on @first, @third's death and return, a map change. @first writes the
    log."""
    from tests.unit.test_fight_events import FIGHT, _run
    return _run(FIGHT).fight_history.fights[0]


def _fight_with(*lines):
    """The same fight with *lines* inserted before its first line after
    BEGIN_COMBAT."""
    from tests.unit.test_fight_events import FIGHT, _run
    return _run(FIGHT[:1] + list(lines) + FIGHT[1:]).fight_history.fights[0]


def _entry(duration_s=120.0, notes=(), recaps=()):
    """An entry of events from recorder calls (name, args...), as the
    rules' tests build them."""
    import fight_events as fe
    recorder = fe.EventRecorder()
    for name, *args in notes:
        getattr(recorder, name)(*args)
    events = recorder.fight_events(0, 600000, ability=lambda a: (f"Ability {a}", ""))
    return SimpleNamespace(duration_s=duration_s, death_recaps=list(recaps), trial_result=None,
                           events=events, players=[], player_names=[])


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class EventsTestCase(unittest.TestCase):

    def setUp(self):
        global _app
        _app = _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.windows = []

    def tearDown(self):
        from gui import text_size
        for win in self.windows:
            win.close()
        text_size.apply(text_size.DEFAULT_PCT)  # the application font is shared
        self.tmp.cleanup()

    def _page(self, entry, hide=False, size=(900, 500)):
        from gui.events_tab import EventsPage
        from gui.name_mask import NameMask
        page = EventsPage()
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.close)
        page.resize(*size)
        page.show()
        page.show_fight(entry, NameMask.for_entry(entry, hide))
        _app.processEvents()
        return page

    def _window(self, *entries):
        """A main window shown and active, its worker stopped, with
        *entries* come in live: each is selected."""
        from PySide6.QtTest import QTest

        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.windows.append(win)
        win.resize(1080, 720)
        win.show()
        win.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(win, 2000))
        _app.processEvents()
        for entry in entries:
            win._on_fight_completed(entry)
        return win

    def _settle(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            _app.processEvents()

    @staticmethod
    def _cells(page, row):
        return [page.model.index(row, column).data() for column in range(page.model.columnCount())]

    @staticmethod
    def _row_of(page, what):
        return next(n for n, row in enumerate(page.shown_rows()) if row.what == what)

    def _select(self, page, row):
        from PySide6.QtCore import QItemSelectionModel
        page.table.selectionModel().setCurrentIndex(
            page.model.index(row, 0), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)


class TestTheTable(EventsTestCase):

    def test_the_columns_rows_and_summary(self):
        """Time, What, Ability, Who and Detail, a row per event in time
        order, the summary above, the count in the bar; the first death
        selected; a death's row bold; the ability's icon at the text size's
        icon size."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont

        from gui.death_render import ICON_PX
        from gui.events_tab import COLUMNS
        from gui.text_size import scaled_px
        page = self._page(_fight())
        model = page.model
        self.assertEqual([model.headerData(c, Qt.Horizontal) for c in range(5)], list(COLUMNS))
        self.assertEqual(COLUMNS, ("Time", "What", "Ability", "Who", "Detail"))
        times = [row.t for row in page.shown_rows()]
        self.assertEqual(times, sorted(times))
        self.assertEqual(self._cells(page, 0),
                         ["0:00.1", "Taunt", "Inner Fire", "@second", "first taunt on Lokkestiiz"])
        self.assertEqual(page.summary.text(), "11 events · 1 death · Lokkestiiz reached 50%")
        self.assertEqual(page.count_label.text(), "11 of 11 shown")
        died = self._row_of(page, "Died")
        self.assertEqual(page.selected().what, "Died")
        self.assertEqual(self._cells(page, died)[:4], ["0:10.0", "Died", "Toppling Blow", "@third"])
        self.assertTrue(QFont(model.index(died, 1).data(Qt.FontRole)).bold())
        self.assertIsNone(model.index(0, 1).data(Qt.FontRole))
        # The killing blow's icon is bundled (death_recap_melee_basic)
        self.assertIsNotNone(model.index(died, 2).data(Qt.DecorationRole))
        self.assertIsNone(model.index(died, 3).data(Qt.DecorationRole))
        self.assertEqual(page.table.iconSize().width(), scaled_px(ICON_PX))
        # A death's row says what Enter does
        self.assertIn("recap", model.index(died, 0).data(Qt.ToolTipRole))

    def test_rows_and_icons_follow_the_text_size(self):
        from gui import text_size
        from gui.death_render import ICON_PX
        page = self._page(_fight())
        small = page.table.verticalHeader().defaultSectionSize()
        text_size.apply(200)
        _app.processEvents()
        self.assertEqual(page.table.iconSize().width(), 2 * ICON_PX)
        self.assertGreater(page.table.verticalHeader().defaultSectionSize(), small)
        self.assertGreaterEqual(page.table.verticalHeader().defaultSectionSize(),
                                page.table.fontMetrics().height())

    def test_a_new_text_size_keeps_the_row_selected_in_view(self):
        from gui import text_size
        notes = [("note_boss_cast", 5000 * n, "Boss", "70", str(n), str(100 + n), "", "", 0)
                 for n in range(80)]
        page = self._page(_entry(duration_s=400.0, notes=notes), size=(700, 400))
        self._select(page, 30)
        page.table.scrollTo(page.model.index(30, 0))
        _app.processEvents()
        text_size.apply(200)
        _app.processEvents()
        rect = page.table.visualRect(page.model.index(30, 0))
        self.assertTrue(page.table.viewport().rect().intersects(rect))

    def test_the_default_categories_and_more(self):
        """The five categories on at first; More's three off, each a click
        away, the button counting those on; a category off hides its rows."""
        from event_rows import DEFAULT_CATEGORIES, MORE
        notes = [("note_taunt", 500, "@tank", "2", "38254", "Boss", "70", True)]
        notes += [("note_boss_cast", t, "Boss", "70", f"s{t}", "11", "@tank", "2", 1500, True)
                  for t in (1000, 7000)]
        notes += [("note_boss_cast", 20000 + 4000 * i, "Boss", "70", f"a{i}", "12", "@dps", "1",
                   500, True) for i in range(9)]
        notes += [("note_boss_cast", 70000, "Boss", "70", "b1", "13", "", "", 2000, False)]
        page = self._page(_entry(notes=notes))
        self.assertEqual(list(page.category_boxes), list(DEFAULT_CATEGORIES))
        self.assertTrue(all(box.isChecked() for box in page.category_boxes.values()))
        self.assertEqual(list(page.more_actions), list(MORE))
        self.assertFalse(any(action.isChecked() for action in page.more_actions.values()))
        self.assertEqual({row.category for row in page.shown_rows()}, {"taunts", "boss"})
        page.more_actions["tank"].setChecked(True)
        self.assertEqual({row.category for row in page.shown_rows()}, {"taunts", "boss", "tank"})
        self.assertEqual(page.more_button.text(), "More (1)")
        page.more_actions["auto"].setChecked(True)
        self.assertIn("auto", {row.category for row in page.shown_rows()})
        page.category_boxes["boss"].setChecked(False)
        self.assertNotIn("boss", {row.category for row in page.shown_rows()})
        # One taunt, a cast, two at the tank and nine quick strikes: 13 rows
        self.assertEqual(page.count_label.text(), f"{len(page.shown_rows())} of 13 shown")

    def test_show_the_last_60_seconds(self):
        """Show's Last 60 s keeps the rows from a minute before the fight's
        end; the row selected before it goes to the first of them."""
        notes = [("note_map", t, f"Map {t}") for t in (5000, 50000, 70000, 110000)]
        page = self._page(_entry(duration_s=120.0, notes=notes))
        self.assertEqual(len(page.shown_rows()), 4)
        self._select(page, 0)
        page.show_picker.setCurrentIndex(1)
        self.assertEqual(page.show_picker.currentText(), "Last 60 s")
        self.assertEqual([row.t for row in page.shown_rows()], [70000, 110000])
        self.assertEqual(page.selected().t, 70000)
        page.show_picker.setCurrentIndex(0)
        self.assertEqual(len(page.shown_rows()), 4)
        self.assertEqual(page.selected().t, 70000)  # kept while shown

    def test_show_the_seconds_around_a_moment(self):
        """Show's ± choices keep the rows either side of the row selected
        when the choice is made, and say the moment; ±30 s keeps that
        moment; another fight goes back to the whole fight."""
        notes = [("note_map", t, f"Map {t}") for t in (5000, 42000, 50000, 58000, 75000, 110000)]
        page = self._page(_entry(duration_s=120.0, notes=notes))
        self._select(page, 2)                      # 0:50.0
        page.show_picker.setCurrentIndex(2)
        self.assertEqual(page.show_picker.currentText(), "±10 s around a moment")
        self.assertEqual([row.t for row in page.shown_rows()], [42000, 50000, 58000])
        self.assertEqual(page.selected().t, 50000)
        self.assertEqual(page.count_label.text(), "3 of 6 shown · around 0:50.0")
        self._select(page, 0)                      # another row: the moment stays
        page.show_picker.setCurrentIndex(3)
        self.assertEqual([row.t for row in page.shown_rows()], [42000, 50000, 58000, 75000])
        page.show_picker.setCurrentIndex(0)
        self.assertEqual((len(page.shown_rows()), page.count_label.text()), (6, "6 of 6 shown"))
        # Chosen again: around the row selected now, 0:42.0
        page.show_picker.setCurrentIndex(2)
        self.assertEqual([row.t for row in page.shown_rows()], [42000, 50000])
        page.show_fight(_entry(duration_s=120.0, notes=notes))
        self.assertEqual((page.show_picker.currentIndex(), len(page.shown_rows())), (0, 6))

    def test_show_around_a_moment_another_view_sends(self):
        """show_around: the rows within ten seconds of the moment, the first
        from it on selected; nothing with no fight."""
        notes = [("note_map", t, f"Map {t}") for t in (5000, 42000, 50000, 58000, 110000)]
        page = self._page(_entry(duration_s=120.0, notes=notes))
        page.show_around(49000)
        self.assertEqual(page.show_picker.currentText(), "±10 s around a moment")
        self.assertEqual([row.t for row in page.shown_rows()], [42000, 50000, 58000])
        self.assertEqual(page.selected().t, 50000)
        self.assertIn("around 0:49.0", page.count_label.text())
        page.clear()
        page.show_around(1000)
        self.assertEqual(page.shown_rows(), [])

    def test_ctrl_g_and_the_link_ask_for_the_row_on_the_graph(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.events_tab import GRAPH_HREF
        page = self._page(_fight())
        asked = []
        page.graph_requested.connect(lambda ms, label: asked.append((ms, label)))
        self._select(page, self._row_of(page, "Died"))
        page.table.setFocus()
        QTest.keyClick(page.table, Qt.Key_G, Qt.ControlModifier)
        self.assertEqual(asked, [(10000, "Died · Toppling Blow")])
        self._select(page, self._row_of(page, "Back"))
        page.full_row.linkActivated.emit(GRAPH_HREF)
        self.assertEqual(asked[-1], (16000, "Back"))
        self.assertIn(page.full_row, page.focus_chain())  # its link is a Tab stop

    def test_an_entry_from_before_the_events_says_so(self):
        from gui.events_tab import OLD_FIGHT
        page = self._page(SimpleNamespace(events=None, duration_s=10.0, death_recaps=[]))
        self.assertEqual(page.summary.text(), OLD_FIGHT)
        self.assertEqual(page.model.rowCount(), 0)
        self.assertEqual(page.count_label.text(), "")
        page.clear()
        self.assertEqual(page.summary.text(), "")


class TestTheDeathRow(EventsTestCase):

    def test_enter_and_a_double_click_on_a_death_ask_for_its_recap(self):
        """Enter on the single death's row asks for (unit id, number);
        Enter on another row asks for nothing; a double-click (a click,
        then the double-click, as a real one sends) asks again."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        page = self._page(_fight())
        asked = []
        page.recap_requested.connect(lambda unit, number: asked.append((unit, number)))
        page.table.setFocus()
        died = self._row_of(page, "Died")
        self._select(page, died)
        QTest.keyClick(page.table, Qt.Key_Return)
        self.assertEqual(asked, [("3", 1)])
        self._select(page, 0)
        QTest.keyClick(page.table, Qt.Key_Return)
        self.assertEqual(asked, [("3", 1)])
        centre = page.table.visualRect(page.model.index(died, 1)).center()
        QTest.mouseClick(page.table.viewport(), Qt.LeftButton, Qt.NoModifier, centre)
        QTest.mouseDClick(page.table.viewport(), Qt.LeftButton, Qt.NoModifier, centre)
        self.assertEqual(asked, [("3", 1), ("3", 1)])

    def test_the_row_selected_is_whole_under_the_table(self):
        """Every cell of the row selected on the line under the table, cut
        or not, and what Enter does on a single death's."""
        from gui.events_tab import GRAPH_HREF, GRAPH_KEYS, GRAPH_LINK, RECAP_TIP
        page = self._page(_fight(), size=(500, 400))
        died = self._row_of(page, "Died")
        self._select(page, died)
        text = page.full_row.text()
        self.assertTrue(text.startswith("0:10.0 · Died · Toppling Blow · @third · from Lokkestiiz"))
        self.assertIn("resurrected by @first at 0:16.0", text)
        # What Enter does, then the row's moment on the DPS graph
        from gui.fight_render import link_color
        link = (f'<a href="{GRAPH_HREF}" style="text-decoration:none;color:{link_color(False)}">'
                f'{GRAPH_LINK}</a> ({GRAPH_KEYS})')
        self.assertTrue(text.endswith(f"{RECAP_TIP} — {link}"))
        self._select(page, self._row_of(page, "Back"))
        self.assertNotIn(RECAP_TIP, page.full_row.text())
        self.assertTrue(page.full_row.text().endswith(link))
        page.show_fight(None)
        self.assertEqual(page.full_row.text(), "")

    def test_enter_on_the_events_tab_opens_the_death_in_the_player_window(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.player_window import DEATHS_TAB
        entry = _fight()
        win = self._window(entry)
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        self.assertEqual(page.selected().what, "Died")  # a new fight: its first death
        page.table.setFocus()
        QTest.keyClick(page.table, Qt.Key_Return)
        window = win._player_window
        self.assertIsNotNone(window)
        self.assertEqual((window.entry, window.unit_id, window.current_tab()),
                         (entry, "3", DEATHS_TAB))


class TestHideNames(EventsTestCase):

    def test_who_and_detail_are_masked_and_read_as_hidden_names(self):
        """Every player but the one writing the log (@first) hidden in Who
        and Detail, as '@' and blocks; a reader hears 'hidden name'; a
        search finds the masked text, never the name."""
        from PySide6.QtCore import Qt
        page = self._page(_fight(), hide=True)
        swap = next(n for n, row in enumerate(page.shown_rows()) if row.detail.startswith("took"))
        self.assertEqual(self._cells(page, swap)[3:], ["@▒▒▒▒▒", "took Lokkestiiz from @▒▒▒▒▒▒"])
        self.assertEqual(page.model.index(swap, 3).data(Qt.AccessibleTextRole), "hidden name")
        cast = self._row_of(page, "Boss cast")
        self.assertEqual(self._cells(page, cast)[3:],
                         ["Lokkestiiz", "at @first · interrupted by @▒▒▒▒▒▒"])
        self.assertIsNone(page.model.index(cast, 3).data(Qt.AccessibleTextRole))
        self.assertEqual(page.set_search("second"), 0)
        # @first kept: the cast at them, the hit on them, the death and return they raised
        self.assertEqual(page.set_search("@first"), 4)
        texts = " ".join(" ".join(self._cells(page, r)) for r in range(page.model.rowCount()))
        self.assertNotIn("@second", texts)

    def test_hide_names_redraws_the_tab_in_place(self):
        win = self._window(_fight())
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        self._select(page, 0)
        self.assertEqual(self._cells(page, 0)[3], "@second")
        win.hide_names_action.setChecked(True)
        self.assertEqual(self._cells(page, 0)[3], "@▒▒▒▒▒▒")
        self.assertEqual(page.selected().what, "Taunt")  # the row kept


class TestKeepingThePlace(EventsTestCase):

    def test_the_same_fight_drawn_again_measures_its_columns_again(self):
        """Rows logged later can be wider: the same fight drawn again in
        place sizes its columns for them."""
        import fight_events as fe
        from gui.events_tab import WHO_COL
        entry = _entry(notes=[("note_taunt", 1000, "@a", "1", "1", "Boss", "70", True)])
        page = self._page(entry, size=(1200, 400))
        narrow = page.table.columnWidth(WHO_COL)
        recorder = fe.EventRecorder()
        recorder.note_taunt(1000, "@a", "1", "1", "Boss", "70", True)
        recorder.note_taunt(5000, "@a much longer handle", "2", "1", "Boss", "70", True)
        entry.events = recorder.fight_events(0, 600000, ability=lambda a: (f"Ability {a}", ""))
        page.show_fight(entry)
        _app.processEvents()
        self.assertGreater(page.table.columnWidth(WHO_COL), narrow)

    def test_a_fight_update_keeps_the_row_selected(self):
        """The fight changes in place (a later death, the rest of a fight
        the game cut in two): the rows are drawn again, the row selected
        found by what it says although a row came before it."""
        from tests.unit.test_fight_events import _boss, _event, _player
        entry = _fight()
        win = self._window(entry)
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        self._select(page, self._row_of(page, "Map"))
        before = page.model.rowCount()
        # The same entry, its events now with a big hit on @second first
        later = _fight_with(_event(10050, "DAMAGE", 15000, _boss(), _player(2, 5000), ability=555))
        entry.events = later.events
        entry.death_recaps = later.death_recaps
        win._on_fight_updated(entry)
        self.assertEqual(page.model.rowCount(), before + 1)
        self.assertEqual(page.selected().what, "Map")
        self.assertEqual(page.shown_rows()[0].what, "Hit")

    def test_the_scroll_is_kept_in_place(self):
        notes = [("note_map", 1000 * t, f"Map {t}") for t in range(1, 80)]
        entry = _entry(notes=notes)
        page = self._page(entry, size=(700, 300))
        bar = page.table.verticalScrollBar()
        self.assertGreater(bar.maximum(), 10)
        bar.setValue(bar.maximum() // 2)
        self._select(page, bar.value() + 2)
        key = (page.selected().t, page.selected().ability)
        scroll = bar.value()
        page.show_fight(entry)  # the same fight drawn again
        self.assertEqual(bar.value(), scroll)
        self.assertEqual((page.selected().t, page.selected().ability), key)
        # A new fight starts at the top, its first row selected
        page.show_fight(_entry(notes=notes))
        self.assertEqual(bar.value(), 0)
        self.assertEqual(page.selected().t, 1000)


class TestTheSearch(EventsTestCase):

    def test_the_search_filters_the_rows_and_counts_them(self):
        """On the Events tab the search keeps the rows that hold its text,
        whatever the case, and the field counts them; Enter goes to the
        next row; cleared, every row is back with the row selected kept.
        Back on the Fight tab, the search highlights again."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.fight_tabs import count_text
        win = self._window(_fight())
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        total = page.model.rowCount()
        win.search_field.setText("LOKK")
        rows = page.shown_rows()
        self.assertTrue(rows)
        self.assertLess(len(rows), total)
        for n in range(len(rows)):
            self.assertIn("lokk", " ".join(self._cells(page, n)).lower())
        self.assertEqual(win.search_count.text(), count_text(len(rows)))
        self.assertIs(page.selected(), rows[0])
        QTest.keyClick(win.search_field, Qt.Key_Return)
        self.assertIs(page.selected(), rows[1])
        win.search_field.setText("@second")
        # The first taunt, the swap, the cast @second interrupted
        self.assertEqual(win.search_count.text(), count_text(3))
        chosen = page.selected()
        win.search_field.clear()
        self.assertEqual(page.model.rowCount(), total)
        self.assertEqual(page.selected(), chosen)
        self.assertEqual(win.search_count.text(), "")
        win.search_field.setText("Lokkestiiz")
        win.fight_tabs.setCurrentIndex(0)
        self.assertTrue(win._search_matches())
        self.assertNotEqual(win.search_count.text(), count_text(len(page.shown_rows())))
        win.fight_tabs.setCurrentWidget(win.events_view)
        self.assertEqual(win.search_count.text(), count_text(len(page.shown_rows())))


class TestJumps(EventsTestCase):
    """Issue #214: from an Events row to the DPS graph and back, and from
    the buff strip's pop-up and a death's recap to the Events tab."""

    def test_ctrl_g_marks_the_rows_moment_on_the_dps_graph(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        entry = _fight()
        win = self._window(entry)
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        page.table.setFocus()
        QTest.keyClick(page.table, Qt.Key_G, Qt.ControlModifier)   # on the first death
        self.assertIs(win.fight_tabs.currentWidget(), win.dps_panel)
        self.assertIs(win.dps_panel.entry, entry)
        self.assertEqual(win.dps_panel.graph.cursor, (10.0, "Died · Toppling Blow"))
        # Another fight shown: the mark was the last fight's
        other = _fight()
        win._on_fight_completed(other)
        self.assertIs(win.dps_panel.entry, other)
        self.assertIsNone(win.dps_panel.graph.cursor)

    def test_a_double_click_on_the_graph_opens_the_events_around_it(self):
        entry = _fight()
        win = self._window(entry)
        win.fight_tabs.setCurrentWidget(win.dps_panel)
        win.dps_panel.moment_requested.emit(12000)
        page = win.events_view
        self.assertIs(win.fight_tabs.currentWidget(), page)
        self.assertEqual(page.show_picker.currentText(), "±10 s around a moment")
        times = [row.t for row in page.shown_rows()]
        self.assertTrue(times and all(2000 <= t <= 22000 for t in times), times)
        self.assertGreaterEqual(page.selected().t, 12000)
        self.assertIn("around 0:12.0", page.count_label.text())
        self.assertEqual(win.dps_panel.graph.cursor, (12.0, ""))
        self.assertTrue(page.table.hasFocus())

    def test_the_strips_popup_link_opens_the_events_around_its_moment(self):
        entry = _fight()
        win = self._window(entry)
        self.assertTrue(win.timeline_strip._moment_links)   # the fight has its events
        win.timeline_strip.moment_requested.emit(3000)
        page = win.events_view
        self.assertIs(win.fight_tabs.currentWidget(), page)
        self.assertTrue(all(t <= 13000 for t in (row.t for row in page.shown_rows())))
        # A fight from before the events: no link, and nothing to open
        from tests.unit.test_death_recap_gui import _entry_with_deaths
        old = _entry_with_deaths()
        win._on_fight_completed(old)
        self.assertFalse(win.timeline_strip._moment_links)
        win.fight_tabs.setCurrentIndex(0)
        win.timeline_strip.moment_requested.emit(3000)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)

    def test_a_deaths_events_link_selects_its_fight_and_opens_the_tab(self):
        """From the player window, which keeps the fight it was opened for:
        that fight is selected in the list again, and the Events tab shows
        the seconds around the death."""
        from gui.player_window import DEATHS_TAB
        first, second = _fight(), _fight()
        win = self._window(first, second)
        self.assertIs(win.history_list.current_entry(), second)
        win._open_player("3", DEATHS_TAB, entry=first, death=1)
        win._player_window.events_requested.emit(first, "3", 10000)
        self.assertIs(win.history_list.current_entry(), first)
        page = win.events_view
        self.assertIs(win.fight_tabs.currentWidget(), page)
        self.assertIs(page.entry, first)
        self.assertEqual((page.selected().what, page.selected().t), ("Died", 10000))

    def test_a_fight_gone_from_the_list_opens_nothing(self):
        """As the window's Show in list: said in the status bar, and the
        Events tab left alone."""
        from gui.player_window import DEATHS_TAB
        first, second = _fight(), _fight()
        win = self._window(first, second)
        win._open_player("3", DEATHS_TAB, entry=first, death=1)
        gone = _fight()
        win._player_window.events_requested.emit(gone, "3", 10000)
        self.assertIs(win.history_list.current_entry(), second)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertIn("not in the list", win.statusBar().currentMessage())

    def test_another_fight_picked_takes_the_mark_with_the_graph_not_drawn(self):
        """The mark is the fight's: back on the fight after a visit to
        another, with the graph never on screen between, it is gone."""
        first, second = _fight(), _fight()
        win = self._window(first, second)
        win.history_list.select_entry(first)
        win.fight_tabs.setCurrentWidget(win.events_view)
        win.events_view._ask_graph()
        self.assertIsNotNone(win.dps_panel.graph.cursor)
        win.fight_tabs.setCurrentIndex(0)
        win.history_list.select_entry(second)
        win.history_list.select_entry(first)
        win.fight_tabs.setCurrentWidget(win.dps_panel)
        self.assertIsNone(win.dps_panel.graph.cursor)

    def test_a_deaths_link_selects_the_row_that_tells_it(self):
        """Players who died together are one row at the first death's time:
        the link of the last to die selects that row, not the next one; the
        Deaths box unticked is ticked again; a search that narrows the rows
        is said in the count."""
        recaps = [{"unit_id": key, "name": f"@{key}", "time_ms": t, "ability": "Melt",
                   "ability_id": "5", "killer": "Boss", "icon": "", "cause": ""}
                  for key, t in (("1", 60000), ("2", 60400), ("3", 60900))]
        notes = [("note_map", t, f"Map {t}") for t in (55000, 61000, 65000)]
        page = self._page(_entry(duration_s=120.0, notes=notes, recaps=recaps))
        page.category_boxes["deaths"].setChecked(False)
        self.assertTrue(page.show_around(60900, unit_key="3"))
        self.assertTrue(page.category_boxes["deaths"].isChecked())
        self.assertEqual((page.selected().what, page.selected().t), ("Died x3", 60000))
        # A moment that is no death: the first row from it on
        page.show_around(60900)
        self.assertEqual(page.selected().t, 61000)
        page.set_search("Melt")
        self.assertEqual(page.count_label.text(),
                         "1 of 4 shown · around 1:00.9 · matching the search")
        page.set_search("")
        self.assertNotIn("matching", page.count_label.text())
        page.clear()
        self.assertFalse(page.show_around(1000))     # no fight to show it for

    def test_the_line_under_the_table_is_a_tab_stop_only_with_a_row(self):
        from PySide6.QtCore import Qt
        page = self._page(_fight())
        self.assertTrue(page.full_row.textInteractionFlags() & Qt.LinksAccessibleByKeyboard)
        page.clear()
        self.assertEqual(page.full_row.textInteractionFlags(), Qt.NoTextInteraction)
        self.assertEqual(page.full_row.focusPolicy(), Qt.NoFocus)


class TestInTheWindow(EventsTestCase):

    def test_the_tab_after_deaths_with_alt_v(self):
        """Events is the third tab, after Deaths, Alt+V its key; a fight
        from before the events were recorded says so there."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.events_tab import OLD_FIGHT
        from tests.unit.test_death_recap_gui import _entry_with_deaths
        win = self._window(_entry_with_deaths())
        tabs = win.fight_tabs
        self.assertEqual(tabs.indexOf(win.events_view), tabs.indexOf(win.deaths_view) + 1)
        self.assertEqual(tabs.tabText(tabs.indexOf(win.events_view)), "E&vents")
        QTest.keyClick(win, Qt.Key_V, Qt.AltModifier)
        self.assertIs(tabs.currentWidget(), win.events_view)
        self.assertEqual(win.events_view.summary.text(), OLD_FIGHT)
        # The next fight is drawn on the tab chosen
        second = _fight()
        win._on_fight_completed(second)
        self.assertIs(win.events_view.entry, second)
        self.assertEqual(win.events_view.selected().what, "Died")
        # No fight: the page keeps nothing
        win._show_replaying()
        self.assertIsNone(win.events_view.entry)
        self.assertEqual(win.events_view.model.rowCount(), 0)

    def test_a_page_drawn_while_hidden_is_drawn_when_shown(self):
        win = self._window(_fight())
        second = _fight()
        win._on_fight_completed(second)
        self.assertIsNot(win.events_view.entry, second)  # not drawn while hidden
        win.fight_tabs.setCurrentWidget(win.events_view)
        self.assertIs(win.events_view.entry, second)

    def test_tab_reaches_every_control_of_the_page(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        win = self._window(_fight())
        win.fight_tabs.setCurrentWidget(win.events_view)
        win.fight_tabs.tabBar().setFocus()
        _app.processEvents()
        reached = []
        for _ in range(12):
            QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab)
            reached.append(QApplication.focusWidget())
        chain = win.events_view.focus_chain()
        self.assertEqual([w for w in reached if w in chain][:len(chain)], chain)
        first = reached.index(chain[0])
        # Only the search (or the Find button) comes between the bar and the page
        self.assertTrue(set(reached[:first]) <= {win.search_field, win.fight_views.find_button})

    def test_the_filter_bar_wraps_at_large_text(self):
        """At 200% text the page asks for less width than the tab bar's
        labels: its controls go onto more lines rather than widen the
        column."""
        from gui import text_size
        win = self._window(_fight())
        win.set_text_size(200)
        win.fight_tabs.setCurrentWidget(win.events_view)
        self._settle()
        page = win.events_view
        self.assertLess(page.minimumSizeHint().width(), win.fight_tabs.tabBar().sizeHint().width())
        self.assertEqual(text_size.percent(), 200)
        boxes = list(page.category_boxes.values())
        self.assertTrue(all(box.isVisible() for box in boxes))
        for widget in page.focus_chain()[:-1]:
            self.assertLessEqual(widget.geometry().right(), page.width())


class TestTheFindButton(EventsTestCase):

    def _compact_window(self):
        """A window at 200% text whose right column is too narrow for the
        search in the corner."""
        win = self._window(_fight())
        win.set_text_size(200)
        self._settle()
        views = win.fight_views
        bar = win.fight_tabs.tabBar().sizeHint().width()
        total = sum(win._splitter.sizes())
        right = views.minimumSizeHint().width() + 12
        if right - 12 >= bar + win.search_field.least_width():
            self.skipTest("the corner holds the field at the column's least here")
        win._splitter.setSizes([total - right, right])
        self._settle()
        return win

    def test_the_corner_holds_a_find_button_at_large_text(self):
        """No row of its own: the corner holds Find (Ctrl+F); the button
        shows the field on its row with the cursor in it; Esc on the empty
        field hides it and gives the button the focus; Ctrl+F shows it
        again."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        win = self._compact_window()
        views, field, button = win.fight_views, win.search_field, win.fight_views.find_button
        self.assertTrue(views.is_compact())
        self.assertIs(win.fight_tabs.cornerWidget(), button)
        self.assertTrue(button.isVisible())
        self.assertFalse(field.isVisible())
        self.assertEqual(button.accessibleName(), "Find (Ctrl+F)")
        self.assertEqual(button.toolTip(), "Find (Ctrl+F)")
        QTest.mouseClick(button, Qt.LeftButton)
        _app.processEvents()
        self.assertTrue(field.isVisible())
        self.assertFalse(views.in_corner())
        self.assertFalse(button.isVisible())
        self.assertIs(QApplication.focusWidget(), field)
        QTest.keyClick(field, Qt.Key_Escape)
        _app.processEvents()
        self.assertFalse(field.isVisible())
        self.assertTrue(button.isVisible())
        self.assertIs(QApplication.focusWidget(), button)
        win.history_list.setFocus()
        _app.processEvents()
        QTest.keyClick(win.history_list, Qt.Key_F, Qt.ControlModifier)
        _app.processEvents()
        self.assertTrue(field.isVisible())
        self.assertIs(QApplication.focusWidget(), field)

    def test_a_search_in_use_keeps_its_row(self):
        """Text in the field keeps its row as the focus leaves; Esc clears
        it first, and the empty field left hides the row."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._compact_window()
        views, field = win.fight_views, win.search_field
        win._find()
        QTest.keyClicks(field, "Lokk")
        win.history_list.setFocus()
        _app.processEvents()
        self.assertTrue(field.isVisible())
        self.assertTrue(win.search_count.text())
        field.setFocus()
        _app.processEvents()
        QTest.keyClick(field, Qt.Key_Escape)
        self.assertEqual(field.text(), "")
        self.assertTrue(field.isVisible())  # the first Esc clears
        win.history_list.setFocus()
        _app.processEvents()
        self.assertFalse(field.isVisible())  # left empty: the row goes
        self.assertTrue(views.find_button.isVisible())

    def test_a_search_given_text_comes_out_on_its_row(self):
        """Text put in the hidden field (the search kept from before) shows
        it on its row, where its count can be read."""
        win = self._compact_window()
        self.assertFalse(win.search_field.isVisible())
        win.search_field.setText("Lokk")
        self.assertTrue(win.search_field.isVisible())
        self.assertTrue(win.fight_views.search_open())

    def test_the_search_goes_back_to_the_corner_with_room(self):
        win = self._compact_window()
        win.set_text_size(100)
        win.resize(1600, 720)
        total = sum(win._splitter.sizes())
        win._splitter.setSizes([total // 3, total - total // 3])
        self._settle()
        self.assertTrue(win.fight_views.in_corner())
        self.assertFalse(win.fight_views.find_button.isVisible())
        self.assertTrue(win.search_field.isVisible())


if __name__ == "__main__":
    unittest.main()
