"""Lasting problems reach the window (issue #111): a split file that cannot
be written, and the log failing to read poll after poll, are warnings shown
until they clear, not diagnostics that pass in four seconds."""

import tempfile
import unittest
from pathlib import Path

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory, LogFileMonitor
from tests.unit.test_gui import HAVE_QT, GuiTestCase, _ensure_app

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'golden_fight.log'


class _FullDisk:
    """A file handle whose writes fail, as on a full disk."""

    def write(self, text):
        raise OSError(28, 'No space left on device')

    def flush(self):
        pass

    def close(self):
        pass


class _FlushFails(_FullDisk):
    """Writes into the buffer go through; the flush to disk fails, which is
    how a full disk usually shows."""

    def write(self, text):
        pass

    def flush(self):
        raise OSError(28, 'No space left on device')


class TestSplitWriteWarning(unittest.TestCase):

    def test_a_failing_flush_warns_and_a_good_one_clears(self):
        lines = [line for line in FIXTURE.read_text(encoding='utf-8').splitlines()
                 if ',END_LOG' not in line]
        # After BEGIN_COMBAT, where the split is renamed and reopened (which
        # would replace the failing handle)
        third = next(i for i, line in enumerate(lines) if ',BEGIN_COMBAT' in line) + 3
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            log.write_bytes(b'')
            recorder = RecordingListener()
            analyzer = ESOLogAnalyzer()
            analyzer.fight_history = FightHistory()
            analyzer.add_listener(recorder)
            monitor = LogFileMonitor(analyzer, log, tail_and_split=True,
                                     split_dir=Path(tmp) / 'splits')
            splitter = monitor.log_splitter

            def batch(part):
                with open(log, 'a', encoding='utf-8') as f:
                    f.write(''.join(line + '\n' for line in part))
                monitor._process_new_lines()

            try:
                batch(lines[:third])  # the split file is open from here
                # ...and before END_COMBAT, which closes the split
                end = next(i for i, line in enumerate(lines) if ',END_COMBAT' in line)
                real, splitter.file_handle = splitter.file_handle, _FlushFails()
                batch(lines[third:end - 1])
                warnings = recorder.of_kind('warning')
                self.assertEqual(len(warnings), 1)
                self.assertIn('No space left on device', warnings[0][2])
                splitter.file_handle = real
                batch(lines[end - 1:])
                self.assertEqual(recorder.of_kind('warning')[-1], ('warning', 'split', None))
            finally:
                splitter.cleanup()

    def test_warned_once_and_cleared_when_writing_works_again(self):
        lines = [line for line in FIXTURE.read_text(encoding='utf-8').splitlines()
                 if ',END_LOG' not in line]
        third = len(lines) // 3
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            log.write_bytes(b'')
            recorder = RecordingListener()
            analyzer = ESOLogAnalyzer()
            analyzer.fight_history = FightHistory()
            analyzer.add_listener(recorder)
            monitor = LogFileMonitor(analyzer, log, tail_and_split=True,
                                     split_dir=Path(tmp) / 'splits')
            splitter = monitor.log_splitter
            try:
                def batch(part):
                    with open(log, 'a', encoding='utf-8') as f:
                        f.write(''.join(line + '\n' for line in part))
                    monitor._process_new_lines()

                batch(lines[:third])
                self.assertEqual(recorder.of_kind('warning'), [])
                real, splitter.file_handle = splitter.file_handle, _FullDisk()
                batch(lines[third:2 * third])
                batch(lines[2 * third:2 * third + 2])  # still failing: no second warning
                warnings = recorder.of_kind('warning')
                self.assertEqual(len(warnings), 1)
                self.assertEqual(warnings[0][1], 'split')
                self.assertIn('No space left on device', warnings[0][2])
                splitter.file_handle = real
                batch(lines[2 * third + 2:])
                self.assertEqual(recorder.of_kind('warning')[-1], ('warning', 'split', None))
            finally:
                splitter.cleanup()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestPollWarning(GuiTestCase):

    def test_three_failed_polls_warn_and_a_good_one_clears(self):
        worker = self._worker()
        warnings = []
        worker.warning.connect(lambda source, message: warnings.append((source, message)))

        class Monitor:
            log_file = FIXTURE
            last_position = FIXTURE.stat().st_size
            fail = True

            def _process_new_lines(self):
                if self.fail:
                    raise MemoryError()

        worker.monitor = Monitor()
        for _ in range(worker.POLL_FAILURES_WARN + 2):
            worker._poll()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0][0], 'poll')
        self.assertIn('keeps failing', warnings[0][1])
        worker.monitor.fail = False
        worker._poll()
        worker._poll()
        self.assertEqual(warnings[-1], ('poll', None))
        self.assertEqual(len(warnings), 2)

    def test_one_failed_poll_is_no_warning(self):
        worker = self._worker()
        warnings = []
        worker.warning.connect(lambda source, message: warnings.append((source, message)))

        class Monitor:
            log_file = FIXTURE
            last_position = FIXTURE.stat().st_size
            calls = 0

            def _process_new_lines(self):
                self.calls += 1
                if self.calls == 1:
                    raise OSError('busy')

        worker.monitor = Monitor()
        worker._poll()
        worker._poll()
        self.assertEqual(warnings, [])


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestWarningLabel(GuiTestCase):

    def test_label_shows_until_cleared(self):
        from gui.main_window import MainWindow
        _ensure_app()
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            self.assertFalse(win.warning_label.isVisibleTo(win))
            win._on_warning('split', 'Split file writing stopped: disk full')
            win._on_warning('poll', 'Reading the log keeps failing: MemoryError')
            self.assertTrue(win.warning_label.isVisibleTo(win))
            self.assertIn('disk full', win.warning_label.toolTip())
            self.assertIn('MemoryError', win.warning_label.toolTip())
            # A status message does not hide it (it is a permanent widget)
            win.statusBar().showMessage('something else', 4000)
            self.assertTrue(win.warning_label.isVisibleTo(win))
            win._on_warning('split', None)
            self.assertNotIn('disk full', win.warning_label.toolTip())
            win._on_warning('poll', None)
            self.assertFalse(win.warning_label.isVisibleTo(win))
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
