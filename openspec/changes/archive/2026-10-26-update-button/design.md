# Design: The Update button

## Context

See proposal.md for the motivation. What this builds on:

- `update_check.py` (0.3.x, 2026-09-27): one GET of the repository's latest release through urllib with a 10-second timeout; `release_to_update_info` picks this platform's asset (`PLATFORM_ASSETS`: the Windows installer, the Linux tarball) and ignores drafts and pre-releases; `is_newer` compares `major.minor.patch`; `download_file` streams to the temp folder with a progress callback. Every failure returns None.
- The engine worker runs the check 3 s after `start()` returns, which is after the startup replay, on the engine thread; `download_update` runs there too, with progress through `parse_progress`. The window's `_on_update_available` opens the modal `_prompt_update` (Update now / Later / Skip this version, the notes under "Show details"); `_on_update_ready` opens a second modal and, on Yes, `subprocess.Popen([installer])` and `self.close()`; a `Popen` failure opens a warning box.
- `HAS_INSTALLER = sys.platform == "win32"`; elsewhere "Update now" opens the release page.
- Config: `update.check_enabled` (default True), `update.skip_version` (cleared whenever Settings is saved with the check on). `AppConfig.get`, `set`, `save`.
- The toolbar is a fixed `QToolBar` of `QAction`s, drawn as flat text buttons; it holds no widget yet. The status bar carries the shared `progress_bar` at its right. `_dark` and the theme colours drive every rendered text colour, and `_on_theme_maybe_changed` re-renders what bakes a colour in.
- `BuildIssuesPopup` is the transient popup precedent: a `Qt.Popup` frame that deletes itself on close, placed after it is shown, external links opened by the system browser.
- GitHub's latest-release reply carries `tag_name`, `body` (markdown; this repository's releases use GitHub's generated notes, a "What's Changed" list of one PR line each and a "Full Changelog" compare link), `published_at`, `html_url`, `assets[]`, and an `ETag` header. Unsigned requests are limited to 60 an hour per address. A request sent with `If-None-Match` and answered `304 Not Modified` does not count against that limit. A limit reply is 403 or 429 with `X-RateLimit-Reset` (epoch seconds) or `Retry-After` (seconds).
- The thread lessons in `engine_worker.py`'s docstring and the 0.6.x settings crash: a Qt object freed off the UI thread aborts the app; a background thread must create no QObject and hand back plain data.

## Goals / Non-Goals

**Goals:**
- No modal dialog and no focus change anywhere in the update path: the user learns of a release from a button that appears, and the app closes only on a click that says so.
- A check that costs the user and GitHub nothing while nothing has changed, and never delays the fight pane.
- The offer always names the latest release; nothing stale is installed.

**Non-Goals:**
- Installing without a click, or a silent installer run: the installer's own screens stay.
- A history of past releases in the app: the popup shows the notes of the release on offer and links out for more.
- Telling a portable-zip install from an installed one on Windows: both get the installer today, and this change keeps that (see Risks).
- Pre-releases and drafts: still ignored.
- macOS (#32).

## Decisions

- **The button lives in the toolbar, not the title bar.** Windows' native title bar takes no widgets; a button there means a frameless window with a custom title bar, which has to rebuild dragging, snapping, the system menu, maximise and close, and the dark title Windows paints, for one button. The toolbar is the app's own strip right under the title and already holds flat text buttons; a stretch widget pushes the Update button and the `ⓘ` to its right end, where nothing competes. *Alternative*: the status bar's right end, by the progress bar. Rejected: the bottom strip is where transient messages pass; a button that must be noticed belongs at the top. The window title also carries " · 0.15.0 available" while the offer stands (the maintainer's choice, 2026-10-26): the taskbar and Alt-Tab show the title where the toolbar is out of sight, and it goes when the button goes.
- **One click on Windows: "Update to X" downloads and installs.** The click downloads (the shared progress bar; the button disabled and reading "Downloading X…") and, as the file lands, starts the installer and closes the app. The maintainer chose this on 2026-10-26 over a second "Install X and restart" click: the button is the consent, and a restart that follows the click by seconds to a minute is the user's own timing; the hover text says the app restarts. A failed download or a failed start puts the button back with the reason in the status bar. On Linux one click, "Get X", opens the release page, as now.
- **The `ⓘ` is a flat tool button with the fight list's glyph** (`fight_render.ISSUES_CUE`), in the link colour, with the version and date as its hover text. Clicking opens `UpdateNotesPopup`, a `Qt.Popup` frame after `BuildIssuesPopup`, 520 px wide, scrolling once taller than 400 px, holding "ESO Log Tail 0.15.0 · released 26 October 2026", the release notes, "Release page" and "Changelog" links, and "Don't show this version again". The notes are GitHub's `body` rendered as markdown (`QLabel` with `Qt.MarkdownText`, or `QTextBrowser.setMarkdown`), so the PR links work. *Alternative, open to the maintainer*: fetch `CHANGELOG.md` at the new tag from raw.githubusercontent.com (outside the API limit) and show the entries above the running version, which say far more than PR titles. Not chosen by default: the entries run to a dozen lines each and the popup would become a reader, and the "Changelog" link opens the same text. The fetch is one function and the popup's content one string, so the choice does not change the structure.
- **Skipping stays, inside the popup.** "Don't show this version again" sets `update.skip_version`, hides the button and the `ⓘ` until a newer release appears, and Settings saved with the check on clears it, as today. *Alternative*: drop skipping, since a button is passive. Rejected: a user who means to stay on a version would see the button all night.
- **An `UpdatePoller` QObject on the UI thread owns the schedule.** It holds a `QTimer` at `update.check_interval_min` × 60 s (default 15; a config key without a Settings control, since "every 15 minutes or so" is the issue's own number), fires the first check 3 s after the window is shown, and keeps checking after a release is found so a newer one replaces the offer. Its signals: `update_available(UpdateInfo)`, `update_gone()` (the latest release is no longer newer, or is the skipped one), `download_progress(done, total)`, `update_ready(path)`, `update_failed(reason)`. The window connects to these as it did to the worker's. *Alternative*: keep the timer on the engine worker. Rejected: the check would wait behind a replay and share the thread that polls the log.
- **Each check and each download runs on a daemon `threading.Thread`** started by the poller. The thread calls `update_check` functions only (urllib, json, the file write) and emits the poller's signals with plain data (`UpdateInfo`, `str`, `int`); emitted from a thread the poller does not live in, the signals are queued to the UI thread. The thread creates no QObject and holds no widget, which is the rule the 0.6.x settings crash and issue #18 taught. One check or download at a time: a tick while a thread runs is skipped. *Alternative*: leave both on the engine thread with a shorter timeout. Rejected: a wedged network still stalls the fight pane for the timeout every 15 minutes, and a download stalls it for its length. *Alternative*: `QThreadPool` and a `QRunnable`. Equivalent; rejected as more Qt surface for the same effect and harder to patch in tests.
- **Conditional requests.** `fetch_latest_release` takes the last `ETag` and sends `If-None-Match`; a 304 returns a not-modified result and the poller changes nothing; a 200 returns the JSON and the new `ETag`. A 403 or 429 carrying `X-RateLimit-Reset` or `Retry-After` returns the time to wait, capped at an hour, and the poller skips ticks until then. The ETag is kept for the run only; each start sends one full request. The budget: four checks an hour, all 304 while nothing changes, so a household of several copies behind one address stays far under 60. *Alternative*: a plain GET every time. Rejected: four of the 60 an hour per copy, and a full body each time, for no information.
- **No dialog anywhere.** `_prompt_update` goes; `_on_update_ready` starts the installer and closes the app; a `Popen` failure reverts the button and shows the reason in the status bar for 15 s, as `update_failed` does. The one call to `self.close()` follows a started installer only.
- **A newer release replaces the offer.** The poller compares the found version with the one on offer: the same version is a no-op (the usual 304 never gets this far); a newer one re-emits `update_available`, and the window resets the button to "Update to Y" and refreshes the notes and the title; a download runs one at a time and installs as it lands, so there is no stale file to forget. A check that finds nothing newer (a release withdrawn, or the skip set) emits `update_gone` and the window hides both buttons and restores the title.
- **Settings.** The box reads "Check GitHub for a newer release at startup and every 15 minutes, and show an Update button in the toolbar". On save the window tells the poller: disabled → stop and hide; enabled → (re)start with an immediate check, and the skip cleared as now.
- **Colours follow the theme**: the `ⓘ`'s colour and the popup's text follow `_dark` through `_on_theme_maybe_changed`, as the other rendered pieces do.

## Risks / Trade-offs

- [A Python thread emitting a Qt signal] → PySide6 queues it to the receiver's thread; the thread touches no Qt object, and the poller's test asserts the slot ran on the UI thread.
- [A download thread outliving the window at close] → a daemon thread; the poller's `stop()` disconnects its signals and late results are dropped; the temp file is harmless.
- [GitHub sends a weak ETag or none] → the request works without the header; a weak ETag (`W/"…"`) is sent back as received, which GitHub accepts.
- [A clock far wrong makes `X-RateLimit-Reset` look distant] → the wait is capped at an hour; a tick after that tries again.
- [Portable-zip users on Windows get the installer] → unchanged behaviour; the installer can be cancelled; noted for a later issue.
- [The button appears mid-fight] → a flat button at the toolbar's end, no animation, no sound, no focus; the fight pane does not move.
- [One click closes the app seconds to a minute later] → the hover text says the download installs at once and the app restarts; the click can wait until a pull is over, and nothing happens without it.
- [GitHub's generated notes are thin] → the "Changelog" link opens the full entry; the changelog-section option is one decision away.

## Migration Plan

Nothing to migrate: the two config keys keep their meaning, and `update.check_interval_min` is read with a default. A user on an older build sees the old pop-up once more, offering the first build with this change.

## Open Questions

None. The three choices put to the maintainer on issue #56 were answered on 2026-10-26: the window title carries the suffix; one click on Windows downloads and installs; the popup shows GitHub's notes with a Changelog link.

## As built (2026-10-26)

- Built as designed, with the three choices as answered.
- `update_check.check_for_update(version, skip, etag)` returns a `CheckResult` (`info`, `etag`, `not_modified`, `retry_at`, `error`); `fetch_latest_release(etag)` a `FetchResult`. One live run against GitHub: the full reply carried a weak ETag (`W/"…"`), the repeat sent with it was answered 304 (`not_modified`), and a run claiming a version above the release saw nothing to offer.
- The toolbar's two widgets are shown and hidden through the `QAction`s that `addWidget` returns, since the toolbar's layout shows a directly hidden widget again; the tests read those actions.
- The poller's thread hand-off is three private signals connected with `Qt.QueuedConnection`; its test asserts that the public signal's slot runs on the application thread.
- The ⓘ popup renders the notes with `QTextBrowser.setMarkdown`, sized to the document up to 400 px; `place_popup` in `build_issues_popup.py` is shared by both popups.
- Tests: `tests/unit/test_update_check.py` (the conditional request and each reply), `tests/unit/test_update_poller.py` (the schedule, every outcome, a late result after `stop()`, the download) and the update tests of `tests/unit/test_gui.py` (button, title, hover text, the click on each platform, the installer hand-over and its failure, the popup, the skip, Settings, the theme). The whole suite: 948 passed, 3 skipped.
- `docs/screencaps/update-button.png` and `update-notes.png` come from a crafted release one patch above the running version, captured offscreen over a Sunspire split by `scripts/capture_screenshots.py`.
