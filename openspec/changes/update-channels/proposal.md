# Proposal: Stable and Beta update channels

## Why

Issue #134: every `v*` tag publishes a full release, and every install offers it within 15 minutes with a one-click install. From 24 to 28 October 2026 that was 22 releases, a median two hours apart, while the home page (#58) invites people who never asked for a release every two hours. The maintainer wants a Settings choice between a **Stable** channel, the default, and a **Beta** channel that keeps today's pace, and release rules that make Stable mean something: a Stable release is a beta that has been used in real fights for a while with nothing found.

## What Changes

The maintainer chose option A of #134 on 2026-10-29: every tag is published as a GitHub pre-release (a beta), and a beta is made Stable by turning that same release into a full one. Stable then runs exactly the build beta users ran, and installs on 0.25.0 or older, which already ignore pre-releases, become Stable users with no change. The work ships in two steps, in this order, because the app must know about channels before the release job starts publishing betas, or the maintainer's own install stops seeing releases.

**Step 1, the app (this change's first PR), shipped as an ordinary full release:**

- `update.channel`, `stable` (the default) or `beta`; Settings → Updates gains a *Channel* choice, off while checks are off.
- Stable keeps reading `/releases/latest`. Beta reads the newest ten releases and offers the highest version among them, pre-release or not. Neither offers a version lower than the one running.
- A release counts only when its tag is exactly `vX.Y.Z` (the release list carries data releases too).
- The poller passes the channel and never sends one endpoint's ETag to the other.
- On Beta the window title ends ` · beta`; About names the channel (both the maintainer's choice).
- The ⓘ popup links to every change since the running version, however many releases lie between.

**Step 2, the release process (a later PR, after step 1 is released):**

- The release job checks out the history, refuses a tag that is not `vX.Y.Z`, does not match `src/version.py` or is not on `main`, and publishes with `prerelease: true`, `make_latest: false` and `previous_tag`.
- `scripts/promote_release.py` makes a beta Stable (and `--demote` pulls a bad one back to a draft) on the maintainer's word, then starts Pages on `main`; Pages also keeps rebuilding after every tag for the home page's new Beta link.
- A weekly workflow opens an issue when a beta that meets the promotion rules has waited more than 14 days.
- `scripts/release.py X.Y.Z` makes the release commit's edits; changelog fragments per PR and `docs/design.md` regenerated only in the release commit remove the two files every PR edits.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `app-updates` (specified in the archived `2026-10-26-update-button` change): the check runs on a channel; the title, About and the ⓘ popup change as above.

## Impact

- `src/update_check.py`, `src/gui/update_poller.py`, `src/gui/settings_dialog.py`, `src/gui/main_window.py`, `src/gui/about.py`, `src/gui/update_popup.py`, `src/app_config.py`; their tests.
- Step 2: `.github/workflows/build-installers.yml`, `.github/workflows/pages.yml`, a new reminder workflow, `scripts/build_site.py`, new `scripts/promote_release.py` and `scripts/release.py`, `docs/development.md`'s release section.
- No dependency changes. The dependency baseline of 2026-10-29 (v0.24.0's build) has nothing due; the pinned `softprops/action-gh-release` v3.0.3 has the `prerelease`, `make_latest` and `previous_tag` inputs step 2 needs.
