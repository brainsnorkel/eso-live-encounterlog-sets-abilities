"""A review on a thread of its own (issue #107): the window lists its fights,
Cancel stops it, a large log is outlined and the reader asked, and closing
the window during a review is safe."""

import threading
import time
import unittest
from unittest import mock

from tests.unit.test_gui import FIXTURE_LOG, HAVE_QT, GuiTestCase, _ensure_app


def _pump(app, until, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return False


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestReviewThread(GuiTestCase):

    def _window(self):
        from gui.main_window import MainWindow
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        return win

    def test_review_runs_off_the_ui_and_engine_threads(self):
        import review_load
        threads = []
        real = review_load.replay_log

        def recording(*args, **kwargs):
            threads.append(threading.current_thread().name)
            return real(*args, **kwargs)

        app = _ensure_app()
        win = self._window()
        try:
            with mock.patch.object(review_load, 'replay_log', recording):
                win.request_review.emit(str(FIXTURE_LOG), '')
                self.assertTrue(win.review_cancel_button.isVisibleTo(win))
                self.assertTrue(_pump(app, lambda: win._review_fights is not None))
            self.assertEqual(threads, ['review'])
            self.assertTrue(win._review_fights)
            self.assertEqual(win.history_list.count(), len(win._review_fights))
            self.assertFalse(win.review_cancel_button.isVisibleTo(win))
        finally:
            win.close()

    def test_cancel(self):
        import review_load
        started = threading.Event()

        def waits_for_cancel(analyzer, path, member=None, from_begin_log=-1,
                             progress=None, cancel=None):
            started.set()
            while not cancel.is_set():
                time.sleep(0.01)
            raise review_load.ReviewCancelled()

        app = _ensure_app()
        win = self._window()
        try:
            with mock.patch.object(review_load, 'replay_log', waits_for_cancel):
                win.request_review.emit(str(FIXTURE_LOG), '')
                self.assertTrue(started.wait(5))
                # A second review while one runs is refused
                win.request_review.emit(str(FIXTURE_LOG), '')
                self.assertIn('still loading', win.statusBar().currentMessage())
                win.review_cancel_button.click()
                self.assertTrue(_pump(app, lambda: 'cancelled' in win.statusBar().currentMessage()))
            self.assertIsNone(win._review_fights)
            self.assertFalse(win.review_cancel_button.isVisibleTo(win))
        finally:
            win.close()

    def test_large_log_offers_recent_sessions(self):
        from PySide6.QtWidgets import QMessageBox

        import review_load
        from app_startup import build_analyzer
        text = FIXTURE_LOG.read_text(encoding='utf-8')
        two = self.dir / 'two.log'
        two.write_text(text + text.replace('1755729685851', '1755816085851'), encoding='utf-8')
        calls, offered = [], []
        real = review_load.replay_log

        def recording(*args, **kwargs):
            calls.append(kwargs.get('from_begin_log', args[3] if len(args) > 3 else -1))
            return real(*args, **kwargs)

        def choose_last(box):
            offered.extend(b.text() for b in box.buttons())
            next(b for b in box.buttons() if b.text().startswith('Last')).click()

        app = _ensure_app()
        win = self._window()
        try:
            with mock.patch.object(review_load, 'LARGE_REVIEW_BYTES', 0), \
                    mock.patch.object(review_load, 'RECENT_FIGHTS', 1), \
                    mock.patch.object(review_load, 'replay_log', recording), \
                    mock.patch.object(QMessageBox, 'exec', choose_last):
                win.request_review.emit(str(two), '')
                self.assertTrue(_pump(app, lambda: win._review_fights is not None))
            self.assertEqual(calls, [1])  # the second session's BEGIN_LOG
            self.assertIn('Whole log', offered)
            self.assertTrue(any(t.startswith('Last 1 session, ') for t in offered), offered)
            whole = len(review_load.replay_log(build_analyzer(self.config, []), two)[1])
            self.assertEqual(len(win._review_fights), whole // 2)
        finally:
            win.close()

    def test_close_during_a_review(self):
        import review_load

        def slow(analyzer, path, member=None, from_begin_log=-1, progress=None, cancel=None):
            while not cancel.is_set():
                time.sleep(0.01)
            raise review_load.ReviewCancelled()

        app = _ensure_app()
        win = self._window()
        with mock.patch.object(review_load, 'replay_log', slow):
            win.request_review.emit(str(FIXTURE_LOG), '')
            self.assertTrue(win._review.running)
            win.close()
        self.assertFalse(win._review.running)
        for _ in range(5):
            app.processEvents()  # the queued 'cancelled' event reaches no slot


if __name__ == '__main__':
    unittest.main()
