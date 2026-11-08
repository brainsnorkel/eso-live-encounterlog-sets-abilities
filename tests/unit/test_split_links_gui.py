#!/usr/bin/env python3
"""The split logs beside a run (issue #194, #196's PR 8), offscreen: the
Instance tab and the result strip list the split logs of the run's
sessions, open folder and copy path on each, by their place in the list;
Hide names shows a file's name alone and copies its full path all the
same; split logs off, a session's file missing and a session not known
each say so; a block over two sessions lists both; a review lists the
reviewed file, and its banner names the file alone under Hide names."""

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT
from tests.unit.test_instance_tab_gui import HEADER, InstanceTabTestCase, _session

KYNES = "261015191452"
SUNSPIRE = "261014223802"


def _stamped(fights, stamp=KYNES):
    """*fights* with *stamp* as their session's, the last one Sunspire's."""
    for fight in fights[:-1]:
        fight.session_stamp = stamp
    fights[-1].session_stamp = SUNSPIRE
    return fights


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class SplitLinksTestCase(InstanceTabTestCase):

    def setUp(self):
        super().setUp()
        self.splits = self.root / "splits"
        self.splits.mkdir()
        self.kynes = self.splits / f"{KYNES}-Kyne's-Aegis-vet.log"
        self.kynes.write_text("a split\n", encoding="utf-8")
        (self.splits / f"{SUNSPIRE}-Sunspire-vet.log").write_text("another\n", encoding="utf-8")

    def _split_window(self, *entries, enabled=True):
        """A window whose config has split logs on, into the test's folder
        (or off), before the fights come in."""
        from app_config import AppConfig
        config = AppConfig(path=self.root / "config.json")
        config.set("split.enabled", enabled)
        config.set("split.dir", str(self.splits))
        config.save()
        return self._window(*entries)

    def _split_hrefs(self, view):
        return [href for href, _start, _end in view._links() if href.startswith("esolog:split/")]


class TestTheLinks(SplitLinksTestCase):

    def test_the_instance_lists_its_split_log_with_its_links(self):
        win = self._split_window(*_stamped(_session()))
        self._click(win, HEADER)
        text = win.instance_view.toPlainText()
        self.assertIn(f"Split log {self.kynes} (open folder) (copy path)", text)
        self.assertEqual(self._split_hrefs(win.instance_view),
                         ["esolog:split/0/open", "esolog:split/0/copy"])
        self.assertIn("folder", win.instance_view._tooltips["esolog:split/0/open"])

    def test_open_folder_and_copy_path(self):
        """Open folder shows the file in its folder; copy path copies the
        full path, Hide names or not, where the page shows its name alone."""
        from PySide6.QtGui import QGuiApplication
        win = self._split_window(*_stamped(_session()))
        self._click(win, HEADER)
        shown = []
        with mock.patch("gui.main_window.reveal_file", shown.append):
            self._activate(win, "esolog:split/0/open")
        self.assertEqual(shown, [self.kynes])
        win.hide_names_action.setChecked(True)
        self._settle()
        text = win.instance_view.toPlainText()
        self.assertIn(f"Split log {self.kynes.name} (open folder)", text)
        self.assertNotIn(str(self.splits), text)
        self._activate(win, "esolog:split/0/copy")
        self.assertEqual(QGuiApplication.clipboard().text(), str(self.kynes))

    def test_the_result_strip_lists_it_too(self):
        """The fight that completed the run lists its session's split log on
        its result strip; another fight has no strip."""
        from PySide6.QtCore import QUrl
        fights = _stamped(_session())
        win = self._split_window(*fights)
        win.history_list.select_entry(fights[3])
        self.assertIn(f"Split log {self.kynes}", win.fight_view.toPlainText())
        shown = []
        with mock.patch("gui.main_window.reveal_file", shown.append):
            win.fight_view.anchorClicked.emit(QUrl("esolog:split/0/open"))
        self.assertEqual(shown, [self.kynes])
        win.history_list.select_entry(fights[1])
        self.assertNotIn("Split log", win.fight_view.toPlainText())

    def test_a_file_gone_says_so(self):
        win = self._split_window(*_stamped(_session()))
        self._click(win, HEADER)
        self.kynes.unlink()
        shown = []
        with mock.patch("gui.main_window.reveal_file", shown.append):
            self._activate(win, "esolog:split/0/open")
        self.assertEqual(shown, [])
        self.assertEqual(win.statusBar().currentMessage(), "That log is not there now")


class TestNoFile(SplitLinksTestCase):

    def test_split_logs_off(self):
        """The default: a line says where to turn them on, with no links."""
        win = self._split_window(*_stamped(_session()), enabled=False)
        self._click(win, HEADER)
        self.assertIn("Split log: split logs are off: Settings → Files and splits",
                      win.instance_view.toPlainText())
        self.assertEqual(self._split_hrefs(win.instance_view), [])

    def test_missing_and_not_known(self):
        """A session no file holds, and fights from a session whose
        BEGIN_LOG the app never saw, each say so, in the fights' order."""
        fights = _stamped(_session())
        fights[0].session_stamp = ""
        for fight in fights[1:4]:
            fight.session_stamp = "261015201400"
        win = self._split_window(*fights)
        self._click(win, HEADER)
        text = win.instance_view.toPlainText()
        unknown = text.index("Split log: not known: the session began before the app read the log")
        missing = text.index("Split log: the session begun 20:14 is not in the split folder")
        self.assertLess(unknown, missing)
        self.assertEqual(self._split_hrefs(win.instance_view), [])

    def test_a_block_over_two_sessions_lists_both(self):
        fights = _stamped(_session())
        later = self.splits / "261015201400-Kyne's-Aegis-vet.log"
        later.write_text("the next session\n", encoding="utf-8")
        for fight in fights[2:4]:
            fight.session_stamp = "261015201400"
        win = self._split_window(*fights)
        self._click(win, HEADER)
        text = win.instance_view.toPlainText()
        self.assertLess(text.index(str(self.kynes)), text.index(str(later)))
        self.assertEqual(self._split_hrefs(win.instance_view),
                         ["esolog:split/0/open", "esolog:split/0/copy",
                          "esolog:split/1/open", "esolog:split/1/copy"])


class TestReview(SplitLinksTestCase):

    def test_a_review_lists_the_reviewed_file(self):
        """Under a review the page lists the reviewed file, whose links act
        on it; the banner names it whole, or by its name alone under Hide
        names."""
        reviewed = self.splits / "261020200000-Sunspire-vet.log"
        reviewed.write_text("reviewed\n", encoding="utf-8")
        win = self._split_window()
        win._on_review_loaded(str(reviewed), _stamped(_session()))
        self._settle()
        self._click(win, HEADER)
        self.assertIn(f"Reviewed log {reviewed} (open folder)", win.instance_view.toPlainText())
        shown = []
        with mock.patch("gui.main_window.reveal_file", shown.append):
            self._activate(win, "esolog:split/0/open")
        self.assertEqual(shown, [reviewed])
        self.assertIn(str(reviewed), win.banner.text())
        win.hide_names_action.setChecked(True)
        self._settle()
        self.assertIn(reviewed.name, win.banner.text())
        self.assertNotIn(str(self.splits), win.banner.text())


class TestRendering(unittest.TestCase):
    """The lines and their links, without a window."""

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_the_lines_the_hrefs_and_their_hovers(self):
        from pathlib import Path

        from gui.fight_render import _theme, split_from_href, split_lines_html, split_tooltips
        files = [("Split log", Path("D:/splits/a.log"), ""), ("Split log", None, "a note")]
        lines = split_lines_html(files, _theme(False))
        self.assertIn("esolog:split/0/open", lines[0])
        self.assertIn(str(Path("D:/splits/a.log")), lines[0])
        self.assertIn("a note", lines[1])
        self.assertNotIn("esolog:split/1/", lines[1])
        hidden = split_lines_html(files, _theme(False), hide_paths=True)
        self.assertIn("a.log", hidden[0])
        self.assertNotIn("splits", hidden[0])
        self.assertEqual(set(split_tooltips(files)), {"esolog:split/0/open", "esolog:split/0/copy"})
        self.assertEqual(split_from_href("esolog:split/3/copy"), (3, "copy"))
        for bad in ("esolog:split/x/open", "esolog:split/1/delete", "esolog:split/²/open",
                    "esolog:split/", "esolog:banner/open"):
            self.assertIsNone(split_from_href(bad), bad)


if __name__ == "__main__":
    unittest.main()
