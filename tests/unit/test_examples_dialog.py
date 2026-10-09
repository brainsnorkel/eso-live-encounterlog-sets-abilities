#!/usr/bin/env python3
"""The example-rules picker (offscreen Qt): one checkable item per example,
ticked unless the box already has a rule of that name; Add gives the
ticked lines, Copy puts them on the clipboard."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from effect_rules import EXAMPLE_RULES, parse_rules


class TestExampleLibrary(unittest.TestCase):

    def test_every_example_line_parses_and_names_are_unique(self):
        lines = [line for _t, _n, line in EXAMPLE_RULES]
        rules, errors = parse_rules("\n".join(lines))
        self.assertEqual(errors, [])
        self.assertEqual(len(rules), len(EXAMPLE_RULES))
        self.assertEqual(len({r.name.lower() for r in rules}), len(rules))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestExamplesDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_items_start_ticked_unless_already_present(self):
        from gui.examples_dialog import ExamplesDialog
        dialog = ExamplesDialog(present_names=["Crux", "off-balance"])
        states = {dialog.list.item(i).data(Qt.UserRole).split("=")[0].strip():
                  dialog.list.item(i).checkState() == Qt.Checked
                  for i in range(dialog.list.count())}
        self.assertFalse(states["Crux"])
        self.assertFalse(states["Off-Balance"])
        self.assertTrue(states["Touch of Z'en"])
        self.assertEqual(len(states), len(EXAMPLE_RULES))
        # Only the ticked lines come back, in library order
        lines = dialog.selected_lines()
        self.assertNotIn("Crux = 184220 on self stacks", lines)
        self.assertEqual(lines[0], "Touch of Z'en = 126597 on boss stacks")
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_copy_puts_the_ticked_lines_on_the_clipboard(self):
        from gui.examples_dialog import ExamplesDialog
        dialog = ExamplesDialog()
        for i in range(dialog.list.count()):
            dialog.list.item(i).setCheckState(Qt.Unchecked)
        dialog.list.item(2).setCheckState(Qt.Checked)  # Crux
        dialog.copy_button.click()
        self.assertEqual(QGuiApplication.clipboard().text(), "Crux = 184220 on self stacks\n")
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_lines_already_in_the_box_are_not_added_twice(self):
        from gui.examples_dialog import example_lines_to_add
        new = example_lines_to_add(["Crux = 184220 on self stacks", "Relequen = 107203 on boss stacks"],
                                   "crux = 1 on self\n")
        self.assertEqual(new, ["Relequen = 107203 on boss stacks"])


if __name__ == '__main__':
    unittest.main()
