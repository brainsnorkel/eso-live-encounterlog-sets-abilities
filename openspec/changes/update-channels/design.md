# Design: Stable and Beta update channels

## Context

Issue #134 holds the analysis: the release figures, five options weighed (A, flip the pre-release flag; B, semver beta tags rebuilt for Stable; C, two long-lived branches; D, release less often; E, a client-side delay), a critical review of today's branching and release practice, and the maintainer's twelve decisions of 2026-10-29. This file records what the code does and why.

## Decisions

- **Stable keeps `/releases/latest`.** GitHub never points it at a pre-release or a draft, so it follows a promotion and a demotion exactly, and its reply is about 8 KB. Reading the list on Stable too would have to re-derive "latest" and could disagree with GitHub's own mark.
- **Beta reads `/releases?per_page=10`** (about 80 KB for a full reply, measured on the real list on 2026-10-29) and takes the highest version among releases with this platform's asset, pre-release or not, never a draft. Ten is plenty: GitHub lists newest first, and the highest version is almost always the first entry. The endpoint answers `If-None-Match` with a 304 that costs nothing, like the latest endpoint (a weak ETag, checked live).
- **A tag counts only when it is exactly `vX.Y.Z`** (`_TAG_RE.fullmatch`). The old `search` for three dotted numbers anywhere was harmless while only `/releases/latest` was read; the list also carries `esobuild-assets-<update>-<date>` data releases.
- **No downgrade, ever.** Both channels compare with the running version, so someone who leaves Beta keeps the version they have until Stable passes it; Settings says so.
- **One ETag, kept with its channel.** The two channels ask different endpoints. A Settings save restarts the poller, which clears the ETag anyway; keeping the channel beside it means a validator is never sent to the other endpoint even if the config changes some other way.
- **The title names Beta, only while checks are on.** The maintainer chose " · beta" in the title (against About-only) so screenshots show it; with checks off no channel is in effect, so nothing is shown.
- **The popup's compare link.** A Stable user will skip several betas at once and the notes are the offered release's own; GitHub's compare page lists every change between the two tags.

## Interim behaviour

Until step 2 publishes betas as pre-releases, every release is a full one, so `/releases/latest` and the highest version in the list are the same release and both channels offer it. The live check of 2026-10-29 (`check_for_update('0.24.0', channel=…)`) returned 0.25.0 on both.

## Risks

- A data release given a `vX.Y.Z` tag would be read as an app release on both channels; the release recipe forbids it (`esobuild-assets-*` tags).
- An install that is several betas behind on Beta sees only the newest release's notes; the compare link covers the rest.
