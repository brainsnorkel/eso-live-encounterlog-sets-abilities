#!/usr/bin/env python3
"""The engine worker is freed on the UI thread once its thread has ended,
and never waits for Python's garbage collector (issue #18, offscreen Qt).

Until this was fixed, the window asked the UI thread to pull the worker over
from the finished engine thread before deleting it. Qt refuses that ("Cannot
move to target thread": only an object's own thread may move it), so the
deletion was posted to a thread that would never run it, and the worker,
held in a reference cycle with its listener, was left to the garbage
collector, which frees things on whichever thread is allocating."""

import gc
import os
import tempfile
import threading
import time
import unittest
import weakref
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWorkerTeardown(unittest.TestCase):

    def setUp(self):
        from PySide6.QtCore import qInstallMessageHandler
        self.app = QApplication.instance() or QApplication([])
        self.tmp = tempfile.TemporaryDirectory()
        self.messages = []
        self._previous_handler = qInstallMessageHandler(
            lambda _kind, _context, text: self.messages.append(text))

    def tearDown(self):
        from PySide6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(self._previous_handler)
        self.tmp.cleanup()

    def _config(self):
        from app_config import AppConfig
        config = AppConfig(path=Path(self.tmp.name) / "config.json")
        config.set("log_path", str(Path(self.tmp.name) / "Encounter.log"))  # absent: the worker waits
        config.set("update.check_enabled", False)
        return config

    def _pump_until(self, condition, seconds=10):
        deadline = time.time() + seconds
        while not condition() and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        return condition()

    def test_a_closed_window_frees_its_worker_on_the_ui_thread(self):
        import shiboken6
        from PySide6.QtCore import QEvent, Qt

        from gui.main_window import MainWindow

        win = MainWindow(self._config())
        worker = win.worker
        freed_on = []
        worker.destroyed.connect(lambda *_: freed_on.append(threading.current_thread().name),
                                 Qt.DirectConnection)
        # The worker has started on its own thread and is waiting for the log.
        # Read through the window's own slot, connected before the thread
        # started: a connection made here can miss the signal, which the
        # engine emits within a millisecond of starting on a fast runner
        # (seen on the Linux runner once the window built more before it)
        def started():
            return win._last_placeholder.startswith("Waiting for Encounter.log")

        self.assertTrue(self._pump_until(started), "the engine thread never started")

        win.close()   # stops the engine thread and waits for it, as at exit
        self.assertFalse(win.worker_thread.isRunning())

        def gone():
            # A deletion posted while events are processed waits for the next round
            self.app.sendPostedEvents(None, QEvent.DeferredDelete)
            return not shiboken6.isValid(worker)

        self.assertTrue(self._pump_until(gone, seconds=5), "the worker was never deleted")
        self.assertEqual(freed_on, ["MainThread"])
        self.assertFalse([m for m in self.messages if "moveToThread" in m or "Cannot move" in m],
                         self.messages)
        win.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_a_worker_nobody_holds_is_freed_without_the_garbage_collector(self):
        from gui.engine_worker import EngineWorker
        worker = EngineWorker(self._config())
        ref = weakref.ref(worker)
        enabled = gc.isenabled()
        gc.disable()
        try:
            del worker
            self.assertIsNone(ref(), "the worker is held in a reference cycle")
        finally:
            if enabled:
                gc.enable()


if __name__ == "__main__":
    unittest.main()
