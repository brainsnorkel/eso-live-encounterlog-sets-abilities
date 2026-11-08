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
    ANON,
    KILL,
    clock,
    dps_text,
    outcome_text,
    run_details,
    run_name,
    run_summary,
    runs,
)
from trial_result import result_text

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISCORD_LIMIT = 2000  # characters in one Discord message


def start(entry):
    """The fight's start as the list shows it: local wall-clock time, with
    no zone to name; None for a fight fought before the log gave the time.
    The Instance tab reads it too (gui.instance_render)."""
    try:
        return datetime.strptime(str(entry.timestamp), TIME_FORMAT)  # noqa: DTZ007
    except (TypeError, ValueError):
        return None


def span(fights) -> str:
    """'2026-10-31 20:05 to 22:40': the first fight's start to the last's
    end, from the first and the last fights with a clock (one fought
    before the log gave the time reads 'Unknown Time'); '' with none. The
    Instance tab's heading uses it too (gui.instance_render)."""
    timed = [(began, fight) for fight in fights if (began := start(fight)) is not None]
    if not timed:
        return ""
    first, (last, last_fight) = timed[0][0], timed[-1]
    end = last + timedelta(seconds=float(last_fight.duration_s or 0))
    end_text = end.strftime("%H:%M") if end.date() == first.date() else end.strftime("%Y-%m-%d %H:%M")
    return f"{first.strftime('%Y-%m-%d %H:%M')} to {end_text}"


def kill_figures(pull_fights) -> tuple[float, float, bool]:
    """(seconds, dps, whether that is boss dps) of a kill: the time over the
    pull's fights, and the dps over the same, the boss damage of each fight
    (its boss dps by its boss dps time) over their boss dps times; the
    group's dps the same way when the fights kept no boss figure (a boss
    the game does not flag). The Instance tab writes the same figures
    (gui.instance_render)."""
    duration = sum(float(f.duration_s or 0) for f in pull_fights)
    boss_time = sum(float(getattr(f, "boss_dps_time_s", 0) or 0) for f in pull_fights)
    if boss_time > 0 and any(f.group_boss_dps for f in pull_fights):
        damage = sum(float(f.group_boss_dps or 0) * float(getattr(f, "boss_dps_time_s", 0) or 0)
                     for f in pull_fights)
        return duration, damage / boss_time, True
    times = sum(float(getattr(f, "dps_time_s", 0) or 0) for f in pull_fights)
    if times > 0:
        damage = sum(float(f.group_dps or 0) * float(getattr(f, "dps_time_s", 0) or 0)
                     for f in pull_fights)
        return duration, damage / times, False
    return duration, float(pull_fights[-1].group_dps or 0), False


def _kill_part(pull_fights) -> str:
    """'3:00, 441k boss dps' for a kill (kill_figures); plain 'dps' when the
    fights kept no boss figure."""
    duration, dps, of_bosses = kill_figures(pull_fights)
    return f"{clock(duration)}, {dps_text(dps)} {'boss dps' if of_bosses else 'dps'}"


def players(fights) -> int:
    """The group's size: the largest a pull counted, else the most player
    rows in a fight. The Instance tab's heading uses it too
    (gui.instance_render)."""
    pulls = [int(f.pull.get("players") or 0) for f in fights if getattr(f, "pull", None)]
    if pulls:
        return max(pulls)
    return max((sum(1 for p in f.players if not p.get("companion")) for f in fights), default=0)


def _deaths(count: int) -> str:
    return f"{count} death{'s' if count != 1 else ''}" if count else "no deaths"


def _run_lines(run, names) -> list:
    """A boss's pulls in a row: one line for a single pull, the run row's
    summary with the deaths over every pull and then the kill's own time
    and dps for several, with what ended them under it."""
    fights = [fight for pull in run for fight in pull]
    deaths = sum(int(getattr(f, "deaths", 0) or 0) for f in fights)
    final = run[-1][-1]
    killed = final.pull.get("outcome") == KILL
    if len(run) == 1:
        if killed:
            return [f"{run_name(run)}: kill in 1 pull, {_kill_part(run[-1])}, {_deaths(deaths)}"]
        outcome = outcome_text(final.pull)
        return [f"{run_name(run)}: 1 pull, {outcome[:1].lower()}{outcome[1:]}, {_deaths(deaths)}"]
    line = f"{run_summary(run)}, {_deaths(deaths)}"
    if killed:
        line += f"; the kill {_kill_part(run[-1])}"
    return [line] + [f"  {detail}" for detail in run_details(run, names)]


def _flagged_players(fights) -> int:
    """The players with a possible build issue in any fight: by name, and
    a player the log gives no name by their unit id, so several of them
    are not one."""
    flagged = set()
    for fight in fights:
        for p in fight.players:
            if p.get("build_issues"):
                name = p.get("name")
                flagged.add((ANON, str(p.get("unit_id", ""))) if name == ANON else name)
    return len(flagged)


def trash_text(fights) -> str:
    """'14 fights, 9:30, 3 deaths': the fights of *fights* that are no
    pull, their time and their deaths; '' with none. The Instance tab
    writes the same (gui.instance_render)."""
    trash = [f for f in fights if not getattr(f, "pull", None)]
    if not trash:
        return ""
    deaths = sum(int(f.deaths or 0) for f in trash)
    text = (f"{len(trash)} fight{'s' if len(trash) != 1 else ''}, "
            f"{clock(sum(float(f.duration_s or 0) for f in trash))}")
    return text + (f", {_deaths(deaths)}" if deaths else "")


def _block_lines(fights, names) -> list:
    heading = [header_text(fights[0])]
    when = span(fights)
    if when:
        heading.append(when)
    size = players(fights)
    if size:
        heading.append(f"{size} player{'s' if size != 1 else ''}")
    lines = [" · ".join(heading)]
    for run in runs(fights):
        lines += _run_lines(run, names)
    trash = trash_text(fights)
    if trash:
        lines.append(f"Trash: {trash}")
    flagged = _flagged_players(fights)
    if flagged:
        lines.append(f"ⓘ {flagged} player{'s' if flagged != 1 else ''} with possible build issues")
    # A block ends at the fight that completed its run (fight_blocks)
    result = getattr(fights[-1], "trial_result", None)
    if result:
        lines.append(result_text(result))
    return lines


def recap_text(entries, names=None) -> str:
    """The recap of *entries* (the fight list's fights, in order), one
    block per instance, blocks apart by a blank line; '' for none.
    *names*: the Hide names mask (None keeps every name)."""
    return "\n\n".join("\n".join(_block_lines(fights, names)) for fights in blocks(entries))
