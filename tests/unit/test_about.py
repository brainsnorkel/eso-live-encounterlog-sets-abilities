#!/usr/bin/env python3
"""About dialog: credits for ESO-Hub links and ZeniMax-owned icons."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestAbout(unittest.TestCase):

    def setUp(self):
        self.app = QApplication.instance() or QApplication([])

    def test_credits_name_esohub_and_zenimax(self):
        from gui.about import about_html
        html = about_html('0.4.0')
        self.assertIn('ESO Log Tail 0.4.0', html)
        self.assertIn("href='https://eso-hub.com'", html)
        self.assertIn('hover text', html)
        self.assertIn('ZeniMax Online Studios', html)
        self.assertIn('not the property of this application', html)
        self.assertIn('LibSets', html)
        self.assertIn('EsoExtractData', html)

    def test_toolbar_has_about_action(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(path=Path(tmp) / 'config.json')
            config.set('log_path', str(Path(tmp) / 'Encounter.log'))
            win = MainWindow(config)
            win.worker_thread.quit()
            win.worker_thread.wait(3000)
            try:
                labels = [a.text() for tb in win.findChildren(type(win.addToolBar('x')))
                          for a in tb.actions() if a.text()]
                self.assertTrue(any(label.startswith('About') for label in labels), labels)
            finally:
                win.close()


if __name__ == '__main__':
    unittest.main()
