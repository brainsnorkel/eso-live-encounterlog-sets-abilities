#!/usr/bin/env python3
"""Start-at-login toggle: registry round-trip and settings wiring."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import autostart

TEST_VALUE = "ESO Log Tail Test"


@unittest.skipUnless(sys.platform == 'win32', 'Windows registry feature')
class TestAutostartRegistry(unittest.TestCase):
    """Round-trips a dedicated test value name; never touches the real one."""

    def tearDown(self):
        autostart.set_enabled(False, value_name=TEST_VALUE)

    def test_round_trip(self):
        self.assertFalse(autostart.is_enabled(value_name=TEST_VALUE))
        ok = autostart.set_enabled(True, value_name=TEST_VALUE,
                                   command='"C:\\x\\app.exe"')
        self.assertTrue(ok)
        self.assertTrue(autostart.is_enabled(value_name=TEST_VALUE))
        # Stored command is readable and intact
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, TEST_VALUE)
        self.assertEqual(value, '"C:\\x\\app.exe"')
        self.assertEqual(kind, winreg.REG_SZ)
        # Disable removes it; disabling twice is harmless
        self.assertTrue(autostart.set_enabled(False, value_name=TEST_VALUE))
        self.assertFalse(autostart.is_enabled(value_name=TEST_VALUE))
        self.assertTrue(autostart.set_enabled(False, value_name=TEST_VALUE))

    def test_enable_without_command_fails_cleanly(self):
        # Dev checkout with no installed copy -> no command -> refuse
        if autostart.autostart_command() is None:
            self.assertFalse(autostart.set_enabled(True, value_name=TEST_VALUE,
                                                   command=None))

    def test_autostart_command_is_quoted_when_available(self):
        command = autostart.autostart_command()
        if command is not None:
            self.assertTrue(command.startswith('"') and command.endswith('"'))
            self.assertIn('esolog-gui.exe', command)


@unittest.skipUnless(sys.platform == 'win32', 'Windows registry feature')
class TestSettingsWiring(unittest.TestCase):

    def test_toggle_applies_only_on_change(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog

        with tempfile.TemporaryDirectory() as td:
            config = AppConfig(path=Path(td) / 'c.json')
            with patch.object(autostart, 'autostart_command',
                              return_value='"C:\\x\\app.exe"'), \
                 patch.object(autostart, 'is_enabled', return_value=False), \
                 patch.object(autostart, 'set_enabled') as set_mock:
                dialog = SettingsDialog(config)
                self.assertTrue(dialog.autostart.isEnabled())
                self.assertFalse(dialog.autostart.isChecked())
                # No change -> no registry write
                dialog.apply_to_config()
                set_mock.assert_not_called()
                # Enable -> one registry write
                dialog.autostart.setChecked(True)
                dialog.apply_to_config()
                set_mock.assert_called_once_with(True)
                dialog.deleteLater()

    def test_checkbox_disabled_when_unavailable(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog

        with tempfile.TemporaryDirectory() as td:
            config = AppConfig(path=Path(td) / 'c.json')
            with patch.object(autostart, 'autostart_command',
                              return_value=None), \
                 patch.object(autostart, 'is_enabled', return_value=False):
                dialog = SettingsDialog(config)
                self.assertFalse(dialog.autostart.isEnabled())
                dialog.deleteLater()


class TestStartupGroupPlatform(unittest.TestCase):
    """The Startup group is offered only where the login entry exists."""

    def _checkbox_visible(self, platform):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog

        with tempfile.TemporaryDirectory() as td:
            config = AppConfig(path=Path(td) / 'c.json')
            with patch.object(sys, 'platform', platform), \
                 patch.object(autostart, 'autostart_command',
                              return_value=None), \
                 patch.object(autostart, 'is_enabled', return_value=False):
                dialog = SettingsDialog(config)
                visible = dialog.autostart.isVisibleTo(dialog)
                dialog.deleteLater()
        return visible

    def test_shown_on_windows_hidden_elsewhere(self):
        self.assertTrue(self._checkbox_visible('win32'))
        self.assertFalse(self._checkbox_visible('linux'))


if __name__ == '__main__':
    unittest.main()
