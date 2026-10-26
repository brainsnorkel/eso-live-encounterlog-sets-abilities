# app-updates

## Purpose

When and how the app learns of a newer release on GitHub, what the toolbar shows while one is available, what the Update button and the `ⓘ` do on each platform, and what the Settings box controls; nothing in the path opens a dialog or takes the focus.

## ADDED Requirements

### Requirement: The check runs at startup and on a schedule

While update checking is enabled, the app SHALL check GitHub's latest release within a few seconds of the main window appearing and again at a fixed interval, 15 minutes by default (a configuration value with no Settings control), for as long as the app runs. A check SHALL never open a dialog, change the focus or delay the fight pane: it runs off the thread that reads the log, and a failure of any kind (no network, a timeout, an unexpected reply) changes nothing on screen.

#### Scenario: The app runs through a raid night
- **WHEN** a release is published while the app has been running for hours
- **THEN** the Update button appears within the next interval AND no dialog opens

#### Scenario: No network
- **WHEN** a check cannot reach GitHub
- **THEN** nothing changes on screen AND the next check runs at the usual time

#### Scenario: The engine is busy
- **WHEN** a check runs during a long startup replay or waits on a slow network reply
- **THEN** fight updates keep arriving at their usual rate

### Requirement: An unchanged release costs nothing

Repeat checks SHALL be conditional: the app sends the validator GitHub returned with the last full reply and treats "not modified" as no change. A reply that says the request limit is reached SHALL make the app wait until the time the reply names (at most an hour; the next scheduled check when it names none) before checking again.

#### Scenario: Nothing new
- **WHEN** the latest release has not changed since the last check
- **THEN** the check sends the validator AND the reply is "not modified" AND no release data is downloaded

#### Scenario: Rate limited
- **WHEN** GitHub answers that the limit is reached and names a reset time ten minutes away
- **THEN** no check runs until that time

### Requirement: The Update button and the ⓘ

When a check finds a release newer than the running version, not skipped, that carries this platform's asset, the toolbar SHALL show at its right end a flat button labelled with the version ("Update to 0.15.0" where an installer exists, "Get 0.15.0" elsewhere) and beside it an `ⓘ` in the link colour. Hovering the button SHALL say which version is available, which is running, and that nothing is installed until it is clicked. Neither SHALL be shown otherwise, and both SHALL disappear when a later check finds no newer release or the version is skipped. Nothing SHALL be downloaded or installed until the button is clicked.

#### Scenario: A newer release
- **WHEN** 0.15.0 is published and 0.14.2 is running on Windows
- **THEN** the toolbar shows "Update to 0.15.0" and the `ⓘ` AND no dialog opens

#### Scenario: Up to date
- **WHEN** the latest release is the running version
- **THEN** the toolbar shows neither

#### Scenario: A still newer release
- **WHEN** the button offers 0.15.0 and a check finds 0.15.1
- **THEN** the button reads "Update to 0.15.1" AND the notes are 0.15.1's AND a downloaded 0.15.0 installer is forgotten

### Requirement: Updating on Windows takes two clicks

On a platform with an installer, the first click SHALL download the installer to the temporary folder, with progress in the status bar, the button disabled and reading "Downloading 0.15.0…"; when the download finishes the button SHALL read "Install 0.15.0 and restart" and be enabled again. The second click SHALL start the installer and close the app. If the download or the start fails, the button SHALL return to "Update to 0.15.0" and the status bar SHALL say why. The app SHALL NOT close at any other point of the path.

#### Scenario: The download finishes
- **WHEN** the user clicks "Update to 0.15.0" and the download completes
- **THEN** the button reads "Install 0.15.0 and restart" AND the app is still running

#### Scenario: The second click
- **WHEN** the user clicks "Install 0.15.0 and restart"
- **THEN** the installer starts AND the app closes

#### Scenario: The download fails
- **WHEN** the download is interrupted
- **THEN** the button reads "Update to 0.15.0" again AND the status bar says the download failed

#### Scenario: The installer will not start
- **WHEN** the installer cannot be started
- **THEN** the button reads "Update to 0.15.0" again AND the status bar says why AND the app stays open

### Requirement: Updating elsewhere opens the release page

On a platform without an installer the button SHALL open the release page in the browser and stay as it is.

#### Scenario: Linux
- **WHEN** the user clicks "Get 0.15.0" on Linux
- **THEN** the browser opens the release page AND the app downloads nothing

### Requirement: The ⓘ shows the release notes

Hovering the `ⓘ` SHALL name the version and its release date. Clicking it SHALL open a transient popup beside the pointer showing the version, the release date, the release's notes as published on GitHub with their links working, links to the release page and the changelog, and "Don't show this version again". The popup SHALL close on a click elsewhere or Esc, and SHALL scroll rather than grow past a reasonable height.

#### Scenario: Reading the notes
- **WHEN** the `ⓘ` is clicked
- **THEN** a popup shows "ESO Log Tail 0.15.0", the date, the notes and the two links

#### Scenario: Skipping the version
- **WHEN** "Don't show this version again" is clicked
- **THEN** the popup closes AND the button and the `ⓘ` disappear AND they stay hidden for 0.15.0 while a later release shows them again

### Requirement: The Settings box controls the checks

The Settings box SHALL read "Check GitHub for a newer release at startup and every 15 minutes, and show an Update button in the toolbar". Saving with it cleared SHALL stop the checks and hide the button and the `ⓘ`; saving with it ticked SHALL start the checks at once, clearing a skipped version as before.

#### Scenario: Turned off
- **WHEN** the box is cleared and Settings saved while the button is showing
- **THEN** the button and the `ⓘ` disappear AND no further check runs

#### Scenario: Turned on
- **WHEN** the box is ticked and Settings saved
- **THEN** a check runs within seconds AND the schedule resumes

### Requirement: No dialog in the update path

The app SHALL NOT open a message box or any modal window for finding, downloading, installing or failing an update; every state is shown by the button, the `ⓘ`, the status bar and the popup the user opened.

#### Scenario: Every step
- **WHEN** a release is found, downloaded or installed, or a step fails
- **THEN** no modal window opens
