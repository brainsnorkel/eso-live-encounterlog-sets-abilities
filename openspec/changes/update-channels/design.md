# Design: Stable and Beta update channels

## Context

Issue #134 holds the analysis: the release figures, five options weighed (A, flip the pre-release flag; B, semver beta tags rebuilt for Stable; C, two long-lived branches; D, release less often; E, a client-side delay), a critical review of today's branching and release practice, and the maintainer's twelve decisions of 2026-10-29. This file records what the code does and why.

## Decisions

- **Stable keeps `/releases/latest`.** GitHub never points it at a pre-release or a draft, so it follows a promotion and a demotion exactly, and its reply is about 8 KB. Reading the list on Stable too would have to re-derive "latest" and could disagree with GitHub's own mark.
- **Beta reads `/releases?per_page=10`** (about 80 KB for a full reply, measured on the real list on 2026-10-29) and takes the highest version among releases with this platform's asset, pre-release or not, never a draft. Ten is plenty: GitHub lists newest first, and the highest version is almost always the first entry. The endpoint answers `If-None-Match` with a 304 that costs nothing, like the latest endpoint (a weak ETag, checked live).
- **A tag counts only when it is exactly `vX.Y.Z`** (`_TAG_RE.fullmatch`). The old `search` for three dotted numbers anywhere was harmless while only `/releases/latest` was read; the list also carries `esobuild-assets-<update>-<date>` data releases.
- **No downgrade, ever.** Both channels compare with the running version, so someone who leaves Beta keeps the version they have until Stable passes it; Settings says so.
- **A skipped beta does not hide the release below it.** Beta drops the skipped version before taking the highest, so skipping a bad 0.27.0 still offers 0.26.0 to someone on 0.25.0 (found in the PR's review).
- **The ETag and the channel.** The two channels ask different endpoints. The channel changes only through a Settings save, which restarts the poller, and `start()` clears the ETag: that is the one guarantee, with no second piece of state (an `_etag_channel` was dropped in review).
- **Leaving a channel withdraws its offer at once.** `start()` drops an offer made on another channel and emits `update_gone`, rather than waiting for the first check on the new channel to succeed: offline or rate limited that may take an hour or never happen, and one click would install the beta the user just left (found in review).
- **A save restarts the checks only when update settings changed.** The window compares on/off, the channel and the skipped version before and after the save. Any other Settings change used to cost a full reply (about 80 KB on Beta) and cleared a rate-limit wait (found in review).
- **One channel table.** `update_check.CHANNEL_CHOICES` holds key, name and description; `CHANNELS` is derived from it, and Settings and About read it.
- **The title names Beta, only while checks are on.** The maintainer chose " · beta" in the title (against About-only) so screenshots show it; with checks off no channel is in effect, so nothing is shown.
- **The popup's compare link.** A Stable user will skip several betas at once and the notes are the offered release's own; GitHub's compare page lists every change between the two tags.

## Interim behaviour

Until step 2 publishes betas as pre-releases, every release is a full one, so `/releases/latest` and the highest version in the list are the same release and both channels offer it. The live check of 2026-10-29 (`check_for_update('0.24.0', channel=…)`) returned 0.25.0 on both.

Settings' help line and the guide say so ("until releases start going to Beta first, both get every release"); step 2 removes that sentence.

## Risks

- A data release given a `vX.Y.Z` tag would be read as an app release on both channels; the release recipe forbids it (`esobuild-assets-*` tags).
- An install that is several betas behind on Beta sees only the newest release's notes; the compare link covers the rest.
- Beta reads only the ten newest releases. If none of them were an app release with this platform's asset, Beta would read as "up to date" and withdraw an offer. Every app release carries all three assets (the release job fails otherwise), and data releases come once per game update, so it would take ten data releases in a row; left unguarded (review finding, declined).
- The "Changes since" link assumes the running version has a tag. An installed build always does; a source checkout ahead of its tag gets a GitHub 404 (review finding, declined).
