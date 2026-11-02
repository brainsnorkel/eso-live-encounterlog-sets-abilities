"""
The pane before the first fight (issue #191): what the app is doing, when
Encounter.log was last archived, and a Recent activity link that opens to
the newest archives and split logs, each a link that reviews it.

The pane is the right place: it is empty exactly then, where the fight
list's rows are a session's fights and a row that opened a file would look
like one, and a dialog would say something was wrong when nothing is. The
first line and the archive line are always there, so the reassurance needs
no click; the file lists wait behind the link, so the pane does not open on
a wall of file names. Archives and splits are listed apart, five of each:
archives are rare (one per gigabyte of log) and splits frequent, so one
list of five would nearly always be five splits and no archive.

A link to a file carries its place in activity_paths, never the path: a
path put in an href comes back through QUrl with its percent-encoding
undone here and there, and the window holds the list the page was drawn
from anyway. Clicking one runs Open log for review on it, the toolbar
action's own path, so a zipped split or an archive streams from its zip
and a large log is outlined and the reader asked first.
"""

import html
from pathlib import Path

from gui.fight_render import link_color
from recent_activity import RecentActivity, format_when, split_time
from split_retention import format_bytes

# The link that opens and closes the lists, + 'show' or 'hide'
ACTIVITY_HREF = "esolog:activity/"
# A file to review, + its index in activity_paths
REVIEW_HREF = "esolog:review/"

ACTIVITY_TITLE = "Recent activity"
CLOSED_CUE, OPEN_CUE = "▸", "▾"

# The addon advice for a log that is not there (unchanged since 0.6)
_LOGGING_ADVICE = (
    "Enable encounter logging in ESO (/encounterlog), or install an "
    "addon that turns it on for you, one or the other but not both: "
    "Always Logging (from GitHub, github.com/brainsnorkel/AlwaysLogging) "
    "or Easy Stalking (ESOUI or Minion). "
    "Monitoring starts automatically when the file appears.")


def activity_paths(activity: RecentActivity | None) -> list[Path]:
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
    tooltips[f"{ACTIVITY_HREF}show"] = "The newest archives and split logs, each a click from a review"
    tooltips[f"{ACTIVITY_HREF}hide"] = "Close the list"
    return tooltips


def _archive_phrase(archive) -> str:
    """'2 Nov 2026, 21:14 (Encounter-261102204800.zip, 65 MB; its last
    entry 2 Nov 2026, 20:48)'."""
    detail = f"{html.escape(archive.path.name)}, {format_bytes(archive.size)}"
    if archive.last_entry is not None:
        detail += f"; its last entry {format_when(archive.last_entry)}"
    return f"{format_when(archive.made)} ({detail})"


def first_line(reason: str, activity: RecentActivity | None, delete_original: bool) -> str:
    """What the app is doing, as plain text: *reason* is 'monitoring' (the
    log is watched, no fight yet), 'waiting' (no log file) or 'back' (Back
    to live, no fight in the session yet). With no log, the newest archive
    and the delete setting explain where it went."""
    newest = activity.newest_archive if activity is not None else None
    if reason == "waiting":
        if newest is not None and delete_original:
            return (f"Encounter.log was archived at {_archive_phrase(newest)} and removed, "
                    f"as Settings asks. ESO writes a fresh log the next time encounter "
                    f"logging is on. Waiting for encounters.")
        return "Waiting for Encounter.log…"
    if reason == "back":
        return "Back to live monitoring. No fight has ended in this session yet."
    return "Monitoring Encounter.log for encounters. Fight summaries appear here as combat ends."


def archive_line(reason: str, activity: RecentActivity | None, delete_original: bool) -> str:
    """'Encounter.log was last archived at …', or '' when there is no
    archive or the first line already says so."""
    newest = activity.newest_archive if activity is not None else None
    if newest is None or (reason == "waiting" and delete_original):
        return ""
    return f"Encounter.log was last archived at {_archive_phrase(newest)}."


def _table(rows: list[str]) -> str:
    return f"<table cellpadding='3' cellspacing='0'>{''.join(rows)}</table>"


def _lists_html(activity: RecentActivity, dark: bool) -> str:
    link = link_color(dark)
    parts = []
    index = 0
    if activity.archives:
        where = html.escape(str(activity.archive_dir)) if activity.archive_dir else ""
        parts.append(f"<p style='margin-bottom:0'><b>Archives</b>"
                     f"{' in <code>' + where + '</code>' if where else ''}</p>")
        rows = []
        for archive in activity.archives:
            last = (f"last entry {format_when(archive.last_entry)}"
                    if archive.last_entry is not None else "")
            rows.append(
                f"<tr><td>{format_when(archive.made)}</td>"
                f"<td><a href='{REVIEW_HREF}{index}' style='color:{link}'>"
                f"{html.escape(archive.path.name)}</a></td>"
                f"<td align='right'>{format_bytes(archive.size)}</td>"
                f"<td>{last}</td></tr>")
            index += 1
        parts.append(_table(rows))
    if activity.splits:
        where = html.escape(str(activity.split_dir)) if activity.split_dir else ""
        parts.append(f"<p style='margin-bottom:0'><b>Split logs</b>"
                     f"{' in <code>' + where + '</code>' if where else ''}</p>")
        rows = []
        for split in activity.splits:
            name = html.escape(split.zone) + (" · Veteran" if split.vet else "")
            note = "zipped" if split.zipped else ""
            rows.append(
                f"<tr><td>{format_when(split_time(split))}</td>"
                f"<td><a href='{REVIEW_HREF}{index}' style='color:{link}'>{name}</a></td>"
                f"<td align='right'>{format_bytes(split.size)}</td>"
                f"<td>{note}</td></tr>")
            index += 1
        parts.append(_table(rows))
    return "".join(parts)


def empty_state_html(reason: str, activity: RecentActivity | None, *, dark: bool,
                     text_color: str = "", delete_original: bool = False,
                     expected: str = "", show_activity: bool = False) -> str:
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
    if reason == "waiting":
        where = html.escape(expected or "known ESO log locations")
        parts.append(f"<p>Expected at:<br><code>{where}</code></p>")
        parts.append(f"<p>{_LOGGING_ADVICE}</p>")
    if activity:
        action, cue = ("hide", OPEN_CUE) if show_activity else ("show", CLOSED_CUE)
        parts.append(f"<p><a href='{ACTIVITY_HREF}{action}' style='color:{link}'>"
                     f"{ACTIVITY_TITLE} {cue}</a></p>")
        if show_activity:
            parts.append(_lists_html(activity, dark))
    return "".join(parts)
