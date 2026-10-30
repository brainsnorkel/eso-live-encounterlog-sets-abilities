#!/usr/bin/env python3
"""Cutting a release (issue #134, task 2.5): the changelog fragments and
the release commit (scripts/release.py, run against throwaway git
repositories), the tag on the merged release, the pull request check
(scripts/changelog_check.py) and the design notes' check at a tag
(scripts/build_design_doc.py --check)."""

import importlib.util
import shutil
import subprocess
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


release = _load('release.py')
check = _load('changelog_check.py')
design = _load('build_design_doc.py')

CHANGELOG = """# Changelog

All notable changes are documented in this file.

## [0.2.0] - 2026-10-01

### Added
- Something old
"""


def _git(repo, *args):
    done = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _repo(tmp: str) -> Path:
    """A repository on main at 0.2.0 with a changelog and a fragment guide."""
    repo = Path(tmp)
    (repo / 'src').mkdir()
    (repo / 'docs').mkdir()
    (repo / 'changelog.d').mkdir()
    (repo / 'src' / 'version.py').write_text(
        '"""Version"""\n\n__version__ = "0.2.0"\n__version_info__ = (0, 2, 0)\n', encoding='utf-8')
    (repo / 'CHANGELOG.md').write_text(CHANGELOG, encoding='utf-8')
    (repo / 'changelog.d' / 'README.md').write_text('# Fragments\n', encoding='utf-8')
    (repo / 'docs' / 'design.md').write_text('old\n', encoding='utf-8')
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.name', 'Test')
    _git(repo, 'config', 'user.email', 'test@example.invalid')
    _git(repo, 'config', 'core.autocrlf', 'false')
    _git(repo, 'checkout', '-q', '-b', 'main')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'start')
    return repo


def _fragment(repo: Path, name: str, text: str):
    (repo / 'changelog.d' / name).write_text(text, encoding='utf-8')


class FragmentTests(unittest.TestCase):

    def test_sections_and_their_entries(self):
        notes = release.parse_notes('### Added\n- One\n- Two\n\n### Fixed\n- Three\n', 'f.md')
        self.assertEqual(notes, {'Added': ['- One\n- Two'], 'Fixed': ['- Three']})

    def test_unreadable_fragments_are_refused(self):
        for text, why in (('- loose\n### Added\n- x\n', 'before the first'),
                          ('### Improved\n- x\n', 'unknown section'),
                          ('### Added\n\n', 'no entries'),
                          ('', 'no entries')):
            with self.assertRaises(release.ReleaseError) as caught:
                release.parse_notes(text, 'f.md')
            self.assertIn(why, str(caught.exception))
            self.assertIn('f.md', str(caught.exception))

    def test_fragments_gather_in_file_name_order_without_the_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _repo(tmp)
            _fragment(repo, '140-b.md', '### Fixed\n- B fixed\n')
            _fragment(repo, '139-a.md', '### Added\n- A added\n\n### Fixed\n- A fixed\n')
            notes, files = release.gather(repo)
        self.assertEqual([p.name for p in files], ['139-a.md', '140-b.md'])
        self.assertEqual(notes, {'Added': ['- A added'], 'Fixed': ['- A fixed', '- B fixed']})

    def test_the_section_goes_above_the_newest_release(self):
        section = release.release_section('0.3.0', '2026-11-01',
                                          {'Fixed': ['- F'], 'Added': ['- A']})
        # Keep a Changelog's order, whatever order the notes came in
        self.assertEqual(section, '## [0.3.0] - 2026-11-01\n\n### Added\n- A\n\n### Fixed\n- F\n')
        text = release.add_release(CHANGELOG, section)
        self.assertLess(text.index('## [0.3.0]'), text.index('## [0.2.0]'))
        self.assertIn('### Fixed\n- F\n\n## [0.2.0] - 2026-10-01', text)
        self.assertTrue(text.startswith('# Changelog\n'))

    def test_an_unreleased_section_is_folded_in(self):
        old = CHANGELOG.replace('## [0.2.0]', '## [Unreleased]\n\n### Fixed\n- Left over\n\n## [0.2.0]')
        rest, notes = release.split_unreleased(old)
        self.assertEqual(notes, {'Fixed': ['- Left over']})
        self.assertEqual(rest, CHANGELOG)
        self.assertEqual(release.split_unreleased(CHANGELOG), (CHANGELOG, {}))
        # The real changelog's history keeps an old '[Unreleased] - 2025-01-22'
        # far below the releases, with headings of its own: left alone
        history = CHANGELOG + '\n## [Unreleased] - 2025-01-22\n\n### Major Optimization\n- x\n'
        self.assertEqual(release.split_unreleased(history), (history, {}))

    def test_versions(self):
        self.assertEqual(release.next_version('0.27.0', 'minor'), '0.28.0')
        self.assertEqual(release.next_version('0.27.3', 'patch'), '0.27.4')
        self.assertEqual(release.next_version('0.27.3', 'major'), '1.0.0')
        self.assertEqual(release.next_version('0.27.0', '0.30.0'), '0.30.0')
        for wanted in ('0.27.0', '0.26.9', 'v0.28.0', 'next'):
            with self.assertRaises(release.ReleaseError):
                release.next_version('0.27.0', wanted)
        self.assertEqual(release.suggested_bump({'Fixed': ['- x']}), 'patch')
        self.assertEqual(release.suggested_bump({'Fixed': ['- x'], 'Changed': ['- y']}), 'minor')

    def test_both_version_lines_are_set(self):
        text = '"""v"""\n\n__version__ = "0.27.0"\n__version_info__ = (0, 27, 0)\n'
        self.assertEqual(release.set_version(text, '0.28.1'),
                         '"""v"""\n\n__version__ = "0.28.1"\n__version_info__ = (0, 28, 1)\n')
        with self.assertRaises(release.ReleaseError):
            release.set_version('__version__ = "1.0.0"\n', '1.0.1')

    def test_every_fragment_on_this_branch_reads(self):
        # What the release commit will gather: a malformed fragment fails
        # here, in the pull request that adds it, not at the release
        notes, _files = release.gather(REPO_ROOT)
        for section in notes:
            self.assertIn(section, release.SECTIONS)


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class ReleaseCommitTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = _repo(self.tmp.name)
        self.rebuilt = []

    def tearDown(self):
        self.tmp.cleanup()

    def _regenerate(self):
        (self.repo / 'docs' / 'design.md').write_text('rebuilt\n', encoding='utf-8')
        self.rebuilt.append(True)

    def _prepare(self, wanted='minor', **kwargs):
        from unittest.mock import patch
        with patch('builtins.print'):
            return release.prepare(wanted, '2026-11-01', root=self.repo,
                                   regenerate=self._regenerate, **kwargs)

    def _on_branch_with_fragments(self):
        _git(self.repo, 'checkout', '-q', '-b', 'release')
        _fragment(self.repo, '139-a.md', '### Fixed\n- A fixed\n')
        _fragment(self.repo, '140-b.md', '### Added\n- B added\n')
        _git(self.repo, 'add', '-A')
        _git(self.repo, 'commit', '-q', '-m', 'work')

    def test_the_release_commit(self):
        self._on_branch_with_fragments()
        self.assertEqual(self._prepare(trailers=['Co-Authored-By: Someone <s@example.invalid>']),
                         '0.3.0')
        version = (self.repo / 'src' / 'version.py').read_text(encoding='utf-8')
        self.assertIn('__version__ = "0.3.0"\n__version_info__ = (0, 3, 0)', version)
        changelog = (self.repo / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertIn('## [0.3.0] - 2026-11-01\n\n### Added\n- B added\n\n### Fixed\n- A fixed\n\n'
                      '## [0.2.0]', changelog)
        # The fragments are gone, the guide stays, the design notes rebuilt
        self.assertEqual(sorted(p.name for p in (self.repo / 'changelog.d').iterdir()),
                         ['README.md'])
        self.assertEqual(self.rebuilt, [True])
        self.assertEqual(_git(self.repo, 'log', '-1', '--format=%B'),
                         'chore: release 0.3.0\n\nCo-Authored-By: Someone <s@example.invalid>')
        self.assertEqual(_git(self.repo, 'status', '--porcelain'), '')
        changed = _git(self.repo, 'show', '--name-status', '--format=', 'HEAD').splitlines()
        self.assertEqual(sorted(changed), ['D\tchangelog.d/139-a.md', 'D\tchangelog.d/140-b.md',
                                           'M\tCHANGELOG.md', 'M\tdocs/design.md',
                                           'M\tsrc/version.py'])

    def test_a_dry_run_changes_nothing(self):
        self._on_branch_with_fragments()
        head = _git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(self._prepare('patch', dry_run=True), '0.2.1')
        self.assertEqual(_git(self.repo, 'rev-parse', 'HEAD'), head)
        self.assertEqual(_git(self.repo, 'status', '--porcelain'), '')
        self.assertEqual(self.rebuilt, [])

    def test_refusals(self):
        # On main
        _fragment(self.repo, '139-a.md', '### Fixed\n- A fixed\n')
        _git(self.repo, 'add', '-A')
        _git(self.repo, 'commit', '-q', '-m', 'work on main')
        with self.assertRaisesRegex(release.ReleaseError, "on main"):
            self._prepare()
        _git(self.repo, 'checkout', '-q', '-b', 'release')
        # Uncommitted changes
        (self.repo / 'src' / 'version.py').write_text('changed\n', encoding='utf-8')
        with self.assertRaisesRegex(release.ReleaseError, 'uncommitted'):
            self._prepare()
        _git(self.repo, 'checkout', '--', 'src/version.py')
        # Not higher
        with self.assertRaisesRegex(release.ReleaseError, 'not higher'):
            self._prepare('0.2.0')
        # Nothing to release
        _git(self.repo, 'rm', '-q', 'changelog.d/139-a.md')
        _git(self.repo, 'commit', '-q', '-m', 'no notes')
        with self.assertRaisesRegex(release.ReleaseError, 'nothing to release'):
            self._prepare()
        self.assertEqual(self.rebuilt, [])

    def test_a_leftover_unreleased_section_joins_the_fragments(self):
        _git(self.repo, 'checkout', '-q', '-b', 'release')
        (self.repo / 'CHANGELOG.md').write_text(
            CHANGELOG.replace('## [0.2.0]', '## [Unreleased]\n\n### Fixed\n- Old style\n\n## [0.2.0]'),
            encoding='utf-8')
        _fragment(self.repo, '141-c.md', '### Fixed\n- New style\n')
        _git(self.repo, 'add', '-A')
        _git(self.repo, 'commit', '-q', '-m', 'both')
        self._prepare('patch')
        changelog = (self.repo / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertNotIn('Unreleased', changelog)
        self.assertIn('## [0.2.1] - 2026-11-01\n\n### Fixed\n- Old style\n- New style\n', changelog)


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class TagTests(unittest.TestCase):
    """main: 0.2.0 -> merge of a release branch (0.3.0) -> a later commit
    still at 0.3.0; a branch at 0.4.0 that main never took."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = cls.repo = _repo(cls.tmp.name)
        _git(repo, 'checkout', '-q', '-b', 'feature')
        (repo / 'src' / 'version.py').write_text('__version__ = "0.3.0"\n', encoding='utf-8')
        _git(repo, 'commit', '-q', '-am', 'chore: release 0.3.0')
        cls.release_commit = _git(repo, 'rev-parse', 'HEAD')
        _git(repo, 'checkout', '-q', 'main')
        _git(repo, 'merge', '-q', '--no-ff', '-m', 'Merge pull request #1', 'feature')
        cls.merge = _git(repo, 'rev-parse', 'HEAD')
        (repo / 'README.md').write_text('later\n', encoding='utf-8')
        _git(repo, 'add', '-A')
        _git(repo, 'commit', '-q', '-m', 'later work')
        _git(repo, 'checkout', '-q', '-b', 'unmerged')
        (repo / 'src' / 'version.py').write_text('__version__ = "0.4.0"\n', encoding='utf-8')
        _git(repo, 'commit', '-q', '-am', 'chore: release 0.4.0')
        _git(repo, 'checkout', '-q', 'main')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_merge_commit_carries_the_release(self):
        # Not the release commit on the branch, not the later commit on main
        self.assertEqual(release.merge_commit_of('0.3.0', 'main', self.repo), self.merge)
        self.assertEqual(release.merge_commit_of('0.4.0', 'main', self.repo), '')

    def test_tag_the_merged_release_once(self):
        from unittest.mock import patch
        with patch('builtins.print'):
            commit = release.make_tag('0.3.0', ref='main', fetch=False, root=self.repo)
        self.assertEqual(commit, self.merge)
        self.assertEqual(_git(self.repo, 'rev-parse', 'v0.3.0^{commit}'), self.merge)
        self.assertEqual(_git(self.repo, 'cat-file', '-t', 'v0.3.0'), 'tag')
        self.assertEqual(_git(self.repo, 'tag', '-l', '--format=%(contents:subject)', 'v0.3.0'),
                         'ESO Log Tail 0.3.0')
        with self.assertRaisesRegex(release.ReleaseError, 'already exists'):
            release.make_tag('0.3.0', ref='main', fetch=False, root=self.repo)

    def test_an_unmerged_release_is_not_tagged(self):
        with self.assertRaisesRegex(release.ReleaseError, 'is the release pull request merged'):
            release.make_tag('0.4.0', ref='main', fetch=False, root=self.repo)
        self.assertEqual(_git(self.repo, 'tag', '-l', 'v0.4.0'), '')

    def test_what_a_published_beta_must_be(self):
        names = [{'name': n} for n in ('esolog-tail-windows-setup-0.3.0.exe',
                                        'esolog-tail-windows-portable-0.3.0.zip',
                                        'esolog-tail-linux-x86_64-0.3.0.tar.gz')]
        good = {'isPrerelease': True, 'isDraft': False, 'assets': names}
        self.assertEqual(release.published_problems(good, 'v0.2.0', 'v0.3.0'), [])
        bad = {'isPrerelease': False, 'isDraft': False, 'assets': names[:2]}
        problems = release.published_problems(bad, 'v0.3.0', 'v0.3.0')
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(any('not a pre-release' in p for p in problems))
        self.assertTrue(any('linux' in p for p in problems))
        self.assertTrue(any('Stable moved' in p for p in problems))


class ChangelogCheckTests(unittest.TestCase):

    def test_a_change_with_a_fragment_passes(self):
        self.assertEqual(check.problems([('M', 'src/esolog_tail.py'),
                                         ('A', 'changelog.d/140-thing.md')]), [])

    def test_a_change_without_one_is_refused(self):
        found = check.problems([('M', 'src/esolog_tail.py')])
        self.assertEqual(len(found), 1)
        self.assertIn('no changelog fragment', found[0])
        # The guide is not a fragment
        self.assertEqual(len(check.problems([('M', 'src/a.py'), ('M', 'changelog.d/README.md')])), 1)

    def test_the_shared_files_are_the_release_commits(self):
        found = check.problems([('A', 'changelog.d/140-thing.md'), ('M', 'CHANGELOG.md'),
                                ('M', 'docs/design.md')])
        self.assertEqual(len(found), 2)
        self.assertTrue(any('CHANGELOG.md' in p for p in found))
        self.assertTrue(any('docs/design.md' in p for p in found))

    def test_a_release_and_the_label_pass(self):
        release_pr = [('M', 'src/version.py'), ('M', 'CHANGELOG.md'), ('M', 'docs/design.md'),
                      ('D', 'changelog.d/140-thing.md')]
        self.assertEqual(check.problems(release_pr), [])
        self.assertEqual(check.problems([('M', 'CHANGELOG.md')], labels=['no-changelog']), [])


class DesignCheckTests(unittest.TestCase):

    def test_the_check_compares_with_what_the_code_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'design.md'
            self.assertFalse(design.is_current(path))
            path.write_text(design.build(), encoding='utf-8')
            self.assertTrue(design.is_current(path))
            path.write_text(design.build() + 'stale\n', encoding='utf-8')
            self.assertFalse(design.is_current(path))


if __name__ == '__main__':
    unittest.main()
