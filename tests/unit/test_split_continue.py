#!/usr/bin/env python3
"""Split files continued rather than copied (issue #85): a session split
again gains nothing, a split cut short is completed, a crash's partial line
is trimmed, an older split missing the lines its parser rejected is still
continued at its end, a copy at the session's end is removed against the
folder, two instances of the app on one folder, and every line of the
session reaching the split."""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from esolog_tail import (
    ESOLogAnalyzer,
    LogFileMonitor,
    LogSplitter,
    _handle_replay_log_splitting,
)

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'golden_fight.log'


def _lines():
    return FIXTURE.read_text(encoding='utf-8').splitlines()


def _feed(splitter, lines, parser=None, end=True):
    parser = parser or ESOLogAnalyzer().log_parser
    for line in lines:
        entry = parser.parse_line(line)
        if entry is not None:
            _handle_replay_log_splitting(splitter, entry, line)
    if end:
        splitter.end_encounter()


def _splits(folder: Path):
    return sorted(p.name for p in folder.iterdir() if p.suffix == '.log')


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SplitCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / 'splits'
        self.lines = _lines()
        # The complete split of the fixture's session, made on its own
        reference_dir = Path(self.tmp.name) / 'reference'
        _feed(LogSplitter(FIXTURE, split_dir=reference_dir), self.lines)
        (self.reference,) = [p for p in reference_dir.iterdir() if p.suffix == '.log']
        self.name = self.reference.name

    def tearDown(self):
        self.tmp.cleanup()

    def _split(self) -> Path:
        return self.folder / self.name

    def _cut(self) -> int:
        """A line index a little past the first BEGIN_COMBAT, where the
        split already carries its final name."""
        return next(i for i, line in enumerate(self.lines) if ',BEGIN_COMBAT' in line) + 6


class TestContinuedSplits(SplitCase):

    def test_a_session_split_again_gains_nothing_and_no_copy(self):
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)
        before = _digest(self._split())
        again = LogSplitter(FIXTURE, split_dir=self.folder)
        try:
            # Up to the session's END_LOG, which ends it (issue #225)
            self.assertTrue(self.lines[-1].endswith(',END_LOG'))
            _feed(again, self.lines[:-1], end=False)
            self.assertEqual(_splits(self.folder), [self.name])   # no -1 at any point
            self.assertTrue(again.continued)
            _feed(again, self.lines[-1:], end=False)
            self.assertIsNone(again.file_handle)                  # closed at END_LOG
            self.assertIsNone(again.current_split_file)
        finally:
            again.end_encounter()   # nothing left to close once END_LOG has
        self.assertEqual(_splits(self.folder), [self.name])
        self.assertEqual(_digest(self._split()), before)
        self.assertEqual(self._split().read_bytes(), self.reference.read_bytes())

    def test_a_split_cut_short_is_completed(self):
        first = LogSplitter(FIXTURE, split_dir=self.folder)
        _feed(first, self.lines[:self._cut()], end=False)
        first.close_for_waiting()                   # the app stopped mid-session
        short = self._split().stat().st_size
        self.assertLess(short, self.reference.stat().st_size)
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)   # the restart's replay
        self.assertEqual(_splits(self.folder), [self.name])
        self.assertEqual(self._split().read_bytes(), self.reference.read_bytes())

    def test_a_partial_line_from_a_crash_is_trimmed_first(self):
        cut = self._cut()
        first = LogSplitter(FIXTURE, split_dir=self.folder)
        _feed(first, self.lines[:cut], end=False)
        first.close_for_waiting()
        with open(self._split(), 'ab') as handle:
            handle.write(self.lines[cut][:15].encode('utf-8'))   # cut off mid-line
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)
        self.assertEqual(self._split().read_bytes(), self.reference.read_bytes())

    def test_an_older_split_missing_a_line_is_continued_at_its_end(self):
        """A split by a version that left the parser's rejects out is
        shorter than the lines fed again; the file's own last line marks
        where the new lines begin, so nothing is doubled or lost."""
        rows = self.reference.read_bytes().split(b'\r\n')
        kept, tail = rows[:-6], rows[-6:]            # the last five lines and '' missing
        del kept[10]                                 # and one line in the middle
        self.folder.mkdir()
        self._split().write_bytes(b'\r\n'.join(kept) + b'\r\n')
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)
        self.assertEqual(_splits(self.folder), [self.name])
        self.assertEqual(self._split().read_bytes(),
                         b'\r\n'.join(kept) + b'\r\n' + b'\r\n'.join(tail))

    def test_a_different_session_of_the_same_second_still_gets_a_suffix(self):
        self.folder.mkdir()
        other = self._split()
        other.write_bytes(b'5,BEGIN_LOG,1755729685851,15,"EU Megaserver","en","eso.live.11.1"\r\n'
                          b'something else entirely\r\n')
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)
        self.assertEqual(_splits(self.folder), [self.name.replace('.log', '-1.log'), self.name])

    def test_a_copy_at_the_sessions_end_is_judged_against_the_folder(self):
        _feed(LogSplitter(FIXTURE, split_dir=self.folder), self.lines)
        copy = self.folder / self.name.replace('.log', '-1.log')
        copy.write_bytes(self.reference.read_bytes())
        splitter = LogSplitter(FIXTURE, split_dir=self.folder)
        self.assertTrue(splitter._is_copy_of_another(copy))
        different = self.folder / self.name.replace('.log', '-2.log')
        different.write_bytes(self.reference.read_bytes()[:-3] + b'xyz')
        self.assertFalse(splitter._is_copy_of_another(different))
        self.assertTrue(splitter._is_copy_of_another(self._split()))   # the copy makes it one too


class TestOneSplitterPerFolder(SplitCase):

    def test_a_second_instance_writes_no_splits_while_the_first_lives(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            self.folder.mkdir()
            (self.folder / LogSplitter.LOCK_NAME).write_text(str(other.pid), encoding='utf-8')
            second = LogSplitter(FIXTURE, split_dir=self.folder)
            self.assertTrue(second.disabled)
            self.assertEqual(second.lock_holder, other.pid)
            _feed(second, self.lines)
            self.assertEqual(_splits(self.folder), [])
            second.release_lock()   # not its lock: left alone
            self.assertEqual((self.folder / LogSplitter.LOCK_NAME).read_text(encoding='utf-8'),
                             str(other.pid))
        finally:
            other.kill()
            other.wait()
        # The holder is gone: a stale lock is taken over
        third = LogSplitter(FIXTURE, split_dir=self.folder)
        self.assertFalse(third.disabled)
        self.assertEqual(third.lock_holder, os.getpid())
        _feed(third, self.lines)
        self.assertEqual(_splits(self.folder), [self.name])
        third.release_lock()
        self.assertFalse((self.folder / LogSplitter.LOCK_NAME).exists())

    def test_the_same_process_holds_its_own_lock(self):
        first = LogSplitter(FIXTURE, split_dir=self.folder)
        second = LogSplitter(FIXTURE, split_dir=self.folder)   # a Settings save rebuilt it
        self.assertFalse(first.disabled)
        self.assertFalse(second.disabled)

    def test_the_monitor_says_so(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            self.folder.mkdir()
            (self.folder / LogSplitter.LOCK_NAME).write_text(str(other.pid), encoding='utf-8')
            log = Path(self.tmp.name) / 'Encounter.log'
            log.write_text('', encoding='utf-8')
            analyzer = ESOLogAnalyzer()
            notices = []
            analyzer._notify = lambda kind, *args: notices.append((kind, args))
            LogFileMonitor(analyzer, log, tail_and_split=True, split_dir=self.folder)
            self.assertTrue(any(k == 'on_diagnostic' and 'another ESO Log Tail' in a[0]
                                for k, a in notices), notices)
        finally:
            other.kill()
            other.wait()


class TestEveryLineReachesTheSplit(unittest.TestCase):

    def test_a_line_the_parser_rejects_is_still_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            log.write_text('', encoding='utf-8')
            folder = Path(tmp) / 'splits'
            analyzer = ESOLogAnalyzer()
            monitor = LogFileMonitor(analyzer, log, tail_and_split=True, split_dir=folder)
            rejected = '16914,END_CAST,PLAYER_CANCELLED,7883445,269230'
            self.assertIsNone(analyzer.log_parser.parse_line(rejected))
            lines = _lines()
            combat = next(i for i, line in enumerate(lines) if ',BEGIN_COMBAT' in line)
            for line in lines[:combat + 3] + [rejected] + lines[combat + 3:]:
                monitor._process_one_line(line)
            monitor.log_splitter.end_encounter()
            (split,) = [p for p in folder.iterdir() if p.suffix == '.log']
            self.assertIn(rejected.encode('utf-8') + b'\r\n', split.read_bytes())


class TestSessionEndsAtEndLog(unittest.TestCase):
    """END_LOG closes the session's split (issue #225: until then the parser
    handed it over as ENDLOG, and the split stayed open until the next
    BEGIN_LOG or the app closed). Fed through the tail as the game writes
    it, CRLF lines, a session's split is still the session byte for byte,
    and a session after an END_LOG in the same file gets its own."""

    def _second_session(self):
        # The same session an hour later: another stamp, so another split
        first = _lines()
        epoch = first[0].split(',')[2]
        return [first[0].replace(epoch, str(int(epoch) + 3_600_000))] + first[1:]

    @staticmethod
    def _bytes(lines):
        return ''.join(line + '\r\n' for line in lines).encode('utf-8')

    def _monitor(self, tmp):
        log = Path(tmp) / 'Encounter.log'
        log.write_bytes(b'')
        monitor = LogFileMonitor(ESOLogAnalyzer(), log, tail_and_split=True,
                                 split_dir=Path(tmp) / 'splits')
        return log, monitor

    def _poll(self, log, monitor, lines):
        with open(log, 'ab') as f:
            f.write(self._bytes(lines))
        monitor._process_new_lines()

    def test_a_session_through_the_tail_is_its_split_closed_at_end_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log, monitor = self._monitor(tmp)
            try:
                lines = _lines()
                self._poll(log, monitor, lines)
                splitter = monitor.log_splitter
                self.assertIsNone(splitter.file_handle)          # closed at END_LOG
                self.assertIsNone(splitter.current_split_file)
                (split,) = [p for p in (Path(tmp) / 'splits').iterdir() if p.suffix == '.log']
                self.assertEqual(split.read_bytes(), self._bytes(lines))
            finally:
                monitor.log_splitter.cleanup()

    def test_a_session_after_an_end_log_in_the_same_file_gets_its_own_split(self):
        first, second = _lines(), self._second_session()
        for polls in ([first + second], [first, second]):
            with self.subTest(polls=len(polls)), tempfile.TemporaryDirectory() as tmp:
                log, monitor = self._monitor(tmp)
                try:
                    for lines in polls:
                        self._poll(log, monitor, lines)
                    splits = sorted(p for p in (Path(tmp) / 'splits').iterdir()
                                    if p.suffix == '.log')
                    self.assertEqual(len(splits), 2)
                    self.assertEqual([p.read_bytes() for p in splits],
                                     [self._bytes(first), self._bytes(second)])
                finally:
                    monitor.log_splitter.cleanup()


class TestSplitFlushedPerBatch(unittest.TestCase):
    """The splitter no longer flushes each line (issue #109): every batch the
    monitor reads must still be on disk when the batch ends, with the split
    file open, as a crash would leave it."""

    def test_each_poll_batch_is_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            log.write_bytes(b'')
            folder = Path(tmp) / 'splits'
            monitor = LogFileMonitor(ESOLogAnalyzer(), log, tail_and_split=True, split_dir=folder)
            try:
                lines = [line for line in _lines() if ',END_LOG' not in line]
                half = len(lines) // 2
                for batch in (lines[:half], lines[half:]):
                    with open(log, 'ab') as f:
                        f.write(''.join(line + '\n' for line in batch).encode('utf-8'))
                    monitor._process_new_lines()
                    (split,) = [p for p in folder.iterdir() if p.suffix == '.log']
                    self.assertTrue(split.read_bytes().endswith(batch[-1].encode('utf-8') + b'\r\n'))
            finally:
                monitor.log_splitter.cleanup()


if __name__ == '__main__':
    unittest.main()
