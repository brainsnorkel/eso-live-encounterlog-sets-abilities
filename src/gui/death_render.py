"""
Death recap rendering: the button a player's row gets in the fight view when
they died, its hover summary, and the recap window's HTML (the last seconds
of damage and healing before each of that player's deaths).

The data is FightHistoryEntry.death_recaps, built by the engine's
death_recap module. Colors are theme-aware like the rest of the fight pane.
"""

import html
from typing import Dict, List, Optional

from death_recap import RECAP_WINDOW_MS

DEATHS_HREF = "esolog:deaths/"  # + the player's unit id
SKULL = "☠"
ICON_PX = 20  # ability icon edge in the recap table

RESULT_LABELS = {
    "DAMAGE": "Hit",
    "CRITICAL_DAMAGE": "Critical hit",
    "DOT_TICK": "DoT",
    "DOT_TICK_CRITICAL": "DoT crit",
    "BLOCKED_DAMAGE": "Blocked",
    "FALL_DAMAGE": "Fall",
    "DODGED": "Dodged",
    "MISS": "Missed",
    "HEAL": "Heal",
    "CRITICAL_HEAL": "Critical heal",
    "HOT_TICK": "HoT",
    "HOT_TICK_CRITICAL": "HoT crit",
    "DAMAGE_SHIELDED": "Absorbed",
    "HEAL_ABSORBED": "Heal absorbed",
}

_THEMES = {
    # dark background: lighter accents
    True: {
        "muted": "#9aa0a6",
        "damage": "#ef9a9a",
        "heal": "#81c784",
        "shield": "#4fc3f7",
        "health": ("#81c784", "#ffd54f", "#ffb74d", "#e57373"),
        "chip_fg": "#1b1b1b",
        "chip_bg": "#e57373",
        "rule": "#45494f",
        "final_bg": "#3a2a2a",
    },
    # light background: darker, saturated accents
    False: {
        "muted": "#5f6368",
        "damage": "#c62828",
        "heal": "#2e7d32",
        "shield": "#1565c0",
        "health": ("#2e7d32", "#8a6d00", "#b25a00", "#c62828"),
        "chip_fg": "#ffffff",
        "chip_bg": "#c62828",
        "rule": "#d6d9dc",
        "final_bg": "#fdecea",
    },
}


def death_href(unit_id) -> str:
    return f"{DEATHS_HREF}{unit_id}"


def unit_from_href(href: str) -> Optional[str]:
    """The player's unit id when *href* is a death-recap button, else None."""
    if href and href.startswith(DEATHS_HREF):
        return href[len(DEATHS_HREF):]
    return None


def deaths_by_unit(entry) -> Dict[str, List[dict]]:
    """Unit id -> that player's deaths in the fight, in order."""
    grouped: Dict[str, List[dict]] = {}
    for recap in getattr(entry, "death_recaps", None) or []:
        grouped.setdefault(str(recap.get("unit_id", "")), []).append(recap)
    return grouped


def _clock(ms) -> str:
    seconds = max(0, int(ms)) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def _killed_by(recap: dict) -> str:
    """'Slap (Sharpfang)', or just the ability when the log names no killer."""
    ability = str(recap.get("ability", ""))
    killer = str(recap.get("killer") or "")
    return f"{ability} ({killer})" if killer else ability


def death_chip_html(unit_id, deaths: List[dict], dark: bool,
                    label: str = "") -> str:
    """The death-recap button for a player who died: a filled chip with the
    skull, and ×N when they died more than once, that the fight view routes
    to the recap window. The hover text says what it is; a label is only
    added when a caller asks for one."""
    theme = _THEMES[bool(dark)]
    count = f" ×{len(deaths)}" if len(deaths) > 1 else ""
    text = html.escape(f"{SKULL}{' ' + label if label else ''}{count}")
    return (f'<a href="{html.escape(death_href(unit_id), quote=True)}" '
            f'style="text-decoration:none;font-weight:bold;'
            f'color:{theme["chip_fg"]};background-color:{theme["chip_bg"]}">'
            f'&nbsp;{text}&nbsp;</a>')


def death_tooltips(entry) -> Dict[str, str]:
    """Hover text per death-recap button: when and to what the player died."""
    e = html.escape
    tips = {}
    for unit_id, deaths in deaths_by_unit(entry).items():
        name = e(str(deaths[0].get("name", "")))
        noun = "death" if len(deaths) == 1 else "deaths"
        lines = [f"<b>{name}: {len(deaths)} {noun}</b>"]
        lines.extend(f"{_clock(d.get('time_ms', 0))} &nbsp;{e(_killed_by(d))}"
                     for d in deaths)
        lines.append("<span style='font-size:85%'>Click for the death recap</span>")
        tips[death_href(unit_id)] = "<br>".join(lines)
    return tips


def _offset_text(offset_ms) -> str:
    seconds = round(offset_ms / 1000, 1)
    if seconds >= 0:
        return "0.0s"
    return f"{seconds:.1f}s"


def _health_html(row: dict, theme: dict) -> str:
    maximum = row.get("max_health") or 0
    current = row.get("health") or 0
    if not maximum:
        return ""
    fraction = current / maximum
    good, hurt, low, critical = theme["health"]
    color = (good if fraction > 0.75 else hurt if fraction > 0.5
             else low if fraction > 0.25 else critical)
    return (f"<span style='color:{color}'>{current:,}</span> "
            f"<span style='color:{theme['muted']}'>{round(fraction * 100)}%</span>")


def _amount_html(row: dict, theme: dict) -> str:
    kind = row.get("kind")
    amount = row.get("amount") or 0
    if kind == "damage":
        return f"<span style='color:{theme['damage']}'>{amount:,}</span>"
    if kind == "heal":
        return f"<span style='color:{theme['heal']}'>+{amount:,}</span>"
    if kind == "avoided":
        return f"<span style='color:{theme['muted']}'>–</span>"
    # absorbed by a shield with no hit behind it / a heal eaten by a debuff
    return f"<span style='color:{theme['shield']}'>{amount:,}</span>"


def _result_html(row: dict, theme: dict, e) -> str:
    """'Blocked · 5,603 absorbed by Bone Shield · 1,224 overkill'."""
    kind = row.get("kind")
    label = RESULT_LABELS.get(str(row.get("result")), str(row.get("result", "")))
    color = {"heal": theme["heal"], "avoided": theme["muted"],
             "absorbed": theme["shield"], "heal_absorbed": theme["shield"]}.get(kind)
    parts = [f"<span style='color:{color}'>{e(label)}</span>" if color else e(label)]
    absorbed = row.get("absorbed") or 0
    if absorbed:
        shields = ", ".join(str(s) for s in row.get("shields") or [])
        by = f" by {e(shields)}" if shields else ""
        parts.append(f"<span style='color:{theme['shield']}'>{absorbed:,} absorbed{by}</span>")
    if kind == "damage" and row.get("overflow"):
        parts.append(f"{row['overflow']:,} overkill")
    return " · ".join(parts)


def _icon_html(row: dict, icons) -> str:
    """The ability's icon, or '' when it is not bundled."""
    stem = str(row.get("icon") or "")
    if icons is None or not icons.has(stem):
        return ""
    return (f'<img src="icon:{stem}" width="{ICON_PX}" height="{ICON_PX}" '
            f'style="vertical-align:middle">')


def _death_html(recap: dict, index: int, total: int, theme: dict, icons, e) -> str:
    muted = theme["muted"]
    max_health = recap.get("max_health") or 0
    facts = [f"{_clock(recap.get('time_ms', 0))} into the fight"]
    if max_health:
        facts.append(f"{max_health:,} max health")
    killer = str(recap.get("killer") or "")
    icon = _icon_html(recap, icons)
    ability = e(str(recap.get("ability", "")))
    killed_by = f"{icon}&nbsp;{ability}" if icon else ability
    parts = [
        f"<p style='margin:14px 0 2px 0'><b>Death {index} of {total}</b>"
        f" <span style='color:{muted}'>· {' · '.join(facts)}</span></p>",
        f"<p style='margin:0 0 4px 0'>Killed by <b>{killed_by}</b>"
        + (f" <span style='color:{muted}'>from</span> {e(killer)}" if killer else "")
        + "</p>",
    ]
    rows = recap.get("events") or []
    if not rows:
        parts.append(f"<p style='margin:0;color:{muted}'>No damage or healing was logged "
                     f"in the {RECAP_WINDOW_MS // 1000} seconds before this death.</p>")
        return "".join(parts)

    head = (f"style='color:{muted};border-bottom-style:solid;"
            f"border-bottom-width:1px;border-bottom-color:{theme['rule']}'")
    # Fixed column shares, so every death's table lines up with the others;
    # Result takes what is left. The icon has a column of its own: inline, it
    # would drag its row's text off the line the other cells sit on. Not
    # 100% wide: Qt rounds percentage columns up to a pixel past the pane,
    # which is enough to summon a horizontal scrollbar
    parts.append(
        "<table cellpadding='3' cellspacing='0' width='99%'>"
        f"<tr><td width='7%' align='right' {head}>Time</td>"
        f"<td width='14%' align='right' {head}>Health</td>"
        f"<td colspan='2' {head}>Ability</td><td width='17%' {head}>Source</td>"
        f"<td width='8%' align='right' {head}>Amount</td>"
        f"<td {head}>Result</td></tr>")
    for row in rows:
        # The blow (or blows) that left the player on zero health stands out
        final = row.get("kind") == "damage" and not row.get("health")
        tr = f"<tr bgcolor='{theme['final_bg']}'>" if final else "<tr>"
        bold = "font-weight:bold;" if final else ""
        icon = _icon_html(row, icons)
        # A row without an icon is padded out to the height of one with
        pad = "" if icon else "padding-top:5px;padding-bottom:5px;"
        source = str(row.get("source") or "")
        cells = (
            (" align='right'", f"color:{muted};", _offset_text(row.get("offset_ms", 0))),
            (" align='right'", "", _health_html(row, theme)),
            (f" width='{ICON_PX}'", "", icon),
            (" width='20%'", bold, e(str(row.get("ability", "")))),
            ("", bold, e(source) if source else "–"),
            (" align='right'", bold, _amount_html(row, theme)),
            ("", "", _result_html(row, theme, e)),
        )
        parts.append(tr + "".join(
            f"<td{attrs} valign='middle' style='{pad}{style}'>{content}</td>"
            for attrs, style, content in cells) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def render_death_recap_html(entry, unit_id, dark: bool = False, icons=None,
                            base_pt: float = 9.0) -> str:
    """One player's deaths in a fight as HTML for the recap window.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    leaves the abilities as names. base_pt: the pane's font size, which the
    title is scaled from (Qt rich text ignores percentage sizes).
    """
    theme = _THEMES[bool(dark)]
    e = html.escape
    deaths = deaths_by_unit(entry).get(str(unit_id), [])
    muted = theme["muted"]
    where = " · ".join(e(str(part)) for part in (
        getattr(entry, "boss_name", ""), getattr(entry, "zone_name", ""),
        getattr(entry, "timestamp", "")) if part)
    name = e(str(deaths[0].get("name", ""))) if deaths else ""
    parts = [
        f"<p style='margin:0'>"
        f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{name}</span>"
        f"&nbsp;&nbsp; <span style='color:{muted}'>{where}</span></p>",
    ]
    if not deaths:
        parts.append(f"<p style='color:{muted}'>No deaths recorded for this player.</p>")
        return "".join(parts)
    parts.append(f"<p style='margin:2px 0;color:{muted}'>Damage and healing in the "
                 f"{RECAP_WINDOW_MS // 1000} seconds before each death, oldest first. "
                 f"Health is the value after each event.</p>")
    for index, recap in enumerate(deaths, 1):
        parts.append(_death_html(recap, index, len(deaths), theme, icons, e))
    return "".join(parts)
