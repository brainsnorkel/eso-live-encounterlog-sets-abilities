#!/usr/bin/env python3
"""Check a pull request's changelog fragment and its hands-off files.

Design (issue #134, task 2.5): changes write their notes as fragments in
changelog.d/ and the release commit (scripts/release.py) gathers them into
CHANGELOG.md and rebuilds docs/design.md. A pull request that is not a
release is refused when it:

- adds no fragment of its own (a new ``changelog.d/<name>.md``, directly in
  the folder, not the README), unless it carries the ``no-changelog``
  label: its change would reach the release notes only if someone
  remembered. Editing a fragment already there is not a note of its own,
  and a file in a subfolder is one the release script never reads;
- edits CHANGELOG.md: that edit is what put every open pull request in
  conflict with the others;
- edits docs/design.md: the same, for the design notes, which the release
  commit rebuilds from the docstrings.

The label waives the first rule only: the other two are the conflicts the
whole change exists to end.

A release is a pull request that changes ``__version__`` (read from the
merge base and the head, so an unrelated edit of src/version.py is not
one). It does all three by design and passes, unless changelog.d/ still
holds fragments at its head: they came in with a merge of main after the
release commit, their changes would ship in the release and their notes
in the next one. Reverting the release commit and running the release
script again gathers them.

The fragment's text is not checked here: scripts/release.py refuses one it
cannot read when the release is cut, and the unit tests run the same parser
over every fragment on the branch.

    python3 scripts/changelog_check.py <base sha> <head sha> [--labels a,b]
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_guard

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = "changelog.d/"
FRAGMENT_GUIDE = "README.md"
SKIP_LABEL = "no-changelog"


def is_fragment(path: str) -> bool:
    """A ``.md`` file directly in changelog.d/, other than its README."""
    if not path.startswith(FRAGMENTS):
        return False
    name = path[len(FRAGMENTS):]
    return name.endswith(".md") and "/" not in name and name != FRAGMENT_GUIDE


def problems(changes, labels=(), release=False, left=()) -> list:
    """The reasons to refuse a pull request whose diff against its merge
    base is *changes* ([(status letter, path)], as ``git diff --name-status``
    gives them, renames as their new path), which carries *labels*, is or
    is not a *release*, and holds the fragments *left* at its head."""
    if release:
        if left:
            return [(f"changelog.d/ still holds {', '.join(left)}: merged after the release "
                     f"commit, so their changes would ship in this release with their notes "
                     f"in the next one; revert the release commit and run "
                     f"scripts/release.py again")]
        return []
    found = []
    added = [path for status, path in changes if status[:1] in ("A", "R", "C") and is_fragment(path)]
    if not added and SKIP_LABEL not in labels:
        found.append(f"no changelog fragment: add {FRAGMENTS}<issue>-<slug>.md "
                     f"(see {FRAGMENTS}{FRAGMENT_GUIDE}), or label the pull request {SKIP_LABEL}")
    paths = {path for _status, path in changes}
    if "CHANGELOG.md" in paths:
        found.append(f"CHANGELOG.md is written by the release commit: move the entry "
                     f"into a {FRAGMENTS} fragment")
    if "docs/design.md" in paths:
        found.append("docs/design.md is rebuilt by the release commit: leave it out "
                     "(edit the docstrings it is made from)")
    return found


def _git(root: Path, *args) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout


def changes_between(base: str, head: str, root: Path = ROOT) -> list:
    out = []
    for line in _git(root, "diff", "--name-status", f"{base}...{head}").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0], parts[-1]))
    return out


def is_release(base: str, head: str, root: Path = ROOT) -> bool:
    """True when the pull request changes ``__version__``."""
    merge_base = _git(root, "merge-base", base, head).strip()
    return release_guard.version_at(merge_base, root) != release_guard.version_at(head, root)


def fragments_at(head: str, root: Path = ROOT) -> list:
    done = subprocess.run(["git", "ls-tree", "--name-only", f"{head}:{FRAGMENTS.rstrip('/')}"],
                          cwd=root, capture_output=True, text=True, check=False)
    return [name for name in done.stdout.splitlines() if is_fragment(FRAGMENTS + name)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--labels", default="", help="the pull request's labels, comma separated")
    args = parser.parse_args(argv)
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    found = problems(changes_between(args.base, args.head), labels,
                     release=is_release(args.base, args.head),
                     left=fragments_at(args.head))
    for problem in found:
        print(f"::error::{problem}")
    if not found:
        print("changelog: fine")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
