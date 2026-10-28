#!/usr/bin/env python3
"""Unit tests for the GitHub release update check."""

import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import update_check
from update_check import (
    FetchResult, changelog_url, check_for_update, compare_url, download_file,
    fetch_latest_release, fetch_releases, format_release_date, is_newer,
    newest_release, normalize_channel, parse_version, release_to_update_info,
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
        'published_at': '2026-10-26T00:23:57Z',
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
        self.assertEqual(info.published, '2026-10-26T00:23:57Z')

    def test_release_date_and_changelog_link(self):
        self.assertEqual(format_release_date('2026-10-26T00:23:57Z'), '26 October 2026')
        self.assertEqual(format_release_date('2026-03-05'), '5 March 2026')
        self.assertEqual(format_release_date(''), '')
        self.assertEqual(format_release_date('soon'), '')
        self.assertTrue(changelog_url('v1.2.3').endswith('/blob/v1.2.3/CHANGELOG.md'))
        self.assertIn(update_check.GITHUB_REPO, changelog_url('v1.2.3'))

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

    def test_only_a_whole_version_tag_counts(self):
        # The release list carries data releases too (issue #134): three
        # dotted numbers somewhere in a tag do not make it a version
        for tag in ('esobuild-assets-u51-20261006', 'esobuild-assets-1.2.3',
                    'v1.2.3-beta.1', '1.2.3', 'v1.2.3.4'):
            self.assertIsNone(release_to_update_info(_release(tag=tag), 'win32'), tag)
        self.assertIsNotNone(release_to_update_info(_release(tag='v1.2.3'), 'win32'))

    def test_prerelease_only_when_allowed(self):
        beta = _release(prerelease=True)
        self.assertIsNone(release_to_update_info(beta, 'win32'))
        self.assertEqual(release_to_update_info(beta, 'win32', allow_prerelease=True).version,
                         '0.4.0')
        self.assertIsNone(release_to_update_info(_release(draft=True), 'win32',
                                                 allow_prerelease=True))

    def test_compare_link(self):
        self.assertTrue(compare_url('0.24.0', 'v0.26.1').endswith('/compare/v0.24.0...v0.26.1'))
        self.assertIn(update_check.GITHUB_REPO, compare_url('0.24.0', 'v0.26.1'))


class TestChannels(unittest.TestCase):

    def test_unknown_channel_is_stable(self):
        self.assertEqual(normalize_channel('beta'), 'beta')
        self.assertEqual(normalize_channel('stable'), 'stable')
        for value in (None, '', 'Beta', 'nightly', 3):
            self.assertEqual(normalize_channel(value), 'stable')

    def test_newest_release_takes_the_highest_version_prerelease_or_not(self):
        releases = [
            _release('v0.6.1', assets=[]),                    # no asset for any platform
            _release('v0.7.0', draft=True),                   # drafts never
            _release('esobuild-assets-9.9.9'),                # data release
            _release('v0.6.0', prerelease=True),
            _release('v0.5.0'),
            _release('v0.10.0', prerelease=True),             # by version, not by text
        ]
        self.assertEqual(newest_release(releases, 'win32').version, '0.10.0')
        self.assertEqual(newest_release(releases[:5], 'linux').version, '0.6.0')
        self.assertIsNone(newest_release([], 'win32'))
        self.assertIsNone(newest_release(None, 'win32'))


class _Response:
    """What urlopen yields for a full reply."""

    def __init__(self, payload: bytes, headers: dict):
        self._payload = payload
        self.headers = headers

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _http_error(code, headers=None):
    return urllib.error.HTTPError(update_check.LATEST_RELEASE_URL, code,
                                  'reply', headers or {}, None)


class TestFetchLatestRelease(unittest.TestCase):
    """The conditional request: ETag out, 304 and rate-limit replies in."""

    def _fetch(self, urlopen_result, etag=None):
        kwargs = ({'side_effect': urlopen_result} if isinstance(urlopen_result, BaseException)
                  else {'return_value': urlopen_result})
        with patch.object(update_check.urllib.request, 'urlopen', **kwargs) as urlopen:
            result = fetch_latest_release(etag)
        return result, urlopen.call_args[0][0]

    def test_full_reply_carries_the_etag(self):
        payload = json.dumps(_release('v1.2.3')).encode('utf-8')
        result, request = self._fetch(_Response(payload, {'ETag': '"abc"'}))
        self.assertEqual(result.release['tag_name'], 'v1.2.3')
        self.assertEqual(result.etag, '"abc"')
        self.assertFalse(result.not_modified)
        self.assertIsNone(result.error)
        self.assertFalse(request.has_header('If-none-match'))

    def test_etag_is_sent_and_304_is_not_modified(self):
        result, request = self._fetch(_http_error(304), etag='"abc"')
        self.assertTrue(result.not_modified)
        self.assertEqual(result.etag, '"abc"')
        self.assertIsNone(result.release)
        self.assertIsNone(result.error)
        self.assertEqual(request.get_header('If-none-match'), '"abc"')

    def test_rate_limit_reset_names_the_wait(self):
        reset = int(time.time()) + 600
        result, _ = self._fetch(_http_error(403, {'X-RateLimit-Reset': str(reset)}))
        self.assertIn('rate limited', result.error)
        self.assertAlmostEqual(result.retry_at, reset, delta=2)
        self.assertIsNone(result.release)

    def test_retry_after_names_the_wait(self):
        result, _ = self._fetch(_http_error(429, {'Retry-After': '120'}))
        self.assertAlmostEqual(result.retry_at, time.time() + 120, delta=2)

    def test_rate_limit_wait_is_capped_at_an_hour(self):
        reset = int(time.time()) + 86400
        result, _ = self._fetch(_http_error(403, {'X-RateLimit-Reset': str(reset)}))
        self.assertLessEqual(result.retry_at, time.time() + 3600 + 2)

    def test_rate_limit_without_a_time(self):
        result, _ = self._fetch(_http_error(403))
        self.assertIsNone(result.retry_at)
        self.assertIn('rate limited', result.error)

    def test_other_http_error(self):
        result, _ = self._fetch(_http_error(500))
        self.assertEqual(result.error, 'HTTP 500')
        self.assertIsNone(result.retry_at)

    def test_timeout_is_an_error(self):
        result, _ = self._fetch(TimeoutError('timed out'))
        self.assertIn('timed out', result.error)
        self.assertFalse(result.not_modified)

    def test_latest_reads_the_latest_endpoint(self):
        payload = json.dumps(_release('v1.2.3')).encode('utf-8')
        _, request = self._fetch(_Response(payload, {}))
        self.assertEqual(request.full_url, update_check.LATEST_RELEASE_URL)


class TestFetchReleases(unittest.TestCase):
    """The Beta channel's request: the newest releases, as a list."""

    def _fetch(self, urlopen_result, etag=None):
        kwargs = ({'side_effect': urlopen_result} if isinstance(urlopen_result, BaseException)
                  else {'return_value': urlopen_result})
        with patch.object(update_check.urllib.request, 'urlopen', **kwargs) as urlopen:
            result = fetch_releases(etag)
        return result, urlopen.call_args[0][0]

    def test_a_list_reply(self):
        payload = json.dumps([_release('v1.2.4', prerelease=True),
                              _release('v1.2.3')]).encode('utf-8')
        result, request = self._fetch(_Response(payload, {'ETag': 'W/"l1"'}))
        self.assertEqual(request.full_url, update_check.RELEASES_URL)
        self.assertIn('per_page=10', request.full_url)
        self.assertEqual([r['tag_name'] for r in result.releases], ['v1.2.4', 'v1.2.3'])
        self.assertIsNone(result.release)
        self.assertEqual(result.etag, 'W/"l1"')
        self.assertIsNone(result.error)

    def test_not_modified_and_the_etag_sent(self):
        result, request = self._fetch(_http_error(304), etag='W/"l1"')
        self.assertTrue(result.not_modified)
        self.assertIsNone(result.releases)
        self.assertEqual(request.get_header('If-none-match'), 'W/"l1"')

    def test_a_reply_that_is_not_a_list_is_an_error(self):
        payload = json.dumps({'message': 'Not Found'}).encode('utf-8')
        result, _ = self._fetch(_Response(payload, {}))
        self.assertIsNone(result.releases)
        self.assertIsNone(result.release)
        self.assertEqual(result.error, 'unexpected reply')


class TestCheckForUpdate(unittest.TestCase):

    def setUp(self):
        # check_for_update reads the running platform; pin one with a build
        patcher = patch.object(update_check.sys, 'platform', 'win32')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _check(self, fetched, *args, **kwargs):
        with patch.object(update_check, 'fetch_latest_release',
                          return_value=fetched) as fetch:
            result = check_for_update(*args, **kwargs)
        return result, fetch

    def test_newer_release_returned_with_the_etag(self):
        result, fetch = self._check(
            FetchResult(release=_release('v9.9.9'), etag='"e1"'), '0.3.0')
        self.assertIsNotNone(result.info)
        self.assertEqual(result.info.version, '9.9.9')
        self.assertEqual(result.etag, '"e1"')
        fetch.assert_called_once_with(None)

    def test_etag_passed_through(self):
        result, fetch = self._check(FetchResult(not_modified=True, etag='"e1"'),
                                    '0.3.0', None, '"e1"')
        fetch.assert_called_once_with('"e1"')
        self.assertTrue(result.not_modified)
        self.assertIsNone(result.info)

    def test_same_or_older_ignored(self):
        for tag in ('v0.3.0', 'v0.2.0'):
            result, _ = self._check(FetchResult(release=_release(tag)), '0.3.0')
            self.assertIsNone(result.info)
            self.assertFalse(result.not_modified)
            self.assertIsNone(result.error)

    def test_skip_version_honored(self):
        fetched = FetchResult(release=_release('v9.9.9'))
        self.assertIsNone(self._check(fetched, '0.3.0', skip_version='9.9.9')[0].info)
        self.assertIsNotNone(self._check(fetched, '0.3.0', skip_version='9.9.8')[0].info)

    def test_failures_are_reported_not_raised(self):
        result, _ = self._check(FetchResult(error='timed out'), '0.3.0')
        self.assertIsNone(result.info)
        self.assertEqual(result.error, 'timed out')
        result, _ = self._check(FetchResult(error='rate limited (403)', retry_at=5.0), '0.3.0')
        self.assertEqual(result.retry_at, 5.0)

    def _check_beta(self, fetched, *args, **kwargs):
        with patch.object(update_check, 'fetch_releases', return_value=fetched) as fetch, \
                patch.object(update_check, 'fetch_latest_release') as latest:
            result = check_for_update(*args, channel='beta', **kwargs)
        latest.assert_not_called()
        return result, fetch

    def test_beta_offers_the_newest_release_prerelease_or_not(self):
        fetched = FetchResult(releases=[_release('v0.27.0', prerelease=True),
                                        _release('v0.26.0')], etag='W/"l1"')
        result, fetch = self._check_beta(fetched, '0.26.0', None, 'W/"l0"')
        fetch.assert_called_once_with('W/"l0"')
        self.assertEqual(result.info.version, '0.27.0')
        self.assertEqual(result.etag, 'W/"l1"')

    def test_beta_never_offers_a_lower_version(self):
        # Left Beta for Stable and back: a beta newer than every release stays
        fetched = FetchResult(releases=[_release('v0.26.0')])
        self.assertIsNone(self._check_beta(fetched, '0.27.0')[0].info)

    def test_beta_honours_skip_and_reports_failures(self):
        fetched = FetchResult(releases=[_release('v0.27.0', prerelease=True)])
        self.assertIsNone(self._check_beta(fetched, '0.26.0', '0.27.0')[0].info)
        result, _ = self._check_beta(FetchResult(not_modified=True, etag='W/"l1"'), '0.26.0')
        self.assertTrue(result.not_modified)
        self.assertIsNone(result.info)
        result, _ = self._check_beta(FetchResult(error='timed out'), '0.26.0')
        self.assertEqual(result.error, 'timed out')

    def test_stable_ignores_a_prerelease(self):
        # /releases/latest never names one; if it ever did, Stable would not take it
        result, _ = self._check(FetchResult(release=_release('v9.9.9', prerelease=True)),
                                '0.3.0', channel='stable')
        self.assertIsNone(result.info)

    def test_an_unknown_channel_reads_the_latest_release(self):
        result, fetch = self._check(FetchResult(release=_release('v9.9.9')), '0.3.0',
                                    channel='nightly')
        fetch.assert_called_once_with(None)
        self.assertEqual(result.info.version, '9.9.9')


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
