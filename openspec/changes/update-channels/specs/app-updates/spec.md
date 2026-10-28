# app-updates

## ADDED Requirements

### Requirement: The check runs on a channel

The app SHALL offer two update channels, chosen in Settings → Updates: **Stable**, the default, and **Beta**. On Stable the check SHALL read GitHub's latest release, which is never a pre-release or a draft. On Beta the check SHALL read the newest releases and offer the highest version among those with this platform's asset, pre-release or not, never a draft. A release SHALL count only when its tag is exactly `v` followed by three dot-separated numbers. Neither channel SHALL offer a version that is not newer than the one running. An unknown channel in the config SHALL read as Stable.

#### Scenario: A beta on the Beta channel
- **WHEN** the newest release is pre-release 0.27.0, the newest full release is 0.26.0, and 0.26.0 is running on Beta
- **THEN** the Update button offers 0.27.0

#### Scenario: The same beta on the Stable channel
- **WHEN** the same releases exist and 0.26.0 is running on Stable
- **THEN** no update is offered

#### Scenario: Leaving Beta
- **WHEN** 0.27.0 (a beta) is running and the channel is changed to Stable while Stable is 0.26.0
- **THEN** no update is offered AND nothing is downgraded

#### Scenario: A data release in the list
- **WHEN** a release tagged `esobuild-assets-u52-20261101` is the newest in the list
- **THEN** the Beta channel ignores it

### Requirement: The channel is shown

While update checks are on and the channel is Beta, the window title SHALL end with " · beta" before any " · X available" suffix. The About dialog SHALL name the channel and what it offers, or say that updates are not checked when the checks are off. Saving Settings SHALL apply the channel at once: a full check on the new channel, and an offer the new channel does not make withdrawn.

#### Scenario: Switching to Beta
- **WHEN** Beta is chosen and Settings saved with checks on
- **THEN** the title ends " · beta" AND a check runs within seconds on the Beta channel

#### Scenario: Back to Stable with a beta on offer
- **WHEN** Stable is chosen and Settings saved while the button offers a beta that Stable does not offer
- **THEN** the button and the ⓘ disappear AND the title has neither suffix

### Requirement: The notes popup links every change since the running version

The ⓘ popup SHALL include a link to GitHub's comparison of the running version's tag with the offered release's tag, labelled with the running version.

#### Scenario: Several releases behind
- **WHEN** 0.24.0 is running and 0.27.0 is offered
- **THEN** the popup links "Changes since 0.24.0" to the comparison of `v0.24.0` with `v0.27.0`
