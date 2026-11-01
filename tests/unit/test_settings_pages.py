#!/usr/bin/env python3
"""The Settings dialog's six pages (issue #187, PR B).

One column of thirteen groups was 2,139 px tall at 100% text size, of
which a 1080p screen showed 43%, in the order the features were added.
The groups now sit on six pages in a tab bar, every group keeping its
title and every control its attribute name; the dialog opens at its
tallest page's size, each page is its own scroll area that takes no
focus, a Save with rule lines that will not parse turns to the rules and
asks, and the page the dialog was closed on is remembered within a run.
No pixel heights here: fonts differ between the runners.
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QGroupBox,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QSlider,
    )
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from app_config import AppConfig

# Every group and the page it sits on; Startup and Score banner exist on
# Windows alone
GROUP_PAGES = {
    "Encounter log": "General", "Startup": "General", "Updates": "General",
    "Death recaps": "Fights", "Companions": "Fights",
    "Penetration and critical damage": "Fights",
    "Fight history": "History", "Score banner": "History",
    "Display": "Display", "Privacy": "Display",
    "Per-encounter split files": "Files", "Automatic log archiving": "Files",
}

# A value for every key the dialog writes, none of them the default
NON_DEFAULT = {
    "log_path": "C:/logs/Encounter.log", "split.enabled": True, "split.dir": "C:/logs/splits",
    "split.zip_enabled": True, "split.zip_after_weeks": 6, "split.delete_enabled": True,
    "split.delete_after_weeks": 60, "archive.size_threshold_mb": 2048,
    "archive.dir": "C:/logs/archive", "archive.delete_original": True,
    "update.check_enabled": False, "update.channel": "beta", "privacy.hide_names": True,
    "display.text_scale": 130, "display.colorblind_graph": True, "display.reduce_motion": True,
    "companions.accrue_to_owner": True, "death_recap.window_s": 8, "pen_crit.piercing": False,
    "pen_crit.fighting_finesse": False, "pen_crit.backstabber": True,
    "pen_crit.force_of_nature": True, "pen_crit.force_of_nature_per_effect": 700,
    "pen_crit.cap": 9100, "tracking.rules": "Mine = 12345 on self\n",
}
if sys.platform == "win32":
    NON_DEFAULT.update({"banner.enabled": True, "banner.dir": "C:/logs/banners"})


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSettingsPages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from gui.settings_dialog import SettingsDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = AppConfig(path=Path(self.tmp.name) / "config.json")
        # The page memory is a class attribute: each test starts afresh
        SettingsDialog._last_page = 0
        self.addCleanup(setattr, SettingsDialog, "_last_page", 0)

    def _dialog(self, config=None, **kwargs):
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(config or self.config, **kwargs)
        self.addCleanup(QCoreApplication.sendPostedEvents, None, QEvent.DeferredDelete)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_six_pages_in_order_each_group_on_exactly_one(self):
        from gui.settings_dialog import PAGES
        dialog = self._dialog()
        self.assertEqual(PAGES, ("General", "Fights", "Tracked effects", "History", "Display",
                                 "Files"))
        self.assertEqual([dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
                         list(PAGES))
        found = {group.title(): dialog.page_of(group)
                 for group in dialog.findChildren(QGroupBox)}
        expected = {title: page for title, page in GROUP_PAGES.items()
                    if sys.platform == "win32" or title != "Score banner"}
        self.assertEqual(found, expected)
        # The Tracked effects page is the group: the editor sits on it unboxed
        self.assertEqual(dialog.page_of(dialog.rules_edit), "Tracked effects")
        self.assertEqual(dialog.page_of(dialog.examples_button), "Tracked effects")
        self.assertIsNone(next((g for g in dialog.findChildren(QGroupBox)
                                if g.isAncestorOf(dialog.rules_edit)), None))

    def test_no_page_scrolls_when_the_screen_allows(self):
        """The dialog is sized from its tallest and widest page, so every
        page's body fits its viewport and no bar shows, unless the screen
        capped the dialog (nine tenths of the 800 px offscreen screen):
        then only the capped pages may scroll. With real fonts the dialog
        is about 630 x 580 px at 100% and nothing is capped; the Windows
        runner's offscreen fallback font, with no font directory, is
        twice as wide as a real one and caps the width."""
        from gui.settings_dialog import PAGES
        dialog = self._dialog()
        dialog.show()
        self.app.processEvents()
        screen = self.app.primaryScreen().availableGeometry()
        capped_w = dialog.width() >= int(screen.width() * 0.9)
        capped_h = dialog.height() >= int(screen.height() * 0.9)
        for index, name in enumerate(PAGES):
            dialog.tabs.setCurrentIndex(index)
            self.app.processEvents()
            scroll = dialog._pages[name]
            body = scroll.widget()
            viewport = scroll.viewport()
            # A capped width can show a horizontal bar, which takes height
            # from the viewport
            hbar = scroll.horizontalScrollBar()
            taken = hbar.height() if hbar.isVisible() else 0
            if not capped_h:
                self.assertLessEqual(body.sizeHint().height(), viewport.height() + taken, name)
                if not taken:
                    self.assertFalse(scroll.verticalScrollBar().isVisible(), name)
            if not capped_w:
                self.assertLessEqual(body.sizeHint().width(), viewport.width(), name)
                self.assertFalse(scroll.horizontalScrollBar().isVisible(), name)
            # The editor takes the Tracked effects page's height
            if name == "Tracked effects":
                self.assertGreater(dialog.rules_edit.height(), viewport.height() // 2)
        # The height came from the tallest page: that page fills its viewport
        tallest = max((s.widget() for s in dialog._pages.values()),
                      key=lambda b: b.sizeHint().height())
        if not capped_h and not capped_w:
            scroll = dialog._pages[dialog.page_of(tallest)]
            self.assertGreaterEqual(tallest.sizeHint().height(), scroll.viewport().height() - 4)

    def test_page_up_and_down_scroll_the_page_showing(self):
        """The areas take no focus, so the dialog scrolls the page for
        PageUp and PageDown when the focused control does not take them."""
        from PySide6.QtTest import QTest

        from gui.settings_dialog import PAGES
        dialog = self._dialog()
        dialog.show()
        dialog.resize(dialog.width(), 260)  # a capped page
        dialog.tabs.setCurrentIndex(PAGES.index("Fights"))
        dialog.assume_piercing.setFocus()
        self.app.processEvents()
        bar = dialog._pages["Fights"].verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        self.assertEqual(bar.value(), 0)
        QTest.keyClick(dialog.assume_piercing, Qt.Key_PageDown)
        self.assertGreater(bar.value(), 0)
        QTest.keyClick(dialog.assume_piercing, Qt.Key_PageUp)
        self.assertEqual(bar.value(), 0)

    def test_the_scroll_areas_take_no_focus_and_the_width_follows_the_tab_bar(self):
        dialog = self._dialog()
        for name, scroll in dialog._pages.items():
            self.assertEqual(scroll.focusPolicy(), Qt.NoFocus, name)
        self.assertGreaterEqual(dialog.minimumWidth(), 560)
        self.assertGreaterEqual(dialog.minimumWidth(), dialog.tabs.tabBar().sizeHint().width())
        self.assertGreaterEqual(dialog.width(), dialog.minimumWidth())

    def test_every_config_key_round_trips_from_a_non_default_config(self):
        """No control was lost in the move: every key the dialog writes
        comes back as it went in."""
        for key, value in NON_DEFAULT.items():
            self.config.set(key, value)
        dialog = self._dialog()
        dialog.apply_to_config()
        for key, value in NON_DEFAULT.items():
            self.assertEqual(self.config.get(key), value, key)

    def test_every_control_on_the_pages_has_an_accessible_name(self):
        dialog = self._dialog()
        kinds = (QLineEdit, QAbstractSpinBox, QSlider, QPlainTextEdit, QComboBox, QCheckBox,
                 QPushButton)
        seen = 0
        for widget in (w for kind in kinds for w in dialog.findChildren(kind)):
            if isinstance(widget.parent(), QAbstractSpinBox):
                continue  # a spin box's inner line edit
            iface = QAccessible.queryAccessibleInterface(widget)
            self.assertIsNotNone(iface, widget)
            self.assertTrue(iface.text(QAccessible.Text.Name).strip(), (widget, widget.text()
                            if hasattr(widget, "text") else ""))
            seen += 1
        self.assertGreaterEqual(seen, 30)

    def test_general_has_content_where_startup_is_not_offered(self):
        """The Linux runner's case: the Startup group is hidden and the
        page still holds the log and the updates."""
        import autostart
        with patch.object(sys, "platform", "linux"), \
             patch.object(autostart, "autostart_command", return_value=None), \
             patch.object(autostart, "is_enabled", return_value=False):
            dialog = self._dialog()
            body = dialog._pages["General"].widget()
            shown = [g.title() for g in body.findChildren(QGroupBox) if not g.isHidden()]
            self.assertEqual(shown, ["Encounter log", "Updates"])
            self.assertGreater(body.sizeHint().height(), 0)

    def test_opens_on_general_then_on_the_page_it_was_closed_on(self):
        from gui.settings_dialog import PAGES, SettingsDialog
        first = self._dialog()
        self.assertEqual(first.tabs.currentIndex(), 0)
        first.tabs.setCurrentIndex(PAGES.index("History"))
        first.reject()
        self.assertEqual(SettingsDialog._last_page, PAGES.index("History"))
        second = self._dialog()
        self.assertEqual(second.tabs.currentIndex(), PAGES.index("History"))
        second.accept()
        # A caller can name the page; an unknown name falls back to the memory
        self.assertEqual(self._dialog(open_page="Files").tabs.currentIndex(),
                         PAGES.index("Files"))
        self.assertEqual(self._dialog(open_page="Nowhere").tabs.currentIndex(),
                         PAGES.index("History"))

    def test_save_with_rule_lines_that_do_not_parse_turns_to_the_rules_and_asks(self):
        from gui.settings_dialog import PAGES
        dialog = self._dialog()
        dialog.rules_edit.setPlainText("Fine = 12345 on self\nnot a rule\nnor this\n")
        asked = []
        with patch.object(type(dialog), "confirm_skipped_rules",
                          lambda self, errors: asked.append(list(errors)) or False):
            dialog.accept()
        self.assertEqual(len(asked), 1)
        self.assertEqual(len(asked[0]), 2)
        self.assertNotEqual(dialog.result(), QDialog.Accepted)  # Go back: still open
        # Save anyway, from the Display page: the page memory keeps Display,
        # not the Tracked effects page the question turned to
        dialog.tabs.setCurrentIndex(PAGES.index("Display"))
        with patch.object(type(dialog), "confirm_skipped_rules",
                          lambda self, errors: self.tabs.setCurrentIndex(
                              PAGES.index("Tracked effects")) or True):
            dialog.accept()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(type(dialog)._last_page, PAGES.index("Display"))
        # The real question switches the page and focuses the editor before asking
        other = self._dialog()
        other.rules_edit.setPlainText("broken\n")
        other.show()
        self.app.processEvents()
        with patch("gui.settings_dialog.QMessageBox.exec", return_value=0):
            other.confirm_skipped_rules(["line 1: broken"])
        self.assertEqual(other.tabs.currentIndex(), PAGES.index("Tracked effects"))
        self.assertIs(other.focusWidget(), other.rules_edit)

    def test_a_good_save_asks_nothing_about_the_rules(self):
        dialog = self._dialog()
        with patch.object(type(dialog), "confirm_skipped_rules",
                          lambda self, errors: self.fail("asked with no errors")):
            dialog.accept()
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_a_broken_line_the_dialog_opened_with_is_not_asked_about(self):
        """A rule line an older version saved broken: a Save from any page
        with the rules untouched goes through unasked."""
        self.config.set("tracking.rules", "Fine = 12345 on self\nnot a rule\n")
        dialog = self._dialog()
        self.assertEqual(len(dialog._rule_errors), 1)
        dialog.reduce_motion.setChecked(True)
        with patch.object(type(dialog), "confirm_skipped_rules",
                          lambda self, errors: self.fail("asked about an old line")):
            dialog.accept()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        # Edited this visit, the same broken line is asked about
        again = self._dialog()
        again.rules_edit.setPlainText(again.rules_edit.toPlainText() + "Mine = 1 on self\n")
        asked = []
        with patch.object(type(again), "confirm_skipped_rules",
                          lambda self, errors: asked.append(len(errors)) or True):
            again.accept()
        self.assertEqual(asked, [1])

    def test_the_capture_script_names_a_picture_per_page(self):
        from gui.settings_dialog import PAGES
        script = Path(__file__).resolve().parents[2] / "scripts" / "capture_screenshots.py"
        text = script.read_text(encoding="utf-8")
        old_picture = re.compile(r"(?<![-\w])settings\.png")  # the one tall picture, as a name
        for name in PAGES:
            self.assertIn(f"settings-{name.lower().replace(' ', '-')}.png", text)
        self.assertIsNone(old_picture.search(text))
        guide = script.parents[1] / "docs" / "user-guide.md"
        guide_text = guide.read_text(encoding="utf-8")
        for name in PAGES:
            self.assertIn(f"screencaps/settings-{name.lower().replace(' ', '-')}.png",
                          guide_text)
        self.assertIsNone(old_picture.search(guide_text))


if __name__ == '__main__':
    unittest.main()
