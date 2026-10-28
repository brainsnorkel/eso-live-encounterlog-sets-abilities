"""
The damage window's HTML: one player's damage in a fight, broken down by
ability and by target the way Combat Metrics' fight report breaks it down.

The data is the fight entry's player dict, key 'damage', as
damage_stats.PlayerDamage.snapshot built it: totals, the spans the dps
figures divide by, one row per ability (and per pet ability), the same rows
for the boss units alone, and the targets hit. The figures follow
damage_stats: a row's dps is its damage over the player's dps time (over
their boss dps time in the boss view), crit % is critical hits over hits,
the average is damage over hits, and a target's dps divides by the span of
the player's hits on that target. Colors are theme-aware like the rest of
the fight pane.
"""

import html
from typing import List

from damage_stats import dps as dps_over, dps_time_s
from gui.build_render import player_for
from gui.fight_render import ROLE_NAMES, _fmt_dps, _fmt_duration, _join, _subclass_text, _theme
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px

ICON_PX = 20  # ability icon edge in the table
PET_MARK = "(pet)"
BOSS_MARK = "boss"
DASH = "–"
NO_RECORD = "No damage record was kept for this player in this fight."
NO_DAMAGE = "This player dealt no damage in this fight."
NO_BOSS_DAMAGE = "This player dealt no damage to the bosses of this fight."
DPS_TIME_NOTE = ("Dps time is first hit to last, floored at one second, as in Combat "
                 "Metrics; a row's dps divides by the dps time above, a target's by the "
                 "span of the hits on it. Shield absorbs count as damage, not as hits.")
COLUMNS = (("Ability", "left"), ("Damage", "right"), ("%", "right"), ("Hits", "right"),
           ("Crit %", "right"), ("Max", "right"), ("Avg", "right"), ("DPS", "right"))
TARGET_COLUMNS = (("Target", "left"), ("Damage", "right"), ("%", "right"), ("Hits", "right"),
                  ("Dps time", "right"), ("DPS", "right"))
_RULES = {True: "#45494f", False: "#d6d9dc"}  # under the tables' headers


def damage_title(entry, unit_id, names=None) -> str:
    """Window title: 'Damage – @name'; *names* is the Hide names mask."""
    player = player_for(entry, unit_id)
    name = (names or NO_MASK).text(_join(player.get("name", ""))) if player else ""
    return f"Damage – {name}" if name else "Damage"


def fmt_dps_time(seconds) -> str:
    """'1:32.4', or '8.0s' under a minute; never under the one-second floor."""
    seconds = dps_time_s(float(seconds or 0) * 1000)
    if seconds >= 60:
        return f"{int(seconds // 60)}:{seconds % 60:04.1f}"
    return f"{seconds:.1f}s"


def _n(value) -> str:
    return f"{int(value or 0):,}"


def _pct(part, whole) -> str:
    return f"{100.0 * part / whole:.1f}%" if whole else DASH


def _icon_html(stem, icons) -> str:
    stem = str(stem or "")
    if icons is None or not stem or not icons.has(stem):
        return ""
    return (f'<img src="icon:{stem}" width="{scaled_px(ICON_PX)}" height="{scaled_px(ICON_PX)}" '
            f'alt="" style="vertical-align:middle">')


def _header_html(entry, p, theme, base_pt: float, e, names, text_color: str) -> str:
    muted = theme["muted"]
    # The name, through the Hide names mask (gui.name_mask)
    name = names.html(_join(p.get("name", "")), text_color, base_pt * 1.3, bold=True)
    facts = [ROLE_NAMES.get(p.get("role"), ""), str(p.get("class_name") or ""),
             _subclass_text(p)]
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if getattr(entry, "is_vet", False) else "")
    zone = str(getattr(entry, "zone_name", "") or "")
    fight = [e(str(getattr(entry, "boss_name", "") or "")),
             f"{e(zone)}{vet}" if zone else "",
             e(str(getattr(entry, "timestamp", "") or ""))]
    # Not an <h3>: Qt would scale the nested facts by the heading's size
    return (f"<p style='margin:0'>"
            f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{name}</span>"
            f"&nbsp;&nbsp; <span style='color:{muted}'>"
            f"{' · '.join(e(fact) for fact in facts if fact)}</span></p>"
            f"<p style='margin:2px 0;color:{muted}'>"
            f"{' · '.join(part for part in fight if part)}</p>")


def _offset_text(seconds) -> str:
    seconds = float(seconds or 0)
    if seconds >= 60:
        return _fmt_duration(seconds)
    return f"{seconds:.1f} s"


def _summary_html(entry, p, damage: dict, boss_only: bool, theme, e) -> str:
    """'3.2M damage to the bosses in 1:30.2 dps time · 35.5k dps · 40.1% of
    the group's boss damage', then where the hits sat in the fight and the
    figure over the whole fight."""
    muted = theme["muted"]
    total = damage.get("boss" if boss_only else "total") or 0
    window = damage.get("boss_window" if boss_only else "window") or {}
    span_ms = window.get("span_ms") or 0
    what = "damage to the bosses" if boss_only else "damage"
    share = float(p.get("boss_pct" if boss_only else "dmg_pct") or 0)
    of = "of the group's boss damage" if boss_only else "of the group's damage"
    line = (f"<b>{_n(total)}</b> {what} in <b>{fmt_dps_time(span_ms / 1000.0)}</b> dps time"
            f" · <b>{_fmt_dps(dps_over(total, span_ms))}</b> dps · {share:.1f}% {of}")
    fight_s = float(getattr(entry, "duration_s", 0) or 0)
    details = []
    if window.get("first_s") is not None:
        details.append(f"first hit {_offset_text(window['first_s'])} after the pull, "
                       f"last hit {_offset_text(window['last_s'])} into the "
                       f"{_fmt_duration(fight_s)} fight")
    if fight_s > 0 and total > 0:
        details.append(f"over the whole fight {_fmt_dps(total / fight_s)} dps")
    detail = (f"<br><span style='color:{muted}'>{' · '.join(details)}</span>"
              if details else "")
    return f"<p style='margin:8px 0 6px 0'>{line}{detail}</p>"


def _table_open(columns, theme) -> str:
    head = (f"style='color:{theme['muted']};border-bottom-style:solid;"
            f"border-bottom-width:1px;border-bottom-color:{theme['rule']}'")
    cells = "".join(f"<td align='{align}' {head}>{title}</td>" for title, align in columns)
    # Not 100% wide: Qt rounds percentage columns up to a pixel past the
    # pane, which is enough to summon a horizontal scrollbar
    return (f"<table cellpadding='3' cellspacing='0' width='99%'>"
            f"<tr><td width='{scaled_px(ICON_PX)}' {head}></td>{cells}</tr>")


def _ability_table_html(rows: List[dict], total: int, span_ms: int, theme, icons, e) -> str:
    muted = theme["muted"]
    parts = [_table_open(COLUMNS, theme)]
    for row in rows:
        damage = int(row.get("damage") or 0)
        if damage <= 0:
            continue
        hits = int(row.get("hits") or 0)
        crits = int(row.get("crits") or 0)
        icon = _icon_html(row.get("icon"), icons)
        pad = "" if icon else "padding-top:5px;padding-bottom:5px;"
        name = e(str(row.get("name", "")))
        if row.get("pet"):
            name += f" <span style='color:{muted}'>{PET_MARK}</span>"
        cells = (
            ("left", name),
            ("right", _n(damage)),
            ("right", _pct(damage, total)),
            ("right", _n(hits) if hits else DASH),
            ("right", f"{100.0 * crits / hits:.0f}%" if hits else DASH),
            ("right", _n(row.get("max")) if hits else DASH),
            ("right", _n(round(damage / hits)) if hits else DASH),
            ("right", _fmt_dps(dps_over(damage, span_ms))),
        )
        parts.append(
            f"<tr><td width='{scaled_px(ICON_PX)}' valign='middle' style='{pad}'>{icon}</td>"
            + "".join(f"<td align='{align}' valign='middle' style='{pad}'>{content}</td>"
                      for align, content in cells) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def _target_table_html(targets: List[dict], total: int, boss_only: bool, theme, e) -> str:
    muted = theme["muted"]
    parts = [_table_open(TARGET_COLUMNS, theme)]
    for target in targets:
        damage = int(target.get("damage") or 0)
        if damage <= 0 or (boss_only and not target.get("boss")):
            continue
        span_ms = int(target.get("span_ms") or 0)
        name = e(str(target.get("name", "")))
        if target.get("boss"):
            name = f"<b>{name}</b> <span style='color:{muted}'>{BOSS_MARK}</span>"
        cells = (
            ("left", name),
            ("right", _n(damage)),
            ("right", _pct(damage, total)),
            ("right", _n(target.get("hits")) if target.get("hits") else DASH),
            ("right", fmt_dps_time(span_ms / 1000.0)),
            ("right", _fmt_dps(dps_over(damage, span_ms))),
        )
        parts.append(
            "<tr><td></td>" + "".join(
                f"<td align='{align}' valign='middle' "
                f"style='padding-top:4px;padding-bottom:4px'>{content}</td>"
                for align, content in cells) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def render_damage_html(entry, unit_id, boss_only: bool = False, dark: bool = False,
                       icons=None, base_pt: float = 9.0, names=None,
                       text_color: str | None = None) -> str:
    """One player's damage in a fight as HTML for the damage window.

    boss_only: the rows and totals for the units the game flags as bosses
    alone. icons: object with has(stem) -> bool (the fight view's
    IconCache); None keeps the rows as text. base_pt: the window's font size.
    names: the Hide names mask (gui.name_mask) for the header's name;
    text_color: the pane's own text colour, which a hidden name is drawn in.
    """
    theme = dict(_theme(dark))
    theme["rule"] = _RULES[dark]
    muted = theme["muted"]
    e = html.escape
    p = player_for(entry, unit_id)
    if p is None:
        return f"<p style='color:{muted}'>{NO_RECORD}</p>"
    parts = [_header_html(entry, p, theme, base_pt, e, names or NO_MASK,
                          text_color or theme["text"])]
    damage = p.get("damage")
    if not isinstance(damage, dict) or not damage:
        # An entry from before the record was kept
        parts.append(f"<p style='color:{muted}'>{NO_RECORD}</p>")
        return "".join(parts)
    total = int(damage.get("boss" if boss_only else "total") or 0)
    if total <= 0:
        parts.append(f"<p style='color:{muted}'>{NO_BOSS_DAMAGE if boss_only else NO_DAMAGE}</p>")
        return "".join(parts)
    window = damage.get("boss_window" if boss_only else "window") or {}
    span_ms = int(window.get("span_ms") or 0)
    parts.append(_summary_html(entry, p, damage, boss_only, theme, e))
    rows = damage.get("boss_abilities" if boss_only else "abilities") or []
    parts.append(_ability_table_html(rows, total, span_ms, theme, icons, e))
    targets = damage.get("targets") or []
    if targets:
        parts.append("<p style='margin:12px 0 2px 0'><b>Targets</b></p>")
        parts.append(_target_table_html(targets, total, boss_only, theme, e))
    parts.append(f"<p style='margin:10px 0 0 0;color:{muted};font-size:{base_pt * 0.85:.2f}pt'>"
                 f"{DPS_TIME_NOTE}</p>")
    return "".join(parts)
