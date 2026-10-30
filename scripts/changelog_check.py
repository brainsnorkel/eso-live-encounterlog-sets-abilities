#!/usr/bin/env python3
"""Check a pull request's changelog fragment and its hands-off files.

Design (issue #134, task 2.5): changes write their notes as fragments in
changelog.d/ and the release commit (scripts/release.py) gathers them into
CHANGELOG.md and regenerates docs/design.md. A pull request that is not a
release (it leaves src/version.py alone) is refused when it:

- adds no fragment (``changelog.d/*.md`` other than the folder's README):
  its change would reach the release notes only if someone remembered;
- edits CHANGELOG.md: that edit is what put every open pull request in
  conflict with the others;
- edits docs/design.md: the same, for the design notes, which the release
  commit rebuilds from the docstrings.

A release pull request does all three by design and passes. The
``no-changelog`` label turns the check off for a pull request that needs no
entry (a typo in the guide, a CI tweak, a test-only change); the maintainer
or the session that opens the pull request sets it.

The fragment's text is not checked here: scripts/release.py refuses one it
cannot read when the release is cut, and the unit tests run the same parser
over every fragment on the branch.

    python3 scripts/changelog_check.py <base sha> <head sha> [--labels a,b]
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = "changelog.d/"
FRAGMENT_GUIDE = "changelog.d/README.md"
SKIP_LABEL = "no-changelog"


def problems(changes, labels=()) -> list:
    """The reasons to refuse a pull request whose diff against its base is
    *changes* ([(status letter, path)], as ``git diff --name-status`` gives
    them, renames as their new path) and which carries *labels*."""
    if SKIP_LABEL in labels:
        return []
    paths = {path for _status, path in changes}
    if "src/version.py" in paths:
        return []
    found = []
    added = [path for status, path in changes
             if status[:1] in ("A", "R", "C", "M") and path.startswith(FRAGMENTS)
             and path.endswith(".md") and path != FRAGMENT_GUIDE]
    if not added:
        found.append(f"no changelog fragment: add {FRAGMENTS}<issue>-<slug>.md "
                     f"(see {FRAGMENT_GUIDE}), or label the pull request {SKIP_LABEL}")
    if "CHANGELOG.md" in paths:
        found.append(f"CHANGELOG.md is written by the release commit: move the entry "
                     f"into a {FRAGMENTS} fragment")
    if "docs/design.md" in paths:
        found.append("docs/design.md is rebuilt by the release commit: leave it out "
                     "(edit the docstrings it is made from)")
    return found


def changes_between(base: str, head: str, root: Path = ROOT) -> list:
    done = subprocess.run(["git", "diff", "--name-status", f"{base}...{head}"], cwd=root,
                          capture_output=True, text=True, check=True)
    out = []
    for line in done.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0], parts[-1]))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--labels", default="", help="the pull request's labels, comma separated")
    args = parser.parse_args(argv)
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    found = problems(changes_between(args.base, args.head), labels)
    for problem in found:
        print(f"::error::{problem}")
    if not found:
        print("changelog: fine")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
