#!/usr/bin/env python3
"""The dps over time graph: the two curves (damage_stats, Qt-free), the
chart widget (offscreen Qt), and the window with its legend, mode and boss
switch, opened from the header's group dps figure or the toolbar."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from damage_stats import per_second, running_dps, series_of, smoothed_dps  # noqa: E402

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


# 1000 damage in each of seconds 2..5 of a ten-second fight, 2000 in second 9
SERIES = [[2.0, 1000], [3.0, 1000], [4.0, 1000], [5.0, 1000], [9.0, 2000]]
WINDOW = {'first_ms': 12300, 'last_ms': 19100, 'span_ms': 6800, 'first_s': 2.3, 'last_s': 9.1}


class TestCurves(unittest.TestCase):

    def test_series_of_buckets(self):
        self.assertEqual(series_of({12: 500, 10: 200}, 10000), [[0.0, 200], [2.0, 500]])
        self.assertEqual(series_of({}, 10000), [])

    def test_per_second_places_each_bucket_at_its_nearest_second(self):
        self.assertEqual(per_second(SERIES, 10.0), [0, 0, 1000, 1000, 1000, 1000, 0, 0, 0, 2000, 0])
        # A bucket starting a fraction before the fight counts in its first second
        self.assertEqual(per_second([[-0.4, 300], [0.6, 100]], 2.0), [300, 100, 0])

    def test_smoothed_curve_is_a_centred_moving_average(self):
        points = smoothed_dps(SERIES, 1, 10.0)
        # A one-second window is the series itself, carried to both edges
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[1:4], [(0.5, 0.0), (1.5, 0.0), (2.5, 1000.0)])
        self.assertEqual(points[-2], (10.5, 0.0))
        self.assertEqual(points[-1], (10.0, 0.0))
        points = smoothed_dps(SERIES, 5, 10.0)
        # Seconds 2..6 hold 4,000: 800 a second, centred at 4.5
        self.assertIn((4.5, 800.0), points)
        # Seconds 5..9 hold 3,000
        self.assertIn((7.5, 600.0), points)
        self.assertEqual(points[0][0], 0.0)
        self.assertEqual(points[-1][0], 10.0)
        self.assertEqual(smoothed_dps([], 5, 10.0), [])
        # A window longer than the fight is the whole fight's mean
        self.assertEqual(smoothed_dps(SERIES, 60, 10.0)[1], (5.5, 6000 / 11))

    def test_running_curve_is_the_live_figure(self):
        points = dict(running_dps(SERIES, WINDOW['first_s'], WINDOW['last_s'], 10.0))
        # Nothing before a second after the first hit
        self.assertNotIn(2.0, points)
        self.assertNotIn(3.0, points)
        # At second 4: 3,000 so far over 4 - 2.3 s
        self.assertAlmostEqual(points[4.0], 3000 / 1.7)
        # Past the last hit the elapsed time stops at it, so the figure holds
        self.assertAlmostEqual(points[10.0], 6000 / (9.1 - 2.3))
        self.assertAlmostEqual(points[9.0], 6000 / (9.0 - 2.3))
        self.assertEqual(running_dps(SERIES, None, None, 10.0), [])


def _player(unit_id, name, series, dps, boss_dps=0.0, boss_series=None):
    return {'role': 'D', 'name': name, 'class_abbr': 'NB', 'dps': dps, 'boss_dps': boss_dps,
            'dmg_pct': 50.0, 'boss_pct': 50.0, 'h': 20000, 'm': 30000, 's': 15000,
            'unit_id': unit_id, 'sets': [], 'all_sets': [], 'skill_lines': [], 'class_lines': [],
            'front_bar': [], 'back_bar': [], 'front_bar_slots': [], 'back_bar_slots': [],
            'damage': {'total': sum(d for _t, d in series), 'boss': 0, 'window': WINDOW,
                       'boss_window': WINDOW, 'abilities': [], 'boss_abilities': [], 'targets': [],
                       'series': series, 'boss_series': boss_series or []}}


def _entry(players=10, boss=False):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = 'Sharpfang'
    entry.zone_name = 'Moonlit Cove'
    entry.timestamp = '2026-10-03 16:54:04'
    entry.duration_s = 10.0
    entry.dps_time_s = 6.8
    entry.group_dps = 6000 / 6.8
    entry.group_boss_dps = 3000 / 6.8 if boss else 0.0
    entry.players = [_player(str(n), f'@player{n}', SERIES, 6000 / 6.8) for n in range(1, players + 1)]
    boss_series = [[2.0, 1000], [3.0, 1000], [4.0, 1000]] if boss else []
    if boss:
        entry.players[0]['damage']['boss_series'] = boss_series
        entry.players[0]['damage']['boss'] = 3000
    entry.damage_series = {'all': SERIES, 'boss': boss_series, 'window': WINDOW, 'boss_window': WINDOW}
    return entry


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestGraphWidget(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def test_curves_paint_and_report_values(self):
        from PySide6.QtGui import QColor
        from gui.dps_graph import GROUP_PANEL, PLAYER_PANEL, Curve, DpsGraph
        graph = DpsGraph()
        graph.resize(800, 400)
        group = Curve('Group', 'Group', None, smoothed_dps(SERIES, 5, 10.0), 3.0, panel=GROUP_PANEL)
        player = Curve('1', '@player1', QColor('#2a78d6'), smoothed_dps(SERIES, 1, 10.0))
        graph.set_curves([group, player], 10.0)
        self.assertEqual(len(graph.curves), 2)
        # Two panels, the group's above the players', each on its own scale
        self.assertEqual(graph.panels, [GROUP_PANEL, PLAYER_PANEL])
        self.assertLess(graph._panel_rect(GROUP_PANEL).bottom(), graph._panel_rect(PLAYER_PANEL).top())
        # The five-second average peaks at 800, the every-hit line at 2,000
        self.assertEqual(graph._y_top[GROUP_PANEL], 800.0)
        self.assertEqual(graph._y_top[PLAYER_PANEL], 2000.0)
        image = graph.grab().toImage()
        colors = {image.pixelColor(x, y).name() for x in range(0, 800, 7) for y in range(0, 400, 7)}
        self.assertIn('#2a78d6', colors)  # the player's line was drawn in its hue
        self.assertEqual(player.value_at(2.5), 1000.0)
        # One panel alone takes the whole plot
        graph.set_curves([player], 10.0)
        self.assertEqual(graph.panels, [PLAYER_PANEL])
        self.assertEqual(graph._panel_rect(PLAYER_PANEL), graph._plot_rect())
        graph.set_curves([group, player], 10.0)
        self.assertIsNone(player.value_at(20.0))
        self.assertEqual(graph.second_at(graph._plot_rect().left()), 0)
        self.assertEqual(graph.second_at(graph._plot_rect().right()), 10)
        self.assertIsNone(graph.second_at(2))
        tip = graph.tooltip_html(4)
        self.assertIn('<b>4s</b>', tip)
        self.assertIn('@player1', tip)
        self.assertIn('#2a78d6', tip)
        graph.hover_second = 4
        graph.grab()  # the crosshair and markers paint without error

    def test_empty_graph_says_so(self):
        from gui.dps_graph import DpsGraph
        graph = DpsGraph()
        graph.resize(400, 200)
        graph.set_curves([], 0.0)
        graph.grab()
        self.assertEqual(graph.tooltip_html(1), '')
        self.assertIsNone(graph.second_at(100))

    def test_hover_tracks_the_pointer(self):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from gui.dps_graph import Curve, DpsGraph
        graph = DpsGraph()
        graph.resize(800, 400)
        graph.show()
        graph.set_curves([Curve('Group', 'Group', None, smoothed_dps(SERIES, 1, 10.0))], 10.0)

        def move_to(x, y):
            pos = QPointF(x, y)
            event = QMouseEvent(QEvent.MouseMove, pos, graph.mapToGlobal(pos.toPoint()),
                                Qt.NoButton, Qt.NoButton, Qt.NoModifier)
            _app.sendEvent(graph, event)

        plot = graph._plot_rect()
        move_to(plot.center().x(), plot.center().y())
        self.assertEqual(graph.hover_second, 5)
        move_to(2, 2)
        self.assertIsNone(graph.hover_second)
        graph.close()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestGraphWindow(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _main_window(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / 'config.json')
        config.set('log_path', str(self.root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        return win

    def test_header_figure_is_a_link_with_its_hover_text(self):
        from gui.fight_render import damage_tooltips, render_html
        html = render_html(_entry(), detailed=False)
        self.assertIn('href="esolog:graph/"', html)
        tip = damage_tooltips(_entry())['esolog:graph/']
        self.assertIn('Group damage over 7s dps time', tip)
        self.assertIn('Click for the dps over time graph', tip)
        self.assertNotIn('Boss damage', tip)
        self.assertIn('Boss damage over', damage_tooltips(_entry(boss=True))['esolog:graph/'])

    def test_opens_from_the_header_and_the_toolbar(self):
        from PySide6.QtCore import Qt, QUrl
        from gui.dps_graph import GROUP, MAX_HUES
        win = self._main_window()
        try:
            win._on_fight_completed(_entry(players=10))
            win.history_list.select_fight(0)
            self.assertIsNone(win._graph_dialog)
            win.fight_view.anchorClicked.emit(QUrl('esolog:graph/'))
            dialog = win._graph_dialog
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), 'DPS over time – Sharpfang')
            self.assertIn('10s fight', dialog.header.text())
            # The legend: the group and every player, the first eight on
            self.assertEqual(dialog.legend.count(), 11)
            self.assertEqual(dialog.checked_keys(), [GROUP] + [str(n) for n in range(1, MAX_HUES + 1)])
            self.assertEqual(len(dialog.graph.curves), 9)
            self.assertFalse(dialog.boss_only.isVisibleTo(dialog))
            # Ticking the tenth player draws it dashed in a reused hue
            dialog.legend.item(10).setCheckState(Qt.Checked)
            curves = {c.key: c for c in dialog.graph.curves}
            self.assertTrue(curves['10'].dashed)
            self.assertEqual(curves['10'].color.name(), curves['2'].color.name())
            self.assertFalse(curves['2'].dashed)
            # The toolbar reuses the window
            win.graph_action.trigger()
            self.assertIs(win._graph_dialog, dialog)
        finally:
            win.close()

    def test_mode_and_boss_switch(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry(players=2, boss=True))
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:graph/'))
            dialog = win._graph_dialog
            self.assertTrue(dialog.boss_only.isVisibleTo(dialog))
            group = next(c for c in dialog.graph.curves if c.key == 'Group')
            self.assertEqual(group.points, smoothed_dps(SERIES, 5, 10.0))
            dialog.mode.setCurrentIndex(4)  # the running figure
            group = next(c for c in dialog.graph.curves if c.key == 'Group')
            self.assertEqual(group.points, running_dps(SERIES, 2.3, 9.1, 10.0))
            dialog.boss_only.setChecked(True)
            keys = {c.key for c in dialog.graph.curves}
            # Player 2 dealt no boss damage: no line for them
            self.assertEqual(keys, {'Group', '1'})
            # A fight without boss damage hides the switch and clears it
            win._on_fight_completed(_entry(players=2))
            win.history_list.select_fight(1)
            win.graph_action.trigger()
            self.assertFalse(dialog.boss_only.isVisibleTo(dialog))
            self.assertFalse(dialog.boss_only.isChecked())
            self.assertEqual({c.key for c in dialog.graph.curves}, {'Group', '1', '2'})
        finally:
            win.close()

    def test_legend_choices_and_theme_survive(self):
        from PySide6.QtCore import Qt, QUrl
        win = self._main_window()
        try:
            win._on_fight_completed(_entry(players=3))
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:graph/'))
            dialog = win._graph_dialog
            dialog.legend.item(2).setCheckState(Qt.Unchecked)
            self.assertEqual({c.key for c in dialog.graph.curves}, {'Group', '1', '3'})
            # The same fight again keeps the choice; the player's hue stays theirs
            win.graph_action.trigger()
            self.assertEqual({c.key for c in dialog.graph.curves}, {'Group', '1', '3'})
            third = next(c for c in dialog.graph.curves if c.key == '3')
            self.assertEqual(third.color.name(), '#1baf7a')
            dialog.refresh(True)
            third = next(c for c in dialog.graph.curves if c.key == '3')
            self.assertEqual(third.color.name(), '#199e70')
        finally:
            win.close()

    def _graph_on(self, win, entry):
        """The graph opened from the pane's group dps figure on *entry*, at
        a height its legend scrolls in: (window, legend, the legend's bar)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication
        win._on_fight_completed(entry)
        win.history_list.select_fight(0)
        win.fight_view.anchorClicked.emit(QUrl('esolog:graph/'))
        dialog = win._graph_dialog
        dialog.resize(900, 300)
        QApplication.processEvents()
        bar = dialog.legend.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        return dialog, dialog.legend, bar

    def test_a_redraw_keeps_the_legends_line_and_scroll(self):
        """The legend is filled anew at each redraw (its fight changing in
        place, a theme switch, Hide names): the reader's line in it and its
        scroll stay where they were (issue #196). It went back to the top,
        with no line current. GROUP, the first line, is current with the
        legend scrolled to its end: making the line current again scrolls
        to it, so only the scroll put back brings the end back."""
        win = self._main_window()
        try:
            entry = _entry(players=16)
            dialog, legend, bar = self._graph_on(win, entry)
            legend.setCurrentRow(0)
            bar.setValue(bar.maximum())
            place = (legend.currentRow(), bar.value())
            self.assertEqual(place, (0, bar.maximum()))
            win._on_fight_updated(entry)
            self.assertEqual((legend.currentRow(), bar.value()), place)
            dialog.refresh(True)
            self.assertEqual((legend.currentRow(), bar.value()), place)
        finally:
            win.close()

    def test_a_redraw_leaves_a_line_current_but_not_selected_unselected(self):
        """The legend makes GROUP current without selecting it when it
        takes the focus, as the graph opens: a redraw makes the line current
        again and leaves it unselected, where it showed it selected though
        the reader never picked it (issue #196). A line they picked stays
        selected."""
        from PySide6.QtCore import QItemSelectionModel
        win = self._main_window()
        try:
            entry = _entry(players=16)
            dialog, legend, _bar = self._graph_on(win, entry)
            legend.setCurrentRow(5, QItemSelectionModel.NoUpdate)
            self.assertEqual(legend.selectedItems(), [])
            win._on_fight_updated(entry)
            self.assertEqual(legend.currentRow(), 5)
            self.assertEqual(legend.selectedItems(), [])
            legend.setCurrentRow(3)
            dialog.refresh(True)
            self.assertEqual(legend.currentRow(), 3)
            self.assertEqual(legend.selectedItems(), [legend.item(3)])
        finally:
            win.close()

    def test_a_line_the_fight_ranked_anew_is_scrolled_into_view(self):
        """The reader's line is near the legend's top, scrolled to the top,
        when the fight changing in place ranks that player last: the line is
        current on its new row and scrolled into view, where the old scroll
        put back left it out of sight (issue #196)."""
        from PySide6.QtCore import Qt
        win = self._main_window()
        try:
            entry = _entry(players=16)
            _dialog, legend, bar = self._graph_on(win, entry)
            legend.setCurrentRow(2)
            bar.setValue(0)
            key = legend.currentItem().data(Qt.UserRole)
            # The engine's new ranking: the player of row 2 last
            entry.players = entry.players[:1] + entry.players[2:] + entry.players[1:2]
            win._on_fight_updated(entry)
            self.assertEqual(legend.currentRow(), legend.count() - 1)
            self.assertEqual(legend.currentItem().data(Qt.UserRole), key)
            line = legend.visualItemRect(legend.currentItem())
            self.assertGreaterEqual(line.top(), 0)
            self.assertLessEqual(line.bottom(), legend.viewport().rect().bottom())
        finally:
            win.close()

    def test_a_line_ranked_a_row_up_keeps_the_legends_scroll(self):
        """The legend scrolled to its end, the reader's line near it, when
        the fight changing in place ranks that player a place up: the line
        is current on its new row, still in view at the reader's scroll,
        and the legend stays there (issue #196). Scrolled into view from
        the refilled legend's top, the line was brought only just into
        view, the rows the reader had scrolled to out of it."""
        from PySide6.QtCore import Qt
        win = self._main_window()
        try:
            entry = _entry(players=16)
            _dialog, legend, bar = self._graph_on(win, entry)
            legend.setCurrentRow(12)
            bar.setValue(bar.maximum())
            place = bar.value()
            key = legend.currentItem().data(Qt.UserRole)
            # The engine's new ranking: the players of rows 11 and 12 change places
            players = list(entry.players)
            players[10], players[11] = players[11], players[10]
            entry.players = players
            win._on_fight_updated(entry)
            self.assertEqual(legend.currentRow(), 11)
            self.assertEqual(legend.currentItem().data(Qt.UserRole), key)
            self.assertEqual(bar.value(), place)
            line = legend.visualItemRect(legend.currentItem())
            self.assertGreaterEqual(line.top(), 0)
            self.assertLessEqual(line.bottom(), legend.viewport().rect().bottom())
        finally:
            win.close()

    def test_a_line_scrolled_out_of_view_keeps_the_legends_scroll(self):
        """The reader has scrolled the legend away from their line, above it
        or below it, when the fight changing in place ranks that player a
        place up or down: the line is current on its new row, and the legend
        stays where the reader put it (issue #196). Scrolled into view, the
        line took the legend back to it."""
        from PySide6.QtCore import Qt
        # (the line's row, the legend scrolled to its end, the players swapped)
        for row, at_end, swap in ((1, True, (0, 1)), (16, False, (14, 15))):
            with self.subTest(row=row):
                win = self._main_window()
                try:
                    entry = _entry(players=16)
                    _dialog, legend, bar = self._graph_on(win, entry)
                    # Three rows or more to scroll, so a line moved a row stays out of view
                    self.assertGreaterEqual(bar.maximum(), 3)
                    legend.setCurrentRow(row)
                    bar.setValue(bar.maximum() if at_end else 0)
                    place = bar.value()
                    key = legend.currentItem().data(Qt.UserRole)
                    viewport = legend.viewport().rect()
                    self.assertFalse(legend.visualItemRect(legend.currentItem()).intersects(viewport))
                    players = list(entry.players)
                    players[swap[0]], players[swap[1]] = players[swap[1]], players[swap[0]]
                    entry.players = players
                    win._on_fight_updated(entry)
                    self.assertNotEqual(legend.currentRow(), row)
                    self.assertEqual(legend.currentItem().data(Qt.UserRole), key)
                    self.assertEqual(bar.value(), place)
                finally:
                    win.close()

    def test_the_colour_blind_switch_keeps_the_legends_line_and_scroll(self):
        """A Settings save that switches the graph to its colour-blind
        colours redraws the open graph with them, and the legend keeps its
        line and scroll as at any other redraw (issue #196). It went back to
        the top, with no line current."""
        win = self._main_window()
        try:
            dialog, legend, bar = self._graph_on(win, _entry(players=16))
            legend.setCurrentRow(2)
            bar.setValue(bar.maximum())
            place = (legend.currentRow(), bar.value())
            dialog.set_colorblind(not dialog.colorblind)
            self.assertEqual((legend.currentRow(), bar.value()), place)
        finally:
            win.close()

    def test_window_from_the_engines_own_record(self):
        from PySide6.QtCore import QUrl
        from build_session import fights
        win = self._main_window()
        try:
            entry = fights()[0]
            # Three hits a second into each of three buckets of the fight,
            # which began 10 ms before a whole log second
            self.assertEqual([[round(t, 2), d] for t, d in entry.damage_series['all']],
                             [[1.01, 90000], [11.01, 60000], [21.01, 30000]])
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:graph/'))
            dialog = win._graph_dialog
            self.assertEqual(dialog.legend.count(), 4)
            group = next(c for c in dialog.graph.curves if c.key == 'Group')
            self.assertEqual(group.points[-1][0], entry.duration_s)
            dialog.graph.grab()
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
