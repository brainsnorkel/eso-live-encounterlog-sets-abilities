#!/usr/bin/env python3
"""Make a release's commit, or tag a release once its pull request is merged.

Design (issue #134, task 2.5; the maintainer's decisions 11 and 12 of
2026-10-29): every session cut releases its own way, and almost every pull
request edited the same lines of two shared files, the top of
CHANGELOG.md and docs/design.md, so each merge put every other open pull
request in conflict (24 merges of main into PR branches in five days).
Three changes together end that:

- A change adds its notes as a fragment, ``changelog.d/<issue>-<slug>.md``,
  written under the same ``### Added`` / ``### Changed`` / ``### Fixed``
  headings CHANGELOG.md uses. Two pull requests never edit the same file,
  and the CI check (scripts/changelog_check.py) asks every pull request for
  one.
- ``docs/design.md`` is regenerated in the release commit only. Between
  releases the docstrings it is built from are the source; the release job
  refuses a tag whose design notes are stale (build_design_doc --check).
- This script makes the release commit's edits the same way every time:
  the version in src/version.py, the fragments gathered under
  ``## [X.Y.Z] - YYYY-MM-DD`` at the top of CHANGELOG.md (any
  ``[Unreleased]`` section a branch from before fragments still carries is
  folded in, not lost), the fragments removed, the design notes rebuilt,
  and one commit, ``chore: release X.Y.Z``. Sections come out in Keep a
  Changelog's order and, within a section, in fragment file name order, so
  the same fragments always give the same text.

The release commit goes inside the last pull request of the release, or one
of its own, since main takes pull requests only. The script refuses to
commit on main or over uncommitted changes, and the version must be higher
than the current one. ``minor`` or ``patch`` picks the next number; the
choice stays the releasing session's (a release with only Fixed entries is
a patch).

Once that pull request is merged, ``--tag X.Y.Z`` finds the commit on
origin/main that first carries the version (the merge commit, on main's
first-parent line), runs the release job's own checks on it
(scripts/release_guard.py) and makes the annotated tag. Pushing the tag
publishes a beta to every install on the Beta channel, so it happens only
with ``--push``; ``--watch`` then waits for the tag's workflow run and
checks what it published: a pre-release with all three files, and
``/releases/latest`` (Stable) not moved. Making a beta Stable stays
scripts/promote_release.py's, on the maintainer's word.

Needs git; ``--watch`` needs the GitHub CLI, logged in.

    python scripts/release.py minor|patch|X.Y.Z [--date YYYY-MM-DD] [--trailer TEXT] [--dry-run]
    python scripts/release.py --tag X.Y.Z [--push] [--watch]
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_design_doc
import release_guard
from promote_release import ASSETS, REPO

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = "changelog.d"
FRAGMENT_GUIDE = "README.md"
# Keep a Changelog's sections, in its order
SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
# A release with any of these is a minor one; Fixed and Security alone, a patch
MINOR_SECTIONS = ("Added", "Changed", "Deprecated", "Removed")
TAG_MESSAGE = "ESO Log Tail {version}"
RUN_APPEARS_S = 120

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_SECTION_RE = re.compile(r"^###\s+(\S.*?)\s*$")
_RELEASE_HEADING_RE = re.compile(r"^## \[", re.MULTILINE)
_UNRELEASED_RE = re.compile(r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|\Z)",
                            re.MULTILINE | re.DOTALL)


class ReleaseError(Exception):
    """A refusal or a failed step; the message says which."""


# ---- fragments and the changelog ----

def parse_notes(text: str, name: str) -> dict:
    """{section: [entry text]} from Markdown written under ``### Section``
    headings. Text before the first heading, an unknown heading or a
    fragment with no entries is refused: a note filed under no section
    would be dropped from the release notes without a word."""
    sections = {}
    current = None
    for line in text.splitlines():
        heading = _SECTION_RE.match(line)
        if heading:
            current = heading.group(1)
            if current not in SECTIONS:
                raise ReleaseError(f"{name}: unknown section '### {current}' "
                                   f"(use {', '.join(SECTIONS)})")
            sections.setdefault(current, [])
            continue
        if not line.strip():
            if current and sections[current]:
                sections[current].append("")
            continue
        if current is None:
            raise ReleaseError(f"{name}: text before the first '### Added', '### Changed' "
                               f"or '### Fixed' heading")
        sections[current].append(line.rstrip())
    out = {}
    for section, lines in sections.items():
        entry = "\n".join(lines).strip("\n")
        if entry:
            out[section] = [entry]
    if not out:
        raise ReleaseError(f"{name}: no entries")
    return out


def merge(into: dict, notes: dict) -> dict:
    for section, entries in notes.items():
        into.setdefault(section, []).extend(entries)
    return into


def fragment_files(root: Path) -> list:
    """The fragments in changelog.d/, by file name; the guide is not one."""
    folder = root / FRAGMENTS
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.md") if p.name != FRAGMENT_GUIDE)


def gather(root: Path) -> tuple:
    """({section: [entries]}, [fragment paths]) from changelog.d/."""
    notes = {}
    files = fragment_files(root)
    for path in files:
        merge(notes, parse_notes(path.read_text(encoding="utf-8"), path.name))
    return notes, files


def split_unreleased(changelog: str) -> tuple:
    """(the changelog without its ``[Unreleased]`` section, that section's
    notes or {}). A branch from before fragments may still carry one. Only
    a section above the newest release counts: the changelog's history
    keeps an old ``[Unreleased] - 2025-01-22`` that is not to be touched."""
    first = _RELEASE_HEADING_RE.search(changelog)
    match = _UNRELEASED_RE.search(changelog)
    if not match or match.start() != (first.start() if first else -1):
        return changelog, {}
    body = match.group(1)
    notes = parse_notes(body, "CHANGELOG.md [Unreleased]") if body.strip() else {}
    return changelog[:match.start()] + changelog[match.end():], notes


def release_section(version: str, day: str, notes: dict) -> str:
    out = [f"## [{version}] - {day}", ""]
    for section in SECTIONS:
        if notes.get(section):
            out += [f"### {section}", *notes[section], ""]
    return "\n".join(out).rstrip("\n") + "\n"


def add_release(changelog: str, section: str) -> str:
    """*section* placed above the newest release, or at the end when there
    is none yet."""
    match = _RELEASE_HEADING_RE.search(changelog)
    if not match:
        return changelog.rstrip("\n") + "\n\n" + section
    return changelog[:match.start()] + section + "\n" + changelog[match.start():]


# ---- versions ----

def parse_version(text: str) -> tuple:
    match = _VERSION_RE.fullmatch(text.strip())
    if not match:
        raise ReleaseError(f"{text!r} is not X.Y.Z")
    return tuple(int(part) for part in match.groups())


def next_version(current: str, wanted: str) -> str:
    """*wanted* as a version: ``major``, ``minor`` or ``patch`` counted from
    *current*, or an X.Y.Z of its own, which must be higher."""
    major, minor, patch = parse_version(current)
    bumps = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0),
             "patch": (major, minor, patch + 1)}
    new = bumps.get(wanted) or parse_version(wanted)
    if new <= (major, minor, patch):
        raise ReleaseError(f"{'.'.join(map(str, new))} is not higher than {current}")
    return ".".join(map(str, new))


def suggested_bump(notes: dict) -> str:
    return "minor" if any(notes.get(s) for s in MINOR_SECTIONS) else "patch"


def set_version(text: str, version: str) -> str:
    """src/version.py's text with ``__version__`` and ``__version_info__``
    set to *version*; refused when either line is missing."""
    info = ", ".join(str(n) for n in parse_version(version))
    text, n_version = re.subn(r'^__version__\s*=.*$', f'__version__ = "{version}"',
                              text, flags=re.MULTILINE)
    text, n_info = re.subn(r'^__version_info__\s*=.*$', f'__version_info__ = ({info})',
                           text, flags=re.MULTILINE)
    if not (n_version and n_info):
        raise ReleaseError("src/version.py has no __version__ or no __version_info__ line")
    return text


# ---- git ----

def git(root: Path, *args, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise ReleaseError(f"git {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def current_version(root: Path) -> str:
    match = re.search(r"""^__version__\s*=\s*["']([^"']+)["']""",
                      (root / "src" / "version.py").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ReleaseError("src/version.py has no __version__")
    return match.group(1)


# ---- the release commit ----

def prepare(wanted: str, day: str = "", trailers=(), dry_run: bool = False,
            root: Path = ROOT, regenerate=None) -> str:
    """Make the release commit; returns the version. *regenerate* rebuilds
    docs/design.md (build_design_doc.render unless a test passes its own)."""
    if not dry_run:
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
        if branch in ("main", "HEAD"):
            raise ReleaseError(f"on {branch}: the release commit goes on a pull request's branch")
        if git(root, "status", "--porcelain", "--untracked-files=no"):
            raise ReleaseError("uncommitted changes: commit or set them aside first, so the "
                               "release commit holds only the release")
    current = current_version(root)
    changelog_path = root / "CHANGELOG.md"
    changelog, leftover = split_unreleased(changelog_path.read_text(encoding="utf-8"))
    notes, files = gather(root)
    notes = merge(leftover, notes) if leftover else notes
    if not notes:
        raise ReleaseError(f"nothing to release: no fragments in {FRAGMENTS}/ and no "
                           f"[Unreleased] section")
    version = next_version(current, wanted)
    # The maintainer's local date, as the releases before the script had it
    day = day or datetime.now(timezone.utc).astimezone().date().isoformat()
    section = release_section(version, day, notes)
    print(f"{current} -> {version} (the notes suggest a {suggested_bump(notes)} release); "
          f"{len(files)} fragment{'s' if len(files) != 1 else ''}"
          f"{' and the [Unreleased] section' if leftover else ''}\n")
    print(section)
    if dry_run:
        return version
    version_path = root / "src" / "version.py"
    version_path.write_text(set_version(version_path.read_text(encoding="utf-8"), version),
                            encoding="utf-8")
    changelog_path.write_text(add_release(changelog, section), encoding="utf-8")
    if files:
        git(root, "rm", "-q", "--", *[p.relative_to(root).as_posix() for p in files])
    (regenerate or build_design_doc.render)()
    git(root, "add", "--", "src/version.py", "CHANGELOG.md", "docs/design.md")
    message = f"chore: release {version}"
    if trailers:
        message += "\n\n" + "\n".join(trailers)
    git(root, "commit", "-q", "-m", message)
    print(f"Committed {git(root, 'rev-parse', '--short', 'HEAD')} chore: release {version}. "
          f"Push it, merge the pull request once its checks pass, then:\n"
          f"    python scripts/release.py --tag {version} --push --watch")
    return version


# ---- the tag ----

def merge_commit_of(version: str, ref: str = "origin/main", root: Path = ROOT) -> str:
    """The commit on *ref*'s first-parent line that first carries *version*
    in src/version.py: the release pull request's merge commit; '' when
    none does."""
    for commit in git(root, "rev-list", "--first-parent", ref, "--", "src/version.py").split():
        if (release_guard.version_at(commit, root) == version
                and release_guard.version_at(f"{commit}^", root) != version):
            return commit
    return ""


def make_tag(version: str, push: bool = False, ref: str = "origin/main", fetch: bool = True,
             root: Path = ROOT) -> str:
    """Tag the merged release *version*; returns the tagged commit."""
    tag = f"v{version}"
    parse_version(version)
    if fetch:
        git(root, "fetch", "-q", "--tags", "origin", "main")
    if git(root, "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False):
        raise ReleaseError(f"{tag} already exists")
    if push and git(root, "ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        raise ReleaseError(f"{tag} already exists on origin")
    commit = merge_commit_of(version, ref, root)
    if not commit:
        raise ReleaseError(f"no commit on {ref} carries {version}: is the release pull "
                           f"request merged (and fetched)?")
    errors = release_guard.check(tag, commit, release_guard.version_at(commit, root), ref, root)
    if errors:
        raise ReleaseError("; ".join(errors))
    git(root, "tag", "-a", tag, "-m", TAG_MESSAGE.format(version=version), commit)
    print(f"Tagged {tag} on {commit[:12]} ({git(root, 'log', '-1', '--format=%s', commit)})")
    if push:
        git(root, "push", "-q", "origin", tag)
        print(f"Pushed {tag}: the Build Installers run publishes it as a beta")
    else:
        print(f"Not pushed. Pushing publishes the beta:\n    git push origin {tag}")
    return commit


def gh(*args) -> str:
    done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise ReleaseError(f"gh {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout


def published_problems(release: dict, latest_tag: str, tag: str) -> list:
    """What is wrong with a just-published beta: it must be a pre-release,
    not a draft, with all three files, and not GitHub's latest release."""
    problems = []
    if not release.get("isPrerelease"):
        problems.append(f"{tag} is not a pre-release")
    if release.get("isDraft"):
        problems.append(f"{tag} is a draft")
    version = tag[1:]
    names = {asset.get("name", "") for asset in release.get("assets") or []}
    for prefix, suffix in ASSETS:
        if f"{prefix}{version}{suffix}" not in names:
            problems.append(f"{tag} lacks {prefix}{version}{suffix}")
    if latest_tag == tag:
        problems.append(f"{tag} is the latest release: Stable moved")
    return problems


def watch(version: str) -> list:
    """Wait for the tag's Build Installers run, then check the release."""
    tag = f"v{version}"
    run_id = ""
    deadline = time.monotonic() + RUN_APPEARS_S
    while not run_id and time.monotonic() < deadline:
        runs = json.loads(gh("run", "list", "--workflow", "build-installers.yml",
                             "--branch", tag, "--limit", "1", "--json", "databaseId"))
        run_id = str(runs[0]["databaseId"]) if runs else ""
        if not run_id:
            time.sleep(10)
    if not run_id:
        raise ReleaseError(f"no Build Installers run for {tag} after {RUN_APPEARS_S} s")
    print(f"Watching run {run_id} ...", flush=True)
    done = subprocess.run(["gh", "run", "watch", run_id, "--exit-status", "--interval", "30"],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise ReleaseError(f"run {run_id} failed: gh run view {run_id} --log-failed")
    release = json.loads(gh("release", "view", tag, "--json", "isPrerelease,isDraft,assets"))
    latest = gh("api", f"repos/{REPO}/releases/latest", "--jq", ".tag_name").strip()
    problems = published_problems(release, latest, tag)
    for problem in problems:
        print(f"problem: {problem}")
    if not problems:
        print(f"{tag} is published as a beta with its three files; Stable is still {latest}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version", nargs="?",
                        help="major, minor, patch or X.Y.Z: make the release commit")
    parser.add_argument("--tag", metavar="X.Y.Z", help="tag this merged release instead")
    parser.add_argument("--date", default="", help="the release date (default: today)")
    parser.add_argument("--trailer", action="append", default=[],
                        help="a line for the end of the commit message (repeatable)")
    parser.add_argument("--push", action="store_true", help="push the tag (publishes the beta)")
    parser.add_argument("--watch", action="store_true",
                        help="after --push, wait for the run and check the release")
    parser.add_argument("--dry-run", action="store_true", help="show the notes, change nothing")
    args = parser.parse_args(argv)
    try:
        if args.tag:
            if args.watch and not args.push:
                parser.error("--watch waits for the run a pushed tag starts: add --push")
            make_tag(args.tag, push=args.push)
            if args.watch and watch(args.tag):
                return 1
        elif args.version:
            prepare(args.version, args.date, args.trailer, args.dry_run)
        else:
            parser.error("name the release (minor, patch or X.Y.Z) or --tag X.Y.Z")
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
