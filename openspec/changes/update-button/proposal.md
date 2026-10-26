# Proposal: An Update button in the toolbar, checked every 15 minutes

## Why

Issue #56: the update offer is a modal pop-up that opens once, three seconds after the engine has started, and Windows hands it the focus whatever the user was typing; an app that runs through a raid night, or starts with Windows, never hears of a release published after it started. The maintainer wants a check at startup and about every 15 minutes, a discreet button to update with, and an (i) that shows the release notes, with no pop-up anywhere in the path.

## What Changes

- **The check repeats**: at startup and every 15 minutes (a config value, default 15, with no Settings control) while the Settings box is ticked. Each repeat is a conditional request: GitHub answers an unchanged release with "not modified" and no body, which costs nothing against its limit of 60 unsigned requests an hour; a rate-limit reply makes the app wait for the reset it names. Ticking the box in Settings starts the checks at once; clearing it stops them.
- **The checks and the download leave the engine thread**: today both run on the thread that polls the log, where a wedged network stalls fight updates for the 10-second timeout, or for a whole download. Once per run that was bearable; every 15 minutes it is not.
- **A button instead of a pop-up**: when a newer release with this platform's asset exists, a flat button appears at the right end of the toolbar, "Update to 0.15.0", beside an `ⓘ`. Nothing is downloaded or installed until it is clicked. On Windows the first click downloads the installer (the status bar's progress bar, as today) and the button turns into "Install 0.15.0 and restart"; the second click hands over to the installer and closes the app, so the restart happens at a moment the user chose. On Linux the button, "Get 0.15.0", opens the release page. A failed download puts the button back and says why in the status bar.
- **The `ⓘ` shows the release notes**: hovering names the version and its date; clicking opens a transient popup (the build-issues popup pattern) with GitHub's release notes rendered, links to the release page and the changelog, and "Don't show this version again", which is the old "Skip this version" moved out of a dialog.
- **A newer release replaces the offer**: the button and the notes follow the latest release; a downloaded installer of a superseded version is forgotten.
- **The three update dialogs go**: "Update available", "Install update?" and "Could not start the installer" are replaced by the button's states and status-bar messages. No config value changes meaning: `update.check_enabled` and `update.skip_version` keep theirs.
- Documentation: the user guide's "Automatic updates" section, the README's two update sentences, the changelog, screenshots of the toolbar with the button and of the notes popup, design notes extracted into docs/design.md.

## Capabilities

### New Capabilities

- `app-updates`: when and how the app checks GitHub for a newer release, what the toolbar shows while one exists, what clicking the button and the `ⓘ` does on each platform, and what the Settings box controls.

### Modified Capabilities

(none; the project keeps no main specs, and the update prompt was never specified)

## Impact

- `src/update_check.py`: conditional requests (the ETag in; "not modified" and rate-limit replies out), the release date on `UpdateInfo`.
- New `src/gui/update_poller.py`: the timer, the background check and download threads, the signals the window listens to; the worker's `check_for_update` and `download_update` slots and their three signals move here.
- `src/gui/main_window.py`: the toolbar button and `ⓘ`, their states, the popup, the wiring to the poller; `_prompt_update`, the "Install update?" dialog and the installer warning removed. New `src/gui/update_popup.py`.
- `src/gui/settings_dialog.py`: the box's wording; the window starts or stops the poller on save.
- `src/gui/engine_worker.py`: loses the update slots and signals.
- Tests: `tests/unit/test_update_check.py`, the update tests of `tests/unit/test_gui.py` rewritten, a new `tests/unit/test_update_poller.py`.
- Docs: user guide, README, CHANGELOG, `docs/screencaps/update-button.png` and `update-notes.png`, `docs/design.md` regenerated; `scripts/capture_screenshots.py` gains the captures.
- Behaviour elsewhere: none; the engine's fight entries are untouched.
