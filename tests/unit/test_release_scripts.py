#!/usr/bin/env python3
"""The release scripts of issue #134: the release job's tag guard
(scripts/release_guard.py, run against a throwaway git repository) and the
promotion of a beta to Stable (scripts/promote_release.py, with its GitHub
calls replaced)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load('release_guard.py')
promote = _load('promote_release.py')


# ---- the tag guard ----

def _git(repo, *args):
    done = subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class ReleaseGuardTests(unittest.TestCase):
    """main: v0.1.0 -> v0.2.0 -> merge of a feature branch (v0.3.0); a
    second branch with a commit main never took."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = cls.repo = Path(cls.tmp.name)
        (repo / 'src').mkdir()

        def commit(version, message):
            (repo / 'src' / 'version.py').write_text(f'__version__ = "{version}"\n',
                                                     encoding='utf-8')
            _git(repo, 'add', '-A')
            _git(repo, 'commit', '-q', '-m', message)
            return _git(repo, 'rev-parse', 'HEAD')

        _git(repo, 'init', '-q')
        _git(repo, 'checkout', '-q', '-b', 'main')
        cls.first = commit('0.1.0', 'first')
        _git(repo, 'tag', 'v0.1.0')
        cls.second = commit('0.2.0', 'second')
        _git(repo, 'tag', 'v0.2.0')
        _git(repo, 'checkout', '-q', '-b', 'feature')
        commit('0.3.0', 'feature')
        _git(repo, 'checkout', '-q', 'main')
        _git(repo, 'merge', '-q', '--no-ff', '-m', 'merge feature', 'feature')
        cls.merge = _git(repo, 'rev-parse', 'HEAD')
        _git(repo, 'tag', 'v0.3.0')
        _git(repo, 'checkout', '-q', '-b', 'unmerged')
        cls.unmerged = commit('0.4.0', 'never merged')
        _git(repo, 'checkout', '-q', 'main')
        _git(repo, 'update-ref', 'refs/remotes/origin/main', 'main')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_good_tag_passes(self):
        self.assertEqual(guard.check('v0.3.0', self.merge, '0.3.0', cwd=self.repo), [])

    def test_a_tag_that_is_not_a_version(self):
        for tag in ('v0.3', 'esobuild-assets-u52-20261101', 'v0.3.0-beta.1', '0.3.0'):
            errors = guard.check(tag, self.merge, '0.3.0', cwd=self.repo)
            self.assertTrue(any('is not vX.Y.Z' in e for e in errors), (tag, errors))

    def test_a_tag_that_does_not_match_version_py(self):
        errors = guard.check('v0.3.0', self.merge, '0.2.9', cwd=self.repo)
        self.assertEqual(errors, ['tag v0.3.0 does not match src/version.py (0.2.9)'])

    def test_a_commit_that_is_not_on_main(self):
        errors = guard.check('v0.4.0', self.unmerged, '0.4.0', cwd=self.repo)
        self.assertEqual(len(errors), 1)
        self.assertIn('is not on origin/main', errors[0])

    def test_the_previous_tag_is_main_as_it_was(self):
        # A merge commit's first parent is main before the merge
        self.assertEqual(guard.previous_tag(self.merge, self.repo), 'v0.2.0')
        self.assertEqual(guard.previous_tag(self.second, self.repo), 'v0.1.0')
        self.assertEqual(guard.previous_tag(self.first, self.repo), '')

    def test_main_writes_the_previous_tag_for_the_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'out.txt'
            with patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}):
                code = guard.main(['v0.3.0', self.merge, '--repo', str(self.repo)])
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding='utf-8'), 'previous=v0.2.0\n')

    def test_the_version_is_read_from_the_tagged_commit(self):
        # Not from the working tree: the right version on the wrong commit fails
        self.assertEqual(guard.version_at(self.second, self.repo), '0.2.0')
        self.assertEqual(guard.version_at(self.unmerged, self.repo), '0.4.0')
        self.assertEqual(guard.version_at('no-such-commit', self.repo), '')
        with patch('builtins.print'):
            self.assertEqual(guard.main(['v0.3.0', self.second, '--repo', str(self.repo)]), 1)

    def test_main_refuses_with_a_github_error_line(self):
        with patch('builtins.print') as printed:
            code = guard.main(['v0.4.0', self.unmerged, '--repo', str(self.repo)])
        self.assertEqual(code, 1)
        lines = [call.args[0] for call in printed.call_args_list]
        self.assertTrue(all(line.startswith('::error::') for line in lines), lines)

    def test_the_real_version_file_is_read(self):
        from version import __version__
        self.assertEqual(guard.version_at('HEAD', REPO_ROOT), __version__)


# ---- promotion ----

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def _notes(*titles, start=1):
    lines = [f'* {title} by @brainsnorkel in https://github.com/x/y/pull/{n}'
             for n, title in enumerate(titles, start)]
    return ("## What's Changed\n" + '\n'.join(lines)
            + '\n\n## New Contributors\n* @someone made their first contribution\n'
            + '\n**Full Changelog**: https://github.com/x/y/compare/v1...v2\n')


def _rel(tag, prerelease=True, published='2026-11-01T12:00:00Z', body='', assets=None,
         draft=False):
    version = tag[1:]
    if assets is None:
        assets = [{'name': f'{prefix}{version}{suffix}'} for prefix, suffix in promote.ASSETS]
    return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft,
            'published_at': published, 'body': body, 'assets': assets}


def _issue(number, title, state='OPEN', closed=None, body=''):
    return {'number': number, 'title': title, 'body': body, 'state': state, 'closedAt': closed}


RELEASES = [
    _rel('v0.26.0', prerelease=False, published='2026-10-30T10:26:21Z',
         body=_notes('Update channels in the app')),
    _rel('v0.26.1', published='2026-11-01T12:00:00Z', body=_notes('Fix A', 'Fix B', start=10)),
    _rel('v0.27.0', published='2026-11-03T12:00:00Z', body=_notes('Feature C', start=20)),
    _rel('v0.27.1', published='2026-11-09T12:00:00Z', body=_notes('Feature D', start=30)),
    _rel('esobuild-assets-u52-20261101', prerelease=False, published='2026-11-02T00:00:00Z'),
]
BY_TAG = {r['tag_name']: r for r in RELEASES}


class RulesTests(unittest.TestCase):

    def test_versions_and_app_releases(self):
        self.assertEqual(promote.version_of(BY_TAG['v0.27.1']), (0, 27, 1))
        self.assertIsNone(promote.version_of(BY_TAG['esobuild-assets-u52-20261101']))
        drafts = RELEASES + [_rel('v0.28.0', draft=True)]
        self.assertEqual([r['tag_name'] for r in promote.app_releases(drafts)],
                         ['v0.26.0', 'v0.26.1', 'v0.27.0', 'v0.27.1'])

    def test_all_three_files(self):
        self.assertTrue(promote.has_all_assets(BY_TAG['v0.27.0']))
        two = _rel('v0.27.0', assets=[{'name': 'esolog-tail-windows-setup-0.27.0.exe'},
                                      {'name': 'esolog-tail-linux-x86_64-0.27.0.tar.gz'}])
        self.assertFalse(promote.has_all_assets(two))

    def test_a_regression_names_its_version_in_the_title(self):
        self.assertEqual(promote.introduced_in(_issue(1, 'Regression in v0.27.0: x')), (0, 27, 0))
        # Never the body: a pasted environment would read as a version
        self.assertIsNone(promote.introduced_in(_issue(1, 'Bars wrong',
                                                       body='Python 3.14.10, Qt 6.12.0')))
        self.assertIsNone(promote.introduced_in(_issue(1, 'IP 10.0.0.1 is not a version')))

    def test_a_regression_without_a_version_blocks_every_release(self):
        vague = _issue(8, 'Crash since the last beta', body='Python 3.14.10')
        for tag in ('v0.26.1', 'v0.27.0', 'v0.27.1'):
            self.assertEqual(promote.regressions_affecting(BY_TAG[tag], [vague]), [8], tag)

    def test_which_releases_a_regression_affects(self):
        open_issue = _issue(5, 'Regression in v0.27.0')
        self.assertEqual(promote.regressions_affecting(BY_TAG['v0.26.1'], [open_issue]), [])
        self.assertEqual(promote.regressions_affecting(BY_TAG['v0.27.0'], [open_issue]), [5])
        self.assertEqual(promote.regressions_affecting(BY_TAG['v0.27.1'], [open_issue]), [5])
        # Closed on 5 November: v0.27.0 (3 Nov) carried the fault, v0.27.1 (9 Nov) the fix
        closed = _issue(6, 'Regression in v0.27.0', state='CLOSED', closed='2026-11-05T00:00:00Z')
        self.assertEqual(promote.regressions_affecting(BY_TAG['v0.27.0'], [closed]), [6])
        self.assertEqual(promote.regressions_affecting(BY_TAG['v0.27.1'], [closed]), [])

    def test_what_no_force_overrides(self):
        stable = BY_TAG['v0.26.0']
        self.assertEqual(promote.hard_problems(BY_TAG['v0.27.0'], stable), [])
        self.assertEqual(promote.hard_problems(None, stable), ['there is no such release'])
        self.assertIn('it is already a full release', promote.hard_problems(stable, stable))
        older = _rel('v0.25.9')
        self.assertTrue(any('not newer' in p for p in promote.hard_problems(older, stable)))
        bare = _rel('v0.27.0', assets=[])
        self.assertIn('it lacks one of the three files', promote.hard_problems(bare, stable))
        data = BY_TAG['esobuild-assets-u52-20261101']
        self.assertEqual(promote.hard_problems(data, stable),
                         ['it is not an app release (vX.Y.Z)'])

    def test_what_force_overrides(self):
        self.assertEqual(promote.soft_problems(BY_TAG['v0.27.0'], NOW, [], used_live=True), [])
        young = promote.soft_problems(BY_TAG['v0.27.1'], NOW, [], used_live=True)
        self.assertEqual(young, ['published 24 hours ago; the rule is 48'])
        flagged = promote.soft_problems(BY_TAG['v0.27.0'], NOW,
                                        [_issue(7, 'Regression in v0.27.0')], used_live=True)
        self.assertEqual(flagged, ['affected by regression issue #7'])
        unconfirmed = promote.soft_problems(BY_TAG['v0.27.0'], NOW, [], used_live=False)
        self.assertIn('--used-live', unconfirmed[0])

    def test_candidates_list_betas_newer_than_stable(self):
        report = promote.candidates(RELEASES, BY_TAG['v0.26.0'], NOW, [])
        self.assertEqual([(r['tag_name'], bool(p)) for r, p in report],
                         [('v0.26.1', False), ('v0.27.0', False), ('v0.27.1', True)])


class NotesTests(unittest.TestCase):

    def test_pull_request_lines_only(self):
        lines = promote.change_lines(_notes('Fix A', 'Fix B'))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('* Fix A by @brainsnorkel'))
        self.assertEqual(promote.change_lines(''), [])
        self.assertEqual(promote.change_lines(None), [])

    def test_the_combined_notes(self):
        notes = promote.combined_notes(RELEASES, BY_TAG['v0.26.0'], BY_TAG['v0.27.0'], NOW)
        self.assertTrue(notes.startswith('## Changes since v0.26.0\n'))
        body = notes.split('**Full Changelog**')[0]
        # The releases in between, oldest first; not Stable's own, not later ones
        self.assertLess(body.index('Fix A'), body.index('Fix B'))
        self.assertLess(body.index('Fix B'), body.index('Feature C'))
        self.assertNotIn('Update channels in the app', body)
        self.assertNotIn('Feature D', body)
        self.assertNotIn('first contribution', body)
        self.assertIn('/compare/v0.26.0...v0.27.0', notes)
        self.assertIn('one of 2 beta releases since v0.26.0', notes)
        self.assertNotIn('before meeting every rule', notes)

    def test_repeated_lines_once_and_the_reason(self):
        repeated = RELEASES + [_rel('v0.27.2', body=_notes('Feature C', start=20))]
        notes = promote.combined_notes(repeated, BY_TAG['v0.26.0'], repeated[-1], NOW,
                                       reason='crash fix')
        self.assertEqual(notes.count('Feature C'), 1)
        self.assertIn('Made Stable before meeting every rule: crash fix', notes)


class ActionTests(unittest.TestCase):
    """promote, demote and remind with GitHub replaced."""

    def _github(self, latest=('v0.26.0',), issues=(), open_titles=()):
        calls = []

        def gh(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps([{'number': 99, 'title': t} for t in open_titles])
            return ''
        patches = [
            patch.object(promote, 'fetch_releases', return_value=[dict(r) for r in RELEASES]),
            patch.object(promote, 'fetch_latest_tag', side_effect=list(latest)),
            patch.object(promote, 'fetch_regression_issues', return_value=list(issues)),
            patch.object(promote, 'gh', side_effect=gh),
            patch.object(promote, 'LATEST_RETRY_S', 0),
            patch('builtins.print'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return calls

    def test_a_dry_run_changes_nothing(self):
        calls = self._github()
        notes = promote.promote('v0.27.0', used_live=True, dry_run=True, now=NOW)
        self.assertIn('## Changes since v0.26.0', notes)
        self.assertEqual(calls, [])

    def test_promotion_flips_the_release_checks_latest_and_starts_pages(self):
        calls = self._github(latest=('v0.26.0', 'v0.27.0'))
        promote.promote('v0.27.0', used_live=True, now=NOW)
        self.assertEqual(len(calls), 2)
        args = calls[0]
        self.assertEqual(args[:3], ('release', 'edit', 'v0.27.0'))
        self.assertIn('--prerelease=false', args)
        self.assertIn('--latest', args)
        self.assertIn('--notes-file', args)
        # On main: the github-pages environment deploys from main only
        self.assertEqual(calls[1][:3], ('workflow', 'run', 'pages.yml'))

    def test_a_data_release_as_latest_is_refused_cleanly(self):
        self._github(latest=('esobuild-assets-u52-20261101',))
        with self.assertRaisesRegex(promote.PromotionError, 'not an app release'):
            promote.promote('v0.27.0', used_live=True, dry_run=True, now=NOW)
        self._github(latest=('v0.26.0',))
        with self.assertRaisesRegex(promote.PromotionError, 'not an app release'):
            promote.promote('esobuild-assets-u52-20261101', used_live=True, dry_run=True,
                            now=NOW)

    def test_latest_that_never_moves_is_an_error(self):
        self._github(latest=('v0.26.0', 'v0.26.0', 'v0.26.0'))
        with self.assertRaises(promote.PromotionError):
            promote.promote('v0.27.0', used_live=True, now=NOW)

    def test_refusals_and_force(self):
        self._github(latest=('v0.26.0',) * 4)
        with self.assertRaisesRegex(promote.PromotionError, 'does not meet the rules'):
            promote.promote('v0.27.1', used_live=True, dry_run=True, now=NOW)
        with self.assertRaisesRegex(promote.PromotionError, 'already a full release'):
            promote.promote('v0.26.0', used_live=True, reason='any', dry_run=True, now=NOW)
        notes = promote.promote('v0.27.1', used_live=True, reason='crash fix', dry_run=True,
                                now=NOW)
        self.assertIn('before meeting every rule: crash fix', notes)

    def test_demotion_pulls_the_release_and_falls_back(self):
        releases = [dict(r) for r in RELEASES]
        releases[2]['prerelease'] = False          # v0.27.0 had been made Stable
        calls = self._github(latest=('v0.27.0', 'v0.26.0'))
        with patch.object(promote, 'fetch_releases', return_value=releases):
            self.assertEqual(promote.demote('v0.27.0'), 'v0.26.0')
        # A draft, not a pre-release: a pre-release would still be the newest beta
        self.assertEqual(calls[0][:3], ('release', 'edit', 'v0.27.0'))
        self.assertIn('--draft', calls[0])
        self.assertEqual(calls[1][:3], ('release', 'edit', 'v0.26.0'))
        self.assertIn('--latest', calls[1])
        self.assertEqual(calls[2][:3], ('workflow', 'run', 'pages.yml'))

    def test_only_the_stable_release_can_be_demoted(self):
        self._github()
        with self.assertRaisesRegex(promote.PromotionError, 'is not the Stable release'):
            promote.demote('v0.27.0')

    def test_the_reminder_waits_for_fourteen_days(self):
        # The oldest beta that qualifies, v0.26.1, has waited nine days
        calls = self._github()
        self.assertIsNone(promote.remind(now=NOW))
        self.assertEqual(calls, [])

    def test_the_reminder_measures_the_wait_not_the_gap_to_stable(self):
        # v0.26.1 came two days after Stable; three weeks on, nobody has decided
        later_now = datetime(2026, 11, 23, tzinfo=timezone.utc)
        calls = self._github()
        title = promote.remind(now=later_now)
        self.assertEqual(title, 'Stable is behind: v0.27.1 could be made Stable')
        self.assertEqual(calls[-1][:2], ('issue', 'create'))
        # One open already: nothing new
        calls = self._github(open_titles=('Stable is behind: v0.27.1 could be made Stable',))
        self.assertIsNone(promote.remind(now=later_now))
        self.assertFalse(any(c[:2] == ('issue', 'create') for c in calls))

    def test_no_reminder_right_after_a_promotion(self):
        # v0.27.0 made Stable today: the betas left are newer and young
        promoted = [dict(r) for r in RELEASES]
        promoted[2]['prerelease'] = False
        calls = self._github(latest=('v0.27.0',))
        with patch.object(promote, 'fetch_releases', return_value=promoted):
            self.assertIsNone(promote.remind(now=NOW))
        self.assertEqual(calls, [])

    def test_the_command_line(self):
        self._github(latest=('v0.26.0',) * 2)
        self.assertEqual(promote.main(['--candidates']), 0)
        self.assertEqual(promote.main(['v0.27.1', '--used-live', '--dry-run']), 1)
        with self.assertRaises(SystemExit):
            promote.main([])


class GhTests(unittest.TestCase):

    def test_replies_are_read_as_utf8(self):
        # Read as the Windows code page, a ⓘ in a beta's notes came back as
        # mojibake and went on into the Stable notes
        run = subprocess.run
        echo = ("import json, sys; sys.stdout.buffer.write("
                "json.dumps(['\\u24d8', *sys.argv[1:]], ensure_ascii=False).encode('utf-8'))")

        def fake(argv, **kwargs):
            self.assertEqual(argv[0], 'gh')
            return run([sys.executable, '-c', echo, *argv[1:]], **kwargs)
        with patch.object(promote.subprocess, 'run', side_effect=fake):
            self.assertEqual(json.loads(promote.gh('api', 'repos/o/r/releases')),
                             ['ⓘ', 'api', 'repos/o/r/releases'])


if __name__ == '__main__':
    unittest.main()
