#!/usr/bin/env python3
"""The Settings dialog's fields, text and names: the fixes of issue #187
that do not depend on the layout.

Measured offscreen on 514ffef with the app's windows11 style: every field
stretched to the dialog's width (a spin box with a 122 px hint drawn 459 px
wide), the windows11 spin box at 18 pt clipped "10 seconds" to "10 secon",
Tab in the rules editor inserted a tab character and kept the focus so a
keyboard user could never reach Examples… or Save from it, and nine
controls were announced by their group's title. Save compared nothing and
replayed the session for every change, Reduce motion included; it now
compares the engine's settings (app_startup.engine_settings) before and
after the dialog writes the config.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QAccessible, QFont, QFontDatabase
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QApplication,
        QFormLayout,
        QGroupBox,
        QPushButton,
        QStyleFactory,
    )
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from app_config import AppConfig


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSettingsFields(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = AppConfig(path=Path(self.tmp.name) / "config.json")

    def _dialog(self, config=None):
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(config or self.config)
        self.addCleanup(QCoreApplication.sendPostedEvents, None, QEvent.DeferredDelete)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_only_a_field_that_asks_to_grow_takes_the_rows_width(self):
        dialog = self._dialog()
        forms = dialog.findChildren(QFormLayout)
        self.assertGreaterEqual(len(forms), 9)
        for form in forms:
            self.assertEqual(form.fieldGrowthPolicy(), QFormLayout.ExpandingFieldsGrow)
        dialog.show()
        dialog.resize(1200, dialog.height())
        self.app.processEvents()
        # A spin box and a drop-down at their hints; the path field and the
        # text size slider grow with the dialog
        for spin in (dialog.zip_weeks, dialog.threshold, dialog.recap_window):
            self.assertEqual(spin.width(), spin.sizeHint().width())
        self.assertEqual(dialog.update_channel.width(), dialog.update_channel.sizeHint().width())
        self.assertGreater(dialog.log_row.edit.width(), 600)
        self.assertGreater(dialog.text_size.width(), 400)

    def test_a_spin_box_at_its_hint_shows_its_widest_text_at_any_size(self):
        """The windows11 style's own hint is short by 25 px at 18 pt; the
        box adds the shortfall its style's edit-field rect reports."""
        dialog = self._dialog()
        available = QStyleFactory.keys()  # windows11 exists on Windows alone
        styles = ["windows11"] if "windows11" in available else []
        styles.append(self.app.style().objectName())
        dialog.show()
        for style in styles:
            for points in (9, 18):
                for spin in dialog.findChildren(QAbstractSpinBox):
                    spin.setStyle(QStyleFactory.create(style))
                    spin.setFont(QFont(self.app.font().family(), points))
                    spin.resize(spin.sizeHint())
                    self.app.processEvents()
                    room = spin.lineEdit().width() - 4
                    self.assertGreaterEqual(
                        room, spin._widest(),
                        f"{spin.accessibleName() or spin.suffix()} at {points} pt under {style}")

    def test_tab_leaves_the_rules_editor_without_inserting_one(self):
        dialog = self._dialog()
        self.assertTrue(dialog.rules_edit.tabChangesFocus())
        dialog.show()
        dialog.activateWindow()
        dialog.rules_edit.setFocus()
        self.app.processEvents()
        before = dialog.rules_edit.toPlainText()
        QTest.keyClick(dialog.rules_edit, Qt.Key_Tab)
        self.app.processEvents()
        self.assertEqual(dialog.rules_edit.toPlainText(), before)
        self.assertNotIn("\t", dialog.rules_edit.toPlainText())
        if self.app.focusWidget() is not None:  # offscreen windows do take focus
            self.assertIsNot(self.app.focusWidget(), dialog.rules_edit)

    def test_controls_in_a_row_are_named_for_themselves_not_their_group(self):
        from recycle_bin import TRASH_NAME
        dialog = self._dialog()
        expected = {
            dialog.zip_weeks: "Zip split logs older than, weeks",
            dialog.delete_weeks: f"Move split logs to the {TRASH_NAME} when older than, weeks",
            dialog.text_size: "Text size",
            dialog.rules_edit: "Tracked effect rules",
            dialog.force_of_nature_value: "Force of Nature per status effect",
            dialog.log_row.edit: "Log file",
            dialog.split_dir.edit: "Split folder",
            dialog.archive_dir.edit: "Archive folder",
        }
        for widget, name in expected.items():
            self.assertEqual(widget.accessibleName(), name)
            # What a screen reader is told, not only the property
            iface = QAccessible.queryAccessibleInterface(widget)
            self.assertIsNotNone(iface)
            self.assertEqual(iface.text(QAccessible.Text.Name), name)
        browse = [b for b in dialog.findChildren(QPushButton) if b.text() == "Browse…"]
        self.assertGreaterEqual(len(browse), 3)
        names = {b.accessibleName() for b in browse}
        self.assertEqual(len(names), len(browse), names)
        for name in names:
            self.assertTrue(name.startswith("Browse for the "), name)

    def test_help_is_read_with_its_control_and_the_warning_says_so(self):
        from gui.settings_dialog import DELETE_WARNING, RECAP_HELP, REPLAYS, RULES_HELP
        dialog = self._dialog()
        self.assertEqual(dialog.recap_window.accessibleDescription(), RECAP_HELP)
        self.assertEqual(dialog.rules_edit.accessibleDescription(), RULES_HELP)
        self.assertEqual(dialog.delete_original.accessibleDescription(), DELETE_WARNING)
        self.assertTrue(DELETE_WARNING.startswith("Warning:"))
        # The six settings the engine reads say so, in the same words
        for text in (RECAP_HELP, RULES_HELP, dialog.companion_accrual.accessibleDescription(),
                     dialog.log_row.edit.accessibleDescription(),
                     dialog.split_enabled.accessibleDescription()):
            self.assertTrue(text.endswith(REPLAYS), text)
        for group in dialog.findChildren(QGroupBox):
            self.assertNotIn("(", group.title())
        self.assertEqual(dialog.update_check.text(),
                         "Check for a newer release at startup and every 15 minutes")

    def test_the_retention_preview_shows_only_with_something_to_say(self):
        dialog = self._dialog()
        self.assertEqual(dialog.retention_preview.text(), "")
        self.assertFalse(dialog.retention_preview.isVisibleTo(dialog))
        dialog.zip_enabled.setChecked(True)
        self.assertIn("Would zip", dialog.retention_preview.text())
        self.assertTrue(dialog.retention_preview.isVisibleTo(dialog))
        # A consequence in the normal text colour, at the help's size
        self.assertNotIn("color", dialog.retention_preview.styleSheet())
        self.assertIn("pt;", dialog.retention_preview.styleSheet())

    def test_the_engines_settings_compare_equal_until_one_of_them_changes(self):
        from app_startup import engine_settings
        before = engine_settings(self.config)  # nothing saved yet: every key unset
        dialog = self._dialog()
        dialog.apply_to_config()
        self.assertEqual(engine_settings(self.config), before)
        dialog.reduce_motion.setChecked(True)
        dialog.threshold.setValue(2048)
        dialog.assume_backstabber.setChecked(True)
        dialog.apply_to_config()
        self.assertEqual(engine_settings(self.config), before)
        dialog.companion_accrual.setChecked(True)
        dialog.apply_to_config()
        self.assertNotEqual(engine_settings(self.config), before)
        # The rules as text: a comment is a change
        again = engine_settings(self.config)
        dialog.rules_edit.setPlainText(dialog.rules_edit.toPlainText() + "# mine\n")
        dialog.apply_to_config()
        self.assertNotEqual(engine_settings(self.config), again)

    def test_the_rules_editor_prefers_consolas(self):
        from gui import text_size
        if "Consolas" not in QFontDatabase.families():
            self.skipTest("Consolas not installed")
        self.assertEqual(text_size.fixed_font().family(), "Consolas")
        self.assertEqual(self._dialog().rules_edit.font().family(), "Consolas")


if __name__ == '__main__':
    unittest.main()
