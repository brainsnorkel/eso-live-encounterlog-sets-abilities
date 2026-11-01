"""
The session recap (issue #171): the fight list as plain text for Discord,
for the raid lead who posts the night, not one fight.

Design: the recap is the list's own two groupings written out. Each
instance block (fight_blocks) gets a heading with its zone, the time it
spans and the group's size; under it, one line per boss's pulls in a row
(pull_outcome.runs), in the order they were fought; then the trash, as a
count and a time; then how many players had a possible build issue; then
the run's result when the block completed a trial. A boss killed on the
first pull is one line with the kill's time and boss dps. Two pulls or
more are the run row's summary, the kill's time and dps after it, then
its hover's lines (first deaths, killers, longest dead) indented under
it: what ended the pulls is the part of a progression night nobody wants
to retype.

The copy is plain lines: Discord keeps the breaks and wraps them on a
phone, where a code block would run off the side. A message is 2,000
characters at most; a long night is pasted in parts, and the status bar
says how long the copy is. Every player name goes through the Hide names
mask, the only names being the run's longest dead; build issues are a
count, never names, since a recap posted to a channel is the wrong place
to call players out.

The sums in the data the lines come from (2026-11-01, 378 split
sessions): a median session had 18 fights, 4 boss fights over 3 bosses
and 15 minutes in combat (p90 44 fights), so a typical recap is under 15
lines.
"""

from datetime import datetime, timedelta

from fight_blocks import blocks, header_text
from pull_outcome import (
    KILL,
    clock,
    outcome_text,
    run_details,
    run_name,
    run_summary,
    runs,
)
from trial_result import result_text

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISCORD_LIMIT = 2000  # characters in one Discord message


def _dps(value) -> str:
    value = float(value or 0)
    return f"{value / 1000:.0f}k" if value >= 1000 else f"{value:.0f}"


def _start(entry):
    """The fight's start as the list shows it: local wall-clock time, with
    no zone to name."""
    try:
        return datetime.strptime(str(entry.timestamp), TIME_FORMAT)  # noqa: DTZ007
    except (TypeError, ValueError):
        return None


def _span(fights) -> str:
    """'2026-10-31 20:05 to 22:40': the first fight's start to the last's
    end; '' when the log gave no clock."""
    start, last = _start(fights[0]), _start(fights[-1])
    if start is None or last is None:
        return ""
    end = last + timedelta(seconds=float(fights[-1].duration_s or 0))
    end_text = end.strftime("%H:%M") if end.date() == start.date() else end.strftime("%Y-%m-%d %H:%M")
    return f"{start.strftime('%Y-%m-%d %H:%M')} to {end_text}"


def _players(fights) -> int:
    """The group's size: the largest a pull counted, else the most player
    rows in a fight."""
    pulls = [int(f.pull.get("players") or 0) for f in fights if getattr(f, "pull", None)]
    if pulls:
        return max(pulls)
    return max((sum(1 for p in f.players if not p.get("companion")) for f in fights), default=0)


def _deaths(count: int) -> str:
    return f"{count} death{'s' if count != 1 else ''}" if count else "no deaths"


def _run_lines(run, names) -> list:
    fights = [fight for pull in run for fight in pull]
    deaths = sum(int(getattr(f, "deaths", 0) or 0) for f in fights)
    final = run[-1][-1]
    killed = final.pull.get("outcome") == KILL
    kill_part = ""
    if killed:
        duration = sum(float(f.duration_s or 0) for f in run[-1])
        dps = final.group_boss_dps or final.group_dps
        kill_part = f"{clock(duration)}, {_dps(dps)} boss dps"
    if len(run) == 1:
        if killed:
            return [f"{run_name(run)}: kill in 1 pull, {kill_part}, {_deaths(deaths)}"]
        outcome = outcome_text(final.pull)
        return [f"{run_name(run)}: 1 pull, {outcome[:1].lower()}{outcome[1:]}, {_deaths(deaths)}"]
    line = run_summary(run)
    if killed:
        line += f"; the kill {kill_part}"
    lines = [f"{line}, {_deaths(deaths)}"]
    lines += [f"  {detail}" for detail in run_details(run, names)]
    return lines


def _block_lines(fights, names) -> list:
    heading = [header_text(fights[0])]
    span = _span(fights)
    if span:
        heading.append(span)
    players = _players(fights)
    if players:
        heading.append(f"{players} player{'s' if players != 1 else ''}")
    lines = [" · ".join(heading)]
    for run in runs(fights):
        lines += _run_lines(run, names)
    trash = [f for f in fights if not getattr(f, "pull", None)]
    if trash:
        deaths = sum(int(f.deaths or 0) for f in trash)
        line = f"Trash: {len(trash)} fight{'s' if len(trash) != 1 else ''}, " \
               f"{clock(sum(float(f.duration_s or 0) for f in trash))}"
        lines.append(line + (f", {_deaths(deaths)}" if deaths else ""))
    flagged = {p.get("name") for f in fights for p in f.players if p.get("build_issues")}
    if flagged:
        lines.append(f"ⓘ {len(flagged)} player{'s' if len(flagged) != 1 else ''} "
                     f"with possible build issues")
    result = next((f.trial_result for f in reversed(fights) if getattr(f, "trial_result", None)),
                  None)
    if result:
        lines.append(result_text(result))
    return lines


def recap_text(entries, names=None) -> str:
    """The recap of *entries* (the fight list's fights, in order), one
    block per instance, blocks apart by a blank line; '' for none.
    *names*: the Hide names mask (None keeps every name)."""
    return "\n\n".join("\n".join(_block_lines(fights, names)) for fights in blocks(entries))
