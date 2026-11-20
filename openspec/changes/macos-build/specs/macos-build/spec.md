# macos-build

## ADDED Requirements

### Requirement: Every release carries a macOS app

Every `vX.Y.Z` release from the first that ships it SHALL carry `esolog-tail-macos-arm64-<version>.zip`, a zip of `ESO Log Tail.app` for Apple Silicon, signed with the maintainer's Developer ID certificate, notarized by Apple, and with the notarization ticket stapled to the app. A release SHALL NOT be published when that file could not be built, signed, notarized or started.

#### Scenario: A tag
- **WHEN** a `v*` tag on `main` is pushed and every job passes
- **THEN** the release has four files AND `spctl --assess --type execute -vv` on the expanded app reports `Notarized Developer ID`

#### Scenario: Notarization fails
- **WHEN** Apple's notary refuses the app or cannot be reached
- **THEN** no release is published for the tag, on any platform

### Requirement: The signing key is used by one job, for release tags only

The Developer ID certificate and the notary key SHALL be read only by the signing job, which runs Apple's tools and the release guard (standard library only) and none of the app's code or its dependencies, and only for a `vX.Y.Z` tag on `main` or a manual dry run on `main`. A release SHALL NOT publish a Mac zip that the signing job did not make.

#### Scenario: A pull request
- **WHEN** a pull request runs the workflow
- **THEN** the app is built ad-hoc signed and smoke-tested AND no signing secret is read

#### Scenario: A tag that is not on main
- **WHEN** a `v*` tag is pushed on a commit that is not on `main`
- **THEN** the signing job stops before the certificate is imported

#### Scenario: A dry run
- **WHEN** the workflow is started by hand on `main` with signing on
- **THEN** the app is signed, notarized and smoke-tested AND nothing is published

#### Scenario: The unsigned zip
- **WHEN** a tag's run has made both the unsigned zip and the signed one
- **THEN** the two have different file names AND only the signed one is among the release's files

#### Scenario: A binary the signing missed
- **WHEN** any binary in the signed app lacks the Developer ID signature or the hardened runtime
- **THEN** the signing job fails before notarization

### Requirement: The built app is started before it is released

The workflow SHALL start the zipped app, expanded as a download would be, on every hosted macOS version it claims to support, and SHALL fail when the app exits within 20 seconds or writes an unhandled exception to `crash.log`. The app's declared minimum macOS SHALL be the oldest hosted version on which the test suite and that start both pass, and the README SHALL state the same version.

#### Scenario: The oldest runner passes
- **WHEN** the suite and the start pass on the `macos-15` runner
- **THEN** the bundle declares macOS 15.0 as its minimum

#### Scenario: The oldest runner fails
- **WHEN** either fails on `macos-15` and both pass on `macos-26`
- **THEN** the build and the smoke test no longer use `macos-15` AND the bundle declares macOS 26.0 as its minimum

### Requirement: Keys work as a Mac user expects

On macOS, Return and Enter SHALL open the current row wherever they do on Windows; the tabs' letter keys SHALL work with Option; no shortcut of the app SHALL take ⌘H, ⌘, or ⌘. from the system; and every text that names a key SHALL name the Mac's key.

#### Scenario: Return on an event
- **WHEN** a death row is current on the Events tab and Return is pressed on macOS
- **THEN** the death's recap opens, as on Windows

#### Scenario: A tooltip
- **WHEN** the search field is empty on macOS
- **THEN** its hint reads "Find (⌘F)"

#### Scenario: Hide names
- **WHEN** ⇧⌘H is pressed on macOS
- **THEN** the names are hidden AND ⌘H still hides the application

### Requirement: A log in use is never deleted

On macOS the archive SHALL find another process that has the log open. It SHALL delete the original log only when, at the moment of deleting, it has found that no other process has it open, and SHALL say why when it keeps it.

#### Scenario: The game has the log open
- **WHEN** another process holds `Encounter.log` and an archive is due
- **THEN** the archive is skipped with the in-use notice

#### Scenario: The game opens the log while it is being zipped
- **WHEN** *Delete Encounter.log after a verified archive* is on and another process opens the log after the archive began
- **THEN** the zip is made AND the original log is kept

#### Scenario: The check cannot run
- **WHEN** the same setting is on and the holder check fails or runs out of time
- **THEN** the zip is made AND the original log is kept AND the status line says the log could not be checked

### Requirement: The update check offers the Mac build

On macOS the update check SHALL offer a release that carries the Mac zip, on the user's channel, and the button SHALL open the release page.

#### Scenario: A release without a Mac zip
- **WHEN** the Stable release predates the Mac build
- **THEN** no update is offered on macOS on the Stable channel

### Requirement: The release tools tolerate releases that predate the Mac build

The home page SHALL build from a Stable release that has no Mac zip, leaving the Mac link out. A beta SHALL need the Mac zip to be made Stable only when the Stable release carries one.

#### Scenario: The home page before the first Stable Mac build
- **WHEN** the Stable release has three files
- **THEN** the page builds AND has no Mac download link

#### Scenario: Promoting an older beta
- **WHEN** the Stable release has no Mac zip and a beta with its three files meets the other rules
- **THEN** it can be made Stable

#### Scenario: After the first Stable Mac build
- **WHEN** the Stable release carries a Mac zip and a beta does not
- **THEN** that beta cannot be made Stable
