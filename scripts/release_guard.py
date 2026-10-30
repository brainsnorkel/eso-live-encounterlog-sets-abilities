#!/usr/bin/env python3
"""Check a version tag before the release job publishes it, and name the
tag its notes start from.

Design (issue #134, 2026-10-29): the release job publishes whatever tag
reaches it, and nothing checked the tag until now. Three refusals, each
before anything is published:

- the tag must be exactly ``vX.Y.Z``: the app's update check counts only
  such tags, and data releases (``esobuild-assets-<update>-<date>``) are
  created by hand, never by this job;
- it must equal ``v`` + ``__version__`` in the tagged commit's
  ``src/version.py`` (read from the commit, not the checkout): the assets
  are named from that file, and the app compares its own version with the
  tag, so a mismatch would offer an installer that reports the wrong
  version (a tag pushed on the wrong commit, or a release commit missing);
- its commit must be on ``main`` (``git merge-base --is-ancestor``): tags
  are outside the branch ruleset, so a tag on an unmerged branch would
  publish code no pull request merged.

The previous ``v*`` tag (``git describe`` from the tagged commit's first
parent, which for a merge commit is main as it was) goes to the job's
output as ``previous``: GitHub's generated notes then cover the changes
since the release before this one, whichever release GitHub would
otherwise have picked as the base. Every release is now born a beta, and
with a Stable release as the latest GitHub may compare against that.

Standard library and git only; the job runs it on the runner's own Python.

    python3 scripts/release_guard.py <tag> <commit> [--main-ref origin/main]
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TAG_RE = re.compile(r"v\d+\.\d+\.\d+")
_VERSION_LINE_RE = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.MULTILINE)


def _git(args, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def version_at(commit: str, cwd=None) -> str:
    """``__version__`` in ``src/version.py`` as *commit* has it (not the
    working tree, which need not be that commit); '' when there is none."""
    done = _git(["show", f"{commit}:src/version.py"], cwd)
    match = _VERSION_LINE_RE.search(done.stdout) if done.returncode == 0 else None
    return match.group(1) if match else ""


def is_on(commit: str, ref: str, cwd=None) -> bool:
    """True when *commit* is *ref* or one of its ancestors."""
    return _git(["merge-base", "--is-ancestor", commit, ref], cwd).returncode == 0


def previous_tag(commit: str, cwd=None) -> str:
    """The nearest ``v*`` tag behind *commit*'s first parent; '' when none."""
    done = _git(["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*",
                 f"{commit}^"], cwd)
    return done.stdout.strip() if done.returncode == 0 else ""


def check(tag: str, commit: str, version: str, main_ref: str = "origin/main",
          cwd=None) -> list:
    """The reasons not to publish *tag*; an empty list means publish."""
    errors = []
    if not _TAG_RE.fullmatch(tag):
        errors.append(f"tag {tag} is not vX.Y.Z")
    if tag != f"v{version}":
        errors.append(f"tag {tag} does not match src/version.py ({version or 'no version'})")
    if not is_on(commit, main_ref, cwd):
        errors.append(f"commit {commit[:12]} of tag {tag} is not on {main_ref}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tag")
    parser.add_argument("commit")
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--repo", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    version = version_at(args.commit, args.repo)
    errors = check(args.tag, args.commit, version, args.main_ref, args.repo)
    for error in errors:
        print(f"::error::{error}")
    if errors:
        return 1
    previous = previous_tag(args.commit, args.repo)
    print(f"{args.tag} may be published; its notes start from {previous or 'the beginning'}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as out:
            out.write(f"previous={previous}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
