#!/usr/bin/env python3
"""About dialog: credits for ESO-Hub links and ZeniMax-owned icons."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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

    def test_the_update_channel_line(self):
        from gui.about import about_html
        line = 'Update channel: Beta (every release, as soon as it is published)'
        self.assertIn(f'<p>{line}</p>', about_html('0.26.0', line))
        self.assertNotIn('Update channel', about_html('0.26.0'))
        self.assertNotIn('<p></p>', about_html('0.26.0'))

    def test_credits_name_the_build_window_data_sources(self):
        from gui.about import about_html
        html = about_html('0.6.0')
        self.assertIn('LibFoodDrinkBuff</a> by Scootworks and Baertram', html)
        self.assertIn("href='https://www.esoui.com/downloads/info1902-LibFoodDrinkBuff.html'",
                      html)
        self.assertIn('<b>Poison names, armor weights and weapon types</b>: '
                      'the ESO item database of', html)
        self.assertIn('>UESP</a>', html)

    def test_credits_name_combat_metrics_for_the_dps_definitions(self):
        from gui.about import about_html
        html = about_html('0.12.0')
        self.assertIn("<a href='https://www.esoui.com/downloads/info1360-CombatMetrics.html'>"
                      "Combat Metrics</a> by Solinur", html)
        self.assertIn("<a href='https://github.com/Solinur/LibCombat'>LibCombat</a>", html)
        self.assertIn("<a href='https://github.com/Solinur/CombatMetrics'>Combat Metrics source</a>",
                      html)
        self.assertIn('the dps time', html)

    def test_credits_name_both_logging_addons(self):
        from gui.about import about_html
        html = about_html('0.28.0')
        self.assertIn("<a href='https://www.esoui.com/downloads/info2332-EasyStalking-"
                      "Encounterlog.html'>Easy Stalking - Encounterlog</a>", html)
        self.assertIn("<a href='https://github.com/brainsnorkel/AlwaysLogging'>"
                      "Always Logging</a>", html)

    def test_readme_credits_mirror_the_dialog(self):
        readme = (Path(__file__).resolve().parents[2] / 'README.md').read_text(encoding='utf-8')
        credits = readme[readme.index('## Credits'):]
        for url in ('https://www.esoui.com/downloads/info1360-CombatMetrics.html',
                    'https://github.com/Solinur/LibCombat',
                    'https://github.com/Solinur/CombatMetrics',
                    'https://eso-hub.com', 'https://github.com/Baertram/LibSets',
                    'https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html',
                    'https://github.com/brainsnorkel/AlwaysLogging'):
            self.assertIn(url, credits)

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
