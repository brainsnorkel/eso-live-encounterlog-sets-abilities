"""
The fight's Deaths tab (issue #196): every death of a fight on one page,
where the fight pane has a chip on each player who died and a line on the
first death.

Design: The deaths of a fight, together. The page opens with a summary line
('12 deaths of 12 players · first at 1:03 · the pull ended 27s after it ·
12 dead at the end'), then one table of the deaths in time order: when, the
player's role, the player, what killed them with its icon, from whom, and
how long they stayed dead. Under it: what killed the group, each ability
with its source and counted, a fall or lava among them (#184), and the
share the pull's bosses dealt; each player's time dead in all, longest
first, with its share of the fight; and last the companions' deaths, as a
count, since the log keeps no recap of them. Each name links to that death
on the player window's Deaths tab (death_render.recap_href), with a hover
that says when and to what. A player the fight's table does not list (the
pane's Also died) is listed like any other, with no role. A player the log
gives no name, 'anon', has its row's class beside it, and in the time dead
line its role too, as the opener's line has (fight_render): several anons
would read as one.

How long one death kept the player down is known in two cases, and given
only in those. A player's only death in the fight lasted their time dead
(pull_outcome.TimeDead), unless the fight carries on the last pull, when
that time can hold a span carried from the fight before. A player's last
death, when they were dead at the end, lasted to the fight's end. The
engine keeps time dead by player, not by death (no revive is kept), so a
player's other deaths show a dash, which a note under the table explains,
and their total is in the time dead line. Who was dead at the end is kept
only with a pull (a fight with a named boss the players damaged): the page
of a fight without one says nothing of the end.

Nothing here changes the entry: the engine's thread updates an entry in
place while a page is drawn, so its lists are read with sorted() and
copies, never sorted in place.
"""

import html
from collections import Counter

from gui.death_render import _THEMES, ICON_PX, _icon_html, recap_href
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px
from pull_outcome import ANON, WIPE, at_clock, clock, dead_ms_of

# The page of a fight in which no one died, and of one in which only
# companions did
NO_DEATHS = "No one died in this fight."
NO_PLAYER_DEATHS = "No player died in this fight."
DASH = "–"
# Under the table when a death's time dead is a dash (see the module)
DEAD_FOR_NOTE = ("A dash: time dead is kept for each player in all, not death by death, "
                 "so for a player who died more than once it is in Time dead, below.")
KILLERS_LEAD = "Killers:"
TIME_DEAD_LEAD = "Time dead:"
COMPANIONS_LEAD = "Companions:"
SKULL = "☠"


def _deaths(entry):
    """[(recap, unit id, n, of)] for each death of the fight, in time
    order: n the death's number among its player's, as the player window's
    Deaths tab numbers them (death_render.deaths_by_unit, the order the
    engine logged them), of how many. Deaths at the same moment keep the
    engine's order."""
    rows, seen = [], Counter()
    for index, recap in enumerate(getattr(entry, "death_recaps", None) or []):
        unit_id = str(recap.get("unit_id", ""))
        seen[unit_id] += 1
        rows.append((int(recap.get("time_ms") or 0), index, recap, unit_id, seen[unit_id]))
    return [(recap, unit_id, n, seen[unit_id])
            for _time, _index, recap, unit_id, n in sorted(rows, key=lambda row: row[:2])]


def _dead_at_end(entry):
    """The unit ids dead when the fight ended, or None when the fight has no
    pull to say (see the module)."""
    pull = getattr(entry, "pull", None)
    if not pull:
        return None
    return frozenset(str(key) for key in pull.get("dead_at_end") or [])


def _dead_ms(entry, recap, unit_id, n, of, at_end):
    """How long the death kept the player down, in milliseconds; None when
    that is not known (see the module)."""
    carries = bool((getattr(entry, "pull", None) or {}).get("continues"))
    if of == 1 and not carries:
        return dead_ms_of(entry, unit_id)
    if n == of and at_end and unit_id in at_end:
        end_ms = float(getattr(entry, "duration_s", 0) or 0) * 1000
        return max(0, round(end_ms - int(recap.get("time_ms") or 0)))
    return None


def _anon_html(name: str, row, theme: dict, e, role: bool) -> str:
    """What follows an 'anon' to tell it from the others: its row's class,
    and its role with *role*; '' for any other name (see the module)."""
    if name != ANON or not row:
        return ""
    bits = ([str(row.get("role") or "?")] if role else []) + [str(row.get("class_abbr") or "?")]
    return f" <span style='color:{theme['muted']}'>({e(', '.join(bits))})</span>"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _summary(entry, deaths, at_end) -> str:
    """'12 deaths of 12 players · first at 1:03 · the pull ended 27s after
    it · 12 dead at the end': the last two only for a wipe and for a fight
    with a pull."""
    first = int(deaths[0][0].get("time_ms") or 0)
    players = len({unit_id for _r, unit_id, _n, _of in deaths})
    parts = [f"{_plural(len(deaths), 'death')} of {_plural(players, 'player')}",
             f"first at {at_clock(first)}"]
    pull = getattr(entry, "pull", None) or {}
    if pull.get("outcome") == WIPE:
        later = float(getattr(entry, "duration_s", 0) or 0) - first / 1000
        if later >= 1:
            parts.append(f"the pull ended {clock(later)} after it")
    if at_end is not None:
        parts.append(f"{len(at_end)} dead at the end" if at_end else "no one dead at the end")
    return " · ".join(parts)


def _table_html(entry, deaths, at_end, dark: bool, theme: dict, icons, names,
                base_pt: float, e) -> tuple[str, bool]:
    """The deaths in time order, and whether a time dead is a dash."""
    # fight_render imports death_render, which this module imports: its
    # role colours, the pane's, are taken here
    from gui.fight_render import _theme as pane_theme
    roles = pane_theme(dark)["roles"]
    muted = theme["muted"]
    rows = {str(p.get("unit_id", "")): p for p in getattr(entry, "players", None) or []}
    head = (f"style='color:{muted};border-bottom-style:solid;"
            f"border-bottom-width:1px;border-bottom-color:{theme['rule']}'")
    # Fixed column shares, as the recap's table has; the icon in a column of
    # its own, and not 100% wide, for the reasons given there
    parts = [(
        "<table cellpadding='3' cellspacing='0' width='99%'>"
        f"<tr><td width='7%' align='right' {head}>Time</td>"
        f"<td width='5%' {head}>Role</td>"
        f"<td width='22%' {head}>Player</td>"
        f"<td colspan='2' {head}>Killed by</td>"
        f"<td width='22%' {head}>From</td>"
        f"<td width='15%' align='right' {head}>Dead for</td></tr>")]
    dashed = False
    for recap, unit_id, n, of in deaths:
        p = rows.get(unit_id)
        role = str(p.get("role") or "") if p else ""
        role_html = (f"<span style='color:{roles.get(role, muted)}'>{e(role)}</span>"
                     if role else "")
        # The name, through the Hide names mask, a link to this death on the
        # player window's Deaths tab that looks like plain text; an anon's
        # class after it, the role having its own column
        name = str(recap.get("name") or "unknown")
        link = (f'<a href="{e(recap_href(unit_id, n), quote=True)}" '
                f'style="text-decoration:none;color:{theme["text"]}">'
                f'{names.html(name, theme["text"], base_pt)}</a>'
                f'{_anon_html(name, p, theme, e, role=False)}')
        icon = _icon_html(recap, icons)
        # A row without an icon is padded out to the height of one with
        pad = "" if icon else "padding-top:5px;padding-bottom:5px;"
        # The killer, an enemy, passes the mask; a player (a PvP log,
        # friendly fire) is hidden. A fall has none
        killer = str(recap.get("killer") or "")
        source = (names.html(killer, theme["text"], base_pt) if killer
                  else f"<span style='color:{muted}'>{DASH}</span>")
        ms = _dead_ms(entry, recap, unit_id, n, of, at_end)
        if ms is None:
            dead = f"<span style='color:{muted}'>{DASH}</span>"
            dashed = True
        else:
            dead = e(clock(ms / 1000))
            if n == of and at_end and unit_id in at_end:
                dead += f" <span style='color:{muted}'>to the end</span>"
        cells = (
            (" align='right'", f"color:{muted};", e(at_clock(recap.get("time_ms")))),
            ("", "", role_html),
            ("", "", link),
            (f" width='{scaled_px(ICON_PX)}'", "", icon),
            ("", "", e(str(recap.get("ability") or "unknown"))),
            ("", "", source),
            (" align='right'", "", dead),
        )
        parts.append("<tr>" + "".join(
            f"<td{attrs} valign='middle' style='{pad}{style}'>{content}</td>"
            for attrs, style, content in cells) + "</tr>")
    parts.append("</table>")
    return "".join(parts), dashed


def _killers_html(entry, deaths, theme: dict, names, base_pt: float, e) -> str:
    """'Killers: Grievous Pulse from Lord Falgravn ×10 · Frenzied Cleave
    from Lieutenant Njordal ×2; 83% by Lord Falgravn': each ability with its
    source, most first, then the deaths the pull's bosses dealt."""
    counts = Counter((str(recap.get("ability") or "unknown"), str(recap.get("killer") or ""))
                     for recap, _unit_id, _n, _of in deaths)
    muted = theme["muted"]
    items = []
    for (ability, killer), count in counts.most_common():
        text = f"<b>{e(ability)}</b>"
        if killer:
            text += (f" <span style='color:{muted}'>from</span> "
                     f"{names.html(killer, theme['text'], base_pt)}")
        items.append(text + (f" ×{count}" if count > 1 else ""))
    line = f"<span style='color:{muted}'>{KILLERS_LEAD}</span> " + " · ".join(items)
    bosses = [str(b) for b in (getattr(entry, "pull", None) or {}).get("bosses") or []]
    by_boss = sum(count for (_ability, killer), count in counts.items() if killer in bosses)
    # Said only when the bosses killed someone, as the run's summary does
    if by_boss:
        who = " and ".join(bosses) if len(bosses) <= 2 else "the bosses"
        line += (f"<span style='color:{muted}'>; {round(100 * by_boss / len(deaths))}% "
                 f"by {e(who)}</span>")
    return f"<p style='margin:10px 0 2px 0'>{line}</p>"


def _time_dead_html(entry, deaths, theme: dict, names, base_pt: float, e) -> str:
    """'Time dead: @x 1:32 (30%) · @y 27s (9%)': everyone who died, longest
    first, with the share of the fight."""
    duration = float(getattr(entry, "duration_s", 0) or 0)
    muted = theme["muted"]
    rows = {str(p.get("unit_id", "")): p for p in getattr(entry, "players", None) or []}
    who = {}  # unit id -> name, in the order the deaths come
    for recap, unit_id, _n, _of in deaths:
        who.setdefault(unit_id, str(recap.get("name") or "unknown"))
    items = []
    for unit_id, name in sorted(who.items(), key=lambda item: -dead_ms_of(entry, item[0])):
        ms = dead_ms_of(entry, unit_id)
        share = (f" <span style='color:{muted}'>({min(100, round(100 * ms / 1000 / duration))}%)"
                 f"</span>" if duration > 0 else "")
        who_html = (names.html(name, theme["text"], base_pt)
                    + _anon_html(name, rows.get(unit_id), theme, e, role=True))
        items.append(f"{who_html} {e(clock(ms / 1000))}{share}")
    return (f"<p style='margin:6px 0 2px 0'><span style='color:{muted}'>{TIME_DEAD_LEAD}</span> "
            + " · ".join(items) + "</p>")


def _companions_html(entry, theme: dict, names, base_pt: float, e) -> str:
    """'Companions: @x's Companion ☠ ×2': each companion that died, with its
    deaths, which the log counts but keeps no recap of; '' for none."""
    items = []
    for p in getattr(entry, "players", None) or []:
        count = int(p.get("deaths") or 0) if p.get("companion") else 0
        if count:
            name = p.get("name", "")
            name = ", ".join(str(part) for part in name) if isinstance(name, (list, tuple)) else name
            items.append(f"{names.html(str(name or ''), theme['text'], base_pt)} "
                         f"{SKULL}{f' ×{count}' if count > 1 else ''}")
    if not items:
        return ""
    return (f"<p style='margin:6px 0 2px 0'><span style='color:{theme['muted']}'>"
            f"{COMPANIONS_LEAD}</span> " + " · ".join(items) + "</p>")


def render_fight_deaths_html(entry, dark: bool = False, icons=None, base_pt: float = 9.0,
                             names=None, text_color: str | None = None) -> str:
    """Every death of the fight *entry* as HTML for the Deaths tab, with no
    header of its own (the tab is the fight's).

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    leaves the abilities as names. base_pt: the page's font size. names:
    the Hide names mask (gui.name_mask). text_color: the page's own text
    colour, which a hidden name is drawn in. The hover text for the names is
    fight_deaths_tooltips().
    """
    theme = dict(_THEMES[bool(dark)])
    if text_color:
        theme["text"] = text_color
    names = names or NO_MASK
    e = html.escape
    muted = theme["muted"]
    deaths = _deaths(entry)
    companions = _companions_html(entry, theme, names, base_pt, e)
    if not deaths:
        line = NO_PLAYER_DEATHS if companions else NO_DEATHS
        return f"<p style='margin:0;color:{muted}'>{line}</p>{companions}"
    at_end = _dead_at_end(entry)
    table, dashed = _table_html(entry, deaths, at_end, dark, theme, icons, names, base_pt, e)
    parts = [f"<p style='margin:0 0 6px 0'>{e(_summary(entry, deaths, at_end))}</p>", table]
    if dashed:
        parts.append(f"<p style='margin:2px 0 0 0;color:{muted};"
                     f"font-size:{base_pt * 0.85:.2f}pt'>{DEAD_FOR_NOTE}</p>")
    parts.append(_killers_html(entry, deaths, theme, names, base_pt, e))
    parts.append(_time_dead_html(entry, deaths, theme, names, base_pt, e))
    parts.append(companions)
    return "".join(parts)


def fight_deaths_tooltips(entry, names=None) -> dict[str, str]:
    """Hover text per name on the page: the death, when and to what, and
    where the link goes; *names* is the Hide names mask."""
    names = names or NO_MASK
    e = html.escape
    tips = {}
    rows = {str(p.get("unit_id", "")): p for p in getattr(entry, "players", None) or []}
    for recap, unit_id, n, of in _deaths(entry):
        name = str(recap.get("name") or "unknown")
        row = rows.get(unit_id)
        if name == ANON and row:
            name += f" ({row.get('role') or '?'}, {row.get('class_abbr') or '?'})"
        name = e(names.text(name))
        lines = [f"<b>{name}</b>: death {n} of {of}, at {at_clock(recap.get('time_ms'))}"]
        killer = names.text(str(recap.get("killer") or ""))
        what = e(str(recap.get("ability") or "unknown"))
        lines.append(f"Killed by {what}" + (f" from {e(killer)}" if killer else ""))
        lines.append("<span style='font-size:85%'>Click for this death's recap "
                     "on the player's Deaths tab</span>")
        tips[recap_href(unit_id, n)] = "<br>".join(lines)
    return tips
