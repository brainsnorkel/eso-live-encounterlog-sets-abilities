#!/usr/bin/env python3
"""scripts/dedupe_splits.py: the byte-identical copies of a session's split
are found by stamp, size and whole-file hash, the lowest suffix is kept,
and the copies go to the Recycle Bin only with --recycle."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    path = REPO_ROOT / 'scripts' / 'dedupe_splits.py'
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDedupeSplits(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.script = _load()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        session = b'5,BEGIN_LOG,1755729685851,15,"NA Megaserver"\r\n' + b'x' * 5000
        (self.folder / '260301191700-Hel-Ra-Citadel-vet.log').write_bytes(session)
        (self.folder / '260301191700-Hel-Ra-Citadel-vet-1.log').write_bytes(session)
        (self.folder / '260301191700-Hel-Ra-Citadel-vet-2.log').write_bytes(session)
        # Same stamp and size, different bytes: not a copy
        (self.folder / '260301191700-Hel-Ra-Citadel-vet-3.log').write_bytes(session[:-1] + b'y')
        # Same stamp, a shorter earlier run: not a copy
        (self.folder / '260301191700-Hel-Ra-Citadel-vet-4.log').write_bytes(session[:3000])
        # A copy whose plain name is gone: the lowest suffix is kept
        other = b'5,BEGIN_LOG,1755729700000,15,"NA Megaserver"\r\n' + b'z' * 700
        (self.folder / '260303200108-Infinite-Archive-2.log').write_bytes(other)
        (self.folder / '260303200108-Infinite-Archive-5.log').write_bytes(other)
        (self.folder / '260303200108-Infinite-Archive-temp.log').write_bytes(other)
        (self.folder / '260303200108-Infinite-Archive.log.zip').write_bytes(b'PK')
        (self.folder / 'notes.txt').write_bytes(b'')

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_key(self):
        key = self.script.split_key
        self.assertEqual(key('260301191700-Hel-Ra-Citadel-vet.log'), ('260301191700-Hel-Ra-Citadel-vet', 0))
        self.assertEqual(key('260301191700-Hel-Ra-Citadel-vet-12.log'), ('260301191700-Hel-Ra-Citadel-vet', 12))
        self.assertIsNone(key('260301191700-Hel-Ra-Citadel-vet-temp.log'))
        self.assertIsNone(key('260301191700-Hel-Ra-Citadel-vet.log.zip'))
        self.assertIsNone(key('notes.txt'))

    def test_copies_are_found_by_stamp_size_and_bytes(self):
        groups = self.script.find_copies(self.folder)
        self.assertEqual(
            [(k.name, sorted(c.name for c in cs)) for k, cs in groups],
            [('260301191700-Hel-Ra-Citadel-vet.log',
              ['260301191700-Hel-Ra-Citadel-vet-1.log', '260301191700-Hel-Ra-Citadel-vet-2.log']),
             ('260303200108-Infinite-Archive-2.log', ['260303200108-Infinite-Archive-5.log'])])

    def test_listing_moves_nothing_and_recycle_moves_the_copies(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.script.main(['--dir', str(self.folder)]), 0)
        self.assertIn('2 sessions with copies, 3 copies', out.getvalue())
        self.assertIn('nothing moved', out.getvalue())
        self.assertEqual(len(list(self.folder.glob('*.log'))), 8)
        moved = []
        with mock.patch('recycle_bin.move_to_trash', side_effect=lambda p: moved.append(Path(p).name) or Path(p).unlink()), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.script.main(['--dir', str(self.folder), '--recycle']), 0)
        self.assertEqual(sorted(moved), ['260301191700-Hel-Ra-Citadel-vet-1.log',
                                         '260301191700-Hel-Ra-Citadel-vet-2.log',
                                         '260303200108-Infinite-Archive-5.log'])
        self.assertIn('moved 3 of 3 copies', out.getvalue())
        self.assertTrue((self.folder / '260301191700-Hel-Ra-Citadel-vet.log').exists())
        self.assertTrue((self.folder / '260303200108-Infinite-Archive-2.log').exists())
        self.assertTrue((self.folder / '260301191700-Hel-Ra-Citadel-vet-3.log').exists())
        self.assertTrue((self.folder / '260301191700-Hel-Ra-Citadel-vet-4.log').exists())
        # Nothing left to move
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.script.main(['--dir', str(self.folder), '--recycle']), 0)
        self.assertIn('0 sessions with copies, 0 copies', out.getvalue())

    def test_a_refused_move_is_reported_and_the_rest_still_go(self):
        from recycle_bin import TrashUnavailable

        def refuse_one(path):
            if path.name.endswith('-1.log'):
                raise TrashUnavailable('larger than the bin')
            Path(path).unlink()
        with mock.patch('recycle_bin.move_to_trash', side_effect=refuse_one), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.script.main(['--dir', str(self.folder), '--recycle']), 1)
        self.assertIn('left 260301191700-Hel-Ra-Citadel-vet-1.log: larger than the bin', err.getvalue())
        self.assertTrue((self.folder / '260301191700-Hel-Ra-Citadel-vet-1.log').exists())
        self.assertFalse((self.folder / '260301191700-Hel-Ra-Citadel-vet-2.log').exists())

    def test_missing_folder(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.script.main(['--dir', str(self.folder / 'nowhere')]), 1)


if __name__ == '__main__':
    unittest.main()
