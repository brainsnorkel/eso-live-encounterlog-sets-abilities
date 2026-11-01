#!/usr/bin/env python3
"""The trial completion banner (issue #167): the verification of a grab by
the run's score, the crop from the recognition's boxes, the file's name and
its lookup, the desktop frame conversion (an HDR frame scaled by the SDR
white level), the Windows recognition on the Sunspire fixture where it is
available, and the Settings group on Windows only. For arenas (issue #183):
the burst's length from END_TRIAL's own time, the symmetric crop, the most
complete grab kept, banner.log, and a dry run of the burst's thread."""

import datetime
import os
import struct
import sys
import tempfile
import time
import typing
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import banner_capture as bc
from banner_capture import BannerTarget, OcrLine

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "banner_sunspire.png"

# The fixture's two lines as the Windows recognition reads them (2026-11-01)
TITLE = OcrLine("COMPLETED: SUNSPIRE (VETERAN)", 166, 37, 577, 35)
STATS = OcrLine("Final score 253117 Total Time 22:31 Vitality Bonus 35000", 74, 101, 654, 27)

RESULT = {'trial_id': 12, 'name': 'Sunspire', 'is_vet': True, 'duration_ms': 1351407,
          'score': 253117, 'vitality': 35, 'vitality_max': 36}


def _target(**overrides):
    values = {"name": "Sunspire", "is_vet": True, "score": 253117, "duration_ms": 1351407,
              "ended_epoch": datetime.datetime(2026, 11, 1, 21, 31, 5).timestamp()}  # noqa: DTZ001  local time
    values.update(overrides)
    return BannerTarget(**values)


class VerifyTests(unittest.TestCase):
    def test_score_on_the_stats_line_verifies(self):
        self.assertEqual(bc.verify([TITLE, STATS], _target()), (1, "score"))

    def test_score_split_by_the_recognition_still_matches(self):
        line = OcrLine("Final Score 253 117 Total Time 22:31", 0, 0, 10, 10)
        self.assertEqual(bc.verify([line], _target()), (0, "score"))
        line = OcrLine("Final Score 253,117", 0, 0, 10, 10)
        self.assertEqual(bc.verify([line], _target()), (0, "score"))

    def test_another_number_is_not_the_score(self):
        line = OcrLine("Final Score 2531170 Total Time 22:31", 0, 0, 10, 10)
        self.assertEqual(bc.verify([line], _target()), (0, "time"))
        line = OcrLine("Final Score 25311 Total Time 22:32", 0, 0, 10, 10)
        self.assertIsNone(bc.verify([line], _target()))

    def test_timer_text_is_the_fallback_only_beside_words(self):
        self.assertEqual(bc.verify([OcrLine("Total Time 22:31 Vitality", 0, 0, 1, 1)], _target()), (0, "time"))
        self.assertIsNone(bc.verify([OcrLine("22:31", 0, 0, 1, 1)], _target()))
        self.assertIsNone(bc.verify([OcrLine("Total Time 2:31 Vitality", 0, 0, 1, 1)], _target()))

    def test_a_desktop_without_the_banner_does_not_verify(self):
        lines = [OcrLine("File Edit", 44, 13, 56, 10), OcrLine("drwxr-xr-x 1 253117", 443, 447, 73, 8)]
        self.assertIsNone(bc.verify(lines, _target(score=99999)))
        # the score itself anywhere on screen does count: that is the check
        self.assertEqual(bc.verify(lines, _target()), (1, "score"))


    def test_the_timer_fallback_reads_the_rounded_timer(self):
        # Maelstrom Arena's banner showed 44:10 for 2,649,500 ms (issue #183)
        target = _target(score=557196, duration_ms=2649500)
        self.assertEqual(bc.verify([OcrLine("Final Score 55719 Total Time 44:10 Vita", 0, 0, 1, 1)], target),
                         (0, "time"))
        self.assertIsNone(bc.verify([OcrLine("Final Score 55719 Total Time 44:09 Vita", 0, 0, 1, 1)], target))


# Maelstrom Arena's banner in a 3840x2160 screen's region (2304 wide, centre
# 1152), as a grab mid-wipe reads it and as the whole banner does
M_TITLE_PART = OcrLine("COMPLETED: MAELSTROM A", 830, 74, 470, 70)
M_STATS_PART = OcrLine("Final Score 557196 Total Time 44:10 Vita", 760, 202, 640, 54)
M_TITLE = OcrLine("COMPLETED: MAELSTROM ARENA (VETERAN)", 830, 74, 644, 70)
# the revives count, never read, runs on to 1544, the mirror of 760
M_STATS = OcrLine("Final Score 557196 Total Time 44:10 Vitality Bonus 11000", 760, 202, 690, 54)


def _maelstrom(**overrides):
    values = {"name": "Maelstrom Arena", "score": 557196, "duration_ms": 2649500, "trial_id": 6, "vitality": 11}
    values.update(overrides)
    return _target(**values)


class BurstTimingTests(unittest.TestCase):
    """The burst runs until END_TRIAL's own time plus 45 s, and at least
    15 s (issue #183)."""

    def test_until_end_trial_plus_45_seconds(self):
        ended = 1_762_000_000.0
        self.assertEqual(bc.burst_seconds(ended, now=ended), 45)
        self.assertEqual(bc.burst_seconds(ended, now=ended + 1), 44)       # Vateshran's line, read 1 s late
        self.assertEqual(bc.burst_seconds(ended, now=ended + 21.5), 23.5)  # Maelstrom's, 21.5 s late

    def test_at_least_fifteen_seconds(self):
        ended = 1_762_000_000.0
        self.assertEqual(bc.burst_seconds(ended, now=ended + 40), 15)
        self.assertEqual(bc.burst_seconds(ended, now=ended + 80), 15)


class CropTests(unittest.TestCase):
    def test_band_takes_the_title_and_pads(self):
        # union (74,37)-(743,128): 669 wide, 91 tall; 4% each side, made
        # symmetric about the middle (437), 40% above and below, clamped to
        # the fixture's 874x136
        self.assertEqual(bc.crop_rect([TITLE, STATS], 1, 874, 136), (48, 1, 778, 135))

    def test_a_half_drawn_banner_is_cut_to_the_whole_ones_width(self):
        # The left edge fixes the right: centred on the screen's centre
        # line, the crop of a grab mid-wipe reaches past where the whole
        # banner's words and its revives count end
        x, _y, w, _h = bc.crop_rect([M_TITLE_PART, M_STATS_PART], 1, 2304, 972)
        self.assertEqual(x + w / 2, 1152)
        self.assertLess(x, M_STATS_PART.x)
        self.assertGreaterEqual(x + w, max(M_TITLE.right, M_STATS.right, 2 * 1152 - M_STATS.x))
        # the old crop, 12% past the last word read, ended mid-banner
        self.assertLess(M_STATS_PART.right + int(0.12 * 640), 2 * 1152 - M_STATS.x)

    def test_the_words_reaching_past_the_mirror_widen_both_sides(self):
        # Words further right of the centre than the left edge is left of
        # it: the crop still holds them, and stays centred
        line = OcrLine("Final Score 557196 Total Time 44:10", 1000, 200, 600, 50)
        x, _y, w, _h = bc.crop_rect([line], 0, 2304, 972)
        self.assertEqual(x + w / 2, 1152)
        self.assertGreaterEqual(x + w, line.right)
        self.assertLess(x, line.x)

    def test_an_explicit_centre(self):
        x, _y, w, _h = bc.crop_rect([TITLE, STATS], 1, 874, 136, centre_x=460)
        self.assertEqual(x + w / 2, 460)

    def test_a_far_line_above_is_left_out(self):
        far = OcrLine("Chat line", 100, 2, 300, 10)   # 89 px above, more than 3 x 27
        near = OcrLine("COMPLETED: SUNSPIRE", 166, 60, 577, 35)
        _x, y, _w, _h = bc.crop_rect([far, near, STATS], 2, 874, 200)
        self.assertEqual(y, 60 - int((128 - 60) * bc.PAD_VERTICAL))
        self.assertGreater(y, far.bottom)

    def test_lines_below_the_stats_are_left_out(self):
        below = OcrLine("Something", 100, 140, 300, 10)
        self.assertEqual(bc.crop_rect([TITLE, STATS, below], 1, 874, 300), bc.crop_rect([TITLE, STATS], 1, 874, 300))

    def test_region_is_the_top_centre(self):
        self.assertEqual(bc.region_rect(3840, 2160), (768, 0, 2304, 972))
        self.assertEqual(bc.region_rect(1920, 1080), (384, 0, 1152, 486))


class CompletenessTests(unittest.TestCase):
    """Which verified grab is kept: the one reading the vitality bonus, then
    the one whose stats row reaches furthest right, a later one on a tie."""

    def test_the_whole_banner_reads_the_bonus(self):
        self.assertEqual(bc.completeness([M_TITLE, M_STATS], 1, _maelstrom()), (True, M_STATS.right, 54))
        self.assertEqual(bc.completeness([M_TITLE_PART, M_STATS_PART], 1, _maelstrom()),
                         (False, M_STATS_PART.right, 54))

    def test_a_row_the_recognition_split_counts_whole(self):
        left = OcrLine("Final Score 557196 Total Time 44:10", 760, 202, 450, 54)
        right = OcrLine("Vitality Bonus 11000", 1240, 204, 210, 50)
        self.assertEqual(bc.completeness([M_TITLE, left, right], 1, _maelstrom()), (True, 1450, 54))

    def test_the_score_itself_is_not_the_bonus(self):
        line = OcrLine("Final Score 11000 Total Time 44:10", 760, 202, 450, 54)
        self.assertFalse(bc.completeness([line], 0, _maelstrom(score=11000, vitality=11))[0])
        line = OcrLine("Final Score 11000 Total Time 44:10 Vitality Bonus 11000", 760, 202, 690, 54)
        self.assertTrue(bc.completeness([line], 0, _maelstrom(score=11000, vitality=11))[0])
        # no vitality known: never read
        self.assertFalse(bc.completeness([M_STATS], 0, _maelstrom(vitality=None))[0])

    def test_more_complete(self):
        self.assertTrue(bc.more_complete((True, 900, 50), (False, 1400, 50)))
        self.assertFalse(bc.more_complete((False, 1400, 50), (True, 900, 50)))
        self.assertTrue(bc.more_complete((False, 1400, 50), (False, 1000, 50)))
        # a tie, or a pixel's jitter, goes to the later grab
        self.assertTrue(bc.more_complete((True, 1449, 54), (True, 1450, 54)))
        # a later grab clearly shorter (drawing out) does not
        self.assertFalse(bc.more_complete((True, 1300, 54), (True, 1450, 54)))

    def test_the_target_knows_the_bonus(self):
        self.assertEqual(_maelstrom().bonus_text, "11000")
        self.assertIsNone(_target().bonus_text)
        self.assertEqual(BannerTarget.from_result(dict(RESULT)).bonus_text, "35000")


class BannerLogTests(unittest.TestCase):
    """banner.log: what each burst saw, the newest bursts kept (issue #183)."""

    def _block(self, outcome="Score banner saved: x.png", kept=1):
        target = _maelstrom(ended_epoch=datetime.datetime(2026, 11, 1, 14, 47, 58, 500000).timestamp())  # noqa: DTZ001  local time
        grabs = [
            bc.GrabRecord(21.6, r"\\.\DISPLAY2", "bgra8 3840x2160", [OcrLine("Quest Updated", 0, 0, 1, 1)]),
            bc.GrabRecord(22.6, r"\\.\DISPLAY2", "bgra8 3840x2160", [M_TITLE_PART, M_STATS_PART], "score"),
        ]
        return bc.burst_log_text(target, target.ended_epoch + 21.5, 23.5, outcome, grabs, kept)

    def test_a_bursts_block(self):
        lines = self._block().splitlines()
        self.assertEqual(lines[0], "=== 2026-11-01 14:47:58.5 Maelstrom Arena vet: score 557196, time 44:10")
        self.assertEqual(lines[1], "END_TRIAL written at 14:47:58.5, acted on at 14:48:20.0 (+21.5 s);"
                                   " grabs for 24 s, to +45.0 s")
        self.assertEqual(lines[2], "Score banner saved: x.png")
        self.assertEqual(lines[3], r"+21.6 s \\.\DISPLAY2 bgra8 3840x2160: 1 lines, 0 with digits; no match")
        self.assertEqual(lines[4], r"+22.6 s \\.\DISPLAY2 bgra8 3840x2160: 2 lines, 1 with digits;"
                                   " matched the score, kept")
        # only the lines holding a digit are kept in full
        self.assertEqual(lines[5:], ["    Final Score 557196 Total Time 44:10 Vita"])
        self.assertNotIn("Quest Updated", self._block())
        self.assertNotIn("kept", self._block(kept=None))

    def test_the_newest_bursts_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "banner.log"
            for i in range(5):
                self.assertTrue(bc.append_burst_log(path, self._block(outcome=f"outcome {i}"), keep=3))
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("=== "), 3)
            self.assertNotIn("outcome 1", text)
            self.assertIn("outcome 2", text)
            self.assertTrue(text.rstrip().endswith("Vita"))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["banner.log"])

    def test_an_unwritable_log_is_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "config"
            blocker.write_text("a file where the folder should be", encoding="utf-8")
            self.assertFalse(bc.append_burst_log(blocker / "banner.log", self._block()))
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["config"])


class NamingTests(unittest.TestCase):
    def test_file_name(self):
        when = datetime.datetime(2026, 11, 1, 21, 31, 5).timestamp()  # noqa: DTZ001  local time
        self.assertEqual(bc.banner_file_name("Sunspire", True, 253117, when),
                         "Sunspire Veteran 253117 2026-11-01 2131.png")
        self.assertEqual(bc.banner_file_name("Kyne's Aegis", False, 1000, when),
                         "Kyne's Aegis Normal 1000 2026-11-01 2131.png")
        self.assertEqual(bc.banner_file_name('Trial: <odd>/name', True, 1, when),
                         "Trial odd name Veteran 1 2026-11-01 2131.png")

    def test_target_from_entry_ends_at_start_plus_duration(self):
        from fight_history import FightHistoryEntry
        entry = FightHistoryEntry()
        entry.trial_result = dict(RESULT)
        entry.timestamp = "2026-11-01 21:08:33"
        entry.duration_s = 1351.4
        target = BannerTarget.from_entry(entry)
        self.assertIsNotNone(target)
        start = datetime.datetime(2026, 11, 1, 21, 8, 33).timestamp()  # noqa: DTZ001  local time
        self.assertAlmostEqual(target.ended_epoch, start + 1351.4, places=3)
        self.assertEqual(target.file_name, "Sunspire Veteran 253117 2026-11-01 2131.png")
        self.assertEqual(target.time_text, "22:31")
        self.assertTrue(target.is_live(now=target.ended_epoch + bc.LIVE_WINDOW_S))
        self.assertFalse(target.is_live(now=target.ended_epoch + bc.LIVE_WINDOW_S + 1))

    def test_target_from_result_uses_the_lines_moment_and_the_run_as_key(self):
        result = dict(RESULT, ended_epoch=1761999065.0)
        a = BannerTarget.from_result(result)
        self.assertEqual(a.ended_epoch, 1761999065.0)
        self.assertEqual(a.key, (12, 253117, 1351407))
        # the same run on a fight entry: the key and the file do not move
        # with the fight's span (a fight the game cut in two grows later)
        from fight_history import FightHistoryEntry
        entry = FightHistoryEntry()
        entry.trial_result = dict(result)
        entry.timestamp = "2026-11-01 21:08:33"
        entry.duration_s = 100.0
        b = BannerTarget.from_entry(entry)
        self.assertEqual((b.key, b.file_name), (a.key, a.file_name))
        entry.duration_s = 1351.4
        self.assertEqual(BannerTarget.from_entry(entry).file_name, a.file_name)
        self.assertIsNone(BannerTarget.from_result(None))

    def test_target_falls_back_to_the_engine_clock(self):
        from fight_history import FightHistoryEntry
        entry = FightHistoryEntry()
        entry.trial_result = dict(RESULT)
        entry.timestamp = "Unknown Time"
        entry.ended_at = 1700000000.0
        self.assertEqual(BannerTarget.from_entry(entry).ended_epoch, 1700000000.0)
        entry.trial_result = None
        self.assertIsNone(BannerTarget.from_entry(entry))

    def test_existing_banner_is_found_by_name(self):
        target = _target()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(bc.existing_banner(Path(tmp), target))
            (Path(tmp) / target.file_name).write_bytes(b"png")
            self.assertEqual(bc.existing_banner(Path(tmp), target), Path(tmp) / target.file_name)
        self.assertIsNone(bc.existing_banner(None, target))


class OcrOutputTests(unittest.TestCase):
    def test_records_parse(self):
        records = ["FILE\tC:\\x.png", "LINE\tFinal score 253117\t74\t101\t654\t27",
                   "LINE\tbad\tx\ty\tw\th", "END\t164"]
        lines, error, elapsed = bc.parse_ocr_output(records)
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0].text, lines[0].x, lines[0].h), ("Final score 253117", 74, 27))
        self.assertIsNone(error)
        self.assertEqual(elapsed, 164)
        lines, error, elapsed = bc.parse_ocr_output(["FILE\tC:\\x.png", "ERROR\tno such file", "END\t3"])
        self.assertEqual(lines, [])
        self.assertEqual(error, "no such file")


@unittest.skipUnless(bc.ocr_available(), "Windows text recognition")
class WindowsRecognitionTests(unittest.TestCase):
    """The real recognition on the fixture: skipped where Windows has no
    recognition language (the session then cannot start)."""

    def test_fixture_verifies_by_its_score(self):
        try:
            session = bc.OcrSession()
        except bc.OcrError as exc:
            self.skipTest(str(exc))
        with session:
            lines = session.read(str(FIXTURE))
        found = bc.verify(lines, _target())
        self.assertIsNotNone(found, [l.text for l in lines])
        self.assertEqual(found[1], "score")
        _x, _y, w, h = bc.crop_rect(lines, found[0], 874, 136)
        self.assertGreater(w, 500)
        self.assertGreater(h, 60)


class FrameConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A QApplication, as the GUI tests make: a QGuiApplication here
        # would be the instance the later widget tests find, and abort them
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from gui.banner_burst import frame_to_image
        cls.frame_to_image = staticmethod(frame_to_image)

    def test_bgra8_frame_keeps_its_colours(self):
        import desktop_duplication as dd
        # one pixel: B=10, G=20, R=30, A=255
        frame = dd.Frame(1, 1, dd.FORMAT_B8G8R8A8_UNORM, bytes([10, 20, 30, 255]))
        image = self.frame_to_image(frame)
        colour = image.pixelColor(0, 0)
        self.assertEqual((colour.red(), colour.green(), colour.blue()), (30, 20, 10))

    def test_fp16_frame_is_scaled_by_the_sdr_white_and_gamma_encoded(self):
        import desktop_duplication as dd
        # left: SDR white at 200 nits (2.5 x 80); right: 0.5 linear
        row = struct.pack("<4e", 2.5, 2.5, 2.5, 1.0) + struct.pack("<4e", 0.5, 0.5, 0.5, 1.0)
        frame = dd.Frame(2, 1, dd.FORMAT_R16G16B16A16_FLOAT, row)
        image = self.frame_to_image(frame, sdr_white_nits=200.0)
        self.assertEqual(image.pixelColor(0, 0).red(), 255)
        self.assertEqual(image.pixelColor(1, 0).red(), 124)   # sRGB of 0.2
        unscaled = self.frame_to_image(frame, sdr_white_nits=80.0)
        self.assertEqual(unscaled.pixelColor(1, 0).red(), 188)  # sRGB of 0.5

    def test_sdr_white_lookup_answers_on_every_platform(self):
        enabled, nits = bc.display_sdr_white()
        self.assertIsInstance(enabled, bool)
        self.assertGreaterEqual(nits, 80.0)
        with patch.object(sys, "platform", "linux"):
            self.assertEqual(bc.display_sdr_white(), (False, 80.0))


class SettingsGroupTests(unittest.TestCase):
    """The Score banner group is a Windows-only section of Settings."""

    def _dialog(self, platform):
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        config = AppConfig(Path(self.tmp.name) / "config.json")
        with patch.object(sys, "platform", platform):
            return SettingsDialog(config), config

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(sys.platform == "win32", "the dialog's Startup group reads the registry on win32")
    def test_group_on_windows_saves_its_fields(self):
        dialog, config = self._dialog("win32")
        try:
            self.assertTrue(hasattr(dialog, "banner_enabled"))
            self.assertFalse(dialog.banner_enabled.isChecked())  # off by default
            dialog.banner_enabled.setChecked(True)
            dialog.banner_dir.edit.setText(r"D:\shots")
            dialog.apply_to_config()
            self.assertTrue(config.get("banner.enabled"))
            self.assertEqual(config.get("banner.dir"), r"D:\shots")
        finally:
            dialog.deleteLater()

    def test_no_group_elsewhere(self):
        dialog, config = self._dialog("linux")
        try:
            self.assertFalse(hasattr(dialog, "banner_enabled"))
            dialog.apply_to_config()
            self.assertFalse(config.get("banner.enabled"))
        finally:
            dialog.deleteLater()


class EngineEventTests(unittest.TestCase):
    """The engine reports END_TRIAL as it reads the line, with the line's
    own moment, before the fight that carries the result is delivered."""

    EPOCH_MS = 1761996000000

    def _listener(self, lines):
        from engine_events import RecordingListener
        from esolog_tail import ESOLogAnalyzer
        from fight_history import FightHistory
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        listener = RecordingListener()
        analyzer.add_listener(listener)
        for line in lines:
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
        return listener

    def test_trial_result_is_sent_as_the_line_is_read(self):
        listener = self._listener([
            f'5,BEGIN_LOG,{self.EPOCH_MS},15,"NA Megaserver","en","eso.live.12.1"',
            '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
            '39033,END_TRIAL,12,1351407,T,253117,35000',
        ])
        events = listener.of_kind("trial_result")
        self.assertEqual(len(events), 1)
        result = events[0][1]
        self.assertEqual((result["score"], result["name"], result["is_vet"]), (253117, "Sunspire", True))
        self.assertAlmostEqual(result["ended_epoch"], self.EPOCH_MS / 1000 + 39.033, places=3)
        target = BannerTarget.from_result(result)
        self.assertEqual(target.key, (12, 253117, 1351407))
        self.assertAlmostEqual(target.ended_epoch, result["ended_epoch"], places=3)

    def test_a_failed_run_sends_nothing(self):
        listener = self._listener([
            f'5,BEGIN_LOG,{self.EPOCH_MS},15,"NA Megaserver","en","eso.live.12.1"',
            '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
            '39033,END_TRIAL,12,1351407,F,0,0',
        ])
        self.assertEqual(listener.of_kind("trial_result"), [])


class BannerInTheGuiTests(unittest.TestCase):
    """The captured banner in the app: the result row's cue, the result
    strip's links and the pane's signal for them."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _entry(self, banner=None):
        from fight_history import FightHistoryEntry
        entry = FightHistoryEntry()
        entry.boss_name = "Nahviintaas"
        entry.zone_name = "Sunspire"
        entry.zone_id = "1121"
        entry.difficulty = "VETERAN"
        entry.is_vet = True
        entry.timestamp = "2026-11-01 21:08:33"
        entry.duration_s = 1351.4
        entry.group_dps = 150000.0
        entry.trial_result = dict(RESULT)
        entry.banner_path = banner
        return entry

    def test_result_row_shows_the_cue_once_captured(self):
        from gui.fight_list import KIND_ROLE, FightList
        from gui.fight_list import RESULT as RESULT_KIND
        lst = FightList()
        try:
            entry = self._entry()
            row = lst.add_fight(entry)
            result_row = lst.item(row + 1)
            self.assertEqual(result_row.data(KIND_ROLE), RESULT_KIND)
            self.assertNotIn("banner", result_row.text())
            entry.banner_path = Path("C:/x/Sunspire Veteran 253117 2026-11-01 2131.png")
            lst.update_fight(entry)
            self.assertTrue(lst.item(row + 1).text().endswith("· banner"))
        finally:
            lst.deleteLater()

    def test_result_strip_links_only_with_a_banner(self):
        from gui.fight_render import BANNER_HREF, render_html
        without = render_html(self._entry(), detailed=False)
        self.assertNotIn(BANNER_HREF, without)
        with_banner = render_html(self._entry(Path("C:/x/b.png")), detailed=False)
        for action in ("open", "save", "copy"):
            self.assertIn(f"{BANNER_HREF}{action}", with_banner)
        self.assertIn("Score banner", with_banner)

    def test_pane_reports_the_banner_action(self):
        from PySide6.QtCore import QUrl

        from gui.fight_render import BANNER_HREF
        from gui.fight_view import FightView
        view = FightView()
        try:
            seen = []
            view.banner_requested.connect(seen.append)
            view._on_anchor_clicked(QUrl(f"{BANNER_HREF}copy"))
            view._on_anchor_clicked(QUrl(f"{BANNER_HREF}open"))
            self.assertEqual(seen, ["copy", "open"])
        finally:
            view.deleteLater()


class _FakeSource:
    """A monitor for the dry run: a blank 400x200 frame each grab, whose
    top-centre region is 240x90 (centre 120)."""

    def __init__(self, info, notes):
        self.name = info.device_name
        self.dead = False
        self.last_format = "bgra8"

    def grab(self):
        from PySide6.QtGui import QImage
        image = QImage(400, 200, QImage.Format.Format_RGB32)
        image.fill(0)
        return image

    def close(self):
        pass


class _FakeSession:
    """The recognition for the dry run: what grab n 'reads' comes from
    SCRIPT, by the grab's file name (grab-NN-i.png)."""

    SCRIPT: typing.ClassVar[dict] = {}

    def __init__(self, *args, **kwargs):
        pass

    def read(self, path):
        return list(self.SCRIPT.get(int(Path(path).name.split("-")[1]), []))

    def kill(self):
        pass

    def close(self):
        pass


class _NoRecognition:
    def __init__(self, *args, **kwargs):
        raise bc.OcrError("Windows has no text recognition language installed")


# The Maelstrom banner in the fake region: drawing in, whole, drawing out
DRAWING_IN = [OcrLine("COMPLETED: MAELSTROM A", 50, 20, 50, 12),
              OcrLine("Final Score 557196 Total Time 44:10 Vita", 30, 40, 90, 10)]
WHOLE = [OcrLine("COMPLETED: MAELSTROM ARENA (VETERAN)", 50, 20, 140, 12),
         OcrLine("Final Score 557196 Total Time 44:10 Vitality Bonus 11000", 30, 40, 150, 10)]
DRAWING_OUT = [OcrLine("Final Score 557196 Total Time", 30, 40, 70, 10)]


class BurstDryRunTests(unittest.TestCase):
    """The burst's own thread, with a fake monitor and a fake recognition:
    the banner appearing late, the follow-up grabs, the grab kept, the crop
    saved and banner.log written, on each outcome."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import desktop_duplication as dd
        from gui import banner_burst
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "config" / "banner.log"
        self.folder = self.dir / "Banners"
        output = dd.OutputInfo(0, 0, r"\\.\DISPLAY9", 0, 0, 400, 200)
        for patcher in (patch.object(banner_burst, "_Source", _FakeSource),
                        patch.object(dd, "list_outputs", lambda: [output]),
                        patch.object(bc, "OcrSession", _FakeSession),
                        patch.object(bc, "BURST_INTERVAL_MS", 5)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.burst = None

    def tearDown(self):
        from PySide6.QtCore import QEvent
        if self.burst is not None:
            self.burst.cancel()
            self.burst.deleteLater()
        for _ in range(3):
            self.app.processEvents()
            self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.tmp.cleanup()

    def _run(self, target, script, wait_s=10.0):
        from gui.banner_burst import BannerBurst
        _FakeSession.SCRIPT = script
        self.burst = BannerBurst(target, self.folder, log_path=self.log)
        seen = []
        self.burst.finished.connect(lambda path, message: seen.append((path, message)))
        self.burst.start()
        temp = self.burst._temp
        deadline = time.monotonic() + wait_s
        while not seen and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(seen, "the burst never reported")
        self.burst = None  # it deletes itself once its thread ends
        deadline = time.monotonic() + 5
        while temp.exists() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(temp.exists(), "the temporary grabs were left behind")
        return seen[0]

    def _log_grabs(self):
        return [line for line in self.log.read_text(encoding="utf-8").splitlines() if line.startswith("+")]

    def test_the_whole_banner_is_kept_not_the_first_match(self):
        target = _maelstrom(ended_epoch=time.time() - 1)
        path, message = self._run(target, {2: DRAWING_IN, 3: WHOLE, 4: DRAWING_OUT})
        self.assertEqual(path, self.folder / target.file_name)
        self.assertTrue(message.startswith("Score banner saved"))
        from PySide6.QtGui import QImage
        saved = QImage(str(path))
        # the whole banner's band, symmetric about the region's centre (120):
        # x 30..190 padded 6 a side and mirrored, 24..216; y 20..50 padded 12
        self.assertEqual((saved.width(), saved.height()), (192, 54))
        grabs = self._log_grabs()
        self.assertEqual(len(grabs), 5)  # two blank, the first match and two follow-ups
        self.assertTrue(grabs[0].endswith("no match"))
        self.assertTrue(grabs[2].endswith("matched the score"))
        self.assertTrue(grabs[3].endswith("matched the score, kept"))
        self.assertTrue(grabs[4].endswith("matched the score"))
        self.assertIn(r"\\.\DISPLAY9 bgra8 400x200", grabs[0])
        self.assertIn(message, self.log.read_text(encoding="utf-8"))

    def test_nothing_seen_keeps_nothing_and_logs_the_grabs(self):
        target = _maelstrom(ended_epoch=time.time() - 100)
        with patch.object(bc, "BURST_MIN_SECONDS", 0.05):
            path, message = self._run(target, {})
        self.assertIsNone(path)
        self.assertIn("nothing kept", message)
        self.assertFalse(self.folder.exists())
        grabs = self._log_grabs()
        self.assertTrue(grabs)
        self.assertTrue(all(line.endswith("no match") for line in grabs))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["config"])

    def test_no_recognition_is_logged(self):
        target = _maelstrom(ended_epoch=time.time() - 1)
        with patch.object(bc, "OcrSession", _NoRecognition):
            path, message = self._run(target, {})
        self.assertIsNone(path)
        text = self.log.read_text(encoding="utf-8")
        self.assertIn(message, text)
        self.assertIn("no text recognition language", text)
        self.assertEqual(self._log_grabs(), [])

    def test_a_cancelled_burst_is_logged(self):
        from gui.banner_burst import BannerBurst
        _FakeSession.SCRIPT = {}
        burst = BannerBurst(_maelstrom(ended_epoch=time.time() - 1), self.folder, log_path=self.log)
        burst.start()
        time.sleep(0.05)
        burst.cancel()
        burst.deleteLater()
        self.assertIn("cancelled, the window closed", self.log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
