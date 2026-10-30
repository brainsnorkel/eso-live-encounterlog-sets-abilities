#!/usr/bin/env python3
"""The home page build (scripts/build_site.py): the release's version and
asset links fill the page, every placeholder is known, the screenshots the
page uses exist, and a release that cannot serve the page stops the build."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_site = _load('build_site.py')


def _release(tag='v0.13.3', assets=None, **extra):
    """A release as the GitHub API returns it, cut down to what the build
    reads; the three assets of a real release unless *assets* is given."""
    if assets is None:
        version = tag.lstrip('v')
        base = f'https://github.com/x/y/releases/download/{tag}/'
        assets = [
            {'name': f'esolog-tail-windows-setup-{version}.exe',
             'browser_download_url': base + f'esolog-tail-windows-setup-{version}.exe'},
            {'name': f'esolog-tail-windows-portable-{version}.zip',
             'browser_download_url': base + f'esolog-tail-windows-portable-{version}.zip'},
            {'name': f'esolog-tail-linux-x86_64-{version}.tar.gz',
             'browser_download_url': base + f'esolog-tail-linux-x86_64-{version}.tar.gz'},
        ]
    release = {'tag_name': tag, 'draft': False, 'prerelease': False,
               'html_url': f'https://github.com/x/y/releases/tag/{tag}',
               'assets': assets}
    release.update(extra)
    return release


class ReleaseValuesTests(unittest.TestCase):

    def test_version_and_three_asset_urls(self):
        values = build_site.release_values(_release('v0.13.3'))
        self.assertEqual(values['version'], '0.13.3')
        self.assertEqual(values['release_url'],
                         'https://github.com/x/y/releases/tag/v0.13.3')
        self.assertTrue(values['windows_setup_url'].endswith('-0.13.3.exe'))
        self.assertTrue(values['windows_portable_url'].endswith('-0.13.3.zip'))
        self.assertTrue(values['linux_url'].endswith('-0.13.3.tar.gz'))

    def test_missing_asset_stops_the_build(self):
        release = _release()
        release['assets'] = release['assets'][:2]  # no Linux tarball
        with self.assertRaises(build_site.SiteBuildError) as caught:
            build_site.release_values(release)
        self.assertIn('linux', str(caught.exception))

    def test_draft_prerelease_and_odd_tag_stop_the_build(self):
        for bad in (_release(draft=True), _release(prerelease=True),
                    _release(tag='v1.0'), {'tag_name': 'nightly'}, []):
            with self.subTest(bad=bad), \
                    self.assertRaises(build_site.SiteBuildError):
                build_site.release_values(bad)


class RenderTests(unittest.TestCase):

    def test_fills_placeholders(self):
        out = build_site.render('<a href="{{linux_url}}">{{version}}</a>',
                                {'linux_url': 'u', 'version': '1.2.3'})
        self.assertEqual(out, '<a href="u">1.2.3</a>')

    def test_unknown_placeholder_is_an_error(self):
        with self.assertRaises(build_site.SiteBuildError) as caught:
            build_site.render('{{version}} {{typo}}', {'version': '1'})
        self.assertIn('typo', str(caught.exception))

    def test_page_uses_only_known_placeholders(self):
        html = (REPO_ROOT / 'site' / 'index.html').read_text(encoding='utf-8')
        known = set(build_site.release_values(_release())) | {'site_url', 'beta_line'}
        used = set(build_site._PLACEHOLDER_RE.findall(html))
        self.assertTrue(used <= known, used - known)
        # The buttons and the card need these; a page without them is wrong
        self.assertTrue({'version', 'windows_setup_url', 'site_url'} <= used)


class BuildTests(unittest.TestCase):

    def test_builds_the_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_site.build(Path(tmp) / 'out', _release('v0.13.3'))
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('{{', html)
            self.assertIn('version 0.13.3', html)
            self.assertIn('esolog-tail-windows-setup-0.13.3.exe', html)
            self.assertIn('esolog-tail-windows-portable-0.13.3.zip', html)
            self.assertIn('esolog-tail-linux-x86_64-0.13.3.tar.gz', html)
            # Absolute URLs for the link unfurl, under the page's own URL
            self.assertIn(f'content="{build_site.SITE_URL}social-card.png"', html)
            self.assertIn(f'href="{build_site.SITE_URL}"', html)
            self.assertTrue((out / '.nojekyll').is_file())
            self.assertTrue((out / 'social-card.png').is_file())
            self.assertTrue((out / 'favicon.png').is_file())
            for name in build_site.page_images(html):
                self.assertTrue((out / 'img' / name).is_file(), name)
            self.assertIn('main-window.png', build_site.page_images(html))

    def test_the_beta_line_names_the_newest_beta_newer_than_stable(self):
        releases = [_release('v0.27.1', prerelease=True),
                    _release('v0.27.2', prerelease=True),
                    _release('v0.28.0', prerelease=True, draft=True),
                    _release('v0.27.0'),
                    _release('esobuild-assets-9.9.9', prerelease=True),
                    _release('v0.29.0', prerelease=True, assets=[])]   # no installer
        line = build_site.beta_line(releases, '0.27.0')
        self.assertIn('beta 0.27.2</a> for Windows', line)
        self.assertIn('esolog-tail-windows-setup-0.27.2.exe', line)
        self.assertIn('releases/tag/v0.27.2', line)
        self.assertIn('choose Beta under Settings', line)
        # Nothing newer than Stable, or nothing at all: no line
        self.assertEqual(build_site.beta_line(releases, '0.27.2'), '')
        self.assertEqual(build_site.beta_line([], '0.27.0'), '')
        self.assertEqual(build_site.beta_line(None, '0.27.0'), '')

    def test_the_page_carries_the_beta_line_only_when_there_is_a_beta(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_site.build(Path(tmp) / 'a', _release('v0.27.0'),
                                   releases=[_release('v0.27.1', prerelease=True)])
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('beta 0.27.1</a>', html)
            out = build_site.build(Path(tmp) / 'b', _release('v0.27.0'))
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('still being tried out', html)
            self.assertNotIn('{{', html)

    def test_main_reads_a_saved_release_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'release.json'
            saved.write_text(json.dumps(_release('v0.27.0')), encoding='utf-8')
            listed = Path(tmp) / 'releases.json'
            listed.write_text(json.dumps([_release('v0.27.3', prerelease=True)]),
                              encoding='utf-8')
            out = Path(tmp) / 'site'
            self.assertEqual(build_site.main(['--out', str(out), '--release-json', str(saved),
                                              '--releases-json', str(listed)]), 0)
            self.assertIn('beta 0.27.3', (out / 'index.html').read_text(encoding='utf-8'))

    def test_site_url_override_gets_a_trailing_slash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_site.build(Path(tmp) / 'out', _release(),
                                   site_url='https://example.invalid/tail')
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('content="https://example.invalid/tail/social-card.png"', html)

    def test_main_builds_from_a_saved_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'release.json'
            saved.write_text(json.dumps(_release('v9.8.7')), encoding='utf-8')
            out = Path(tmp) / 'site'
            self.assertEqual(build_site.main(['--out', str(out),
                                              '--release-json', str(saved)]), 0)
            self.assertIn('9.8.7', (out / 'index.html').read_text(encoding='utf-8'))

    def test_main_reports_a_bad_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'release.json'
            saved.write_text(json.dumps(_release(draft=True)), encoding='utf-8')
            self.assertEqual(build_site.main(['--out', str(Path(tmp) / 'site'),
                                              '--release-json', str(saved)]), 1)


if __name__ == '__main__':
    unittest.main()
