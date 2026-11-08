"""The split files behind an instance (issue #194): the stamp each fight
carries is the one its session's split is named by, and splits_for finds a
block's sessions' files, zipped or suffixed, the whole session first, a
missing file told from a session not known."""

import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

import fight_blocks
import split_retention
from esolog_tail import ESOLogAnalyzer, FightHistory, LogFileMonitor
from session_splits import SessionSplits, splits_for

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'golden_fight.log'
FIXTURE_MS = 1755729685851    # its BEGIN_LOG
DAY_MS = 24 * 3600 * 1000

A, B, C = '261104200512', '261104214030', '261105193001'


def _fixture(begin_log_ms=FIXTURE_MS, begin_log=True) -> str:
    text = FIXTURE.read_text(encoding='utf-8').replace(str(FIXTURE_MS), str(begin_log_ms))
    if not begin_log:
        text = ''.join(line for line in text.splitlines(keepends=True)
                       if ',BEGIN_LOG,' not in line)
    return text


def _split_and_analyze(text: str, folder: Path):
    """The app's own path: one monitor writing the splits and feeding the
    analyzer, from a log the game wrote *text* into. The analyzer's fights."""
    log = folder.parent / 'Encounter.log'
    log.write_bytes(b'')
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    monitor = LogFileMonitor(analyzer, log, tail_and_split=True, split_dir=folder)
    try:
        with open(log, 'ab') as f:
            f.write(text.encode('utf-8'))
        monitor._process_new_lines()
    finally:
        monitor.log_splitter.cleanup()
    return analyzer.fight_history.fights


class TestSessionStamp(unittest.TestCase):
    """FightHistoryEntry.session_stamp, as the engine sets it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / 'splits'

    def tearDown(self):
        self.tmp.cleanup()

    def _splits(self):
        return sorted(p.name for p in self.folder.iterdir() if p.suffix == '.log')

    def test_a_fight_carries_the_stamp_its_split_is_named_by(self):
        fights = _split_and_analyze(_fixture(), self.folder)
        (name,) = self._splits()
        stamp = split_retention.parse_split_name(name)[0]
        self.assertEqual(len(fights), 2)
        self.assertEqual([f.session_stamp for f in fights], [stamp, stamp])
        # The splitter's names are local time, to the second
        local = datetime.fromtimestamp(FIXTURE_MS / 1000)  # noqa: DTZ006
        self.assertEqual(stamp, local.strftime('%y%m%d%H%M%S'))
        (session,) = splits_for([f.session_stamp for f in fights], self.folder)
        self.assertEqual(session.best.path, self.folder / name)

    def test_each_session_carries_its_own(self):
        """A block over two sessions: each fight has its own session's
        stamp, the earlier fights keep theirs, and each finds its file."""
        fights = _split_and_analyze(_fixture() + _fixture(FIXTURE_MS + DAY_MS), self.folder)
        names = self._splits()
        stamps = [split_retention.parse_split_name(name)[0] for name in names]
        self.assertEqual(len(stamps), 2)
        self.assertEqual([f.session_stamp for f in fights], [stamps[0]] * 2 + [stamps[1]] * 2)
        (block,) = fight_blocks.blocks(fights)
        self.assertEqual(len(block), 4)
        sessions = splits_for([f.session_stamp for f in block], self.folder)
        self.assertEqual([(s.stamp, s.best.path.name) for s in sessions], list(zip(stamps, names)))

    def test_a_session_over_midnight_keeps_the_day_it_began(self):
        """The stamp is the session's start, never a fight's: a fight after
        midnight carries the day before, as its split's name does."""
        # 23:59 in local time, which the fight list and the splitter's names use
        began = int(datetime(2026, 11, 8, 23, 59, 0).timestamp() * 1000)  # noqa: DTZ001
        fights = _split_and_analyze(_fixture(began), self.folder)
        self.assertEqual([f.timestamp[:10] for f in fights], ['2026-11-08', '2026-11-09'])
        self.assertEqual([f.session_stamp for f in fights], ['261108235900'] * 2)
        self.assertEqual(self._splits(), ['261108235900-Coral-Aerie-vet.log'])

    def test_no_begin_log_seen_leaves_it_empty(self):
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        for line in _fixture(begin_log=False).splitlines():
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
        fights = analyzer.fight_history.fights
        self.assertEqual([f.session_stamp for f in fights], ['', ''])
        (session,) = splits_for([f.session_stamp for f in fights], self.folder)
        self.assertFalse(session.known)
        self.assertFalse(session.missing)


def _log(folder: Path, name: str, size: int) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b'x' * size)
    return path


def _zip(folder: Path, name: str, size: int) -> Path:
    """A split zipped as split retention zips it: <stem>.log.zip holding <stem>.log."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name[:-len('.zip')], b'x' * size)
    return path


class TestScanByStamp(unittest.TestCase):

    def test_other_sessions_files_are_passed_over_by_name(self):
        """With the stamps wanted, the scan reads only their files (the
        review of PR #210: every drawing read the whole folder)."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _log(folder, "261104200512-Sunspire-vet.log", 10)
            _log(folder, "261104210000-Sunspire-vet.log", 10)
            _zip(folder, "261104200512-Sunspire-vet-1.log.zip", 5)
            found = split_retention.scan_splits(folder, {"261104200512"})
            self.assertEqual(sorted(f.path.name for f in found),
                             ["261104200512-Sunspire-vet-1.log.zip", "261104200512-Sunspire-vet.log"])
            self.assertEqual(len(split_retention.scan_splits(folder)), 3)


class TestEarlierSplit(unittest.TestCase):
    """The split of the session before a list's first, for a run the list
    begins inside (the fresh review of PR #210)."""

    def test_the_session_just_before_of_the_same_instance(self):
        from session_splits import earlier_split
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _log(folder, "260830120000-Sunspire-vet.log", 10)
            cut = _log(folder, "260830134913-Sunspire-vet.log", 10)
            whole = _log(folder, "260830134913-Sunspire-vet-1.log", 30)
            _log(folder, "260830142039-Sunspire-vet.log", 5)
            found = earlier_split("260830142039", "Sunspire", True, folder)
            self.assertEqual(found.path, whole)
            self.assertNotEqual(found.path, cut)

    def test_another_instance_an_older_one_or_none_is_not_offered(self):
        from session_splits import earlier_split
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True, folder))
            _log(folder, "260830134913-Fungal-Grotto-I-vet.log", 10)  # veteran, another zone
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True, folder))
            _log(folder, "260830140000-Sunspire.log", 10)  # normal, not veteran
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True, folder))
            self.assertIsNone(earlier_split("", "Sunspire", True, folder))
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True, None))
            # Hours older: another night's run
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True,
                                            Path(tmp) / "nowhere"))
            folder2 = folder / "two"
            _log(folder2, "260830100000-Sunspire-vet.log", 10)
            self.assertIsNone(earlier_split("260830142039", "Sunspire", True, folder2))

    def test_a_zone_name_with_dashes_and_the_keep_folder(self):
        from session_splits import earlier_split
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            kept = _log(folder / split_retention.KEEP_FOLDER, "261015183000-Kyne's-Aegis-vet.log", 10)
            self.assertEqual(earlier_split("261015191452", "Kyne's Aegis", True, folder).path, kept)


class TestSplitsFor(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _files(self, stamps):
        return [[split.path.name for split in session.files]
                for session in splits_for(stamps, self.folder)]

    def test_a_session_and_its_split(self):
        # Named after the zone of the session's first fight, whatever the
        # block's: only the stamp is matched
        _log(self.folder, f'{A}-Maw-of-Lorkhaj-vet.log', 100)
        _log(self.folder, f'{B}-Sunspire-vet.log', 100)
        (session,) = splits_for([A, A, A], self.folder)
        self.assertIsInstance(session, SessionSplits)
        self.assertEqual(session.stamp, A)
        self.assertEqual([f.path.name for f in session.files], [f'{A}-Maw-of-Lorkhaj-vet.log'])
        self.assertIs(session.best, session.files[0])
        self.assertTrue(session.known)
        self.assertFalse(session.missing)

    def test_a_zipped_split(self):
        _zip(self.folder, f'{A}-Sunspire-vet.log.zip', 500)
        (session,) = splits_for([A], self.folder)
        self.assertTrue(session.best.zipped)
        self.assertEqual(session.best.path.name, f'{A}-Sunspire-vet.log.zip')

    def test_the_whole_session_first_of_its_copies(self):
        """Of a session's -N copies the largest comes first: the copies cut
        short are its prefixes (issue #85). At equal sizes the plain name
        comes before -1 before -2."""
        _log(self.folder, f'{A}-Kyne\'s-Aegis-vet.log', 100)
        _log(self.folder, f'{A}-Kyne\'s-Aegis-vet-1.log', 300)
        _log(self.folder, f'{A}-Kyne\'s-Aegis-vet-2.log', 100)
        _log(self.folder, f'{A}-Kyne\'s-Aegis-vet-12.log', 100)
        self.assertEqual(self._files([A]), [[f'{A}-Kyne\'s-Aegis-vet-1.log', f'{A}-Kyne\'s-Aegis-vet.log',
                                              f'{A}-Kyne\'s-Aegis-vet-2.log',
                                              f'{A}-Kyne\'s-Aegis-vet-12.log']])

    def test_a_zip_counts_the_log_inside_it(self):
        # On disk the zip is far smaller than the log it holds
        _log(self.folder, f'{A}-Sunspire-vet.log', 1000)
        _zip(self.folder, f'{A}-Sunspire-vet-1.log.zip', 5000)
        self.assertLess((self.folder / f'{A}-Sunspire-vet-1.log.zip').stat().st_size, 1000)
        self.assertEqual(self._files([A]), [[f'{A}-Sunspire-vet-1.log.zip', f'{A}-Sunspire-vet.log']])

    def test_the_plain_log_before_its_zip_of_the_same_size(self):
        _zip(self.folder, f'{A}-Sunspire-vet.log.zip', 1000)
        _log(self.folder, f'{A}-Sunspire-vet.log', 1000)
        self.assertEqual(self._files([A]), [[f'{A}-Sunspire-vet.log', f'{A}-Sunspire-vet.log.zip']])

    def test_a_zip_that_does_not_open_goes_last(self):
        _log(self.folder, f'{A}-Sunspire-vet.log.zip', 5000)    # not a zip
        _log(self.folder, f'{A}-Sunspire-vet-1.log', 10)
        self.assertEqual(self._files([A]), [[f'{A}-Sunspire-vet-1.log', f'{A}-Sunspire-vet.log.zip']])

    def test_two_sessions_in_a_block(self):
        """A block over two sessions lists each, in the order its fights
        first carry them."""
        _log(self.folder, f'{A}-Sunspire-vet.log', 100)
        _log(self.folder, f'{B}-Sunspire-vet.log', 100)
        sessions = splits_for([B, B, A, A, B], self.folder)
        self.assertEqual([s.stamp for s in sessions], [B, A])
        self.assertEqual([s.best.path.name for s in sessions],
                         [f'{B}-Sunspire-vet.log', f'{A}-Sunspire-vet.log'])

    def test_two_blocks_in_a_session(self):
        """Two instances run in one sitting share their session's split."""
        _log(self.folder, f'{A}-Fungal-Grotto-I.log', 100)
        first, second = splits_for([A, A], self.folder), splits_for([A], self.folder)
        self.assertEqual(first, second)
        self.assertEqual(first[0].best.path.name, f'{A}-Fungal-Grotto-I.log')

    def test_a_missing_file(self):
        """A known session no file holds is missing, not unknown."""
        _log(self.folder, f'{A}-Sunspire-vet.log', 100)
        found, missing = splits_for([A, C], self.folder)
        self.assertFalse(found.missing)
        self.assertEqual((missing.stamp, missing.files, missing.best), (C, (), None))
        self.assertTrue(missing.known)
        self.assertTrue(missing.missing)

    def test_no_stamp(self):
        """A fight whose session's BEGIN_LOG was never seen: not known, and
        no file is offered, even one whose name a blank stamp might match."""
        _log(self.folder, f'{A}-Sunspire-vet.log', 100)
        unknown, session = splits_for(['', '', A, ''], self.folder)
        self.assertEqual((unknown.stamp, unknown.files, unknown.best), ('', (), None))
        self.assertFalse(unknown.known)
        self.assertFalse(unknown.missing)
        self.assertEqual(session.stamp, A)
        self.assertEqual(splits_for([], self.folder), [])

    def test_the_keep_folder_too_and_no_other(self):
        """A split moved into keep/ (which split retention leaves alone) is
        still the session's, after the split folder's own at equal size; no
        other subfolder is looked in."""
        _log(self.folder / split_retention.KEEP_FOLDER, f'{A}-Sunspire-vet.log', 100)
        _log(self.folder / split_retention.KEEP_FOLDER, f'{B}-Sunspire-vet.log', 100)
        _log(self.folder, f'{B}-Sunspire-vet.log', 100)
        _log(self.folder / 'old', f'{C}-Sunspire-vet.log', 100)
        a, b, c = splits_for([A, B, C], self.folder)
        self.assertEqual(a.best.path, self.folder / split_retention.KEEP_FOLDER / f'{A}-Sunspire-vet.log')
        self.assertEqual([f.path for f in b.files],
                         [self.folder / f'{B}-Sunspire-vet.log',
                          self.folder / split_retention.KEEP_FOLDER / f'{B}-Sunspire-vet.log'])
        self.assertTrue(c.missing)

    def test_only_the_splitters_files(self):
        """A session still waiting for its zone (-temp.log), the live log and
        another tool's report are not its split."""
        _log(self.folder, f'{A}-temp.log', 100)
        _log(self.folder, 'Encounter.log', 100)
        _log(self.folder, f'{A}-Sunspire-vet-report.txt', 100)
        (session,) = splits_for([A], self.folder)
        self.assertTrue(session.missing)

    def test_no_folder(self):
        (session,) = splits_for([A], None)
        self.assertTrue(session.missing)
        (session,) = splits_for([A], self.folder / 'not there')
        self.assertTrue(session.missing)


if __name__ == '__main__':
    unittest.main()
