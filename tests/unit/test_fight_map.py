#!/usr/bin/env python3
"""The fight's map (issue #148): the header's thumbnails and their hover
(fight_render), the pictures (gui.fight_map), the fight view serving them
and the window they open (gui.map_window), offscreen."""

import os
import unittest
from array import array

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fight_history import FightHistoryEntry  # noqa: E402
from gui.fight_render import (  # noqa: E402
    MAP_HREF, MAP_LINES, MAP_SCHEME, map_alt, map_index_from_href, map_thumb_px, map_tooltips,
    render_html, render_plain_text, shown_maps,
)

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


VLC = "deadlands/u42tri_lucentcitmap001"


def _map(path=VLC, name="Lucent Citadel", seconds=60, xy=(5000, 5000, 5100, 5100)):
    return {"path": path, "map_id": "2552", "name": name, "xy": array("H", xy),
            "seconds": seconds, "first_s": 0.0}


def _entry(maps):
    entry = FightHistoryEntry()
    entry.zone_name = "Lucent Citadel"
    entry.boss_name = "Xoryn"
    entry.duration_s = 120.0
    entry.positions = maps
    return entry


class TestHeader(unittest.TestCase):

    def test_a_thumbnail_links_to_the_window(self):
        page = render_html(_entry([_map()]), detailed=True, line_px=16)
        px = 16 * MAP_LINES
        self.assertIn(f'<a href="{MAP_HREF}0"><img src="{MAP_SCHEME}:0?px={px}&amp;k=', page)
        self.assertIn('alt="Map of Lucent Citadel, where the group stood"', page)

    def test_no_positions_no_map(self):
        for maps in (None, []):
            page = render_html(_entry(maps), detailed=True)
            self.assertNotIn(f"{MAP_SCHEME}:", page)
        self.assertNotIn("Map", render_plain_text(_entry([_map()])))

    def test_one_thumbnail_per_map_the_group_stayed_on(self):
        maps = [_map(name="Vestibule", seconds=15), _map(name="Passing", seconds=2),
                _map(name="Temple Grounds", seconds=90)]
        self.assertEqual([i for i, _ in shown_maps(_entry(maps))], [0, 2])
        page = render_html(_entry(maps), detailed=True, line_px=16)
        self.assertIn(f'href="{MAP_HREF}2"', page)
        self.assertNotIn(f'href="{MAP_HREF}1"', page)
        self.assertIn("Map 2 of 2, Temple Grounds, where the group stood for 1:30", page)

    def test_a_short_fight_still_shows_its_map(self):
        self.assertEqual([i for i, _ in shown_maps(_entry([_map(seconds=1)]))], [0])

    def test_several_thumbnails_share_the_width(self):
        one = map_thumb_px(1, 16)
        self.assertEqual(one, 16 * MAP_LINES)
        self.assertEqual(map_thumb_px(2, 16), round(one * 0.8))
        self.assertEqual(map_thumb_px(4, 16), round(one * 0.5))

    def test_the_hover_names_the_map_and_a_missing_art(self):
        tips = map_tooltips(_entry([_map(), _map(path="glenumbra/daggerfall_base",
                                                  name="Daggerfall")]))
        self.assertIn("1:00 on this map", tips[f"{MAP_HREF}0"])
        self.assertNotIn("No map art", tips[f"{MAP_HREF}0"])
        self.assertIn("No map art for glenumbra/daggerfall_base", tips[f"{MAP_HREF}1"])

    def test_hrefs(self):
        self.assertEqual(map_index_from_href(f"{MAP_HREF}3"), 3)
        self.assertIsNone(map_index_from_href("esolog:graph/"))
        self.assertEqual(map_alt(_map(name="")), "Map of the fight's map, where the group stood")


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestPictures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_a_picture_is_the_size_asked_at_the_ratio_asked(self):
        from gui.fight_map import map_image
        image = map_image(_map(), 100, 2.0)
        self.assertEqual((image.width(), image.height()), (200, 200))
        self.assertEqual(image.devicePixelRatio(), 2.0)

    def test_pictures_are_cached_per_size_and_view(self):
        from gui.fight_map import map_image
        record = _map()
        self.assertIs(map_image(record, 80), map_image(record, 80))
        self.assertIsNot(map_image(record, 80), map_image(record, 80, whole=True))

    def test_a_map_without_art_is_a_plain_grid(self):
        from gui.fight_map import PLAIN_BACKGROUND, map_image
        # The whole map at 200 px: a line every 10 px, the background between
        image = map_image(_map(path="glenumbra/daggerfall_base", xy=()), 200)
        self.assertEqual(image.pixelColor(15, 15).rgb(), PLAIN_BACKGROUND.rgb())
        self.assertNotEqual(image.pixelColor(100, 15).rgb(), PLAIN_BACKGROUND.rgb())

    def test_the_ramp_darkens_with_the_heat(self):
        from gui.fight_map import heat_color
        low, high = heat_color(0.1), heat_color(1.0)
        self.assertLess(high.lightness(), low.lightness())
        self.assertGreater(high.alphaF(), low.alphaF())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestViewAndWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def test_the_view_serves_the_map_and_reports_a_click(self):
        from gui.fight_view import FightView
        view = FightView()
        view.set_fight_maps([_map()])
        image = view.loadResource(QTextDocument.ImageResource, QUrl(f"{MAP_SCHEME}:0?px=50&k=1"))
        self.assertEqual(image.width(), round(50 * view.devicePixelRatioF()))
        clicked = []
        view.map_requested.connect(clicked.append)
        view.anchorClicked.emit(QUrl(f"{MAP_HREF}0"))
        self.assertEqual(clicked, [0])
        view.deleteLater()

    def test_the_window_has_a_tab_per_map_at_the_one_clicked(self):
        from gui.map_window import MapDialog
        dialog = MapDialog()
        maps = [_map(name="Vestibule"), _map(path="glenumbra/daggerfall_base", name="Daggerfall")]
        dialog.show_maps(_entry(maps), 1)
        self.assertEqual(dialog.tabs.count(), 2)
        self.assertEqual(dialog.tabs.currentIndex(), 1)
        self.assertEqual(dialog.tabs.tabText(0), "1. Vestibule")
        self.assertIn("No map art for glenumbra/daggerfall_base", dialog.note.text())
        dialog.whole.setChecked(True)
        self.assertTrue(all(canvas.whole for canvas in dialog.canvases()))
        # The switch holds for the next fight
        dialog.show_maps(_entry([_map()]), 0)
        self.assertTrue(dialog.canvases()[0].whole)
        self.assertTrue(dialog.tabs.tabBar().isHidden() or dialog.tabs.tabBarAutoHide())
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
