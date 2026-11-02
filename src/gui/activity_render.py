"""
The pane before the first fight (issue #191): what the app is doing, when
Encounter.log was last archived, and Recent activity, the newest archives
and split logs, each a link that reviews it.

The pane is the right place: it is empty exactly then, where the fight
list's rows are a session's fights and a row that opened a file would look
like one, and a dialog would say something was wrong when nothing is. The
first line, in the pane's own text colour, says what is happening; the
archive's detail follows in the muted colour. Archives and splits are
listed apart, five of each: archives are rare (one per gigabyte of log) and
splits frequent, so one list of five would nearly always be five splits
and no archive. The lists start open, since they are the proof the reader
came for (a UX review of 2026-11-03: a page that is three lines and white
space, with the proof behind a link, reassures nobody); the Recent
activity link closes them, and the choice is kept for the session.

Each group's heading counts the files and their bytes on disk rather than
naming the folder: "how much" is what a worried reader wants, and the full
path is on each file's hover. A link to a file carries its place in
activity_paths, never the path: a path put in an href comes back through
QUrl with its percent-encoding undone here and there, and the window holds
the list the page was drawn from anyway. Clicking one runs Open log for
review on it, the toolbar action's own path, so a zipped split or an
archive streams from its zip and a large log is outlined and the reader
asked first.

With no log and the app's own archive to explain it (*Delete Encounter.log
after a verified archive*), the first line says so in the words of that
setting, and the advice on turning logging on goes last, under the lists,
since it is then a reminder and not a fix; with nothing to explain the
absence, the advice follows the first line as it always did.
"""

import html

from gui.fight_render import link_color
from recent_activity import ArchiveFile, RecentActivity, format_when, split_time
from split_retention import format_bytes

# The link that opens and closes the lists, + 'show' or 'hide'
ACTIVITY_HREF = "esolog:activity/"
# A file to review, + its index in activity_paths
REVIEW_HREF = "esolog:review/"

ACTIVITY_TITLE = "Recent activity"
CLOSED_CUE, OPEN_CUE = "▸", "▾"
# The lists start open (see the module)
OPEN_AT_FIRST = True

# The addon advice for a log that is not there (unchanged since 0.6)
_LOGGING_ADVICE = (
    "Enable encounter logging in ESO (/encounterlog), or install an "
    "addon that turns it on for you, one or the other but not both: "
    "Always Logging (from GitHub, github.com/brainsnorkel/AlwaysLogging) "
    "or Easy Stalking (ESOUI or Minion). "
    "Monitoring starts automatically when the file appears.")
_TOOLBAR_NOTE = "Older files: Open log for review… on the toolbar."


def activity_paths(activity: RecentActivity | None) -> list:
    """The files the page links to, in href order: archives, then splits."""
    if activity is None:
        return []
    return [a.path for a in activity.archives] + [s.path for s in activity.splits]


def review_index_from_href(href: str) -> int | None:
    """The index into activity_paths when *href* is a review link, else None."""
    if not href or not href.startswith(REVIEW_HREF):
        return None
    rest = href[len(REVIEW_HREF):]
    return int(rest) if rest.isdigit() else None


def activity_action_from_href(href: str) -> str | None:
    """'show' or 'hide' when *href* is the Recent activity link, else None."""
    if href and href.startswith(ACTIVITY_HREF):
        action = href[len(ACTIVITY_HREF):]
        if action in ("show", "hide"):
            return action
    return None


def activity_tooltips(activity: RecentActivity | None) -> dict:
    """Hover text per link: the file's full path, and what a click does."""
    tooltips = {}
    for index, path in enumerate(activity_paths(activity)):
        tooltips[f"{REVIEW_HREF}{index}"] = f"Open {path} for review"
    tooltips[f"{ACTIVITY_HREF}show"] = "Show the newest archives and split logs, each a click from a review"
    tooltips[f"{ACTIVITY_HREF}hide"] = "Close the lists"
    return tooltips


def explaining_archive(activity: RecentActivity | None, delete_original: bool
                       ) -> ArchiveFile | None:
    """The archive that explains a missing log: the newest, while the app
    deletes the log after archiving it; else None."""
    if activity is None or not delete_original:
        return None
    return activity.newest_archive


def _archive_detail(archive: ArchiveFile) -> str:
    """'Encounter-261102204800.zip, 65 MB, ending 2 Nov 2026, 20:48': the
    archive's name and size, and the time of the last line it holds."""
    detail = f"{archive.path.name}, {format_bytes(archive.size)}"
    if archive.last_entry is not None:
        detail += f", ending {format_when(archive.last_entry)}"
    return detail


def first_line(reason: str, activity: RecentActivity | None, delete_original: bool) -> str:
    """What the app is doing, as plain text: *reason* is 'monitoring' (the
    log is watched, no fight yet), 'waiting' (no log file) or 'back' (Back
    to live, no fight in the session yet). With no log, the newest archive
    and the delete setting explain where it went, in that setting's own
    words."""
    if reason == "waiting":
        archive = explaining_archive(activity, delete_original)
        if archive is not None:
            return (f"Encounter.log was archived at {format_when(archive.made)}, verified and "
                    f"deleted, as set in Settings. Waiting for encounters.")
        return "Waiting for Encounter.log…"
    if reason == "back":
        return "Back to live monitoring. No fight has ended in this session yet."
    return "Monitoring Encounter.log. Fight summaries appear here as combat ends."


def archive_line(reason: str, activity: RecentActivity | None, delete_original: bool) -> str:
    """The newest archive, under the first line: which file it is when the
    first line said the log was archived, else when the log was last
    archived; '' with no archive."""
    newest = activity.newest_archive if activity is not None else None
    if newest is None:
        return ""
    if reason == "waiting" and explaining_archive(activity, delete_original) is not None:
        return (f"The archive is {_archive_detail(newest)}. ESO starts a fresh log the next "
                f"time encounter logging is on.")
    return f"Encounter.log was last archived at {format_when(newest.made)}: {_archive_detail(newest)}."


def status_text(reason, activity: RecentActivity | None, delete_original: bool) -> str:
    """The status bar's text while nothing is monitored: the archive that
    explains it, so the bar does not say in red what the pane says is
    fine; '' when there is none."""
    if reason != "waiting":
        return ""
    archive = explaining_archive(activity, delete_original)
    if archive is None:
        return ""
    return f"Waiting for Encounter.log (archived {format_when(archive.made)})"


def _group_heading(name: str, count: int, size: int, shown: int) -> str:
    """'Archives: 12, 820 MB (newest five)'; the bracket only when some are
    left out. *count* is never less than the files shown."""
    count = max(count, shown)
    text = f"<b>{name}</b>: {count}, {format_bytes(size)}"
    if count > shown:
        text += f" (newest {'five' if shown == 5 else shown})"
    return text


def _lists_html(activity: RecentActivity, dark: bool) -> str:
    """One table for both groups, so the columns line up: a header row, a
    bold row for each group, then its files, the size right-aligned."""
    link = link_color(dark)
    rows = ["<tr><th align='left'>When</th><th align='left'>File</th>"
            "<th align='right'>Size</th><th align='left'>Note</th></tr>"]
    index = 0
    if activity.archives:
        rows.append(f"<tr><td colspan='4'>{_group_heading('Archives', activity.archive_count, activity.archive_bytes, len(activity.archives))}</td></tr>")
        for archive in activity.archives:
            note = (f"ending {format_when(archive.last_entry)}"
                    if archive.last_entry is not None else "")
            rows.append(
                f"<tr><td>{format_when(archive.made)}</td>"
                f"<td><a href='{REVIEW_HREF}{index}' style='color:{link}'>"
                f"{html.escape(archive.path.name)}</a></td>"
                f"<td align='right'>{format_bytes(archive.size)}</td>"
                f"<td>{note}</td></tr>")
            index += 1
    if activity.splits:
        rows.append(f"<tr><td colspan='4'>{_group_heading('Split logs', activity.split_count, activity.split_bytes, len(activity.splits))}</td></tr>")
        for split in activity.splits:
            name = html.escape(split.zone) + (" · Veteran" if split.vet else "")
            note = "zipped" if split.zipped else ""
            rows.append(
                f"<tr><td>{format_when(split_time(split))}</td>"
                f"<td><a href='{REVIEW_HREF}{index}' style='color:{link}'>{name}</a></td>"
                f"<td align='right'>{format_bytes(split.size)}</td>"
                f"<td>{note}</td></tr>")
            index += 1
    return (f"<table cellpadding='3' cellspacing='0'>{''.join(rows)}</table>"
            f"<p>{_TOOLBAR_NOTE}</p>")


def empty_state_html(reason: str, activity: RecentActivity | None, *, dark: bool,
                     text_color: str = "", delete_original: bool = False,
                     expected: str = "", show_activity: bool = OPEN_AT_FIRST) -> str:
    """The pane's page while the fight list is empty (see the module). The
    page goes inside the pane's muted placeholder, so the first line takes
    the pane's own *text_color* when given. *expected* is where the log is
    looked for, shown with the logging advice while there is none."""
    link = link_color(dark)
    opening = html.escape(first_line(reason, activity, delete_original))
    parts = [f"<p style='color:{text_color}'>{opening}</p>" if text_color else f"<p>{opening}</p>"]
    archived = archive_line(reason, activity, delete_original)
    if archived:
        parts.append(f"<p>{html.escape(archived)}</p>")
    advice = []
    if reason == "waiting":
        where = html.escape(expected or "known ESO log locations")
        advice = [f"<p>Expected at:<br><code>{where}</code></p>", f"<p>{_LOGGING_ADVICE}</p>"]
    explained = reason == "waiting" and explaining_archive(activity, delete_original) is not None
    if not explained:
        parts.extend(advice)
    if activity:
        action, cue = ("hide", OPEN_CUE) if show_activity else ("show", CLOSED_CUE)
        parts.append(f"<p><a href='{ACTIVITY_HREF}{action}' style='color:{link}'>"
                     f"{ACTIVITY_TITLE} {cue}</a></p>")
        if show_activity:
            parts.append(_lists_html(activity, dark))
    if explained:
        parts.extend(advice)
    return "".join(parts)
