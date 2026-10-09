#!/usr/bin/env python3
"""The settings dialog is freed on the UI thread, deterministically.

Its path rows used to keep a reference back to the dialog, a cycle only
the garbage collector could free, and the collector runs on whichever
thread is allocating. After Save that was the engine thread replaying the
log, and freeing the dialog's Qt objects there aborted the app
(2026-10-09). The window now deletes the closed dialog itself, and nothing
in the dialog points back at it.
"""

import gc
import os
import tempfile
import unittest
import weakref
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QWidget
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from app_config import AppConfig


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSettingsDialogLifetime(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.tmp = tempfile.TemporaryDirectory()
        # A path with no file: defaults, and nothing is written
        cls.config = AppConfig(path=Path(cls.tmp.name) / "config.json")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_closed_dialog_is_freed_without_the_garbage_collector(self):
        from gui.settings_dialog import SettingsDialog
        parent = QWidget()
        gc.disable()
        try:
            dialog = SettingsDialog(self.config, parent)
            gone = [weakref.ref(dialog), weakref.ref(dialog.log_row),
                    weakref.ref(dialog.split_dir), weakref.ref(dialog.archive_dir)]
            # What the main window does once the dialog has closed
            dialog.deleteLater()
            del dialog
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertEqual([ref() for ref in gone], [None] * 4)
        finally:
            gc.enable()

    def test_tracked_effect_rules_are_checked_as_typed_and_saved(self):
        from gui.settings_dialog import SettingsDialog
        from effect_rules import DEFAULT_RULES
        dialog = SettingsDialog(self.config)
        # A fresh config shows the bundled examples, all of which parse
        self.assertEqual(dialog.rules_edit.toPlainText(), DEFAULT_RULES)
        self.assertEqual(dialog.rules_status.text(), "14 rules")
        dialog.rules_edit.setPlainText("Crux = 184220 on self stacks\nBad = 1 on mobs\n")
        self.assertTrue(dialog.rules_status.text().startswith("1 rule; skipped: line 2:"))
        dialog.apply_to_config()
        self.assertEqual(self.config.get("tracking.rules"), "Crux = 184220 on self stacks\nBad = 1 on mobs\n")
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_example_lines_are_appended_without_duplicates_and_reported(self):
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config)
        # The box already holds the fourteen defaults: adding one again adds nothing
        dialog.append_rules(["Crux = 184220 on self stacks"])
        self.assertTrue(dialog.rules_status.text().startswith("Nothing to add · 14 rules"))
        # A user's own rules stay; new lines go underneath
        dialog.rules_edit.setPlainText("Mine = 1 on boss")
        dialog.append_rules(["Crux = 184220 on self stacks", "Relequen = 107203 on boss stacks"])
        self.assertEqual(dialog.rules_edit.toPlainText(),
                         "Mine = 1 on boss\nCrux = 184220 on self stacks\nRelequen = 107203 on boss stacks\n")
        self.assertTrue(dialog.rules_status.text().startswith("2 rules added · 3 rules"))
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_a_path_rows_browse_dialog_belongs_to_the_settings_window(self):
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config)
        for row in (dialog.log_row, dialog.split_dir, dialog.archive_dir):
            self.assertIs(row.edit.window(), dialog)
            self.assertNotIn('_parent', vars(row))
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
