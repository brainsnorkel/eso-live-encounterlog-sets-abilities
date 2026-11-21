#!/usr/bin/env python3
"""The bundle's check of its own data (self_check, issue #237): every table
the spec bundles is read through the app's own loader, a bundle without one
fails naming it, and the GUI entry runs the check before anything else."""

import ast
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import esolog_gui
import self_check

REPO = Path(__file__).resolve().parents[2]
TARGETS = "data/skills/ability_targets.json"


def _bundle(root: Path, leave_out=()) -> Path:
    """The data of a bundle under *root*, laid out as PyInstaller lays it
    out: a copy of each table the check reads but those in *leave_out*, and
    one icon for the folder of them."""
    for path, _probe in self_check.TABLES:
        if path in leave_out:
            continue
        source, target = REPO / path, root / path
        if source.is_dir():
            target.mkdir(parents=True)
            icon = next(source.glob("*.png"))
            shutil.copyfile(icon, target / icon.name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return root


class TestSelfCheck(unittest.TestCase):

    def setUp(self):
        # The probes fill the loaders' caches from whichever folder they read
        self.addCleanup(self_check.forget_loaded)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def _run(self, bundle=None):
        """(status, report) of a check of *bundle* as a frozen build sees it
        (sys._MEIPASS), or of the repository's data/."""
        out = io.StringIO()
        if bundle is None:
            status = self_check.run(out)
        else:
            with mock.patch.object(sys, "_MEIPASS", str(bundle), create=True):
                status = self_check.run(out)
        return status, out.getvalue()

    def test_the_repository_data_passes(self):
        status, report = self._run()
        self.assertEqual(status, 0, report)
        lines = report.splitlines()
        self.assertEqual(len(lines), len(self_check.TABLES) + 2)
        self.assertIn("(run from source)", lines[0])
        for path, _probe in self_check.TABLES:
            self.assertRegex(report, rf"(?m)^ok     {re.escape(path)}: \S")
        self.assertIn(f"ok     {TARGETS}: ", report)
        self.assertIn("Impulse (28800) area", report)
        self.assertEqual(lines[-1], f"All {len(self_check.TABLES)} bundled tables loaded")

    def test_a_bundle_with_every_table_passes(self):
        status, report = self._run(_bundle(self.tmp))
        self.assertEqual(status, 0, report)
        self.assertIn(str(self.tmp), report.splitlines()[0])

    def test_a_bundle_without_the_target_table_fails_naming_it(self):
        """The fault of issue #237: every other table is found."""
        status, report = self._run(_bundle(self.tmp, leave_out={TARGETS}))
        self.assertEqual(status, 1, report)
        self.assertIn(f"FAILED {TARGETS}: not found, or empty", report)
        self.assertEqual(report.count("FAILED "), 1, report)
        self.assertEqual(report.splitlines()[-1],
                         f"1 of {len(self_check.TABLES)} bundled tables did not load: {TARGETS}")

    def test_an_empty_bundle_fails_every_table(self):
        status, report = self._run(self.tmp)
        self.assertEqual(status, 1)
        for path, _probe in self_check.TABLES:
            self.assertIn(f"FAILED {path}: ", report)

    def test_a_target_table_without_impulse_as_area_fails(self):
        _bundle(self.tmp, leave_out={TARGETS})
        (self.tmp / TARGETS).write_text(json.dumps({"area": [], "single": [28800]}), encoding="utf-8")
        status, report = self._run(self.tmp)
        self.assertEqual(status, 1, report)
        self.assertIn(f"FAILED {TARGETS}: ValueError: Impulse (28800) is not listed as an area "
                      "skill", report)

    def test_a_probe_that_raises_is_reported_not_raised(self):
        def broken():
            raise KeyError("sets")
        with mock.patch.object(self_check, "TABLES", (("data/sets/offense.json", broken),)):
            status, report = self._run()
        self.assertEqual(status, 1)
        self.assertIn("FAILED data/sets/offense.json: KeyError: 'sets'", report)

    def test_every_table_the_spec_bundles_is_checked(self):
        """A table added to the spec's datas needs an entry in TABLES. The
        icons are checked as their folder: the app reads no file there but
        the icons."""
        spec = (REPO / "esolog-tail.spec").read_text(encoding="utf-8")
        folders = ast.literal_eval(re.search(r"for d in (\([^)]*\))", spec).group(1))
        icons = "data/icons/abilities"
        self.assertIn(icons, folders)
        bundled = {icons} | set(re.findall(r"\('(data/[^']+)', 'data/", spec))
        for folder in folders:
            if folder != icons:
                bundled |= {path.relative_to(REPO).as_posix()
                            for path in (REPO / folder).glob("*.json")}
        self.assertIn("data/version.json", bundled)
        self.assertEqual(sorted(bundled), sorted(path for path, _probe in self_check.TABLES))


class TestTheGuiEntry(unittest.TestCase):

    def test_the_check_runs_before_the_crash_log_qt_or_the_config(self):
        with mock.patch.dict(os.environ, {esolog_gui.SELF_CHECK_VARIABLE: "1"}), \
                mock.patch.object(self_check, "run", return_value=1) as run, \
                mock.patch.object(esolog_gui, "_enable_crash_log",
                                  side_effect=AssertionError("the app went on to start")):
            self.assertEqual(esolog_gui.main(), 1)
        run.assert_called_once_with()

    def test_an_error_in_the_check_is_printed_not_raised(self):
        """A windowed build would show a raised one in a dialog."""
        out = io.StringIO()
        with mock.patch.dict(os.environ, {esolog_gui.SELF_CHECK_VARIABLE: "1"}), \
                mock.patch.object(self_check, "run", side_effect=ImportError("no module x")), \
                contextlib.redirect_stdout(out):
            self.assertEqual(esolog_gui.main(), 1)
        self.assertIn("ImportError: no module x", out.getvalue())

    def test_ci_runs_the_check_on_every_bundle(self):
        """The Windows and Linux builds and the macOS smoke test."""
        workflow = (REPO / ".github" / "workflows" / "build-installers.yml").read_text(encoding="utf-8")
        self.assertEqual(esolog_gui.SELF_CHECK_VARIABLE, "ESOLOG_TAIL_SELF_CHECK")
        self.assertEqual(workflow.count("ESOLOG_TAIL_SELF_CHECK=1 "), 3)


if __name__ == "__main__":
    unittest.main()
