#!/usr/bin/env python3
"""The fonts the app asks for by name, chosen per platform (issue #32).

Two places name a font: the death chip's skull (gui.glyphs) and the fixed
font of the rule editor and the examples list (gui.text_size). Both named
Windows fonts first. Measured on macOS 27.2 with PySide6 6.12.0, under the
cocoa plugin and offscreen alike: the first font asked for whose family is
not installed makes Qt search every installed font and log

    Populating font family aliases took 49 ms. Replace uses of missing font
    family "Segoe UI Symbol" with one that exists to avoid this cost.

Qt searches once in a process, so the line names only the first missing
family, and a test of it needs a process of its own: by the time a test
runs in the suite's process, an earlier test has asked for a font the Mac
lacks and the search is done.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QColor, QFont, QFontInfo
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_AND_LINUX_SKULL = ['Segoe UI Symbol', 'DejaVu Sans', 'Noto Sans Symbols2']
# Every family name another platform is asked for: none may reach macOS
ELSEWHERE = set(WINDOWS_AND_LINUX_SKULL) | {'Consolas'}

# The two fonts the app names, built and drawn with, and Qt's log lines
# printed one to a line after a marker. Any family names after the folder
# are asked for last: the test's control.
#
# The process runs offscreen, as the suite does, and the offscreen plugin
# has names of its own that macOS lacks: "Sans Serif" for the application
# font and "Monospace" for a page's <code>. Qt logs the first of them it
# meets and, having searched once, is silent about any family the app
# names later. So the application font is set to the one macOS names for
# titles (the cocoa plugin's own default), and the main window is not
# built here: its start page has a <code>. Under cocoa the whole app (the
# main window, Settings, Examples) logged nothing, run by hand on
# 2026-11-16.
_LOG_SCRIPT = r"""
import sys
from pathlib import Path
root, extra = Path(sys.argv[1]), sys.argv[2:]
sys.path[:0] = [str(root / "src")]
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication, QPlainTextEdit
lines = []
qInstallMessageHandler(lambda kind, context, text: lines.append(text))
app = QApplication([])
app.setFont(QFontDatabase.systemFont(QFontDatabase.TitleFont))
from gui import glyphs, text_size
from gui.fight_render import DEATHS_GLYPH

for dpr in (1.0, 2.0):
    assert glyphs.glyph_image(DEATHS_GLYPH, "#1a73e8", 13, dpr) is not None
# As the rule editor and the examples list use it
editor = QPlainTextEdit("Major Breach = 61743 on boss")
editor.setFont(text_size.fixed_font())
editor.show()
app.processEvents()
for family in extra:
    QFontInfo(QFont(family)).family()
print("QT-LOG-FOLLOWS")
for line in lines:
    print(line.replace("\n", " "))
"""


def _qt_log(*extra_families) -> list[str]:
    """Qt's log lines from a process that builds the app's fonts."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    done = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", _LOG_SCRIPT, str(ROOT), *extra_families],
        env=env, capture_output=True, text=True, timeout=180, check=False)
    if done.returncode != 0 or "QT-LOG-FOLLOWS" not in done.stdout:
        raise AssertionError(f"the font process failed ({done.returncode}): {done.stderr[-2000:]}")
    return done.stdout.split("QT-LOG-FOLLOWS", 1)[1].strip().splitlines()


class TestTheNamesByPlatform(unittest.TestCase):
    """Which families are asked for where; the platform is passed or stood
    in for, so every platform's CI checks every platform's list."""

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_skulls_fonts_on_windows_and_linux_are_what_they_were(self):
        from gui import glyphs
        for platform in ("win32", "linux"):
            self.assertEqual(glyphs.skull_families(platform), WINDOWS_AND_LINUX_SKULL, platform)

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_skulls_font_on_macos_is_apple_symbols_alone(self):
        from gui import glyphs
        self.assertEqual(glyphs.skull_families("darwin"), ["Apple Symbols"])
        self.assertFalse(ELSEWHERE & set(glyphs.skull_families("darwin")))

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_skulls_fonts_follow_the_running_platform(self):
        from gui import glyphs
        for platform, families in (("darwin", ["Apple Symbols"]), ("win32", WINDOWS_AND_LINUX_SKULL),
                                   ("linux", WINDOWS_AND_LINUX_SKULL)):
            with mock.patch.object(glyphs.sys, "platform", platform):
                self.assertEqual(glyphs.skull_families(), families, platform)

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_skull_is_drawn_with_the_platforms_list_then_the_system_font(self):
        """What the painter's font is given, not only what the list says:
        the platform's families, then the system font's, which is where a
        machine without any of them finds its skull."""
        from gui import glyphs
        from gui.fight_render import DEATHS_GLYPH
        QApplication.instance() or QApplication([])
        system = QFont().family()
        for platform, families in (("darwin", ["Apple Symbols"]), ("win32", WINDOWS_AND_LINUX_SKULL),
                                   ("linux", WINDOWS_AND_LINUX_SKULL)):
            asked = []

            class Recorder(QFont):
                def setFamilies(self, names):
                    asked.append(list(names))
                    super().setFamilies(names)

            with mock.patch.object(glyphs.sys, "platform", platform), \
                    mock.patch.object(glyphs, "QFont", Recorder):
                # _draw, not glyph_image: an image drawn before is kept
                image = glyphs._draw(DEATHS_GLYPH, QColor("#1a73e8"), 13, 1.0)
            self.assertEqual(asked, [families + [system]], platform)
            self.assertFalse(image.isNull())

    def test_the_fixed_family_by_platform(self):
        from gui import text_size
        self.assertEqual(text_size.fixed_family("darwin"), "Menlo")
        self.assertEqual(text_size.fixed_family("win32"), "Consolas")
        self.assertEqual(text_size.fixed_family("linux"), "Consolas")
        for platform, family in (("darwin", "Menlo"), ("win32", "Consolas"), ("linux", "Consolas")):
            with mock.patch.object(text_size.sys, "platform", platform):
                self.assertEqual(text_size.fixed_family(), family, platform)

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_fixed_font_asks_for_its_platforms_family_and_no_other(self):
        """fixed_font looks one family up by name. On macOS that is Menlo,
        and Consolas is never asked for; elsewhere it is Consolas, as it
        was. The names it builds a QFont from are recorded."""
        from PySide6 import QtGui

        from gui import text_size
        QApplication.instance() or QApplication([])
        for platform, family in (("darwin", "Menlo"), ("win32", "Consolas"), ("linux", "Consolas")):
            asked = []

            class Recorder(QFont):
                def __init__(self, *args):
                    asked.extend(arg for arg in args if isinstance(arg, str))
                    super().__init__(*args)

            with mock.patch.object(text_size.sys, "platform", platform), \
                    mock.patch.object(QtGui, "QFont", Recorder):
                font = text_size.fixed_font()
            self.assertEqual(asked, [family], platform)
            # Set only where it is installed; else the system's fixed font
            if platform == sys.platform and QFontInfo(QFont(family)).family() == family:
                self.assertEqual(font.family(), family)


@unittest.skipUnless(HAVE_QT and sys.platform == "darwin", "the fonts macOS has")
class TestOnMacOS(unittest.TestCase):

    def test_the_fonts_asked_for_are_installed(self):
        """Apple Symbols and Menlo ship with macOS; Apple Symbols has the
        skull, so it is drawn as an outline the pen colours and not by the
        colour emoji font."""
        from PySide6.QtGui import QRawFont

        from gui import glyphs, text_size
        from gui.death_render import SKULL
        QApplication.instance() or QApplication([])
        for family in glyphs.skull_families():
            self.assertEqual(QFontInfo(QFont(family)).family(), family)
            self.assertTrue(QRawFont.fromFont(QFont(family)).supportsCharacter(ord(SKULL[0])), family)
        # Offscreen, the system's fixed font is the name "monospace", which
        # macOS resolves to its proportional system font: Menlo is set
        fixed = text_size.fixed_font()
        self.assertEqual(fixed.family(), "Menlo")
        self.assertTrue(QFontInfo(fixed).fixedPitch())

    def test_the_apps_fonts_log_no_missing_font_family(self):
        """The skull and the fixed font, built and drawn with in a process
        of its own (the module notes): Qt's log names no missing family,
        Segoe UI Symbol, Consolas or any other."""
        lines = _qt_log()
        missing = [line for line in lines if "missing font family" in line]
        self.assertEqual(missing, [])
        for name in ELSEWHERE:
            self.assertFalse([line for line in lines if name in line], name)

    def test_a_missing_family_does_reach_the_log(self):
        """The control for the test above: the same process, asked at its
        end for a family macOS lacks, logs the line that test looks for,
        naming that family. So Qt still logs it, and nothing the app built
        before had spent Qt's one search on a missing family of its own.
        Without this, a Qt that stopped logging the line would pass for a
        fix."""
        lines = [line for line in _qt_log("Segoe UI Symbol") if "missing font family" in line]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn('"Segoe UI Symbol"', lines[0])


if __name__ == '__main__':
    unittest.main()
