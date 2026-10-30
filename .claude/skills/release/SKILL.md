---
name: release
description: Cut a beta release of ESO Log Tail with scripts/release.py - the release commit gathered from the changelog.d fragments, the merge, the tag, and the check of what GitHub published - and write a change's changelog fragment. Use when asked to release, cut or publish a beta, "release this", do a dot or patch release, tag a version, or add a changelog entry. Not for making a beta Stable, which is promote_release.py and only on the maintainer's word.
license: MIT
compatibility: Needs git and the GitHub CLI (gh), logged in, and Python 3.11+.
metadata:
  author: eso-log-tail
  version: "1.0"
---

Every release of ESO Log Tail is first a **beta**: the tag's workflow run publishes a GitHub pre-release, which the app's Beta channel offers at once and the Stable channel ignores (issue #134). `docs/development.md` ("Releasing") is the reference; this is the order to do it in.

**A change's changelog entry** (every pull request, not only releases)

Add `changelog.d/<issue>-<short-slug>.md` with the entry under `### Added`, `### Changed` or `### Fixed` (also `Deprecated`, `Removed`, `Security`), written for the app's users, the way `CHANGELOG.md` reads. Never edit `CHANGELOG.md` or `docs/design.md` in a pull request: the release commit writes both, and the *Changelog* check refuses them, label or not. A pull request that needs no entry gets the `no-changelog` label (`gh pr edit <n> --add-label no-changelog`), which waives the fragment only. Format and example: `changelog.d/README.md`.

**Cutting a beta**

1. `git fetch origin` and look at what is on `main` since the last tag (`git log --oneline $(git describe --tags --abbrev=0 origin/main)..origin/main`) and at `changelog.d/`. A release covers what is merged plus the pull request the release commit rides in.
2. Pick the branch: the last pull request of the release, or a new branch from `origin/main` (`release-X.Y.Z`) with a pull request of its own. Never `main` itself, which takes pull requests only.
3. Preview, then make the release commit:
   ```
   python scripts/release.py minor --dry-run
   python scripts/release.py minor --trailer "Co-Authored-By: <the attribution line this session uses>"
   ```
   `minor` for anything Added, Changed, Deprecated or Removed; `patch` when there are only Fixed or Security entries (the script prints its suggestion); `X.Y.Z` to name it. The script refuses on `main`, over uncommitted changes, with no fragments, or with a version that is not higher.
4. Push, open or update the pull request, wait for its checks (`gh pr checks <n> --watch`). The release commit needs no new review under the review-on-open rule. If the branch has to take a merge of `main` and that brings in new fragments, the *Changelog* check refuses the release: `git revert --no-edit <release commit>`, then run step 3 again, so their notes are in this release, which ships their changes.
5. Merge: `gh pr merge <n> --merge`. If the merge is refused, give the maintainer the link and stop; never merge locally and push `main`.
6. Tag, publish and check:
   ```
   python scripts/release.py --tag X.Y.Z --dry-run
   python scripts/release.py --tag X.Y.Z --push --watch
   ```
   It finds the merge commit, runs the release job's tag checks on it, checks its design notes and that `changelog.d/` holds no fragments there, pushes the annotated tag, waits for the *Build Installers* run and checks that the release is a pre-release with its three files and that `/releases/latest` (Stable) did not move. If the run fails, nothing was published: read `gh run view <id> --log-failed` and ask the maintainer before moving or deleting the tag.
7. Report: the version, the pull request, the tag, the check's result, and the earliest time it could be made Stable (48 hours after publication, and only after the maintainer has used it live).

**Making a beta Stable** is never part of this. Only on the maintainer's explicit word ("promote", "make it Stable"): `python scripts/promote_release.py vX.Y.Z --used-live --dry-run`, then without `--dry-run`. A session may list candidates (`--candidates`) and propose one.
