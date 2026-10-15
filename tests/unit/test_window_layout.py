#!/usr/bin/env python3
"""The main window remembers its placement and the history/fight split
across runs, in the app's own config file (offscreen Qt)."""

import json
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


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWindowLayoutRemembered(unittest.TestCase):

    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self):
        from app_config import AppConfig
        config = AppConfig(path=self.path)
        config.set("log_path", str(Path(self.tmp.name) / "Encounter.log"))
        config.set("update.check_enabled", False)
        return config

    def _window(self, config):
        """A main window whose engine thread is never started.

        Quitting the thread right after the window starts it races the
        worker's start slot: on a slow runner the slot may already be
        running when quit() lands, the worker is then destroyed on its own
        thread when the thread finishes, and the window's next round of
        events crashed the process (an access violation under PySide 6.12
        on GitHub's Windows runner, three of four runs on 2026-10-15, never
        in 28 local runs of the same versions). This test is about
        geometry, so the thread is replaced by one whose start() does
        nothing: no worker ever runs, nothing is torn down across threads."""
        from unittest import mock

        from gui.main_window import MainWindow
        from PySide6.QtCore import QThread

        class IdleThread(QThread):
            def start(self, *args):
                pass

        with mock.patch("gui.main_window.QThread", IdleThread):
            win = MainWindow(config)
        self.assertFalse(win.worker_thread.isRunning())
        return win

    def _discard(self, win):
        """Close a window and delete it before another is made."""
        from PySide6.QtCore import QEvent
        win.close()
        win.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_geometry_and_split_round_trip_through_config(self):
        first = self._window(self._config())
        first.show()
        first.move(40, 30)
        first.resize(600, 400)
        first._splitter.setSizes([180, 420])
        self.app.processEvents()
        want_pos = first.pos()
        want_size = first.size()
        want_sizes = first._splitter.sizes()
        self._discard(first)

        stored = json.loads(self.path.read_text(encoding="utf-8"))["window"]
        self.assertTrue(stored["geometry"])
        self.assertTrue(stored["splitter"])

        second = self._window(self._config())
        second.show()
        self.app.processEvents()
        try:
            self.assertEqual((second.pos(), second.size()), (want_pos, want_size))
            self.assertEqual(second._splitter.sizes(), want_sizes)
        finally:
            self._discard(second)

    def test_unreadable_saved_state_is_ignored(self):
        config = self._config()
        config.set("window.geometry", "not base64!")
        config.set("window.splitter", 42)
        win = self._window(config)
        try:
            self.assertEqual(win.size().width(), 1080)   # the default size
        finally:
            self._discard(win)


if __name__ == "__main__":
    unittest.main()
