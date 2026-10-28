# Tasks

## 1. The app (step 1, shipped as an ordinary full release)

- [x] 1.1 `update_check`: `CHANNELS`, `normalize_channel`, `RELEASES_URL`, `fetch_releases` (the list in `FetchResult.releases`, a non-list reply an error), `newest_release`, `release_to_update_info(..., allow_prerelease=False)` with the tag matched whole, `compare_url`, `check_for_update(..., channel=)`; the module docstring records the channels. Verified by `tests/unit/test_update_check.py`: whole-tag matching, pre-releases only when allowed, the highest version picked across pre-releases, drafts, data tags and missing assets, the list request and its 304, a non-list reply, Beta never offering a lower version, skip and failures on Beta, Stable ignoring a pre-release, an unknown channel reading the latest release
- [x] 1.2 `UpdatePoller` passes the configured channel; `start()` clears the ETag and withdraws an offer made on another channel at once. Verified by `tests/unit/test_update_poller.py`: the channel passed (junk reads as Stable), no ETag after a channel change, the offer gone at once on leaving Beta even when the next check fails, kept on a restart on the same channel
- [x] 1.2a Review of PR #136 (the session rule): nine findings, seven fixed (a skipped beta hiding the release below it, an offer outliving a channel change, one channel table, interim wording, `_etag_channel` dropped, the fetch plumbing, a restart only when update settings changed), two declined with reasons (the ten-release window, the compare link on an untagged build). Verified by the tests named above, `test_a_skipped_version_leaves_the_one_below_it`, and `test_update_settings_start_and_stop_the_poller`
- [x] 1.3 Settings: the *Channel* choice under the check box, enabled with it, saved as `update.channel`, with its help line. Verified by `tests/unit/test_settings_dialog.py`
- [x] 1.4 The title's " · beta" while checks are on, About's channel line, the popup's "Changes since" link (the link row wraps at the popup's width). Verified by `tests/unit/test_gui.py` and `tests/unit/test_about.py`, and the popup picture
- [x] 1.5 User guide (Settings list and Automatic updates), `docs/development.md`, CHANGELOG, `docs/design.md` regenerated, `settings.png` and `update-notes.png` recaptured (the capture script ticks the update box in the dialog only, so the guide shows the channel live)
- [x] 1.6 Live check: `check_for_update('0.24.0', channel='stable')` and `channel='beta'` both returned 0.25.0 on 2026-10-29, as expected while every release is a full one

## 2. The release process (step 2, after step 1 is released and the maintainer's install is on Beta)

- [ ] 2.1 Release job: full-depth checkout; guards (tag pattern, tag equals `src/version.py`, commit on `origin/main`); the previous `v*` tag to `$GITHUB_OUTPUT`; `prerelease: true`, `make_latest: false`, `previous_tag`
- [ ] 2.2 `scripts/promote_release.py vX.Y.Z` (checks, the combined "Changes since <last stable>" body, the flip, a `/releases/latest` check with one retry) and `--demote`
- [ ] 2.3 `pages.yml`: add `release: types: [released]`, keep `workflow_run`; `scripts/build_site.py` adds a Beta link from the newest pre-release
- [ ] 2.4 Weekly reminder workflow: an issue when a qualifying beta is more than 14 days ahead of Stable
- [ ] 2.5 `scripts/release.py X.Y.Z`; changelog fragments (`changelog.d/`) with a CI check and a `no-changelog` label; `docs/design.md` regenerated only in the release commit
- [ ] 2.6 `docs/development.md`: the release section rewritten for betas, promotion and demotion; a `regression` label created
- [ ] 2.7 Drop the interim sentence ("until releases start going to Beta first, both get every release") from `CHANNEL_HELP`, the user guide and the CHANGELOG wording, and recapture `settings.png`

## 3. Rollout checks

- [ ] 3.1 First beta tag: `/releases/latest` still the Stable release; the home page's Stable buttons unchanged and its Beta link the beta; the maintainer's app offered it; a scratch Stable config offered nothing
- [ ] 3.2 First promotion: the flag flipped and latest set; Pages redeployed on `released`; a scratch Stable config offered the release with the combined notes
