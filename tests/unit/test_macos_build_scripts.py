#!/usr/bin/env python3
"""The macOS build's scripts (issue #32): the start-up smoke test of the
built app (scripts/smoke_macos.py, run here against stand-in programs), the
check of each binary's minimum macOS (scripts/check_macos_stamps.py) and
the icon's rounded-square plate (scripts/create_icon.py)."""

import importlib.util
import plistlib
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke_macos = _load('smoke_macos.py')
stamps = _load('check_macos_stamps.py')

# What every stand-in starts with: where the app would write its crash.log
_STAND_IN_HEAD = '''
    import os, sys, time
    from pathlib import Path
    config = Path(os.environ["HOME"]) / "Library" / "Application Support" / "esolog-tail"
    crash = config / "crash.log"
'''


class TestSmokeVerdict(unittest.TestCase):
    """smoke() on programs that behave as a built app could."""

    # The wait for a stand-in that must write its file before the wait
    # ends: long enough for Python to start on a slow CI machine (a cold
    # Windows runner can take seconds)
    SECONDS = 5

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.folder = Path(self._folder.name)

    def _run(self, body: str, seconds=None):
        program = self.folder / "stand_in.py"
        program.write_text(textwrap.dedent(_STAND_IN_HEAD) + textwrap.dedent(body),
                           encoding="utf-8")
        home = self.folder / "home"
        return smoke_macos.smoke([sys.executable, str(program)],
                                 seconds=self.SECONDS if seconds is None else seconds,
                                 home=home)

    def test_an_app_that_stays_up_passes(self):
        # It prints far more than a pipe holds before it writes crash.log:
        # with its output on a pipe nobody reads, it would block there and
        # the missing crash.log would fail it
        problem, report = self._run('''
            print((config / "config.json").read_text())
            sys.stdout.write("x" * 1_000_000)
            sys.stdout.flush()
            crash.write_text("--- session ---\\n")
            time.sleep(60)
        ''')
        self.assertEqual(problem, "", report)
        self.assertIn("still running after 5 s: True", report)
        # The config it was given: the fixture log, and no update check
        self.assertIn("golden_fight.log", report)
        self.assertIn('"check_enabled": false', report)

    def test_an_app_that_exits_early_fails(self):
        # The wait ends when the program does, so a long one costs nothing
        problem, report = self._run('''
            crash.write_text("--- session ---\\n")
            print("could not start")
            sys.exit(3)
        ''', seconds=60)
        self.assertIn("exited (status 3)", problem)
        self.assertIn("could not start", report)

    def test_an_app_that_logs_a_crash_fails_though_it_stays_up(self):
        problem, report = self._run('''
            crash.write_text("--- session ---\\n[10:00:00] Unhandled exception:\\nTraceback\\n")
            time.sleep(60)
        ''')
        self.assertIn("logged a crash", problem)
        self.assertIn("Traceback", report)

    def test_an_app_that_never_writes_its_crash_log_fails(self):
        # Up, but Python's start-up was never reached (a hung bootloader).
        # Nothing has to be written in time, so the wait is short
        problem, report = self._run('time.sleep(60)', seconds=1)
        self.assertIn("no crash.log", problem)
        self.assertIn("(none)", report)

    def test_the_verdict(self):
        verdict = smoke_macos.verdict
        session = "--- session 2026-11-16 10:00:00 ---\n"
        self.assertEqual(verdict(True, None, session), "")
        self.assertEqual(verdict(True, None, session, "Scanning recent log entries"), "")
        self.assertIn("exited (status -11)", verdict(False, -11, session))
        self.assertIn("no crash.log", verdict(True, None, None))
        for mark in smoke_macos.CRASH_MARKS:
            with self.subTest(mark=mark):
                self.assertIn("crash.log", verdict(True, None, session + mark + ": ..."))
                # Printed before crash.log was opened
                self.assertIn("its output", verdict(True, None, session, mark + ": ..."))

    def test_the_fixture_log_exists(self):
        self.assertTrue(smoke_macos.FIXTURE_LOG.is_file())

    def test_a_failure_is_exit_1_with_an_annotation(self):
        program = self.folder / "gone.py"
        program.write_text("raise SystemExit(4)", encoding="utf-8")
        # main() takes one executable, so the stand-in is run through a
        # launcher only where a script can be executed directly
        if sys.platform == "win32":
            self.skipTest("needs an executable script")
        launcher = self.folder / "launcher"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{program}"\n', encoding="utf-8")
        launcher.chmod(0o755)
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = smoke_macos.main([str(launcher), "--seconds", "2"])
        self.assertEqual(status, 1)
        self.assertIn("::error::the app exited (status 4)", out.getvalue())


# `otool -l` on a thin arm64 binary built with a current linker
_BUILD_VERSION = '''
Load command 10
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos 14.4
      sdk 15.0
   ntools 1
     tool 3
  version 1115.7.3
'''
# ... and on one built with an old one
_VERSION_MIN = '''
Load command 8
      cmd LC_VERSION_MIN_MACOSX
  cmdsize 16
  version 10.13
      sdk 10.15
Load command 9
      cmd LC_SOURCE_VERSION
  cmdsize 16
  version 0.0
'''


class TestMinimumMacOS(unittest.TestCase):

    def test_the_stamp_is_read_from_either_load_command(self):
        self.assertEqual(stamps.min_macos(_BUILD_VERSION), "14.4")
        self.assertEqual(stamps.min_macos(_VERSION_MIN), "10.13")

    def test_the_tool_and_source_versions_are_not_the_stamp(self):
        # "version 1115.7.3" (the linker) and "version 0.0" (the source) sit
        # in the same output
        self.assertEqual(stamps.min_macos(_BUILD_VERSION), "14.4")
        self.assertEqual(stamps.min_macos(_VERSION_MIN), "10.13")

    def test_a_fat_file_gives_its_highest(self):
        both = _BUILD_VERSION + _BUILD_VERSION.replace("14.4", "26.0")
        self.assertEqual(stamps.min_macos(both), "26.0")

    def test_versions_compare_as_numbers(self):
        # As text "9.0" would sort above "14.4"
        self.assertEqual(stamps.min_macos(_BUILD_VERSION + _BUILD_VERSION.replace("14.4", "9.0")),
                         "14.4")

    def test_no_stamp(self):
        self.assertEqual(stamps.min_macos("Load command 0\n      cmd LC_SEGMENT_64\n"), "")

    def test_a_version_with_fewer_parts_is_the_same_version(self):
        self.assertEqual(stamps.version_tuple("15"), stamps.version_tuple("15.0"))
        self.assertEqual(stamps.version_tuple("15.0"), stamps.version_tuple("15.0.0"))
        self.assertLess(stamps.version_tuple("15"), stamps.version_tuple("15.0.1"))


class TestWhichBinariesFail(unittest.TestCase):

    BINDINGS = (
        "Contents/Frameworks/PySide6/QtCore.abi3.so",
        "Contents/Frameworks/PySide6/libpyside6.abi3.6.12.dylib",
        "Contents/Frameworks/shiboken6/libshiboken6.abi3.6.12.dylib",
        "Contents/Frameworks/shiboken6/Shiboken.abi3.so",
    )
    NOT_BINDINGS = (
        "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
        "Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib",
        "Contents/Frameworks/Python.framework/Versions/3.14/Python",
        "Contents/Frameworks/libssl.3.dylib",
        "Contents/Frameworks/lib-dynload/_ssl.cpython-314-darwin.so",
        "Contents/MacOS/esolog-gui",
    )

    def test_only_the_bindings_own_libraries_are_excused(self):
        for path in self.BINDINGS:
            self.assertTrue(stamps.is_binding(path), path)
        for path in self.NOT_BINDINGS:
            self.assertFalse(stamps.is_binding(path), path)

    def test_a_binary_above_the_floor_fails_and_a_binding_is_reported(self):
        found = {path: "26.0" for path in self.BINDINGS + self.NOT_BINDINGS}
        too_new, bindings_above = stamps.judge(found, "15.0")
        self.assertEqual(sorted(too_new), sorted(self.NOT_BINDINGS))
        self.assertEqual(sorted(bindings_above), sorted(self.BINDINGS))

    def test_a_floor_written_short_still_passes_its_own_version(self):
        self.assertEqual(stamps.judge({"Contents/MacOS/esolog-gui": "15.0"}, "15"), ({}, {}))

    def test_at_or_below_the_floor_passes(self):
        found = {"Contents/MacOS/esolog-gui": "15.0",
                 "Contents/Frameworks/libssl.3.dylib": "11.0",
                 "Contents/Frameworks/PySide6/QtCore.abi3.so": "14.4",
                 "Contents/Resources/no-stamp": ""}
        self.assertEqual(stamps.judge(found, "15.0"), ({}, {}))

    def test_a_homebrew_python_fails(self):
        # The bundle built on the maintainer's Mac: Python and OpenSSL made
        # for that Mac's macOS
        found = {"Contents/Frameworks/Python.framework/Versions/3.14/Python": "27.0",
                 "Contents/Frameworks/libcrypto.3.dylib": "27.0"}
        too_new, _ = stamps.judge(found, "15.0")
        self.assertEqual(len(too_new), 2)


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("otool"),
                     "reads real binaries with otool")
class TestTheCheckOnRealBinaries(unittest.TestCase):

    def _app(self, floor: str) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        app = Path(folder.name) / "Stand-in.app"
        (app / "Contents" / "MacOS").mkdir(parents=True)
        with open(app / "Contents" / "Info.plist", "wb") as handle:
            plistlib.dump({"LSMinimumSystemVersion": floor}, handle)
        shutil.copy("/usr/bin/true", app / "Contents" / "MacOS" / "stand-in")
        (app / "Contents" / "MacOS" / "link").symlink_to("stand-in")
        (app / "Contents" / "Resources").mkdir()
        (app / "Contents" / "Resources" / "notes.txt").write_text("not a binary")
        return app

    def test_the_bundles_binaries_are_found_once_each(self):
        found, unread = stamps.read_stamps(self._app("99.0"))
        self.assertEqual(list(found), ["Contents/MacOS/stand-in"])
        self.assertRegex(found["Contents/MacOS/stand-in"], r"^\d+\.\d+")
        self.assertEqual(unread, [])

    def test_a_file_otool_cannot_read_fails_without_a_traceback(self):
        import contextlib
        import io
        app = self._app("99.0")
        # A Java class file starts with the bytes of a fat Mach-O file
        (app / "Contents" / "Resources" / "Thing.class").write_bytes(
            b"\xca\xfe\xba\xbe" + b"\x00\x00\x00\x41" + b"not a binary at all")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = stamps.main([str(app)])
        if "otool could not read" not in out.getvalue():
            self.skipTest("this otool reads the stand-in file")
        self.assertEqual(status, 1)
        self.assertIn("Contents/Resources/Thing.class", out.getvalue())

    def test_the_floor_comes_from_the_bundles_own_plist(self):
        import contextlib
        import io
        for floor, status in (("99.0", 0), ("10.0", 1)):
            with self.subTest(floor=floor):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(stamps.main([str(self._app(floor))]), status, out.getvalue())
                if status:
                    self.assertIn("::error::1 binaries need a newer macOS", out.getvalue())
                    self.assertIn("Contents/MacOS/stand-in", out.getvalue())


class TestMacIcon(unittest.TestCase):

    def setUp(self):
        try:
            import PIL  # noqa: F401  (a build-time dependency)
        except ImportError:
            self.skipTest("needs Pillow, from requirements-build.txt")
        self.icon = _load('create_icon.py')

    def test_the_die_sits_on_a_rounded_square_plate(self):
        image = self.icon.render_mac(128)
        self.assertEqual(image.size, (128, 128))
        alpha = image.getchannel("A")
        # Clear outside the plate: the canvas's corner and its edge
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(alpha.getpixel((64, 2)), 0)
        # Clear where the plate's own corner is rounded off, solid just
        # inside its straight edges and at the centre
        edge = round(128 * (1 - self.icon.MAC_PLATE) / 2)
        self.assertEqual(alpha.getpixel((edge + 1, edge + 1)), 0)
        self.assertEqual(alpha.getpixel((64, edge + 3)), 255)
        self.assertEqual(alpha.getpixel((edge + 3, 64)), 255)
        self.assertEqual(alpha.getpixel((64, 64)), 255)

    def test_the_icns_holds_every_size(self):
        from PIL import Image
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "icon.icns"
        self.icon.create_mac_icon(path)
        with Image.open(path) as image:
            sizes = {(width * scale) for width, _, scale in image.info["sizes"]}
        self.assertEqual(sizes, set(self.icon.MAC_SIZES))


if __name__ == '__main__':
    unittest.main()
