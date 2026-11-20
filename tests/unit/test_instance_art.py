#!/usr/bin/env python3
"""Instance art (issue #249): the table of scripts/extract_instance_art.py
and the pictures it wrote; the cut that covers a slot; the header rows of
the fight list with and without art, on a band and off, with the setting
off and under high contrast; the strip across the Instance page, the room
the page leaves for it, and a page that asks for none; the setting."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ART = REPO_ROOT / "data" / "art" / "instances"
SUNSPIRE, KYNES_AEGIS, CRAGLORN = "1121", "1196", "888"  # the last has no art


def _script():
    path = REPO_ROOT / "scripts" / "extract_instance_art.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _differs(a, b, by=10) -> bool:
    return max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())) > by


class TestTheTable(unittest.TestCase):

    def setUp(self):
        self.script = _script()
        self.table = self.script.instances()

    def test_a_line_reads_as_zone_name_painting_and_focus(self):
        sunspire = self.table[SUNSPIRE]
        self.assertEqual(sunspire, {"name": "Sunspire", "art": "loadscreen_sunspire_01",
                                    "focus": self.script.FOCUS})
        # The names that follow no rule (see the script)
        self.assertEqual(self.table["639"]["art"], "loadscreen_serpenttrial_01")
        self.assertEqual(self.table["725"]["art"], "loadscreen_maw_of_lorkaj")
        self.assertEqual(self.table["1436"]["art"], "loadscreen_endless_archive_01")

    def test_a_zone_twice_or_a_focus_out_of_range_stops_the_run(self):
        with (patch.object(self.script, "INSTANCES", ((1, "A", "a"), (1, "B", "b"))),
              self.assertRaisesRegex(ValueError, "twice")):
            self.script.instances()
        with (patch.object(self.script, "INSTANCES", ((1, "A", "a", 1.5),)),
              self.assertRaisesRegex(ValueError, "focus")):
            self.script.instances()
        with patch.object(self.script, "INSTANCES", ((1, "A", "a", 0.1),)):
            self.assertEqual(self.script.instances()["1"]["focus"], 0.1)
        # A line copied for a new trial with its painting left as it was
        with (patch.object(self.script, "INSTANCES", ((1, "Old", "Paint_01"), (2, "New", "paint_01"))),
              self.assertRaisesRegex(ValueError, "both Old and New")):
            self.script.instances()

    def test_only_a_picture_an_earlier_run_wrote_is_ever_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            for name in ("635.jpg", "77.jpg", "88.jpg", "holiday.jpg"):
                (out / name).write_bytes(b"x")
            # 77 was written by an earlier run and its line is gone; 88 and
            # the holiday picture are somebody else's; 635 still has a line
            previous = {"635": {}, "77": {}, "99": {}}
            self.assertEqual(self.script.remove_stale(out, previous, self.table), ["77.jpg"])
            self.assertEqual(sorted(path.name for path in out.iterdir()),
                             ["635.jpg", "88.jpg", "holiday.jpg"])

    def test_the_art_is_dated_in_the_bundles_stamp(self):
        """About's data dates and stamp_data_version.py --check know the
        art's manifest as they know the icons'."""
        path = REPO_ROOT / "scripts" / "stamp_data_version.py"
        spec = importlib.util.spec_from_file_location(path.stem, path)
        stamp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stamp)
        self.assertIn("data/art/instances/manifest.json", [file for _name, file in stamp.TABLES])
        stamped = json.loads((REPO_ROOT / "data" / "version.json").read_text(encoding="utf-8"))
        self.assertIn("data/art/instances/manifest.json",
                      [table["file"] for table in stamped["tables"]])

    def test_every_trial_and_arena_the_app_names_has_a_line(self):
        """A raid the game adds goes into trial_result.TRIAL_NAMES; this
        says it wants its art too: one line in INSTANCES and a run of the
        script. Until then the app draws its header plain."""
        from fight_opener import ARENA_ZONE_IDS
        from trial_result import TRIAL_NAMES
        names = {entry["name"] for entry in self.table.values()}
        self.assertEqual(set(TRIAL_NAMES.values()) - names, set())
        self.assertEqual(set(ARENA_ZONE_IDS) - set(self.table), set())

    def test_the_band_is_the_whole_width_and_the_focus_places_it(self):
        script = self.script
        self.assertEqual((script.WIDTH, script.HEIGHT), (1680, 240))
        self.assertEqual(script.band_box((1680, 1052), 0.0), (0, 0, 1680, 240))
        self.assertEqual(script.band_box((1680, 1052), 1.0), (0, 812, 1680, 1052))
        self.assertEqual(script.band_box((1680, 1052), 0.42), (0, 341, 1680, 581))
        # A painting of another size is scaled to the width first
        self.assertEqual(script.band_box((840, 526), 1.0), (0, 812, 1680, 1052))
        # One too flat to hold the band gives what it has, from its top
        self.assertEqual(script.band_box((1680, 100), 0.5), (0, 0, 1680, 240))

    def test_the_strip_of_a_painting(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        painting = Image.new("RGB", (840, 526), "navy")
        painting.paste("white", (0, 263, 840, 526))  # the lower half
        self.assertEqual(self.script.strip_of(painting, 0.0).size, (1680, 240))
        self.assertEqual(self.script.strip_of(painting, 0.0).getpixel((800, 120)), (0, 0, 128))
        self.assertEqual(self.script.strip_of(painting, 1.0).getpixel((800, 120)), (255, 255, 255))

    def test_the_paintings_are_found_by_their_file_names(self):
        rows = [(10, 5, "\\esoui\\art\\icons\\ability_x.dds"),
                (11, 5, "\\esoui\\art\\loadingscreens\\LoadScreen_Sunspire_01.dds"),
                (12, 5, "\\esoui\\art\\loadingscreens\\loadscreen_sunspire_veteran_01.dds"),
                (13, 5, "\\other\\loadscreen_cloudrest_01.dds")]
        found = self.script.art_positions(rows, {"loadscreen_sunspire_01.dds",
                                                 "loadscreen_cloudrest_01.dds"})
        self.assertEqual(found, {"loadscreen_sunspire_01.dds": 1})


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestThePictures(unittest.TestCase):
    """What the script wrote into data/art/instances is what the table
    says, and what the build bundles."""

    def setUp(self):
        _ensure_app()
        self.script = _script()
        self.table = self.script.instances()

    def test_every_line_has_its_picture_at_the_strips_size(self):
        from PySide6.QtGui import QImage
        for zone_id, entry in self.table.items():
            image = QImage(str(ART / f"{zone_id}.jpg"))
            self.assertFalse(image.isNull(), f"{entry['name']}: no picture Qt can read")
            self.assertEqual((image.width(), image.height()),
                             (self.script.WIDTH, self.script.HEIGHT), entry["name"])

    def test_no_picture_without_a_line(self):
        self.assertEqual({path.stem for path in ART.glob("*.jpg")} - set(self.table), set())

    def test_the_manifest_lists_the_table(self):
        manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["width"], manifest["height"]),
                         (self.script.WIDTH, self.script.HEIGHT))
        self.assertEqual(set(manifest["instances"]), set(self.table))
        self.assertEqual(manifest["count"], len(self.table))
        for zone_id, entry in self.table.items():
            listed = manifest["instances"][zone_id]
            self.assertEqual((listed["name"], listed["art"], listed["focus"]),
                             (entry["name"], entry["art"], entry["focus"]))

    def test_the_build_bundles_the_folder_the_app_reads(self):
        from gui import instance_art
        spec = (REPO_ROOT / "esolog-tail.spec").read_text(encoding="utf-8")
        self.assertIn("'data/art/instances'", spec)
        self.assertEqual(instance_art.art_dir(), ART)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ArtTestCase(unittest.TestCase):

    def setUp(self):
        from gui import instance_art
        self.app = _ensure_app()
        instance_art.set_enabled(True)
        self.addCleanup(instance_art.set_enabled, True)

    def _pump(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            self.app.processEvents()


class TestCover(ArtTestCase):

    def test_the_part_of_a_picture_that_covers_a_slot(self):
        from PySide6.QtCore import QRectF, QSize

        from gui.instance_art import cover_source
        size = QSize(1680, 240)
        # A slot of the picture's own shape takes all of it
        self.assertEqual(cover_source(size, 840, 120), QRectF(0, 0, 1680, 240))
        # A squarer slot loses the two sides evenly
        self.assertEqual(cover_source(size, 240, 120), QRectF(600, 0, 480, 240))
        # A flatter one loses top and bottom evenly
        self.assertEqual(cover_source(size, 1680, 120), QRectF(0, 60, 1680, 120))
        self.assertTrue(cover_source(size, 0, 120).isEmpty())
        self.assertTrue(cover_source(QSize(), 10, 10).isEmpty())


class TestTheCache(ArtTestCase):

    def test_a_zone_with_art_and_the_zones_without(self):
        from gui.instance_art import ArtCache
        cache = ArtCache()
        self.assertEqual(cache.image(SUNSPIRE).width(), 1680)
        self.assertIs(cache.image(SUNSPIRE), cache.image(int(SUNSPIRE)))  # read once
        for zone in (CRAGLORN, "", None, "Sunspire", "../../icon", "1121/..", "-1"):
            self.assertIsNone(cache.image(zone), zone)

    def test_only_a_number_names_a_file(self):
        from gui.instance_art import ArtCache
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "sub").mkdir()
            cache = ArtCache(Path(folder) / "sub")
            with patch("gui.instance_art.QImage") as reads:
                cache.image("../secret")
                reads.assert_not_called()

    def test_a_folder_without_the_picture_gives_none(self):
        from gui.instance_art import ArtCache
        with tempfile.TemporaryDirectory() as folder:
            cache = ArtCache(folder)
            self.assertIsNone(cache.image(SUNSPIRE))
            self.assertIsNone(cache.fitted(SUNSPIRE, 300, 44))
            (Path(folder) / f"{SUNSPIRE}.jpg").write_bytes(b"not a picture")
            self.assertIsNone(ArtCache(folder).image(SUNSPIRE))

    def test_fitted_to_a_slot_at_a_pixel_ratio(self):
        from gui.instance_art import ArtCache
        cache = ArtCache()
        fitted = cache.fitted(SUNSPIRE, 300, 44, 2.0)
        self.assertEqual((fitted.width(), fitted.height()), (600, 88))
        self.assertEqual(fitted.devicePixelRatio(), 2.0)
        self.assertIs(cache.fitted(SUNSPIRE, 300, 44, 2.0), fitted)
        self.assertIsNone(cache.fitted(SUNSPIRE, 0, 44))
        self.assertIsNone(cache.fitted(CRAGLORN, 300, 44))

    def test_the_fitted_pictures_kept_are_bounded(self):
        from gui import instance_art
        cache = instance_art.ArtCache()
        for width in range(200, 200 + instance_art.FITTED_KEPT + 20):
            cache.fitted(SUNSPIRE, width, 44)
        self.assertEqual(len(cache._fitted), instance_art.FITTED_KEPT)


class TestTheSwitch(ArtTestCase):

    def test_the_setting_and_what_it_answers(self):
        from gui import instance_art
        self.assertEqual(instance_art.zone_with_art(SUNSPIRE), SUNSPIRE)
        self.assertEqual(instance_art.zone_with_art(int(SUNSPIRE)), SUNSPIRE)
        self.assertEqual(instance_art.zone_with_art(CRAGLORN), "")
        self.assertEqual(instance_art.zone_with_art(None), "")
        self.assertFalse(instance_art.set_enabled(True))   # no change
        self.assertTrue(instance_art.set_enabled(False))
        self.assertFalse(instance_art.enabled())
        self.assertEqual(instance_art.zone_with_art(SUNSPIRE), "")

    def test_high_contrast_turns_it_off(self):
        from gui import instance_art
        with patch.object(instance_art, "high_contrast", return_value=True):
            self.assertFalse(instance_art.enabled())
            self.assertEqual(instance_art.zone_with_art(SUNSPIRE), "")
        self.assertTrue(instance_art.enabled())

    def test_high_contrast_is_the_systems_preference(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        from gui import instance_art
        hints = QGuiApplication.styleHints()
        self.assertFalse(instance_art.high_contrast())  # the test platform asks for none
        with patch.object(type(hints.accessibility()), "contrastPreference",
                          return_value=Qt.ContrastPreference.HighContrast):
            self.assertTrue(instance_art.high_contrast())
        with patch.object(QGuiApplication, "styleHints", side_effect=AttributeError):
            self.assertFalse(instance_art.high_contrast())  # a Qt that cannot tell

    def test_a_headers_height(self):
        from gui.instance_art import header_height
        self.assertEqual(header_height(30, 16), 44)   # the Windows 11 style, 100%
        self.assertEqual(header_height(16, 16), 44)   # Fusion: the font decides
        self.assertEqual(header_height(46, 32), 88)   # 200% text
        self.assertEqual(header_height(40, 10), 54)   # never less than a row and the extra


class TestHeaderRows(ArtTestCase):
    """The fight list: Sunspire (art), Craglorn (none), Kyne's Aegis (art,
    on the band)."""

    def _list(self, room=260, fights=None):
        """The list, as wide as leaves *room* px for the art after the
        Sunspire header's title: the fonts, and so the title's width and
        the rows', differ from one platform to the next, and a width in
        pixels would test another case on each."""
        from gui.fight_list import FightList
        from tests.unit.test_fight_list_gui import _entry
        lst = FightList()
        self.addCleanup(lst.close)
        lst.resize(900, 400)
        lst.set_fights(fights or [
            _entry("Lokkestiiz"), _entry("Yolnahkriin"),
            _entry("Iron Atronach", "Craglorn", CRAGLORN, "NONE"),
            _entry("Yandir the Butcher", "Kyne's Aegis", KYNES_AEGIS)])
        lst.show()
        self._pump()
        for _ in range(3):  # a scroll bar coming or going changes the viewport
            _image, asked = self._painted(lst)
            wanted = asked[SUNSPIRE][0] + room
            if lst.viewport().width() == wanted:
                break
            lst.resize(lst.width() + wanted - lst.viewport().width(), lst.height())
            self._pump()
        self.assertEqual(lst.viewport().width(), wanted)
        return lst

    def _painted(self, lst):
        """The viewport as painted, and what the delegate asked
        paint_header_art for: {zone: (left, row, whether art was drawn)}."""
        from PySide6.QtCore import QRect

        from gui import instance_art
        asked = {}
        real = instance_art.paint_header_art

        def spy(painter, zone, left, row, ground):
            drawn = real(painter, zone, left, row, ground)
            asked[zone] = (left, QRect(row), drawn)
            return drawn

        with patch.object(instance_art, "paint_header_art", side_effect=spy):
            image = lst.viewport().grab().toImage()
        return image, asked

    def _rows(self, lst):
        """The header rows and their rectangles, cut to the viewport: a
        list narrower than its rows scrolls sideways, and a row's own
        rectangle then reaches past what a picture of the viewport holds."""
        from gui.fight_list import HEADER, KIND_ROLE
        headers = [row for row in range(lst.count()) if lst.item(row).data(KIND_ROLE) == HEADER]
        view = lst.viewport().rect()
        return headers, [lst.visualItemRect(lst.item(row)).intersected(
            view.adjusted(0, -10000, 0, 10000)) for row in headers]

    def test_a_header_carries_its_zone(self):
        from gui.fight_list import ZONE_ROLE
        lst = self._list()
        headers, _rects = self._rows(lst)
        self.assertEqual([lst.item(row).data(ZONE_ROLE) for row in headers],
                         [SUNSPIRE, CRAGLORN, KYNES_AEGIS])
        self.assertIsNone(lst.item(headers[0] + 1).data(ZONE_ROLE))  # a fight row has none
        self.assertEqual(lst.item(headers[0]).text(), "Sunspire · Veteran")  # the item is as it was

    def test_a_header_with_art_is_taller_and_one_without_is_as_before(self):
        from PySide6.QtGui import QFontMetrics

        from gui import instance_art
        lst = self._list()
        headers, rects = self._rows(lst)
        fight = lst.visualItemRect(lst.item(headers[0] + 1)).height()
        line = QFontMetrics(lst.item(headers[0]).font()).height()
        tall = instance_art.header_height(rects[1].height(), line)
        self.assertEqual([rect.height() for rect in rects], [tall, rects[1].height(), tall])
        self.assertGreater(tall, rects[1].height())
        self.assertLessEqual(abs(rects[1].height() - fight), 2)  # a plain header: a row's height

    def test_the_art_is_painted_after_the_title_and_the_title_on_the_ground(self):
        from PySide6.QtGui import QColor, QPalette
        lst = self._list(room=260)
        _headers, rects = self._rows(lst)
        image, asked = self._painted(lst)
        base = lst.palette().color(QPalette.Active, QPalette.Base)
        row = rects[0]
        # The art runs from after the title to the viewport's right edge
        left, in_view, drawn = asked[SUNSPIRE]
        self.assertTrue(drawn)
        self.assertEqual(in_view.right(), lst.viewport().width() - 1)
        self.assertEqual(in_view.right() + 1 - left, 260)
        self.assertEqual(row.right(), image.width() - 1)  # every pixel read below is in the picture
        self.assertNotIn(CRAGLORN, asked)  # a zone without art is left to the style
        # The row's own ground at its left edge: the list's base colour, not
        # the disabled group's grey a header's own palette answers with
        self.assertEqual(QColor(image.pixel(row.left() + 1, row.top() + 1)).name(), base.name())
        # Art over the right of the row
        right = [QColor(image.pixel(x, y))
                 for x in range(row.right() - 120, row.right() - 2, 6)
                 for y in range(row.top() + 4, row.bottom() - 3, 6)]
        painted = sum(1 for colour in right if _differs(colour, base))
        self.assertGreater(painted, 0.8 * len(right))
        # None on the header whose zone has no art: its own ground (the
        # band's, it is the second block) out to the right edge
        plain = rects[1]
        ground = QColor(image.pixel(plain.right() - 1, plain.top() + 1))
        self.assertFalse(any(
            _differs(QColor(image.pixel(x, plain.center().y())), ground, by=2)
            for x in range(plain.right() - 120, plain.right() - 2, 6)))

    def test_a_banded_blocks_header_keeps_the_band_under_its_title(self):
        from PySide6.QtGui import QColor, QPalette

        from gui.fight_list import BLOCK_ROLE, band_color
        lst = self._list()
        headers, rects = self._rows(lst)
        # Craglorn is the banded block here, Kyne's Aegis the third, off it;
        # a list of two art blocks puts the second on the band
        from tests.unit.test_fight_list_gui import _entry
        lst.set_fights([_entry("Lokkestiiz"),
                        _entry("Yandir the Butcher", "Kyne's Aegis", KYNES_AEGIS)])
        self._pump()
        headers, rects = self._rows(lst)
        self.assertEqual(lst.item(headers[1]).data(BLOCK_ROLE), 1)
        image = lst.viewport().grab().toImage()
        palette = lst.palette()
        band = band_color(palette.color(QPalette.Base), palette.color(QPalette.Text))
        self.assertEqual(QColor(image.pixel(rects[1].left() + 1, rects[1].top() + 1)).name(),
                         band.name())
        self.assertTrue(_differs(QColor(image.pixel(rects[1].right() - 20, rects[1].center().y())),
                                 band))

    def test_the_title_is_where_a_plain_headers_is(self):
        """The first inked column of an art header's title is a plain
        header's, so the two line up in one list."""
        from PySide6.QtGui import QColor, QPalette
        lst = self._list()
        _headers, rects = self._rows(lst)
        image = lst.viewport().grab().toImage()
        text = lst.palette().color(QPalette.Active, QPalette.Text)

        def first_ink(rect):
            for x in range(rect.left(), rect.left() + 60):
                for y in range(rect.top() + 2, rect.bottom() - 1):
                    if not _differs(QColor(image.pixel(x, y)), text, by=90):
                        return x
            return None

        # 'S' of Sunspire and 'C' of Craglorn both begin at the text's left
        # edge, within a pixel of each other's side bearing
        self.assertIsNotNone(first_ink(rects[0]))
        self.assertLessEqual(abs(first_ink(rects[0]) - first_ink(rects[1])), 1)

    def test_too_little_room_draws_no_art(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage, QPainter

        from gui import instance_art
        canvas = QImage(400, 44, QImage.Format_RGB32)
        canvas.fill(QColor("white"))
        painter = QPainter(canvas)
        row = QRect(0, 0, 400, 44)
        short = 400 - instance_art.MIN_ART_WIDTH + 1
        self.assertFalse(instance_art.paint_header_art(painter, SUNSPIRE, short, row, QColor("white")))
        self.assertFalse(instance_art.paint_header_art(painter, CRAGLORN, 100, row, QColor("white")))
        self.assertEqual(QColor(canvas.pixel(399, 22)).name(), "#ffffff")
        self.assertTrue(instance_art.paint_header_art(painter, SUNSPIRE, 100, row, QColor("white")))
        painter.end()
        # The art fades in from the ground: its first column is the ground
        self.assertFalse(_differs(QColor(canvas.pixel(100, 22)), QColor("white"), by=4))
        self.assertTrue(_differs(QColor(canvas.pixel(398, 22)), QColor("white")))
        self.assertEqual(QColor(canvas.pixel(99, 22)).name(), "#ffffff")  # nothing before it

    def test_a_narrow_list_keeps_the_header_and_drops_the_art(self):
        from PySide6.QtGui import QColor, QPalette

        from gui import instance_art
        lst = self._list(room=instance_art.MIN_ART_WIDTH - 1)
        _headers, rects = self._rows(lst)
        tall = rects[0].height()
        image, asked = self._painted(lst)
        self.assertFalse(asked[SUNSPIRE][2])  # one pixel short of the least room
        base = lst.palette().color(QPalette.Active, QPalette.Base)
        row = rects[0]
        for x in range(asked[SUNSPIRE][0], image.width(), 7):
            self.assertFalse(_differs(QColor(image.pixel(x, row.top() + 2)), base, by=2), x)
        self.assertGreater(tall, rects[1].height())  # the header keeps its height
        # With exactly the least room the art is there
        wide = self._list(room=instance_art.MIN_ART_WIDTH)
        image, asked = self._painted(wide)
        self.assertTrue(asked[SUNSPIRE][2])
        row = self._rows(wide)[1][0]
        self.assertTrue(_differs(QColor(image.pixel(image.width() - 3, row.center().y())), base))

    def test_a_list_that_scrolls_sideways_cuts_the_art_to_the_room_in_view(self):
        """A row wider than the viewport makes every row's rectangle that
        wide. The art ends at the viewport's edge all the same, follows the
        title as the list is scrolled, and starts at the viewport's left
        edge once the title has scrolled out."""
        from PySide6.QtGui import QColor, QPalette

        from tests.unit.test_fight_list_gui import _entry
        lst = self._list(room=300, fights=[_entry("Lokkestiiz"),
                                           _entry("A boss with a very long name " * 12)])
        bar = lst.horizontalScrollBar()
        self.assertGreater(bar.maximum(), 300)
        header = lst.item(0)
        edge = lst.viewport().width() - 1
        self.assertGreater(lst.visualItemRect(header).right(), edge + 300)  # the row runs on
        image, asked = self._painted(lst)
        left, in_view, drawn = asked[SUNSPIRE]
        self.assertTrue(drawn)
        self.assertEqual((in_view.right(), in_view.right() + 1 - left), (edge, 300))
        base = lst.palette().color(QPalette.Active, QPalette.Base)
        row = self._rows(lst)[1][0]
        # At the viewport's edge the art is at full strength, not at the
        # faint start of a fade that runs on out of sight
        self.assertTrue(_differs(QColor(image.pixel(edge - 2, row.center().y())), base, by=40))
        for scrolled in (40, bar.maximum()):  # at the last the title is out of view
            bar.setValue(scrolled)
            self._pump()
            _image, asked = self._painted(lst)
            now_left, now_in_view, now_drawn = asked[SUNSPIRE]
            self.assertEqual((now_left, now_in_view.right(), now_drawn),
                             (max(0, left - scrolled), edge, True))

    def test_a_sideways_scroll_paints_the_viewport_again(self):
        """Qt scrolls a list by moving the pixels it has; art cut to the
        room in view has to be painted again."""
        from gui.fight_list import FightList
        from tests.unit.test_fight_list_gui import _entry
        with patch.object(FightList, "_repaint_art", autospec=True) as again:
            lst = FightList()
            self.addCleanup(lst.close)
            lst.resize(300, 300)
            lst.set_fights([_entry("A boss with a very long name " * 12)])
            lst.show()
            self._pump()
            again.reset_mock()
            lst.horizontalScrollBar().setValue(25)
            self.assertTrue(again.called)

    def test_the_setting_off_gives_plain_headers_and_on_brings_the_art_back(self):
        from gui import instance_art
        lst = self._list()
        _headers, rects = self._rows(lst)
        tall, plain = rects[0].height(), rects[1].height()
        instance_art.set_enabled(False)
        lst.refresh_art()
        self._pump()
        self.assertEqual([rect.height() for rect in self._rows(lst)[1]], [plain] * 3)
        instance_art.set_enabled(True)
        lst.refresh_art()
        self._pump()
        self.assertEqual([rect.height() for rect in self._rows(lst)[1]], [tall, plain, tall])

    def test_high_contrast_gives_plain_headers(self):
        from gui import instance_art
        lst = self._list()
        self.assertGreater(len({rect.height() for rect in self._rows(lst)[1]}), 1)
        with patch.object(instance_art, "high_contrast", return_value=True):
            lst.refresh_art()
            self._pump()
            self.assertEqual(len({rect.height() for rect in self._rows(lst)[1]}), 1)
            _image, asked = self._painted(lst)
            self.assertEqual(asked, {})

    def test_a_click_on_a_header_with_art_still_opens_its_instance(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        lst = self._list()
        headers, rects = self._rows(lst)
        asked = []
        lst.instance_requested.connect(asked.append)
        on_the_art = rects[0].center()
        on_the_art.setX(lst.viewport().width() - 30)
        QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, on_the_art)
        self.assertEqual(asked, [headers[0]])

    def test_the_delegate_holds_nothing_of_the_list(self):
        lst = self._list()
        delegate = lst.itemDelegate()
        self.assertIs(delegate.parent(), lst)
        # No Python reference back to the list: the pair would be a cycle,
        # freed by the garbage collector on whichever thread it runs
        self.assertFalse(any(value is lst for value in vars(delegate).values()))


class TestTheStrip(ArtTestCase):
    """The Instance page's strip, on a FightView."""

    PAGE = ("<p style='margin:0;font-size:1pt'>&nbsp;</p>"
            "<p style='margin-top:126px;margin-bottom:0'>Heading</p>" + "<p>line</p>" * 60)

    def _view(self):
        from gui.fight_view import FightView
        view = FightView()
        self.addCleanup(view.close)
        view.resize(600, 300)
        view.show()
        return view

    def test_the_art_asked_for_is_painted_across_the_pages_top(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QPalette

        from gui import instance_art
        view = self._view()
        view.set_art(SUNSPIRE)
        view.setHtml(self.PAGE)
        self._pump()
        margin = round(view.document().documentMargin())
        self.assertEqual(view.art_rect(), QRect(margin, margin, view.viewport().width() - 2 * margin,
                                                instance_art.STRIP_HEIGHT))
        image = view.viewport().grab().toImage()
        base = view.palette().color(QPalette.Active, QPalette.Base)
        inside = [QColor(image.pixel(x, y)) for x in range(20, image.width() - 20, 20)
                  for y in range(margin + 6, margin + instance_art.STRIP_HEIGHT - 6, 12)]
        self.assertGreater(sum(1 for colour in inside if _differs(colour, base)), 0.9 * len(inside))
        # Nothing under the strip but the page, and no sideways scroll
        self.assertFalse(_differs(QColor(image.pixel(image.width() - 30,
                                                     margin + instance_art.STRIP_HEIGHT + 3)), base))
        self.assertEqual(view.horizontalScrollBar().maximum(), 0)

    def test_it_moves_with_the_page_and_follows_its_width(self):
        from gui import instance_art
        view = self._view()
        view.set_art(SUNSPIRE)
        view.setHtml(self.PAGE)
        self._pump()
        top = view.art_rect().top()
        view.verticalScrollBar().setValue(50)
        self.assertEqual(view.art_rect().top(), top - 50)
        view.verticalScrollBar().setValue(0)
        view.resize(900, 300)
        self._pump()
        margin = round(view.document().documentMargin())
        self.assertEqual(view.art_rect().width(), view.viewport().width() - 2 * margin)
        self.assertEqual(view.art_rect().height(), instance_art.STRIP_HEIGHT)
        self.assertEqual(view.horizontalScrollBar().maximum(), 0)

    def test_a_page_that_does_not_ask_has_none(self):
        view = self._view()
        view.set_art(SUNSPIRE)
        view.setHtml(self.PAGE)
        self.assertFalse(view.art_rect().isEmpty())
        view.setHtml("<p>another page</p>")  # set with no asking
        self.assertTrue(view.art_rect().isEmpty())
        view.set_art(SUNSPIRE)
        view.setHtml(self.PAGE)
        view.clear()
        self.assertTrue(view.art_rect().isEmpty())
        view.set_art(SUNSPIRE)
        view.clear()                          # an asking never used
        view.setHtml("<p>another page</p>")
        self.assertTrue(view.art_rect().isEmpty())

    def test_a_page_without_art_is_painted_as_before(self):
        from PySide6.QtGui import QColor, QPalette
        view = self._view()
        view.setHtml("<p>plain</p>")
        self._pump()
        image = view.viewport().grab().toImage()
        base = view.palette().color(QPalette.Active, QPalette.Base)
        self.assertFalse(_differs(QColor(image.pixel(image.width() - 30, 60)), base))

    def test_the_strip_says_nothing_to_a_screen_reader_or_the_search(self):
        view = self._view()
        view.set_art(SUNSPIRE)
        view.setHtml(self.PAGE)
        self.assertTrue(view.accessible_text().startswith("Heading"))
        self.assertNotIn("￼", view.toPlainText())


class TestTheInstancePage(ArtTestCase):

    def _block(self):
        from tests.unit.test_instance_tab_gui import _session
        return _session()[:4]  # the Kyne's Aegis fights

    def test_the_page_leaves_room_only_when_asked(self):
        import re

        from gui import instance_art
        from gui.instance_render import render_instance_html
        block = self._block()
        plain = render_instance_html(block, lambda fight: None)
        roomy = render_instance_html(block, lambda fight: None, art_space=instance_art.STRIP_SPACE)
        self.assertTrue(plain.startswith("<p style='margin:0'><span"))
        self.assertNotIn("margin-top", plain.split("</p>")[0])
        self.assertTrue(roomy.startswith(
            "<p style='margin:0;font-size:1pt'>&nbsp;</p>"
            f"<p style='margin-top:{instance_art.STRIP_SPACE}px;margin-bottom:0'><span"))
        # Nothing else differs
        self.assertEqual(roomy.split("<span", 1)[1], plain.split("<span", 1)[1])
        self.assertEqual(re.sub(r"<[^>]+>", "", roomy).replace("&nbsp;", "", 1),
                         re.sub(r"<[^>]+>", "", plain))

    def test_the_heading_starts_under_the_strip(self):
        from gui import instance_art
        from gui.fight_view import FightView
        from gui.instance_render import render_instance_html
        view = FightView()
        self.addCleanup(view.close)
        view.resize(900, 500)
        view.show()
        view.set_art(KYNES_AEGIS)
        view.setHtml(render_instance_html(self._block(), lambda fight: None,
                                          art_space=instance_art.STRIP_SPACE))
        self._pump()
        document = view.document()
        heading = document.findBlockByNumber(1)
        self.assertIn("Kyne's Aegis", heading.text())
        top = document.documentLayout().blockBoundingRect(heading).top()
        self.assertGreaterEqual(top, view.art_rect().bottom() + 1)
        self.assertLess(top, view.art_rect().bottom() + 1 + instance_art.STRIP_GAP + 12)


class TestTheWindow(ArtTestCase):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _config(self, **display):
        from app_config import AppConfig
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        for key, value in display.items():
            config.set(f"display.{key}", value)
        return config

    def _window(self, config, *entries):
        from gui.main_window import MainWindow
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.addCleanup(win.close)
        win.resize(1080, 720)
        win.show()
        self.app.processEvents()
        for entry in entries:
            win._on_fight_completed(entry)
        self._pump()
        return win

    def _entries(self):
        from tests.unit.test_fight_list_gui import _entry
        return [_entry("Lokkestiiz"), _entry("Iron Atronach", "Craglorn", CRAGLORN, "NONE")]

    def test_it_is_on_for_a_new_install_and_read_at_start(self):
        from app_config import AppConfig
        from gui import instance_art
        self.assertIs(AppConfig(path=self.root / "new.json").get("display.instance_art"), True)
        self._window(self._config(instance_art=False))
        self.assertFalse(instance_art.enabled())
        self._window(self._config())
        self.assertTrue(instance_art.enabled())

    def test_the_settings_box_writes_it(self):
        from gui.settings_dialog import SettingsDialog
        config = self._config()
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.instance_art.isChecked())
        self.assertTrue(dialog.instance_art.accessibleDescription())  # its help is read with it
        dialog.instance_art.setChecked(False)
        dialog.apply_to_config()
        self.assertIs(config.get("display.instance_art"), False)

    def test_the_instance_page_has_the_strip_for_a_zone_with_art_only(self):
        from gui import instance_art
        lokkestiiz, atronach = self._entries()
        win = self._window(self._config(), lokkestiiz, atronach)
        win.history_list.select_entry(lokkestiiz)
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._pump()
        self.assertEqual(win.instance_view.art_rect().height(), instance_art.STRIP_HEIGHT)
        self.assertIn("Sunspire", win.instance_view.document().findBlockByNumber(1).text())
        win.history_list.select_entry(atronach)   # Craglorn: no art, no room left
        self._pump()
        self.assertTrue(win.instance_view.art_rect().isEmpty())
        self.assertIn("Craglorn", win.instance_view.document().findBlockByNumber(0).text())

    def test_saving_the_setting_off_takes_the_art_away_and_on_brings_it_back(self):
        from gui import instance_art
        from gui.fight_list import HEADER, KIND_ROLE
        from gui.settings_dialog import SettingsDialog
        lokkestiiz, _atronach = self._entries()
        config = self._config()
        win = self._window(config, lokkestiiz)
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._pump()
        lst = win.history_list
        header = next(lst.item(row) for row in range(lst.count())
                      if lst.item(row).data(KIND_ROLE) == HEADER)
        tall = lst.visualItemRect(header).height()
        self.assertFalse(win.instance_view.art_rect().isEmpty())

        def save(on):
            class Settings:
                Accepted = SettingsDialog.Accepted

                def __init__(self, config, *_args, **_kwargs):
                    self.config = config

                def exec(self):
                    return self.Accepted

                def apply_to_config(self):
                    self.config.set("display.instance_art", on)

                def deleteLater(self):
                    pass
            with patch("gui.main_window.SettingsDialog", Settings):
                win._open_settings()
            self._pump()

        save(False)
        self.assertFalse(instance_art.enabled())
        self.assertLess(lst.visualItemRect(header).height(), tall)
        self.assertTrue(win.instance_view.art_rect().isEmpty())
        self.assertIs(lst.current_entry(), lokkestiiz)  # the fight on screen stays
        save(True)
        self.assertEqual(lst.visualItemRect(header).height(), tall)
        self.assertFalse(win.instance_view.art_rect().isEmpty())

    def test_the_system_turning_high_contrast_on_takes_the_art_away_at_once(self):
        """With the app open: the list's headers and the Instance page's
        strip go together, and come back together."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        from gui import instance_art
        from gui.fight_list import HEADER, KIND_ROLE
        lokkestiiz, _atronach = self._entries()
        win = self._window(self._config(), lokkestiiz)
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._pump()
        lst = win.history_list
        header = next(lst.item(row) for row in range(lst.count())
                      if lst.item(row).data(KIND_ROLE) == HEADER)
        tall = lst.visualItemRect(header).height()
        changed = QGuiApplication.styleHints().accessibility().contrastPreferenceChanged
        with patch.object(instance_art, "high_contrast", return_value=True):
            changed.emit(Qt.ContrastPreference.HighContrast)  # the system's own signal
            self._pump()
            self.assertLess(lst.visualItemRect(header).height(), tall)
            self.assertTrue(win.instance_view.art_rect().isEmpty())
            self.assertIn("Sunspire", win.instance_view.document().findBlockByNumber(0).text())
        changed.emit(Qt.ContrastPreference.NoPreference)
        self._pump()
        self.assertEqual(lst.visualItemRect(header).height(), tall)
        self.assertFalse(win.instance_view.art_rect().isEmpty())

    def test_a_page_that_fails_to_render_leaves_no_asking_behind(self):
        lokkestiiz, _atronach = self._entries()
        win = self._window(self._config(), lokkestiiz)
        with (patch("gui.main_window.render_instance_html", side_effect=RuntimeError("no page")),
              self.assertRaises(RuntimeError)):
            win._draw_instance(lokkestiiz)
        win.instance_view.setHtml("<p>the next page set, with no room left for art</p>")
        self.assertTrue(win.instance_view.art_rect().isEmpty())


if __name__ == "__main__":
    unittest.main()
