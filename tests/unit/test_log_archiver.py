#!/usr/bin/env python3
"""Unit tests for the startup log archiver (log-archiving spec)."""

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import log_archiver
from app_config import AppConfig
from engine_events import RecordingListener
from log_archiver import FREE, HELD, UNKNOWN, LogArchiver, holder_check

EPOCH_MS = 1755729685851
BEGIN_LOG = f'5,BEGIN_LOG,{EPOCH_MS},15,"NA Megaserver","en","eso.live.11.1"'


class ArchiverTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / 'Encounter.log'
        self.config = AppConfig(path=self.dir / 'config.json')
        self.archiver = LogArchiver(self.config)
        self.recorder = RecordingListener()
        self.archiver.add_listener(self.recorder)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_log(self, extra_bytes=0):
        body = BEGIN_LOG + '\n3600000,END_COMBAT\n'
        if extra_bytes:
            body += 'x' * extra_bytes + '\n'
        self.log.write_text(body, encoding='utf-8')

    def _events(self, kind):
        return [e[1] for e in self.recorder.of_kind('archive_event')
                if e[1].kind == kind]

    def _hold_open_in_another_process(self):
        """A child process with the log open for append, as ESO would have."""
        child = subprocess.Popen(
            [sys.executable, '-c',
             'import sys, time\n'
             'handle = open(sys.argv[1], "a")\n'
             'print("ready", flush=True)\n'
             'time.sleep(60)\n',
             str(self.log)],
            stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        self.addCleanup(child.stdout.close)
        return child


class TestArchiveOperation(ArchiverTestCase):

    def test_dated_zip_created_and_verified(self):
        """Archive name derives from the latest log entry (spec: dated zip)."""
        self._write_log()
        result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)
        # EPOCH_MS + 3600000 ms formatted as local %y%m%d%H%M%S
        import datetime
        expected_stamp = datetime.datetime.fromtimestamp(
            (EPOCH_MS + 3600000) / 1000.0).strftime('%y%m%d%H%M%S')
        self.assertEqual(result.name, f'Encounter-{expected_stamp}.zip')
        with zipfile.ZipFile(result) as zf:
            self.assertIsNone(zf.testzip())
            self.assertEqual(zf.read('Encounter.log'),
                             self.log.read_bytes())
        completed = self._events('completed')
        self.assertEqual(len(completed), 1)
        self.assertFalse(completed[0].original_deleted)

    def test_collision_suffixes(self):
        self._write_log()
        first = self.archiver.archive(self.log)
        second = self.archiver.archive(self.log)
        self.assertNotEqual(first, second)
        self.assertTrue(second.stem.endswith('-1'))

    def test_progress_events_stream(self):
        # ~9 MB -> 3 chunks at 4 MB
        self._write_log(extra_bytes=9 * 1024 * 1024)
        self.archiver.archive(self.log)
        progress = self._events('progress')
        self.assertGreaterEqual(len(progress), 3)
        self.assertEqual(progress[-1].done_bytes, progress[-1].total_bytes)
        dones = [p.done_bytes for p in progress]
        self.assertEqual(dones, sorted(dones))
        self.assertEqual(len(self._events('started')), 1)

    def test_default_keeps_original(self):
        """Spec scenario: default keep."""
        self._write_log()
        self.archiver.archive(self.log)
        self.assertTrue(self.log.exists())

    def test_opt_in_delete_removes_original_after_verify(self):
        """Spec scenario: opt-in delete."""
        self._write_log()
        self.config.set('archive.delete_original', True)
        result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)
        self.assertFalse(self.log.exists())
        completed = self._events('completed')
        self.assertTrue(completed[0].original_deleted)
        # Marker resets so a fresh log starts from zero
        self.assertEqual(self.config.get('archive.size_at_last_archive'), 0)

    def test_verification_failure_keeps_original_and_removes_zip(self):
        """Spec scenario: verification failure."""
        self._write_log()
        self.config.set('archive.delete_original', True)  # must still keep
        self.archiver._verify = lambda *a, **k: False
        result = self.archiver.archive(self.log)
        self.assertIsNone(result)
        self.assertTrue(self.log.exists())
        self.assertEqual(list(self.dir.glob('*.zip')), [])
        failed = self._events('failed')
        self.assertEqual(len(failed), 1)
        self.assertIn('verification', failed[0].reason)

    def test_missing_log_skips(self):
        result = self.archiver.archive(self.dir / 'nope.log')
        self.assertIsNone(result)
        self.assertEqual(len(self._events('skipped')), 1)

    def test_custom_archive_dir(self):
        self._write_log()
        target_dir = self.dir / 'archives'
        self.config.set('archive.dir', str(target_dir))
        result = self.archiver.archive(self.log)
        self.assertEqual(result.parent, target_dir)


@unittest.skipUnless(sys.platform == 'win32', 'exclusive sharing is Windows-only')
class TestInUseGuard(ArchiverTestCase):

    def test_skip_when_file_held_open(self):
        """Spec scenarios: ESO has the file open / manual archive while ESO runs."""
        self._write_log()
        held = open(self.log, 'a', encoding='utf-8')  # simulates ESO's writer handle
        try:
            result = self.archiver.archive(self.log)
        finally:
            held.close()
        self.assertIsNone(result)
        skipped = self._events('skipped')
        self.assertEqual(len(skipped), 1)
        self.assertIn('in use', skipped[0].reason)
        self.assertEqual(list(self.dir.glob('*.zip')), [])

    def test_archive_proceeds_when_file_free(self):
        """Spec scenario: file free at startup; handle released afterwards."""
        self._write_log()
        result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)
        # Exclusive access must be released after completion
        with open(self.log, 'a', encoding='utf-8'):
            pass


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux /proc holder scan')
class TestInUseGuardLinux(ArchiverTestCase):

    def test_skip_when_another_process_holds_the_log(self):
        self._write_log()
        self.config.set('archive.delete_original', True)  # must still keep
        self._hold_open_in_another_process()
        result = self.archiver.archive(self.log)
        self.assertIsNone(result)
        skipped = self._events('skipped')
        self.assertEqual(len(skipped), 1)
        self.assertIn('in use', skipped[0].reason)
        self.assertTrue(self.log.exists())
        self.assertEqual(list(self.dir.glob('*.zip')), [])

    def test_archive_proceeds_once_the_holder_is_gone(self):
        self._write_log()
        child = self._hold_open_in_another_process()
        child.kill()
        child.wait()
        self.assertIsNotNone(self.archiver.archive(self.log))

    def test_own_handles_do_not_count(self):
        """The app's own open handle (the tail) must not block an archive."""
        self._write_log()
        with open(self.log, 'rb'):
            self.assertIsNotNone(self.archiver.archive(self.log))


class TestHolderCheck(unittest.TestCase):
    """holder_check reads lsof's answer into held, free or unknown. lsof is
    patched, so these run on every platform; only "free" lets macOS delete
    the log, so everything that is not plainly free must come out unknown."""

    def _answer(self, returncode=0, stdout='', stderr=''):
        done = subprocess.CompletedProcess(['lsof'], returncode, stdout, stderr)
        with mock.patch.object(log_archiver.subprocess, 'run', return_value=done) as run:
            answer = holder_check(Path('/logs/Encounter.log'))
        self.run_call = run.call_args
        return answer

    def test_another_process_is_held(self):
        self.assertEqual(self._answer(0, '4242\n'), HELD)

    def test_another_process_beside_our_own_is_held(self):
        self.assertEqual(self._answer(0, f'{os.getpid()}\n4242\n'), HELD)

    def test_our_own_id_only_is_free(self):
        """The app's tail and the archive's read handle are this process."""
        self.assertEqual(self._answer(0, f'{os.getpid()}\n'), FREE)

    def test_exit_1_with_both_streams_empty_is_free(self):
        """What lsof gives for a file nobody has open."""
        self.assertEqual(self._answer(1), FREE)

    def test_exit_1_with_a_message_on_stderr_is_unknown(self):
        self.assertEqual(
            self._answer(1, stderr='lsof: status error on /logs/Encounter.log: '
                                   'No such file or directory\n'), UNKNOWN)

    def test_our_own_id_with_a_message_on_stderr_is_unknown(self):
        """A warning may mean lsof could not look at every process."""
        self.assertEqual(self._answer(0, f'{os.getpid()}\n', "lsof: WARNING: can't stat()\n"),
                         UNKNOWN)

    def test_an_exit_code_that_fits_neither_answer_is_unknown(self):
        self.assertEqual(self._answer(0), UNKNOWN)
        self.assertEqual(self._answer(1, f'{os.getpid()}\n'), UNKNOWN)
        self.assertEqual(self._answer(2), UNKNOWN)

    def test_output_that_is_not_process_ids_is_unknown(self):
        self.assertEqual(self._answer(0, 'COMMAND PID USER\n'), UNKNOWN)

    def test_a_missing_lsof_is_unknown(self):
        with mock.patch.object(log_archiver.subprocess, 'run',
                               side_effect=FileNotFoundError('/usr/sbin/lsof')):
            self.assertEqual(holder_check(Path('/logs/Encounter.log')), UNKNOWN)

    def test_a_timeout_is_unknown(self):
        with mock.patch.object(log_archiver.subprocess, 'run',
                               side_effect=subprocess.TimeoutExpired('lsof', 5)):
            self.assertEqual(holder_check(Path('/logs/Encounter.log')), UNKNOWN)

    def test_lsof_is_asked_for_ids_of_this_path_with_a_time_limit(self):
        """By its full path (the app's PATH is not a shell's), with its
        warnings on (-t alone turns them off, and a thing lsof could not look
        into would read as free), after "--" so a path that starts with a
        dash is not read as an option."""
        self._answer(1)
        args, kwargs = self.run_call
        self.assertEqual(args[0],
                         ['/usr/sbin/lsof', '-t', '+w', '--', str(Path('/logs/Encounter.log'))])
        self.assertEqual(kwargs['timeout'], 5)


@unittest.skipUnless(sys.platform == 'darwin', 'macOS lsof holder check')
class TestInUseGuardMac(ArchiverTestCase):
    """The Linux scenarios against the real lsof, and the second check at the
    moment of the delete."""

    def test_skip_when_another_process_holds_the_log(self):
        self._write_log()
        self.config.set('archive.delete_original', True)  # must still keep
        self._hold_open_in_another_process()
        result = self.archiver.archive(self.log)
        self.assertIsNone(result)
        skipped = self._events('skipped')
        self.assertEqual(len(skipped), 1)
        self.assertIn('in use', skipped[0].reason)
        self.assertTrue(self.log.exists())
        self.assertEqual(list(self.dir.glob('*.zip')), [])

    def test_archive_proceeds_once_the_holder_is_gone(self):
        self._write_log()
        child = self._hold_open_in_another_process()
        child.kill()
        child.wait()
        self.assertIsNotNone(self.archiver.archive(self.log))

    def test_own_handles_do_not_count(self):
        """The app's own open handle (the tail) must not block an archive,
        nor the delete: the archive's own read handle is open at that check."""
        self._write_log()
        self.config.set('archive.delete_original', True)
        with open(self.log, 'rb'):
            self.assertIsNotNone(self.archiver.archive(self.log))
        completed = self._events('completed')
        self.assertTrue(completed[0].original_deleted)
        self.assertEqual(completed[0].kept_reason, '')
        self.assertFalse(self.log.exists())

    def test_a_holder_that_arrives_during_the_zip_keeps_the_original(self):
        """The game opens the log after the first check and writes nothing
        while it is zipped, so the size verification passes: only the second
        check, against the real lsof, stands between it and the delete."""
        self._write_log()
        self.config.set('archive.delete_original', True)
        real_verify = self.archiver._verify

        def verify_then_the_game_starts(*args):
            verified = real_verify(*args)
            self._hold_open_in_another_process()
            return verified

        self.archiver._verify = verify_then_the_game_starts
        result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)
        self.assertTrue(result.exists())
        self.assertTrue(self.log.exists())
        completed = self._events('completed')
        self.assertFalse(completed[0].original_deleted)
        self.assertEqual(completed[0].kept_reason, 'the log is in use')


@unittest.skipIf(sys.platform == 'win32', 'the POSIX handle; Windows denies sharing instead')
class TestMacDeleteGate(ArchiverTestCase):
    """What macOS does with holder_check's answers, at the start and at the
    moment of the delete. The answers are given, not asked of lsof, and the
    platform is said to be macOS, so Linux runs these too: CI has no Mac."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(log_archiver.sys, 'platform', 'darwin')
        self.addCleanup(patcher.stop)
        patcher.start()

    def _answers(self, *answers):
        """holder_check gives *answers* in turn: the start, then the delete."""
        patcher = mock.patch.object(log_archiver, 'holder_check', side_effect=list(answers))
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_a_holder_at_the_start_skips_the_archive(self):
        self._write_log()
        self.config.set('archive.delete_original', True)
        check = self._answers(HELD)
        self.assertIsNone(self.archiver.archive(self.log))
        self.assertEqual(check.call_count, 1)
        self.assertIn('in use', self._events('skipped')[0].reason)
        self.assertTrue(self.log.exists())
        self.assertEqual(list(self.dir.glob('*.zip')), [])

    def test_a_holder_at_delete_time_keeps_the_original(self):
        self._write_log()
        self.config.set('archive.delete_original', True)
        self._answers(FREE, HELD)
        result = self.archiver.archive(self.log)
        self.assertTrue(result.exists())
        self.assertTrue(self.log.exists())
        completed = self._events('completed')
        self.assertFalse(completed[0].original_deleted)
        self.assertEqual(completed[0].kept_reason, 'the log is in use')

    def test_the_log_is_deleted_straight_after_the_answer(self):
        """Not at the handle's close, which comes after the config's save and
        the listeners: when they hear of the archive the log is gone."""
        self._write_log()
        self.config.set('archive.delete_original', True)
        self._answers(FREE, FREE)
        there = []

        class AtTheEvent:
            def on_archive_event(listener, event):
                if event.kind == 'completed':
                    there.append(self.log.exists())

        self.archiver.add_listener(AtTheEvent())
        self.assertIsNotNone(self.archiver.archive(self.log))
        self.assertEqual(there, [False])

    def test_a_log_that_cannot_be_deleted_is_said_to_be_kept(self):
        self._write_log()
        self.config.set('archive.delete_original', True)
        self._answers(FREE, FREE)
        with mock.patch.object(Path, 'unlink', side_effect=PermissionError('no')):
            result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)
        self.assertTrue(self.log.exists())
        completed = self._events('completed')
        self.assertFalse(completed[0].original_deleted)
        self.assertEqual(completed[0].kept_reason, 'the log could not be deleted')
        self.assertEqual(self.config.get('archive.size_at_last_archive'),
                         self.log.stat().st_size)

    def test_the_check_failing_at_delete_time_keeps_the_original(self):
        self._write_log()
        self.config.set('archive.delete_original', True)
        check = self._answers(FREE, UNKNOWN)
        result = self.archiver.archive(self.log)
        self.assertEqual(check.call_count, 2)
        self.assertIsNotNone(result)
        self.assertTrue(result.exists())  # the zip is kept
        self.assertTrue(self.log.exists())
        completed = self._events('completed')
        self.assertFalse(completed[0].original_deleted)
        self.assertEqual(completed[0].kept_reason,
                         'could not check whether the log is in use')
        # The log is still there, so the marker is its size, as for a kept one
        self.assertEqual(self.config.get('archive.size_at_last_archive'),
                         self.log.stat().st_size)

    def test_the_check_failing_at_the_start_still_makes_the_zip(self):
        """Unknown is not held: the zip is made, and the delete asks again."""
        self._write_log()
        self.config.set('archive.delete_original', True)
        self._answers(UNKNOWN, FREE)
        self.assertIsNotNone(self.archiver.archive(self.log))
        completed = self._events('completed')
        self.assertTrue(completed[0].original_deleted)
        self.assertFalse(self.log.exists())

    def test_no_second_check_when_the_original_is_kept_anyway(self):
        self._write_log()
        check = self._answers(FREE)
        self.assertIsNotNone(self.archiver.archive(self.log))
        self.assertEqual(check.call_count, 1)
        completed = self._events('completed')
        self.assertEqual(completed[0].kept_reason, '')
        self.assertTrue(self.log.exists())


class TestTriggerAndMarker(ArchiverTestCase):

    def test_below_threshold_no_archive(self):
        """Spec scenario: below threshold."""
        self._write_log()  # tiny file, default 1024 MB threshold
        result = self.archiver.auto_archive_if_needed(self.log)
        self.assertIsNone(result)
        self.assertEqual(self.recorder.of_kind('archive_event'), [])

    def test_threshold_exceeded_triggers(self):
        """Spec scenario: threshold exceeded at startup."""
        self.config.set('archive.size_threshold_mb', 0)  # any growth triggers
        self._write_log(extra_bytes=1024)
        result = self.archiver.auto_archive_if_needed(self.log)
        self.assertIsNotNone(result)

    def test_archived_but_kept_does_not_retrigger(self):
        """Spec scenario: archived but kept."""
        self.config.set('archive.size_threshold_mb', 0)
        self._write_log(extra_bytes=1024)
        first = self.archiver.auto_archive_if_needed(self.log)
        self.assertIsNotNone(first)
        # No growth since the marker: no new archive
        second = self.archiver.auto_archive_if_needed(self.log)
        self.assertIsNone(second)

    def test_growth_after_archive_retriggers(self):
        self.config.set('archive.size_threshold_mb', 0)
        self._write_log(extra_bytes=1024)
        self.archiver.auto_archive_if_needed(self.log)
        with open(self.log, 'a', encoding='utf-8') as f:
            f.write('7200000,BEGIN_COMBAT\n')
        result = self.archiver.auto_archive_if_needed(self.log)
        self.assertIsNotNone(result)

    def test_log_rotation_resets_marker(self):
        """Spec scenario: log rotated."""
        self.config.set('archive.size_threshold_mb', 0)
        self._write_log(extra_bytes=4096)
        self.archiver.auto_archive_if_needed(self.log)
        self.assertGreater(self.config.get('archive.size_at_last_archive'), 0)
        # User deletes the log; ESO writes a fresh, smaller one
        self.log.unlink()
        self._write_log()
        self.archiver.growth_since_last_archive(self.log)
        self.assertEqual(self.config.get('archive.size_at_last_archive'), 0)

    def test_marker_persists_across_instances(self):
        self.config.set('archive.size_threshold_mb', 0)
        self._write_log(extra_bytes=1024)
        self.archiver.auto_archive_if_needed(self.log)
        fresh_config = AppConfig(path=self.config.path)
        fresh_archiver = LogArchiver(fresh_config)
        self.assertIsNone(fresh_archiver.auto_archive_if_needed(self.log))

    def test_manual_archive_ignores_threshold(self):
        """Spec scenario: manual archive below threshold."""
        self._write_log()  # far below the default threshold
        result = self.archiver.archive(self.log)
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
