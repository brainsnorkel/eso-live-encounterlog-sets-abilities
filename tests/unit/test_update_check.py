#!/usr/bin/env python3
"""Unit tests for the GitHub release update check."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import update_check
from update_check import (
    check_for_update, download_file, is_newer, parse_version,
    release_to_update_info,
)


def _release(tag='v0.4.0', assets=None, **extra):
    if assets is None:
        version = tag.lstrip("v")
        assets = [{
            'name': f'esolog-tail-windows-setup-{version}.exe',
            'browser_download_url': f'https://example.invalid/{tag}/setup.exe',
        }, {
            'name': f'esolog-tail-windows-portable-{version}.zip',
            'browser_download_url': f'https://example.invalid/{tag}/portable.zip',
        }, {
            'name': f'esolog-tail-linux-x86_64-{version}.tar.gz',
            'browser_download_url': f'https://example.invalid/{tag}/linux.tar.gz',
        }]
    return {
        'tag_name': tag,
        'assets': assets,
        'body': 'Release notes',
        'html_url': f'https://github.com/x/releases/{tag}',
        'draft': False,
        'prerelease': False,
        **extra,
    }


class TestVersionParsing(unittest.TestCase):

    def test_parse_version(self):
        self.assertEqual(parse_version('v0.3.0'), (0, 3, 0))
        self.assertEqual(parse_version('1.12.3'), (1, 12, 3))
        self.assertIsNone(parse_version('not-a-version'))
        self.assertIsNone(parse_version(''))

    def test_is_newer(self):
        self.assertTrue(is_newer('v0.4.0', '0.3.0'))
        self.assertTrue(is_newer('0.3.10', '0.3.9'))
        self.assertFalse(is_newer('v0.3.0', '0.3.0'))
        self.assertFalse(is_newer('v0.2.9', '0.3.0'))
        self.assertFalse(is_newer('garbage', '0.3.0'))


class TestReleaseParsing(unittest.TestCase):

    def test_valid_release(self):
        info = release_to_update_info(_release(), platform='win32')
        self.assertEqual(info.version, '0.4.0')
        self.assertEqual(info.tag, 'v0.4.0')
        self.assertIn('setup', info.installer_name)
        self.assertTrue(info.installer_url)

    def test_asset_follows_platform(self):
        release = _release()
        win = release_to_update_info(release, platform='win32')
        self.assertEqual(win.installer_name, 'esolog-tail-windows-setup-0.4.0.exe')
        linux = release_to_update_info(release, platform='linux')
        self.assertEqual(linux.installer_name,
                         'esolog-tail-linux-x86_64-0.4.0.tar.gz')
        self.assertTrue(linux.installer_url.endswith('linux.tar.gz'))
        # The running platform is the default
        if sys.platform in update_check.PLATFORM_ASSETS:
            self.assertEqual(
                release_to_update_info(release).installer_name,
                release_to_update_info(release, sys.platform).installer_name)

    def test_platform_without_a_build_is_rejected(self):
        self.assertIsNone(release_to_update_info(_release(), platform='darwin'))

    def test_release_without_this_platforms_asset_rejected(self):
        # A Windows-only release offers nothing to Linux, and vice versa
        windows_only = _release(assets=[{
            'name': 'esolog-tail-windows-setup-0.4.0.exe',
            'browser_download_url': 'https://x/setup.exe'}])
        self.assertIsNotNone(release_to_update_info(windows_only, 'win32'))
        self.assertIsNone(release_to_update_info(windows_only, 'linux'))

    def test_draft_and_prerelease_rejected(self):
        self.assertIsNone(release_to_update_info(_release(draft=True)))
        self.assertIsNone(release_to_update_info(_release(prerelease=True)))

    def test_missing_installer_asset_rejected(self):
        release = _release(assets=[{'name': 'esolog-tail-windows-portable-0.4.0.zip',
                                    'browser_download_url': 'https://x/p.zip'}])
        self.assertIsNone(release_to_update_info(release, platform='win32'))
        self.assertIsNone(release_to_update_info(release, platform='linux'))

    def test_bad_tag_rejected(self):
        self.assertIsNone(release_to_update_info(_release(tag='nightly')))
        self.assertIsNone(release_to_update_info(None))


class TestCheckForUpdate(unittest.TestCase):

    def setUp(self):
        # check_for_update reads the running platform; pin one with a build
        patcher = patch.object(update_check.sys, 'platform', 'win32')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_newer_release_returned(self):
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=_release('v9.9.9')):
            info = check_for_update('0.3.0')
        self.assertIsNotNone(info)
        self.assertEqual(info.version, '9.9.9')

    def test_same_or_older_ignored(self):
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=_release('v0.3.0')):
            self.assertIsNone(check_for_update('0.3.0'))
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=_release('v0.2.0')):
            self.assertIsNone(check_for_update('0.3.0'))

    def test_skip_version_honored(self):
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=_release('v9.9.9')):
            self.assertIsNone(check_for_update('0.3.0', skip_version='9.9.9'))
            self.assertIsNotNone(check_for_update('0.3.0', skip_version='9.9.8'))

    def test_network_failure_is_none(self):
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=None):
            self.assertIsNone(check_for_update('0.3.0'))


class TestDownload(unittest.TestCase):

    def test_download_local_file_with_progress(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'src.bin'
            payload = os.urandom(700 * 1024)  # multiple 256 KiB chunks
            src.write_bytes(payload)
            dest = Path(td) / 'dest.bin'
            calls = []
            ok = download_file(src.as_uri(), dest,
                               progress=lambda d, t: calls.append((d, t)))
            self.assertTrue(ok)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertGreaterEqual(len(calls), 2)
            self.assertEqual(calls[-1][0], len(payload))

    def test_download_failure_removes_partial(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / 'dest.bin'
            ok = download_file((Path(td) / 'missing.bin').as_uri(), dest)
            self.assertFalse(ok)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
