#!/usr/bin/env python3
"""The Hide names switch (issue #72) through the widgets, offscreen: the
fight pane and its hover texts, the view serving the pixelated stand-ins,
the build, damage and death-recap windows, the dps graph's legend, the
timeline strip's hover and pop-up, the clipboard copy, the toolbar action
with Ctrl+H and the Settings box; and the character name beside the handle
and in the handle's hover (issue #71)."""

import os
import re
import tempfile
import unittest
from math import ceil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None
BLOCK = "▒"
FRIEND = "@" + BLOCK * 6  # '@friend' hidden
FRIEND_CHAR = BLOCK * 11  # 'Friend Char' hidden
IMG_SRC = re.compile(r'<img src="(mask:[a-z_]+\?color=[0-9a-f]{6}&amp;pt=[0-9.]+&amp;b=[01])"')


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _player(unit_id, name, character, is_local=False):
    return {"role": "D", "name": name, "character": character, "is_local": is_local,
            "class_abbr": "NB", "class_name": "Nightblade", "dps": 1000.0, "boss_dps": 0.0,
            "dmg_pct": 33.3, "boss_pct": 0.0, "h": 20000, "m": 30000, "s": 15000,
            "unit_id": unit_id, "sets": [], "all_sets": [], "skill_lines": [], "class_lines": [],
            "front_bar": [], "back_bar": [], "front_bar_slots": [], "back_bar_slots": []}


def _heal_row(source):
    return {"offset_ms": -1500, "kind": "heal", "result": "HOT_TICK", "source": source,
            "ability": "Radiating Regeneration", "ability_id": "1", "icon": "", "amount": 2500,
            "overflow": 0, "absorbed": 0, "shields": [], "health": 8913, "max_health": 18678}


def _entry(local="1"):
    """@me wrote the log; @friend and a player without a handle fought with
    them; @me died once, healed by @friend; a player the table does not
    list died too; @friend kept Major Force on @me."""
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = "Sharpfang"
    entry.zone_name = "Moonlit Cove"
    entry.timestamp = "2026-10-27 20:00:00"
    entry.duration_s = 100.0
    entry.dps_time_s = 92.0
    entry.group_dps = 3000.0
    entry.players = [_player("1", "@me", "My Char", local == "1"),
                     _player("2", "@friend", "Friend Char", local == "2"),
                     _player("3", "Nameless One", "Nameless One", local == "3")]
    entry.death_recaps = [
        {"unit_id": "1", "name": "@me", "time_ms": 54000, "killer": "Sharpfang",
         "ability": "Slap", "ability_id": "9", "icon": "", "max_health": 18678,
         "events": [_heal_row("@friend")]},
        {"unit_id": "77", "name": "@passerby", "time_ms": 61000, "killer": "Sharpfang",
         "ability": "Tremor", "ability_id": "9", "icon": "", "max_health": 18678, "events": []},
    ]
    entry.deaths = 2
    entry.buff_timeline = {"duration_ms": 100_000, "effects": {"Major Force": [
        {"start_ms": 10_000, "end_ms": 20_000, "source": "@friend", "target": "@me"},
        {"start_ms": 30_000, "end_ms": 40_000, "source": "@me", "target": "Nameless One"},
    ]}}
    return entry


def _mask(entry=None):
    from gui.name_mask import NameMask
    return NameMask.for_entry(entry or _entry(), True)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class HideNamesTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _window(self, hide=False):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        config.set("privacy.hide_names", hide)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        return win


class TestThePane(HideNamesTestCase):

    def test_rows_keep_the_logging_player_and_pixelate_the_others(self):
        from gui.fight_render import render_html
        html = render_html(_entry(), detailed=False, names=_mask())
        self.assertIn(">@me</a>", html)
        self.assertNotIn("@friend", html)
        self.assertNotIn("Nameless One", html)
        # Another player's handle: the @ as text, then the image, bold like
        # the row, in the pane's text colour at its size
        self.assertRegex(html, r'>@<img src="mask:[a-z_]+\?color=202124&amp;pt=9\.00&amp;b=1"')
        # The player without a handle: the image alone, with the space
        self.assertRegex(html, r'><img src="mask:[a-z_]+_[a-z_]+\?color=202124&amp;pt=9\.00&amp;b=1"')
        # The unlisted player who died: their chip label as blocks
        self.assertIn("Also died:", html)
        self.assertIn("@" + BLOCK * 8, html)
        self.assertNotIn("@passerby", html)
        # Off, every name is text
        plain = render_html(_entry(), detailed=False)
        for name in ("@me", "@friend", "Nameless One", "@passerby"):
            self.assertIn(name, plain)
        self.assertNotIn("mask:", plain)

    def test_the_pane_follows_the_text_colour_and_size_it_is_given(self):
        from gui.fight_render import render_html
        html = render_html(_entry(), detailed=False, names=_mask(), dark=True,
                           text_color="#abcdef", base_pt=10.5)
        self.assertRegex(html, r'>@<img src="mask:[a-z_]+\?color=abcdef&amp;pt=10\.50&amp;b=1"')

    def test_hover_texts_read_as_blocks(self):
        from gui.death_render import death_tooltips
        from gui.fight_render import (
            build_href,
            build_tooltips,
            damage_href,
            damage_tooltips,
        )
        entry, mask = _entry(), _mask()
        build = build_tooltips(entry, mask)
        self.assertIn("<b>@me</b><br>My Char<br>", build[build_href("1")])
        self.assertIn(f"<b>{FRIEND}</b><br>{FRIEND_CHAR}<br>", build[build_href("2")])
        damage = damage_tooltips(entry, mask)
        self.assertIn("<b>@me</b>", damage[damage_href("1")])
        self.assertIn(f"<b>{FRIEND}</b>", damage[damage_href("2")])
        deaths = death_tooltips(entry, mask)
        self.assertIn("<b>@me: 1 death</b>", deaths["esolog:deaths/1"])
        self.assertIn("<b>@" + BLOCK * 8 + ": 1 death</b>", deaths["esolog:deaths/77"])
        self.assertNotIn("@passerby", deaths["esolog:deaths/77"])

    def test_a_player_who_killed_is_hidden_like_any_player(self):
        """A PvP log: the killer is a handle, not a monster."""
        from gui.death_render import death_tooltips, render_death_recap_html
        entry = _entry()
        entry.death_recaps[0]["killer"] = "@enemyplayer"
        mask = _mask(entry)
        tip = death_tooltips(entry, mask)["esolog:deaths/1"]
        self.assertIn("Slap (@" + BLOCK * 11 + ")", tip)
        self.assertNotIn("@enemyplayer", tip)
        page = render_death_recap_html(entry, "1", names=mask)
        self.assertNotIn("@enemyplayer", page)
        self.assertRegex(page, r"from</span> @<img src=\"mask:[a-z_]+\?color=202124&amp;pt=9\.00&amp;b=0\"")
        # The same recap unmasked names the killer, as a monster is named
        self.assertIn("from</span> @enemyplayer", render_death_recap_html(entry, "1"))
        self.assertIn("from</span> Sharpfang", render_death_recap_html(_entry(), "1"))

    def test_the_copied_fight_hides_the_same_names(self):
        from gui.fight_render import render_plain_text
        text = render_plain_text(_entry(), names=_mask())
        self.assertIn("[D] @me", text)
        self.assertIn(f"[D] {FRIEND}", text)
        self.assertIn("[D] " + BLOCK * 12, text)
        self.assertNotIn("@friend", text)
        self.assertIn("@friend", render_plain_text(_entry()))

    def test_a_friends_log_keeps_the_friend(self):
        from gui.fight_render import render_html
        entry = _entry(local="2")
        html = render_html(entry, detailed=False, names=_mask(entry))
        self.assertIn(">@friend</a>", html)
        self.assertNotIn("@me", html)


class TestTheViewServesTheImages(HideNamesTestCase):

    def test_a_mask_url_is_answered_in_the_views_font_and_the_page_draws_it(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QFont, QFontMetricsF, QImage, QTextDocument

        from gui.fight_render import render_html
        from gui.fight_view import FightView
        view = FightView()
        image = view.loadResource(QTextDocument.ImageResource,
                                  QUrl("mask:abcdef?color=202124&pt=9.00&b=1"))
        font = QFont(view.font())
        font.setPointSizeF(9.0)
        font.setBold(True)
        self.assertEqual(image.width(), ceil(QFontMetricsF(font).horizontalAdvance("abcdef")))
        for bad in ("mask:abc?color=zzzzzz&pt=9&b=1", "mask:ABC?color=202124&pt=9&b=1",
                    "mask:abc?pt=9&b=1", "mask:abc?color=202124&pt=200&b=0"):
            served = view.loadResource(QTextDocument.ImageResource, QUrl(bad))
            self.assertFalse(isinstance(served, QImage) and not served.isNull(), bad)
        html = render_html(_entry(), detailed=False, names=_mask())
        view.resize(520, 160)
        view.show()
        view.setHtml(html)
        _app.processEvents()
        sources = IMG_SRC.findall(html)
        self.assertEqual(len(sources), 2)
        for src in sources:
            url = QUrl(src.replace("&amp;", "&"))
            served = QImage(view.document().resource(QTextDocument.ImageResource, url))
            self.assertFalse(served.isNull(), src)
            self.assertGreater(served.width(), 10)
        self.assertFalse(view.grab().isNull())


class TestTheWindows(HideNamesTestCase):

    def test_the_action_flips_the_pane_the_config_and_back(self):
        from app_config import AppConfig
        win = self._window()
        try:
            self.assertFalse(win.hide_names_action.isChecked())
            self.assertEqual(win.hide_names_action.shortcut().toString(), "Ctrl+H")
            # Flipping with nothing on screen is harmless
            win.hide_names_action.setChecked(True)
            win.hide_names_action.setChecked(False)
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            self.assertIn("@friend", win.fight_view.toPlainText())
            win.hide_names_action.setChecked(True)
            text = win.fight_view.toPlainText()
            self.assertIn("@me", text)
            self.assertNotIn("@friend", text)
            self.assertIn("mask:", win.fight_view.toHtml())
            self.assertTrue(AppConfig(path=win.config.path).get("privacy.hide_names"))
            # The hover text of the pane follows
            self.assertIn(FRIEND, win.fight_view._tooltips["esolog:build/2"])
            win.hide_names_action.setChecked(False)
            self.assertIn("@friend", win.fight_view.toPlainText())
            self.assertFalse(AppConfig(path=win.config.path).get("privacy.hide_names"))
        finally:
            win.close()

    def test_the_config_sets_the_action_at_start(self):
        win = self._window(hide=True)
        try:
            self.assertTrue(win.hide_names_action.isChecked())
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            self.assertNotIn("@friend", win.fight_view.toPlainText())
        finally:
            win.close()

    def test_settings_box_round_trips_and_sets_the_action(self):
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        win = self._window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            dialog = SettingsDialog(win.config, win)
            self.assertFalse(dialog.hide_names.isChecked())
            dialog.hide_names.setChecked(True)
            dialog.apply_to_config()
            win.config.save()
            dialog.deleteLater()
            self.assertTrue(AppConfig(path=win.config.path).get("privacy.hide_names"))
            win._apply_privacy_settings()
            self.assertTrue(win.hide_names_action.isChecked())
            self.assertNotIn("@friend", win.fight_view.toPlainText())
            again = SettingsDialog(win.config, win)
            self.assertTrue(again.hide_names.isChecked())
            again.deleteLater()
        finally:
            win.close()

    def test_open_windows_follow_a_flip(self):
        """The player window and the DPS graph tab follow a flip of the
        switch: the window's title, picker and page on screen at once
        (issue #196)."""
        from PySide6.QtCore import QUrl

        from gui.player_window import BUILD_TAB, DAMAGE_TAB, DEATHS_TAB
        win = self._window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            window = win._player_window
            self.assertEqual(window.windowTitle(), "Build – @friend (Friend Char)")
            self.assertIn("@friend", window.picker.currentText())
            win.graph_action.trigger()
            graph = win.dps_panel
            self.assertTrue(graph.legend.item(2).text().startswith("@friend"))

            win.hide_names_action.setChecked(True)
            self.assertEqual(window.windowTitle(), f"Build – {FRIEND} ({FRIEND_CHAR})")
            self.assertIn(FRIEND, window.picker.currentText())
            names = [window.picker.itemText(i) for i in range(window.picker.count())]
            self.assertFalse(any("@friend" in name for name in names), names)
            self.assertNotIn("@friend", window.view(BUILD_TAB).toPlainText())
            win.fight_view.anchorClicked.emit(QUrl("esolog:damage/2"))
            self.assertEqual(window.windowTitle(), f"Damage – {FRIEND}")
            self.assertNotIn("@friend", window.view(DAMAGE_TAB).toPlainText())
            # The logging player's own recap keeps their name; the heal
            # from the friend is hidden, the killing enemy is not
            win.fight_view.anchorClicked.emit(QUrl("esolog:deaths/1"))
            self.assertEqual(window.windowTitle(), "Death recap – @me")
            recap = window.view(DEATHS_TAB)
            recap_text = recap.toPlainText()
            self.assertNotIn("@friend", recap_text)
            self.assertIn("Sharpfang", recap_text)
            self.assertIn("mask:", recap.toHtml())
            self.assertTrue(graph.legend.item(1).text().startswith("@me"))
            self.assertTrue(graph.legend.item(2).text().startswith(FRIEND))
            self.assertTrue(graph.legend.item(3).text().startswith(BLOCK * 12))

            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            win.hide_names_action.setChecked(False)
            self.assertEqual(window.windowTitle(), "Build – @friend (Friend Char)")
            self.assertTrue(graph.legend.item(2).text().startswith("@friend"))
        finally:
            win.close()

    def test_a_closed_window_is_left_alone_and_reopens_with_the_mask(self):
        from PySide6.QtCore import QUrl
        win = self._window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            build = win._player_window
            build.hide()
            win.hide_names_action.setChecked(True)
            self.assertEqual(build.windowTitle(), "Build – @friend (Friend Char)")
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            self.assertEqual(build.windowTitle(), f"Build – {FRIEND} ({FRIEND_CHAR})")
        finally:
            win.close()

    def test_the_strips_popup_and_hover_hide_the_names(self):
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        win = self._window(hide=True)
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            strip = win.timeline_strip
            summary = strip.summary_html("Major Force")
            self.assertIn("@me", summary)
            self.assertIn(FRIEND, summary)
            self.assertIn(BLOCK * 12, summary)
            self.assertNotIn("@friend", summary)
            self.assertNotIn("Nameless One", summary)
            strip.show()
            row = strip._row_rect(0)
            pos = QPoint(int(strip._x_for_ms(15_000)), int(row.center().y()))
            self.assertTrue(strip.event(QHelpEvent(QEvent.ToolTip, pos, strip.mapToGlobal(pos))))
            tip = QToolTip.text()
            self.assertIn(f"{FRIEND} → @me", tip)
            self.assertNotIn("@friend", tip)
        finally:
            win.close()

    def test_each_window_keeps_a_mask_for_its_own_fight(self):
        """A window opened on one fight, another fight selected, then a
        flip: the window hides by its own fight's roster, where the pane
        hides by the fight on screen."""
        from PySide6.QtCore import QUrl
        win = self._window()
        try:
            first, second = _entry(), _entry(local="2")  # in the second, @friend wrote the log
            win._on_fight_completed(first)
            win._on_fight_completed(second)
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            build = win._player_window
            win.history_list.select_fight(1)
            win.hide_names_action.setChecked(True)
            pane = win.fight_view.toPlainText()
            self.assertIn("@friend", pane)
            self.assertNotIn("@me", pane)
            self.assertEqual(build.windowTitle(), f"Build – {FRIEND} ({FRIEND_CHAR})")
        finally:
            win.close()

    def test_the_strip_follows_a_flip(self):
        win = self._window()
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            strip = win.timeline_strip
            self.assertIn("@friend", strip.summary_html("Major Force"))
            win.hide_names_action.setChecked(True)
            self.assertNotIn("@friend", strip.summary_html("Major Force"))
            self.assertIn(FRIEND, strip.summary_html("Major Force"))
            win.hide_names_action.setChecked(False)
            self.assertIn("@friend", strip.summary_html("Major Force"))
        finally:
            win.close()

    def test_the_graphs_hover_names_the_curves_as_the_legend_does(self):
        series = [[2.0, 1000], [3.0, 1000], [4.0, 1000]]
        window = {"first_ms": 12000, "last_ms": 14000, "span_ms": 2000, "first_s": 2.0, "last_s": 4.0}
        entry = _entry()
        for p in entry.players:
            p["damage"] = {"total": 3000, "boss": 0, "window": window, "boss_window": window,
                           "abilities": [], "boss_abilities": [], "targets": [],
                           "series": series, "boss_series": []}
        entry.damage_series = {"all": series, "boss": [], "window": window, "boss_window": window}
        win = self._window(hide=True)
        try:
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            win.graph_action.trigger()
            hover = win.dps_panel.graph.tooltip_html(3)
            self.assertIn("@me", hover)
            self.assertIn(FRIEND, hover)
            self.assertNotIn("@friend", hover)
        finally:
            win.close()

    def test_another_players_recap_is_masked(self):
        from PySide6.QtCore import QUrl
        entry = _entry()
        entry.death_recaps.append(
            {"unit_id": "2", "name": "@friend", "time_ms": 70000, "killer": "Sharpfang",
             "ability": "Slap", "ability_id": "9", "icon": "", "max_health": 18678,
             "events": [_heal_row("@me")]})
        win = self._window(hide=True)
        try:
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:deaths/2"))
            from gui.player_window import DEATHS_TAB
            recap = win._player_window
            self.assertEqual(recap.windowTitle(), f"Death recap – {FRIEND}")
            self.assertIn(FRIEND, recap.picker.currentText())
            text = recap.view(DEATHS_TAB).toPlainText()
            self.assertNotIn("@friend", text)
            self.assertIn("@me", text)  # the logging player's heal
            self.assertIn("Sharpfang", text)
        finally:
            win.close()

    def test_a_window_redrawn_for_its_fight_hides_a_player_the_fight_gained(self):
        """The game cut the fight in two, and a player without a handle who
        joined in the second part healed @me before the death. The recap
        window open on the fight redraws with a mask made from the whole
        fight, so that player is hidden too (issue #196); the mask the
        window had knew only the first part's players."""
        from PySide6.QtCore import QUrl
        win = self._window(hide=True)
        try:
            entry = _entry()
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:deaths/1"))
            from gui.player_window import DEATHS_TAB
            page = win._player_window.view(DEATHS_TAB)
            self.assertEqual(page.toPlainText().count("Radiating Regeneration"), 1)
            # The whole fight's players and recaps, as the engine copies them
            # onto the entry the window holds
            entry.players = entry.players + [_player("4", "Late Comer", "Late Comer")]
            entry.death_recaps = [dict(entry.death_recaps[0],
                                       events=[_heal_row("Late Comer"), _heal_row("@friend")]),
                                  entry.death_recaps[1]]
            win._on_fight_updated(entry)
            _app.processEvents()  # the window draws a burst of updates once
            text = page.toPlainText()
            self.assertEqual(text.count("Radiating Regeneration"), 2)
            self.assertNotIn("Late Comer", text)
            self.assertNotIn("@friend", text)
            # The window's title names the player, the logging one, unhidden
            self.assertEqual(win._player_window.windowTitle(), "Death recap – @me")
        finally:
            win.close()

    def test_a_theme_flip_keeps_the_mask(self):
        from PySide6.QtCore import QUrl
        win = self._window(hide=True)
        try:
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            from gui.player_window import BUILD_TAB
            build = win._player_window
            build.refresh(True)
            self.assertEqual(build.windowTitle(), f"Build – {FRIEND} ({FRIEND_CHAR})")
            self.assertIn(FRIEND, build.picker.currentText())
            self.assertIn("#9aa0a6", build.view(BUILD_TAB).toHtml())  # the dark theme's muted colour
        finally:
            win.close()

    def test_ctrl_h_flips_the_switch_from_any_window(self):
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtTest import QTest
        win = self._window()
        try:
            # A shortcut needs an active window, which show() alone does
            # not give offscreen
            win.show()
            win.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(win, 2000))
            win._on_fight_completed(_entry())
            win.history_list.select_fight(0)
            QTest.keyClick(win, Qt.Key_H, Qt.ControlModifier)
            self.assertTrue(win.hide_names_action.isChecked())
            self.assertNotIn("@friend", win.fight_view.toPlainText())
            # From the build window too (the action's context is the application)
            win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
            build = win._player_window
            build.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(build, 2000))
            QTest.keyClick(build, Qt.Key_H, Qt.ControlModifier)
            self.assertFalse(win.hide_names_action.isChecked())
            self.assertIn("@friend", win.fight_view.toPlainText())
        finally:
            win.close()

    def test_the_pane_stays_where_it_was_scrolled(self):
        """The fight's page, scrolled half way down, is redrawn by the
        switch where the reader had it (FightView.keeping_place)."""
        win = self._window()
        try:
            win.show()
            # Flush the worker's queued startup signals: its "waiting for
            # log" page would replace the fight drawn below, and the page
            # scrolled would be that one
            _app.processEvents()
            # A long page in a short pane, whatever the platform's fonts and
            # window geometry make of the layout
            win.fight_view.setFixedHeight(120)
            entry = _entry()
            entry.players = entry.players * 20
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            view = win.fight_view
            # Qt lays a long document out lazily; asking for its size lays
            # it out whole and sizes the scrollbar (the Linux runner never
            # got there on its own)
            view.document().documentLayout().documentSize()
            _app.processEvents()
            self.assertIn("@friend", view.toPlainText())
            bar = view.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            bar.setValue(bar.maximum() // 2)
            kept = bar.value()
            self.assertGreater(kept, 0)
            win.hide_names_action.setChecked(True)
            view.document().documentLayout().documentSize()
            _app.processEvents()
            self.assertNotIn("@friend", view.toPlainText())
            self.assertEqual(bar.value(), kept)
        finally:
            win.close()

    def test_the_pane_redrawn_again_before_the_step_keeps_its_place(self):
        """The switch flipped and flipped back in the same pass, the bar
        moved between, before the step after layout has run: the pane comes
        back where the reader had it, the step's place, not where the bar
        was meanwhile (FightView.keeping_place, issue #196)."""
        win = self._window()
        try:
            win.show()
            # Flush the worker's queued startup signals (its "waiting for
            # log" page would replace the fight drawn below)
            _app.processEvents()
            win.fight_view.setFixedHeight(120)
            entry = _entry()
            entry.players = entry.players * 20
            win._on_fight_completed(entry)
            win.history_list.select_fight(0)
            view = win.fight_view
            view.document().documentLayout().documentSize()  # as above
            _app.processEvents()
            self.assertIn("@me", view.toPlainText())
            bar = view.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            kept = bar.maximum() // 2
            bar.setValue(kept)
            win.hide_names_action.setChecked(True)
            bar.setValue(0)
            win.hide_names_action.setChecked(False)
            _app.processEvents()
            self.assertEqual(bar.value(), kept)
        finally:
            win.close()

    def test_the_copy_follows_the_switch(self):
        from gui.fight_render import render_plain_text
        win = self._window(hide=True)
        try:
            win._on_fight_completed(_entry())
            entry = win._current_fights()[0]
            text = render_plain_text(entry, names=win._names_for(entry))
            self.assertIn(FRIEND, text)
            self.assertNotIn("@friend", text)
        finally:
            win.close()


class TestCharacterName(HideNamesTestCase):
    """Issue #71: the character name where the handle is."""

    def test_the_handles_hover_names_the_character(self):
        from gui.fight_render import build_href, build_tooltips
        tips = build_tooltips(_entry())
        self.assertIn("<b>@me</b><br>My Char<br>", tips[build_href("1")])
        # A player whose name is their character name is not doubled
        self.assertEqual(tips[build_href("3")].count("Nameless One"), 1)

    def test_the_build_window_puts_it_beside_the_handle(self):
        from gui.build_render import build_title, render_build_html
        entry = _entry()
        self.assertEqual(build_title(entry, "2"), "Build – @friend (Friend Char)")
        self.assertEqual(build_title(entry, "3"), "Build – Nameless One")
        html = render_build_html(entry, "2")
        self.assertIn(">@friend</span><span style='font-size:11.70pt'> · Friend Char</span>", html)
        self.assertEqual(html.count("Friend Char"), 1)
        # Hidden: both names are images at the title's size, the handle bold
        masked = render_build_html(entry, "2", names=_mask(entry))
        self.assertRegex(masked, r">@<img src=\"mask:[a-z_]+\?color=202124&amp;pt=11\.70&amp;b=1\"")
        self.assertRegex(masked, r"> · <img src=\"mask:[a-z_]+_[a-z_]+\?color=202124&amp;pt=11\.70&amp;b=0\"")
        self.assertNotIn("Friend Char", masked)

    def test_the_penetration_sections_casters_are_hidden(self):
        import html as html_lib

        from gui.build_render import _casters_text
        from gui.name_mask import NO_MASK
        casters = [{"name": "@friend", "pct": 80, "via": "Infused Inferno Staff"},
                   {"name": "@me", "pct": 20}]
        plain = _casters_text(casters, html_lib.escape, NO_MASK, "#5f6368", 7.65)
        self.assertIn("@friend", plain)
        masked = _casters_text(casters, html_lib.escape, _mask(), "#5f6368", 7.65)
        self.assertNotIn("@friend", masked)
        self.assertRegex(masked, r'^@<img src="mask:[a-z_]+\?color=5f6368&amp;pt=7\.65&amp;b=0"')
        self.assertIn("via Infused Inferno Staff</span> 80%, @me 20%", masked)


class TestPositionsWindowNames(HideNamesTestCase):
    """The positions window (issue #214): its own mask, made from the one
    the main window hands it and the locator's players; its table, hover,
    label and copy through it; a flip, a theme switch, and Ctrl+H from
    it."""

    def _fight(self):
        from tests.unit.test_positions_window_gui import session, split_and_states
        _log, _path, fights, states = split_and_states(self.root, session())
        return fights[0], states

    def _positions(self, hide, parent=None):
        from fight_reread import RereadEvent
        from gui.name_mask import NameMask
        from gui.positions_window import PositionsWindow
        from tests.unit.test_positions_window_gui import DEATH, DPS
        entry, states = self._fight()
        window = PositionsWindow(parent)
        if parent is None:
            self.addCleanup(window.deleteLater)
            self.addCleanup(window.close)
        window.open(entry, DEATH, DPS, dark=False, names=NameMask.for_entry(entry, hide))
        window.reread_done(RereadEvent("loaded", entry.locator, states))
        return window

    def _names_shown(self, window):
        from gui.positions_window import NAME_COL
        model = window.model
        return [model.data(model.index(row, NAME_COL)) for row in range(model.rowCount())]

    def test_the_table_title_and_copy_hide_every_other_player(self):
        window = self._positions(hide=True)
        shown = self._names_shown(window)
        self.assertIn("@tester", shown)  # the player writing the log
        self.assertIn("Test Boss", shown)  # an enemy, never hidden
        for name in ("@dps", "@healer", "@stranger", "Lead Leaver"):
            self.assertNotIn(name, shown)
        self.assertIn("@" + BLOCK * 3, shown)
        self.assertEqual(window.windowTitle(), "Positions – Test Boss")
        text = window.moment_text()
        for name in ("@dps", "@healer", "@stranger", "Lead Leaver", "Dps Char"):
            self.assertNotIn(name, text)

    def test_a_player_who_left_in_the_lead_in_is_hidden(self):
        """The player with no handle left before the pull: the engine's
        player_names never had them, the window's mask from the locator
        does."""
        from gui.name_mask import NameMask
        window = self._positions(hide=True)
        entry = window.entry
        self.assertFalse(NameMask.for_entry(entry, True).hides("Lead Leaver"))
        self.assertTrue(window.names().hides("Lead Leaver"))
        self.assertNotIn("Lead Leaver", self._names_shown(window))

    def test_the_selected_name_is_pixelated_on_the_canvas(self):
        from unittest import mock

        from gui import positions_canvas
        from gui.name_mask import stand_in
        window = self._positions(hide=True)
        window.resize(1000, 640)
        calls = []
        real = positions_canvas.mask_image

        def spy(word, *args, **kwargs):
            calls.append(word)
            return real(word, *args, **kwargs)
        with mock.patch.object(positions_canvas, "mask_image", spy):
            self.assertFalse(window.canvas.grab().isNull())
        self.assertEqual(calls, [stand_in("@dps")])
        self.assertNotIn("@dps", window.canvas.tooltip_text(
            next(u for u in window.scene().units if u.key == "3")))

    def test_a_flip_and_a_theme_switch(self):
        from gui.name_mask import NameMask
        window = self._positions(hide=False)
        self.assertIn("@dps", self._names_shown(window))
        window.refresh(False, names=NameMask.for_entry(window.entry, True))
        self.assertNotIn("@dps", self._names_shown(window))
        window.refresh(True)  # a theme switch keeps the mask
        self.assertNotIn("@dps", self._names_shown(window))
        window.refresh(True, names=NameMask.for_entry(window.entry, False))
        self.assertIn("@dps", self._names_shown(window))

    def test_ctrl_h_flips_the_switch_from_the_positions_window(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window()
        try:
            # The main window's action is an application shortcut once its
            # window has been shown, as in the app
            win.show()
            win.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(win, 2000))
            window = self._positions(hide=False, parent=win)
            window.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(window, 2000))
            QTest.keyClick(window, Qt.Key_H, Qt.ControlModifier)
            self.assertTrue(win.hide_names_action.isChecked())
            QTest.keyClick(window.table, Qt.Key_H, Qt.ControlModifier)
            self.assertFalse(win.hide_names_action.isChecked())
        finally:
            win.close()
