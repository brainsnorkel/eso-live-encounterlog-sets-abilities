"""
The Instance tab (issue #196): the trial, arena or dungeon run the fight
on screen belongs to, on one page, where the fight list spreads it over a
header row, run rows and their hover, a result row and Copy session.

Design: The instance page. An instance is a block of the fight list
(fight_blocks.blocks: the fights fought one after another in one zone at
one difficulty, closed by a completed run, #129), taken anew at each
drawing. The page reads, from the top:

- **Heading**: the zone and difficulty, the time from the first fight's
  start to the last one's end, the fights, the group's size and the game
  version, the span and the size as the session recap writes them
  (session_recap.span and players), then Copy this instance, which copies
  the block as Copy session writes each instance (session_recap.recap_text,
  #171). The live list's first instance can have begun before the logging
  session the app read at its start, since a start reads the log's latest
  session only (LogFileMonitor._load_latest_session), so that page says
  it is listed from its first fight and that any earlier fights are in
  the previous session's log: "any", since mostly there are none.
- **Result**: a completed veteran trial's or arena's result, as the result
  row writes it (trial_result), with the fight pane's Score banner links,
  which act on the fight with the result whichever fight is on screen;
  under it the split logs of the instance's sessions, as the result strip
  lists them (gui.fight_render.split_lines_html, #194). A dungeon or a
  failed run has no result, only a veteran run that succeeds writes
  END_TRIAL, and its strip holds the split logs alone.
- **Bosses**: a row for each boss's pulls in a row (pull_outcome.runs),
  one pull included: the pulls, the result, the kill's time and boss dps,
  and the deaths over all its pulls. The result is the run row's words
  after its count ("killed on pull 3, 41s between pulls"), or one pull's
  verdict ("kill", "wipe 62%"), then the best earlier kill with this
  roster from the fight history (fight_index.run_best_kill, #170), as the
  run row adds it. The kill's figures are the session recap's
  (session_recap.kill_figures): its time over the pull's fights, and the
  boss damage of each fight over their boss dps times (the group's dps,
  said so, for a boss the game does not flag), so the page and its copy
  agree. Under two or more pulls a line
  reads "Pulls: pull 1 (wipe 62%) · pull 2 (kill)", each pull a link to
  its last fight, whose verdict it names (the log can cut a pull in two).
  Each row holds a named anchor (run_anchor), numbered over every run of
  the block in order, where a click on the list's run row opens the page.
  It sits on the count of pulls, plain text: Qt hangs an empty named
  anchor on the first letter of the text after it, and when that text
  was a link, only that letter stayed marked as an anchor, all
  FightView's hover cue and Tab key then took for the link (probed on
  PySide6 6.12.0).
- **What ended the pulls**: the run row's hover widened to every pull of
  the instance, counted once for both (pull_outcome.what_ended): the
  first death of each pull, the killers and the share the bosses dealt,
  and the longest dead, a second or more (a solo player's fight ends as
  they die, which would read "0s"), the TOP of each and an ellipsis when
  there are more. A killer is named after the ability when it is not one
  of the instance's bosses.
- **Trash**, in the copy's words (session_recap.trash_text), and a solo
  dungeon's Misfortunes once: the run's, the same at every pull
  (misfortunes.py).
- **Players**: everyone of the instance but the companions, each once,
  told by handle across its fights, a player the log gives no name
  ("anon") by unit id and class, as the run row's hover tells them apart:
  the class keeps apart two that took one unit id in two logging sessions
  of the instance. Not by role, which the engine guesses fight by fight (a
  healer can read as a damage dealer on trash): role and class are the
  ones most of their fights read, the latest winning a tie. Pulls
  counts the pulls they were in; deaths and time dead count every fight,
  trash too, as each death in a trial costs vitality, so a player's time
  dead can exceed the longest dead line's, which counts the pulls. A
  player's possible build issues go on a line under their row, each
  finding once (by its rule, set, skill and star) in its latest words,
  with the number of their fights it was found in: as a column beside the
  names they were squeezed to a word a line at 200% text, a 12-player
  trial's table 1,522 px tall, 688 with the line (measured; the line
  costs 30-85 px at 100%). A player who died with no row of their own
  (the pane's Also died) is listed with no role. Each name is a link to
  that player's window on Build, on the fight on screen when they have a
  row in it, else their last fight of the instance with one; a player who
  never had a row (their build never reached the log) opens on Deaths, at
  their last death, as the pane's Also died does. The hover names that
  fight ("@x in Nahviintaas, pull 13").

The tables keep their words whole up to 200% text (measured over real
splits): no heading breaks; the figures' columns are as narrow as their
words (FIT) and set apart from the column before (FIGURE), so the boss
and the result keep the width; and every column of the players' table is
as narrow as its words, an empty one taking the rest, so role and class
stay by the name.

Links carry the fight's place in the list the page was drawn from
(index_of), never a path or an entry, as the Recent activity page's do
(gui.activity_render): a link whose fight has left the list does nothing,
and the window says so. A fight index_of does not place gets no link.
Pull links take the link colour; the players' names keep the look of
plain text, as the fight pane's do. Every player's name goes through the
Hide names mask, in its text form in the hover texts.

Nothing here changes an entry: the engine's thread updates delivered
fights in place while a page is drawn (MainWindow._fight_changed), so
their lists are read and counted into new lists and dicts, sorted with
sorted(), never in place.
"""

import html
from collections import Counter

import session_recap
from fight_blocks import header_text
from fight_index import fmt_dps, run_best_kill, short_version
from gui.fight_render import (
    ISSUES_TITLE,
    MISFORTUNE_HREF,
    _banner_links,
    _join,
    split_lines_html,
    _theme,
    misfortunes_tooltips,
)
from gui.name_mask import NO_MASK
from pull_outcome import (
    ANON,
    KILL,
    TOP,
    clock,
    outcome_text,
    pulls,
    run_name,
    run_outcome_parts,
    runs,
    what_ended,
)
from trial_result import result_text

# + the fight's place in the list the page was drawn from: a pull, which
# a click shows on the Fight tab
FIGHT_HREF = "esolog:fight/"
# + that place, '/' and the player's unit id in that fight: their player
# window, on Build
PLAYER_HREF = "esolog:player/"
# Copy this instance (session_recap.recap_text)
INSTANCE_COPY_HREF = "esolog:instance/copy"
# + the run's number from 1 over every run of the block: the <a name> its
# row of the Bosses table holds
RUN_ANCHOR = "run-"

COPY_TEXT = "Copy this instance"
NO_FIGHTS = "No fights in this instance."
# Under the heading of the live list's first instance (see the module)
LISTED_FROM = "Listed from {time}; any earlier fights are in the previous session's log."
LISTED_EARLIER = "Any earlier fights are in the previous session's log."
BOSS_HEADINGS = ("Boss", "Pulls", "Result", "Kill", "Boss dps", "Deaths")
PLAYER_HEADINGS = ("Player", "Role", "Class", "Pulls", "Deaths", "Time dead")
# Before a player's build issues, on the line under their row
ISSUES_LEAD = f"{ISSUES_TITLE}:"
PULLS_LEAD = "Pulls:"
FIRST_DEATHS_LEAD = "First deaths:"
KILLERS_LEAD = "Killers:"
MOST_DEAD_LEAD = "Most time dead:"
MOST_DEAD_MIN_MS = 1000  # the least time dead the longest dead line names
TRASH_LEAD = "Trash:"
MISFORTUNES_LEAD = "Misfortunes:"
BEST_KILL = "best kill with this roster"  # the run row's words (gui.fight_list.run_text)
ALL_TARGETS = "(all targets)"  # after a kill's dps when the game flagged no boss
MORE = "…"
DASH = "–"
# A text column's left padding after a right-aligned figure, which ran into
# it at 200% text ('1 kill' under 'Pulls Result')
GAP = "padding-left:12px;"
# A figures' column: never broken, and set off from the column before, as
# the headings 'Kill Boss dps Deaths' ran together at 200% text
FIGURE = "white-space:nowrap;padding-left:10px;"
# A fixed column width in pixels, for a column as narrow as its words: Qt
# widens a fixed column to its widest unbroken text. Left variable, the
# figures' columns took the width a line spanning the table lends every
# column (Qt spreads a spanning cell's width over the columns it spans),
# and at 200% text the boss names broke in two (measured; shares in per
# cent for the names fared worse)
FIT = "1"
# The table's order: tanks, healers, damage dealers, then anyone else
ROLE_ORDER = {"T": 0, "H": 1, "D": 2}
FIGHT_TIP = "Click to show this fight on the Fight tab"
PLAYER_TIP = "Click for their build in that fight"
DEATH_TIP = "Click for their death in that fight"  # a player who never had a row
COPY_TIP = ("Copy this instance as text for Discord: its bosses, what ended the pulls, the "
            "trash and the result, as Copy session (Ctrl+Shift+C) writes each instance")


# ----------------------------------------------------------------- links --

def fight_href(index) -> str:
    return f"{FIGHT_HREF}{int(index)}"


def player_href(index, unit_id) -> str:
    return f"{PLAYER_HREF}{int(index)}/{unit_id}"


def _place_number(text: str) -> int | None:
    # isdigit alone takes '²', which int refuses
    return int(text) if text.isascii() and text.isdigit() else None


def fight_from_href(href: str) -> int | None:
    """The fight's place in the list when *href* is a pull's link, else
    None."""
    if not href or not href.startswith(FIGHT_HREF):
        return None
    return _place_number(href[len(FIGHT_HREF):])


def player_from_href(href: str) -> tuple[int, str] | None:
    """(the fight's place in the list, the player's unit id in it) when
    *href* is a player's link, else None."""
    if not href or not href.startswith(PLAYER_HREF):
        return None
    place, slash, unit_id = href[len(PLAYER_HREF):].partition("/")
    number = _place_number(place)
    if number is None or not slash or not unit_id:
        return None
    return number, unit_id


def run_anchor(n: int) -> str:
    """The <a name> the *n*-th run's row of the Bosses table holds: *n*
    from 1 over every run of pull_outcome.runs(block), one pull or more,
    in block order."""
    return f"{RUN_ANCHOR}{int(n)}"


# ------------------------------------------------------------ the block --

def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _deaths_of(fights) -> int:
    return sum(int(getattr(fight, "deaths", 0) or 0) for fight in fights)


def _places(block_runs) -> dict:
    """id(fight) -> (its run, the pull's number in the run from 1, the
    fight's part of the pull from 1, the pull's parts), for each fight of
    a pull."""
    places = {}
    for run in block_runs:
        for number, pull in enumerate(run, 1):
            for part, fight in enumerate(pull, 1):
                places[id(fight)] = (run, number, part, len(pull))
    return places


def _fight_label(fight, places) -> str:
    """'Nahviintaas, pull 13', with ', part 2 of 2' in a pull the log cut
    in two; 'Daedroth (trash, 21:44)' for a fight that is no pull."""
    place = places.get(id(fight))
    if place is not None:
        run, number, part, parts = place
        label = f"{run_name(run)}, pull {number}"
        return label + (f", part {part} of {parts}" if parts > 1 else "")
    start = session_recap.start(fight)
    boss = str(getattr(fight, "boss_name", "") or "")
    if boss:
        return f"{boss} (trash, {start:%H:%M})" if start else f"{boss} (trash)"
    return f"a trash fight at {start:%H:%M}" if start else "a trash fight"


def _run_result(run, fight_index) -> str:
    """'killed on pull 3, 41s between pulls', 'best 43%, 8 wipes at 80 to
    90%, 43s between pulls' (the run row's summary after its count,
    pull_outcome.run_outcome_parts), or for one pull its verdict, 'kill' or
    'wipe 62%'; then the best earlier kill with this roster when the fight
    history has one."""
    final = getattr(run[-1][-1], "pull", None) or {}
    if len(run) == 1:
        text = "kill" if final.get("outcome") == KILL else _lower_first(outcome_text(final))
    else:
        text = ", ".join(run_outcome_parts(run))
    parts = [text] if text else []
    best = run_best_kill(fight_index, run)
    if best:
        parts.append(f"{BEST_KILL} {fmt_dps(best)}")
    return ", ".join(parts)


def _player_key(name: str, unit_id: str, cls: str) -> tuple:
    """Who a row or a death is across the block's fights: the handle, or an
    anon's unit id and class (see the module)."""
    if name == ANON:
        return (ANON, unit_id, cls)
    return (name,)


def _most(values: list) -> str:
    """The value most of *values* hold, the latest of them winning a tie;
    '' for none."""
    if not values:
        return ""
    counts = Counter(values)
    last = {value: at for at, value in enumerate(values)}
    return max(counts, key=lambda value: (counts[value], last[value]))


def _players(block, block_pulls) -> list:
    """The block's players in the table's order (see the module), each a
    dict: name, role, class, pulls (how many), deaths, dead_ms, issues
    ({finding's key: (latest title, fights)}) and seen ([(fight, unit id,
    whether they have a row in it)], in block order)."""
    pull_of = {id(fight): number for number, pull in enumerate(block_pulls) for fight in pull}
    # An anon's class by unit id, for a death of theirs with no row
    classes = {str(p.get("unit_id", "")): _join(p.get("class_abbr", ""))
               for fight in block for p in getattr(fight, "players", None) or []
               if not p.get("companion") and _join(p.get("name", "")) == ANON}
    found = {}

    def note(key, name):
        if key not in found:
            found[key] = {"name": name, "roles": [], "classes": [], "pulls": set(), "deaths": 0,
                          "dead_ms": 0, "issues": {}, "seen": []}
        return found[key]

    def was_in(player, fight, unit_id, row, died, time_dead):
        player["seen"].append((fight, unit_id, row))
        player["deaths"] += died.get(unit_id, 0)
        player["dead_ms"] += int(time_dead.get(unit_id, 0) or 0)
        if id(fight) in pull_of:
            player["pulls"].add(pull_of[id(fight)])

    for fight in block:
        recaps = getattr(fight, "death_recaps", None) or []
        died = Counter(str(recap.get("unit_id", "")) for recap in recaps)
        time_dead = getattr(fight, "time_dead", None) or {}
        listed = set()
        for p in getattr(fight, "players", None) or []:
            if p.get("companion"):
                continue
            unit_id = str(p.get("unit_id", ""))
            name = _join(p.get("name", ""))
            role, cls = str(p.get("role") or ""), _join(p.get("class_abbr", ""))
            player = note(_player_key(name, unit_id, cls), name)
            listed.add(unit_id)
            if role:
                player["roles"].append(role)
            if cls:
                player["classes"].append(cls)
            was_in(player, fight, unit_id, True, died, time_dead)
            for finding in p.get("build_issues") or []:
                key = tuple(str(finding.get(part) or "") for part in ("rule", "set", "skill", "star"))
                _title, fights = player["issues"].get(key, ("", 0))
                player["issues"][key] = (str(finding.get("title") or ""), fights + 1)
        # A player who died with no row of their own in this fight
        for recap in recaps:
            unit_id = str(recap.get("unit_id", ""))
            if unit_id in listed:
                continue
            listed.add(unit_id)
            name = str(recap.get("name") or "unknown")
            was_in(note(_player_key(name, unit_id, classes.get(unit_id, "")), name),
                   fight, unit_id, False, died, time_dead)
    out = []
    for player in found.values():
        out.append({"name": player["name"], "role": _most(player["roles"]),
                    "class": _most(player["classes"]), "pulls": len(player["pulls"]),
                    "deaths": player["deaths"], "dead_ms": player["dead_ms"],
                    "issues": player["issues"], "seen": player["seen"]})
    return sorted(out, key=lambda p: (ROLE_ORDER.get(p["role"], len(ROLE_ORDER)),
                                      p["name"] == ANON, p["name"].casefold(), p["class"]))


def _link_place(player, index_of, shown):
    """(place, unit id, fight, whether they have a row in it) of the fight
    a player's name opens: of the fights they have a row in, the one on
    screen, else their last; for a player who never had one, their last
    death, which the window opens on Deaths (see the module). Each only
    when index_of places it; None when it places none."""
    seen = list(reversed(player["seen"]))
    rows = [each for each in seen if each[2]]
    order = [each for each in rows if each[0] is shown] + rows + [each for each in seen if not each[2]]
    for fight, unit_id, row in order:
        place = index_of(fight)
        if place is not None:
            return place, unit_id, fight, row
    return None


def _who_text(player) -> str:
    """The player's name, an anon's with its role and class."""
    if player["name"] == ANON:
        return f"{ANON} ({player['role'] or '?'}, {player['class'] or '?'})"
    return player["name"]


# ------------------------------------------------------------- sections --

def _heading_html(block, theme: dict, e, base_pt: float, opens_list: bool) -> str:
    muted = theme["muted"]
    facts = []
    when = session_recap.span(block)
    if when:
        facts.append(when)
    facts.append(_plural(len(block), "fight"))
    size = session_recap.players(block)
    if size:
        facts.append(_plural(size, "player"))
    versions = []
    for fight in block:
        version = short_version(getattr(fight, "game_version", "") or "")
        if version and version not in versions:
            versions.append(version)
    if versions:
        facts.append("game " + ", ".join(versions))
    copy = (f'<a href="{INSTANCE_COPY_HREF}" style="color:{theme["link"]}">'
            f"{COPY_TEXT}</a>")
    parts = [(f"<p style='margin:0'><span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>"
              f"{e(header_text(block[0]))}</span>&nbsp;&nbsp; "
              f"<span style='color:{muted}'>{e(' · '.join(facts))} · </span>{copy}</p>")]
    if opens_list:
        start = next((at for at in map(session_recap.start, block) if at is not None), None)
        note = LISTED_FROM.format(time=f"{start:%H:%M}") if start else LISTED_EARLIER
        parts.append(f"<p style='margin:0;color:{muted}'>{e(note)}</p>")
    return "".join(parts)


def _result_html(block, theme: dict, e, split_files=None, hide_paths=False) -> str:
    """The run's result in a strip framed like the fight pane's, the split
    logs' lines under it; '' for a block with neither."""
    fight = next((f for f in reversed(block) if getattr(f, "trial_result", None)), None)
    lines = ([f"<b>{e(result_text(fight.trial_result))}</b>{_banner_links(fight, theme)}"]
             if fight is not None else [])
    lines += split_lines_html(split_files, theme, hide_paths)
    if not lines:
        return ""
    return (f"<table cellpadding='5' cellspacing='0' width='99%' "
            f"style='border-style:solid;border-width:1px;border-color:{theme['frame_border']};"
            f"border-collapse:collapse;background-color:{theme['frame_bg']};margin-top:6px'>"
            f"<tr><td>{'<br>'.join(lines)}</td></tr></table>")


def _head_row(headings, theme: dict, numeric=(), fit=(), gap=()) -> str:
    """A table's heading row: muted, ruled under and never broken inside a
    word (at 200% text 'Role' broke in two, as the Deaths tab's headings
    did, #206). The *numeric* headings, a figures' column's, are
    right-aligned and set off from the column before (FIGURE); a *fit*
    column is as narrow as its words (FIT); a *gap* heading's column is set
    off from a figure before it (GAP)."""
    style = (f"color:{theme['muted']};border-bottom-style:solid;border-bottom-width:1px;"
             f"border-bottom-color:{theme['frame_border']};white-space:nowrap;")
    cells = []
    for heading in headings:
        attrs, extra = "", ""
        if heading in numeric:
            attrs, extra = " align='right'", FIGURE
        if heading in fit:
            attrs += f" width='{FIT}'"
        if heading in gap:
            extra += GAP
        cells.append(f"<td{attrs} style='{style}{extra}'>{heading}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def _bosses_html(block_runs, index_of, theme: dict, e, fight_index) -> str:
    """A row per run, each with its anchor, and a line of its pulls under a
    run of two or more; '' for a block without a pull."""
    if not block_runs:
        return ""
    muted = theme["muted"]
    dash = f"<span style='color:{muted}'>{DASH}</span>"
    figure = " align='right'"
    figures = ("Pulls", "Kill", "Boss dps", "Deaths")
    parts = ["<table cellpadding='3' cellspacing='0' width='99%' style='margin-top:6px'>",
             _head_row(BOSS_HEADINGS, theme, numeric=figures, fit=figures, gap=("Result",))]
    for number, run in enumerate(block_runs, 1):
        last = run[-1]
        kill = dps = dash
        if (getattr(last[-1], "pull", None) or {}).get("outcome") == KILL:
            seconds, value, of_bosses = session_recap.kill_figures(last)
            kill = e(clock(seconds))
            dps = e(fmt_dps(value))
            if not of_bosses:
                dps += f" <span style='color:{muted}'>{ALL_TARGETS}</span>"
        # The row's anchor, on the count of pulls (see the module)
        cells = (
            ("", "", f"<b>{e(run_name(run))}</b>"),
            (figure, FIGURE, f"<a name='{run_anchor(number)}'></a>{len(run)}"),
            ("", GAP, e(_run_result(run, fight_index))),
            (figure, FIGURE, kill),
            (figure, FIGURE, dps),
            (figure, FIGURE, str(_deaths_of(fight for pull in run for fight in pull))),
        )
        parts.append("<tr>" + "".join(f"<td{attrs} valign='top' style='{style}'>{content}</td>"
                                      for attrs, style, content in cells) + "</tr>")
        if len(run) > 1:
            parts.append(f"<tr><td colspan='{len(BOSS_HEADINGS)}' "
                         f"style='padding-left:14px;color:{muted}'>{PULLS_LEAD} "
                         f"{_pulls_html(run, index_of, theme, e)}</td></tr>")
    parts.append("</table>")
    return "".join(parts)


def _pulls_html(run, index_of, theme: dict, e) -> str:
    """'pull 1 (wipe 62%) · pull 2 (kill)': each pull a link to its last
    fight, whose verdict it gives."""
    items = []
    for number, pull in enumerate(run, 1):
        label = e(f"pull {number} ({_lower_first(outcome_text(pull[-1].pull))})")
        place = index_of(pull[-1])
        if place is not None:
            label = (f'<a href="{fight_href(place)}" '
                     f'style="text-decoration:none;color:{theme["link"]}">{label}</a>')
        items.append(label)
    return " · ".join(items)


def _counted_html(counter: Counter, item_html) -> str:
    """The TOP most counted, each with its count past one, and an ellipsis
    when there are more."""
    items = [item_html(key) + (f" ×{count}" if count > 1 else "")
             for key, count in counter.most_common(TOP)]
    if len(counter) > TOP:
        items.append(MORE)
    return " · ".join(items)


def _ended_html(block_pulls, theme: dict, names, base_pt: float, e) -> str:
    """First deaths, killers and the longest dead over every pull of the
    block, as the run row's hover counts them for a run
    (pull_outcome.what_ended); '' when nobody died in a pull."""
    ended = what_ended(block_pulls)
    if not ended["total"]:
        return ""
    muted, text = theme["muted"], theme["text"]

    def death_html(key):
        ability, killer = key
        out = f"<b>{e(ability)}</b>"
        return out + (f" ({names.html(killer, text, base_pt)})" if killer else "")

    def lead(words, margin):
        return f"<p style='margin:{margin}'><span style='color:{muted}'>{words}</span> "

    killers_line = _counted_html(ended["killers"], death_html)
    if ended["by_boss"]:
        bosses = [str(boss) for boss in ended["bosses"]]
        named = " and ".join(bosses) if len(bosses) <= 2 else "the bosses"
        killers_line += (f"<span style='color:{muted}'>; "
                         f"{round(100 * ended['by_boss'] / ended['total'])}% by {e(named)}</span>")

    def dead_html(ident):
        name, row = ended["who"][ident]
        out = names.html(name, text, base_pt)
        if name == ANON:
            row = row or {}
            out += (f" <span style='color:{muted}'>({e(str(row.get('role') or '?'))}, "
                    f"{e(_join(row.get('class_abbr', '')) or '?')})</span>")
        return out

    parts = [lead(FIRST_DEATHS_LEAD, "8px 0 0 0") + _counted_html(ended["firsts"], death_html)
             + "</p>", lead(KILLERS_LEAD, "2px 0 0 0") + killers_line + "</p>"]
    # Under a second dead is no one's longest: a solo player's fight ends
    # as they die, which reads '0s'
    longest = [(ident, ms) for ident, ms in ended["dead"].most_common(TOP)
               if ms >= MOST_DEAD_MIN_MS]
    if longest:
        items = [f"{dead_html(ident)} {e(clock(ms / 1000))}" for ident, ms in longest]
        parts.append(lead(MOST_DEAD_LEAD, "2px 0 0 0") + " · ".join(items) + "</p>")
    return "".join(parts)


def _trash_html(block, theme: dict, e) -> str:
    """'Trash: 12 fights, 8:20, 3 deaths', in the copy's words
    (session_recap.trash_text); '' with none."""
    text = session_recap.trash_text(block)
    if not text:
        return ""
    return (f"<p style='margin:8px 0 0 0'><span style='color:{theme['muted']}'>{TRASH_LEAD}</span> "
            f"{e(text)}</p>")


def _misfortunes_fight(block):
    """The block's last fight that holds the run's Misfortunes (a solo
    dungeon's), None in any other zone."""
    return next((fight for fight in reversed(block)
                 if getattr(fight, "misfortunes", None) is not None), None)


def _misfortunes_html(block, theme: dict, e) -> str:
    """'Misfortunes: Warm Welcome · Revoke of Respite', as the fight pane
    writes them, each with a text a hover anchor; '' outside a solo
    dungeon."""
    fight = _misfortunes_fight(block)
    if fight is None:
        return ""
    muted = theme["muted"]
    items = []
    for number, (name, text) in enumerate(fight.misfortunes or []):
        label = e(str(name))
        if text:
            label = (f'<a href="{MISFORTUNE_HREF}{number}" '
                     f'style="text-decoration:none;color:{muted}">{label}</a>')
        items.append(label)
    return (f"<p style='margin:2px 0 0 0;color:{muted}'>{MISFORTUNES_LEAD} "
            f"{' · '.join(items) or 'none'}</p>")


def _players_html(players, index_of, shown, theme: dict, names, base_pt: float, e) -> str:
    """The players' table (see the module), a player's build issues on a
    line of their own under their row; '' with none."""
    if not players:
        return ""
    muted, text = theme["muted"], theme["text"]
    roles = theme["roles"]
    figure = " align='right'"
    nowrap = "white-space:nowrap;"
    small = f"color:{muted};font-size:{base_pt * 0.85:.2f}pt"
    # Each column as narrow as its words and an empty one taking the rest,
    # so role and class stay by the name: the issues' line lent the role
    # and class columns its width, and they drifted across the page
    parts = ["<table cellpadding='3' cellspacing='0' width='99%' style='margin-top:8px'>",
             _head_row(PLAYER_HEADINGS + ("",), theme, numeric=("Pulls", "Deaths", "Time dead"),
                       fit=PLAYER_HEADINGS)]
    for player in players:
        name = names.html(player["name"], text, base_pt)
        place = _link_place(player, index_of, shown)
        if place is not None:
            href = e(player_href(place[0], place[1]), quote=True)
            name = f'<a href="{href}" style="text-decoration:none;color:{text}">{name}</a>'
        role = player["role"]
        role_html = f"<span style='color:{roles.get(role, muted)}'>{e(role)}</span>" if role else ""
        dead = (e(clock(player["dead_ms"] / 1000)) if player["dead_ms"] > 0
                else f"<span style='color:{muted}'>{DASH}</span>")
        cells = (
            ("", nowrap, name),
            ("", nowrap, role_html),
            ("", nowrap, e(player["class"])),
            (figure, FIGURE, str(player["pulls"])),
            (figure, FIGURE, str(player["deaths"])),
            (figure, FIGURE, dead),
            ("", "", ""),
        )
        parts.append("<tr>" + "".join(f"<td{attrs} valign='top' style='{style}'>{content}</td>"
                                      for attrs, style, content in cells) + "</tr>")
        if player["issues"]:
            issues = " · ".join(e(title) + (f" ×{fights}" if fights > 1 else "")
                                for title, fights in player["issues"].values())
            parts.append(f"<tr><td colspan='{len(cells)}' "
                         f"style='padding-left:14px;padding-top:0;{small}'>"
                         f"{ISSUES_LEAD} {issues}</td></tr>")
    parts.append("</table>")
    return "".join(parts)


# ------------------------------------------------------------- the page --

def render_instance_html(block, index_of, shown=None, dark: bool = False, icons=None,
                         base_pt: float = 9.0, names=None, text_color: str | None = None,
                         opens_list: bool = False, fight_index=None, split_files=None,
                         hide_paths: bool = False) -> str:
    """The instance *block* (fight_blocks.blocks: one instance's fights, in
    order) as HTML for the Instance tab (see the module).

    index_of(entry): the entry's place in the fight list the page is drawn
    from, which the links carry; None leaves that fight unlinked. shown:
    the fight on screen, whose players' names open it. icons: taken as
    every page renderer takes it, and unused: the page names abilities in
    words. base_pt: the page's font size. names: the Hide names mask
    (gui.name_mask). text_color: the page's own text colour, which a name
    and a hidden name are drawn in. opens_list: the block opens the live
    fight list, so its fights may go back before the log session the app
    read (see the module). fight_index: the fight history
    (fight_index.FightIndex) the best earlier kills come from; None for
    none. split_files: the split logs of the instance's sessions, under its
    result (gui.fight_render.split_lines_html), and hide_paths, Hide names
    on, so they show by their names alone. The hover texts are
    instance_tooltips(), with split_tooltips() for the split logs."""
    theme = dict(_theme(dark))
    if text_color:
        theme["text"] = text_color
    names = names or NO_MASK
    e = html.escape
    block = list(block or [])
    if not block:
        return f"<p style='margin:0;color:{theme['muted']}'>{NO_FIGHTS}</p>"
    shown = shown if any(fight is shown for fight in block) else None
    block_runs = runs(block)
    block_pulls = pulls(block)
    return "".join((
        _heading_html(block, theme, e, base_pt, opens_list),
        _result_html(block, theme, e, split_files, hide_paths),
        _bosses_html(block_runs, index_of, theme, e, fight_index),
        _ended_html(block_pulls, theme, names, base_pt, e),
        _trash_html(block, theme, e),
        _misfortunes_html(block, theme, e),
        _players_html(_players(block, block_pulls), index_of, shown, theme, names, base_pt, e),
    ))


def _pull_tip(run, number: int, pull, e) -> str:
    """A pull link's hover: the run's boss, the pull, its verdict, time,
    start and deaths, a pull the log cut in two said so."""
    title = run_name(run)
    facts = [outcome_text(pull[-1].pull, title),
             clock(sum(float(getattr(f, "duration_s", 0) or 0) for f in pull))]
    start = session_recap.start(pull[0])
    if start:
        facts.append(f"{start:%H:%M:%S}")
    deaths = _deaths_of(pull)
    facts.append(_plural(deaths, "death") if deaths else "no deaths")
    lines = [f"<b>{e(title)}, pull {number}</b>: {e(' · '.join(fact for fact in facts if fact))}"]
    if len(pull) > 1:
        lines.append(e(f"The log cut it into {len(pull)} fights; this shows the last"))
    lines.append(f"<span style='font-size:85%'>{FIGHT_TIP}</span>")
    return "<br>".join(lines)


def instance_tooltips(block, index_of, shown=None, names=None) -> dict[str, str]:
    """Hover text per link on the page: each pull, each player's name (the
    fight it opens), Copy this instance and the Misfortunes. *index_of* and
    *shown* as render_instance_html takes them; *names*: the Hide names
    mask."""
    names = names or NO_MASK
    e = html.escape
    block = list(block or [])
    if not block:
        return {}
    shown = shown if any(fight is shown for fight in block) else None
    block_runs = runs(block)
    places = _places(block_runs)
    tips = {}
    # The pulls the page links: a run's of two or more
    for run in block_runs:
        for number, pull in enumerate(run if len(run) > 1 else (), 1):
            place = index_of(pull[-1])
            if place is not None:
                tips[fight_href(place)] = _pull_tip(run, number, pull, e)
    for player in _players(block, pulls(block)):
        link = _link_place(player, index_of, shown)
        if link is None:
            continue
        place, unit_id, fight, row = link
        line = f"<b>{e(names.text(_who_text(player)))}</b> in {e(_fight_label(fight, places))}"
        if fight is shown:
            line += " (the fight on screen)"
        tip = PLAYER_TIP if row else DEATH_TIP
        tips[player_href(place, unit_id)] = (f"{line}<br>"
                                             f"<span style='font-size:85%'>{tip}</span>")
    tips[INSTANCE_COPY_HREF] = e(COPY_TIP)
    fight = _misfortunes_fight(block)
    if fight is not None:
        tips.update(misfortunes_tooltips(fight))
    return tips
