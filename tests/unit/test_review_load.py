"""The review's engine side (issue #107): the outline of a log's sessions,
the recent sessions offered for a large log, and a replay that starts at a
session's BEGIN_LOG giving that session's fights as a whole-file replay
does."""

import tempfile
import threading
import unittest
from pathlib import Path

import review_load
from app_config import AppConfig
from app_startup import build_analyzer

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'golden_fight.log'


def _key(fights):
    return [(f.zone_name, round(f.group_dps, 1), [p.get('name') for p in f.players])
            for f in fights]


class TestReviewLoad(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.config = AppConfig(path=self.dir / 'config.json')
        text = FIXTURE.read_text(encoding='utf-8')
        # Two sessions: the fixture, then the fixture logged a day later
        self.log = self.dir / 'two.log'
        self.log.write_text(text + text.replace('1755729685851', '1755816085851'),
                            encoding='utf-8')
        self.fixture_fights = self._replay(FIXTURE)

    def tearDown(self):
        self.tmp.cleanup()

    def _replay(self, path, from_begin_log=-1, cancel=None):
        _shown, fights = review_load.replay_log(
            build_analyzer(self.config, []), path, from_begin_log=from_begin_log, cancel=cancel)
        return fights

    def test_outline_counts_sessions_and_fights(self):
        outline = review_load.outline(self.log)
        self.assertEqual(len(outline.starts), 2)
        self.assertEqual(outline.starts[0], 0)
        self.assertEqual(outline.fights, [2, 2])
        self.assertFalse(outline.headless)
        self.assertEqual(outline.total, self.log.stat().st_size)

    def test_recent_sessions_hold_enough_fights(self):
        outline = review_load.outline(self.log)
        self.assertEqual(outline.recent(fights=1), 1)
        self.assertEqual(outline.recent(fights=2), 1)
        self.assertEqual(outline.recent(fights=3), 0)  # needs both: the whole log
        self.assertEqual(outline.begin_log(0), -1)
        self.assertEqual(outline.begin_log(1), 1)
        self.assertEqual(outline.fights_from(1), 2)
        self.assertLess(outline.size_from(1), outline.total)

    def test_replay_from_a_session_start_gives_its_fights(self):
        whole = self._replay(self.log)
        last = self._replay(self.log, from_begin_log=1)
        self.assertEqual(len(whole), 2 * len(self.fixture_fights))
        self.assertEqual(_key(last), _key(whole[len(self.fixture_fights):]))
        self.assertEqual(_key(last), _key(self.fixture_fights))

    def test_a_log_that_opens_mid_session(self):
        lines = FIXTURE.read_text(encoding='utf-8').splitlines(keepends=True)
        headless = self.dir / 'headless.log'
        text = FIXTURE.read_text(encoding='utf-8')
        headless.write_text(''.join(line for line in lines if ',BEGIN_LOG,' not in line) + text,
                            encoding='utf-8')
        outline = review_load.outline(headless)
        self.assertTrue(outline.headless)
        self.assertEqual(len(outline.starts), 2)
        # Its second session is the file's first BEGIN_LOG
        self.assertEqual(outline.begin_log(1), 0)
        self.assertEqual(_key(self._replay(headless, outline.begin_log(1))),
                         _key(self.fixture_fights))

    def test_cancel_stops_the_replay(self):
        cancel = threading.Event()
        cancel.set()
        big = self.dir / 'big.log'
        big.write_text(FIXTURE.read_text(encoding='utf-8') * 400, encoding='utf-8')
        with self.assertRaises(review_load.ReviewCancelled):
            self._replay(big, cancel=cancel)
        with self.assertRaises(review_load.ReviewCancelled):
            review_load.outline(big, cancel=cancel)

    def test_estimate(self):
        self.assertAlmostEqual(review_load.estimate_seconds(review_load.REVIEW_BYTES_PER_SECOND), 1.0)


if __name__ == '__main__':
    unittest.main()
