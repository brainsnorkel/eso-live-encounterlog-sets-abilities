"""
Rendering of FightHistoryEntry data for the GUI: HTML for the detail pane,
plain text for clipboard copy, and one-line summaries for the history list.

Colors are theme-aware: the window passes dark=True/False from its palette,
and each theme gets colors with adequate contrast on its background.
"""

import html

ROLE_NAMES = {"T": "Tank", "H": "Healer", "D": "DPS"}

_THEMES = {
    # dark background: lighter accents
    True: {
        "muted": "#9aa0a6",
        "detail": "#b8bcc0",
        "vet": "#ffb74d",
        "roles": {"T": "#4fc3f7", "H": "#81c784", "D": "#e57373"},
    },
    # light background: darker, saturated accents
    False: {
        "muted": "#5f6368",
        "detail": "#3c4043",
        "vet": "#b25a00",
        "roles": {"T": "#1565c0", "H": "#2e7d32", "D": "#c62828"},
    },
}


def _theme(dark: bool) -> dict:
    return _THEMES[bool(dark)]


def muted_color(dark: bool) -> str:
    """Secondary-text color with adequate contrast for the theme."""
    return _theme(dark)["muted"]


def _join(value, sep=", ") -> str:
    """Lists/tuples joined for display; other values stringified."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return sep.join(str(v) for v in value)
    return str(value)


def _fmt_dps(dps: float) -> str:
    if dps >= 1_000_000:
        return f"{dps / 1_000_000:.2f}M"
    if dps >= 1_000:
        return f"{dps / 1_000:.1f}k"
    return f"{dps:.0f}"


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    if total >= 60:
        return f"{total // 60}:{total % 60:02d}"
    return f"{total}s"


def _fmt_resource(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{v / 1000:.1f}k" if v else "-"


def summary_line(entry) -> str:
    """History-list line: boss · duration · gdps · zone · timestamp."""
    vet = " vet" if entry.is_vet else ""
    zone = entry.zone_name or "Unknown"
    parts = []
    if entry.boss_name:
        parts.append(entry.boss_name)
    parts.append(_fmt_duration(entry.duration_s))
    parts.append(f"{_fmt_dps(entry.group_dps)} gdps")
    parts.append(f"{zone}{vet}")
    parts.append(str(entry.timestamp))
    return " · ".join(parts)


def render_html(entry, detailed: bool, dark: bool = False) -> str:
    """Render one fight as HTML for a QTextBrowser."""
    theme = _theme(dark)
    e = html.escape
    zone = e(entry.zone_name or "Unknown")
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if entry.is_vet else "")
    # Order: boss name (title), then time · zone on the line below
    muted = theme["muted"]
    detail_color = theme["detail"]
    if entry.boss_name:
        title = e(entry.boss_name)
        subline_zone = f" · {zone}{vet}"
    else:
        title = f"{zone}{vet}"
        subline_zone = ""
    parts = [
        f"<h3 style='margin:0'>{title}</h3>",
        f"<p style='margin:2px 0;color:{muted}'>"
        f"{_fmt_duration(entry.duration_s)}"
        f" · {_fmt_dps(entry.group_dps)} gdps"
        f"{subline_zone}"
        f" · {e(str(entry.timestamp))}"
        f" · Deaths {entry.deaths}</p>",
    ]
    # Text uptime line only when there is no timeline strip to show it
    # (the graph carries the uptimes when the experiment is on)
    has_timeline = bool(getattr(entry, "buff_timeline", None)
                        and entry.buff_timeline.get("effects"))
    if entry.buff_summary and not has_timeline:
        parts.append(f"<p style='margin:2px 0'>{e(_join(entry.buff_summary))}</p>")

    parts.append("<table cellpadding='3' cellspacing='0' width='100%'>")
    first_dealer = str(entry.first_damage_dealer or "")
    starred = False
    for p in entry.players:
        role = p.get("role") or "D"
        color = theme["roles"].get(role, muted)
        name = e(_join(p.get("name", "")))
        if first_dealer and str(p.get("unit_id", "")) == first_dealer:
            name = f"{name} <b>*</b>"
            starred = True
        class_abbr = e(_join(p.get("class_abbr", "")))
        dps = _fmt_dps(float(p.get("dps") or 0))
        pct = float(p.get("dmg_pct") or 0)
        row = (f"<tr><td style='color:{color};font-weight:bold'>{role}</td>"
               f"<td><b>{name}</b> <span style='color:{muted}'>{class_abbr}</span></td>"
               f"<td align='right'>{dps}</td>"
               f"<td align='right'>{pct:.1f}%</td>"
               f"<td align='right' style='color:{muted}'>"
               f"H {_fmt_resource(p.get('h'))} · M {_fmt_resource(p.get('m'))}"
               f" · S {_fmt_resource(p.get('s'))}</td></tr>")
        parts.append(row)
        if detailed:
            skill_lines = e(_join(p.get("skill_lines"), sep=" / "))
            front = e(_join(p.get("front_bar")))
            back = e(_join(p.get("back_bar")))
            # Full equipment: every set with piece counts, misc pieces
            # (monster sets, arena weapons, mythics) included — not just
            # the 5pc/mythic summary used elsewhere
            sets = _sets_text(p.get("all_sets") or p.get("sets"))
            detail = (f"<tr><td></td><td colspan='4' "
                      f"style='color:{detail_color};font-size:90%'>"
                      f"{skill_lines}"
                      f"{'<br>' + front if front else ''}"
                      f"{'<br>' + back if back else ''}"
                      f"{'<br><i>' + e(sets) + '</i>' if sets else ''}"
                      f"</td></tr>")
            parts.append(detail)
    parts.append("</table>")
    if starred:
        parts.append(f"<p style='margin:2px 0;color:{muted};font-size:85%'>"
                     f"* dealt the first damage of the fight</p>")
    return "".join(parts)


def _sets_text(sets_value) -> str:
    """Human-readable gear sets from the entry's sets field.

    The engine stores either a preformatted string or a list of
    (piece_count, set_name, is_perfected) tuples.
    """
    if not sets_value:
        return ""
    if isinstance(sets_value, str):
        return sets_value
    try:
        chunks = []
        for item in sets_value:
            count, name = item[0], item[1]
            perfected = "p" if len(item) > 2 and item[2] else ""
            chunks.append(f"{count}{perfected}pc {name}")
        return ", ".join(chunks)
    except (TypeError, IndexError):
        return str(sets_value)


def render_plain_text(entry) -> str:
    """Plain-text rendering for clipboard copy."""
    lines = [summary_line(entry)]
    if entry.buff_summary:
        lines.append(_join(entry.buff_summary))
    first_dealer = str(entry.first_damage_dealer or "")
    for p in entry.players:
        role = p.get("role") or "D"
        dps = _fmt_dps(float(p.get("dps") or 0))
        pct = float(p.get("dmg_pct") or 0)
        star = (" *" if first_dealer
                and str(p.get("unit_id", "")) == first_dealer else "")
        lines.append(f"[{role}] {_join(p.get('name', ''))}{star} "
                     f"{_join(p.get('class_abbr', ''))} — {dps} ({pct:.1f}%)")
        skill_lines = _join(p.get("skill_lines"), sep=" / ")
        if skill_lines:
            lines.append(f"      {skill_lines}")
        for bar in (p.get("front_bar"), p.get("back_bar")):
            bar_text = _join(bar)
            if bar_text:
                lines.append(f"      {bar_text}")
        sets = _sets_text(p.get("all_sets") or p.get("sets"))
        if sets:
            lines.append(f"      {sets}")
    return "\n".join(lines)
