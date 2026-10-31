#!/usr/bin/env python3
"""The trial completion banner (issue #167): the verification of a grab by
the run's score, the crop from the recognition's boxes, the file's name and
its lookup, the desktop frame conversion (an HDR frame scaled by the SDR
white level), the Windows recognition on the Sunspire fixture where it is
available, and the Settings group on Windows only."""

import datetime
import os
import struct
import sys
import tempfile
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


class CropTests(unittest.TestCase):
    def test_band_takes_the_title_and_pads(self):
        # union (74,37)-(743,128): 669 wide, 91 tall; 4% left, 12% right,
        # 40% above and below, clamped to the fixture's 874x136
        self.assertEqual(bc.crop_rect([TITLE, STATS], 1, 874, 136), (48, 1, 775, 135))

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


if __name__ == "__main__":
    unittest.main()
