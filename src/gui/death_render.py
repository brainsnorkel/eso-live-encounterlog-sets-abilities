"""
Death recap rendering: the button a player's row gets in the fight view when
they died, its hover summary, and the recap window's HTML (the last seconds
of damage and healing before each of that player's deaths, each followed by
a summary of the kinds of damage in it, and the whole fight's damage taken
at the bottom).

The data is FightHistoryEntry.death_recaps, built by the engine's
death_recap module, and the player dict's 'taken' key (damage_kinds).
Colors are theme-aware like the rest of the fight pane.

The kinds summary (issue #73). Each of the three splits (direct against over
time, area against single target, Martial against Magical) is a two-colour
bar: a one-row table of two cells with a bgcolor and percentage widths, which
Qt's rich text draws without images, between the two sides' labels with
their amounts and percentages. A side's label is a link to the ESO-Hub page
of the first Warfare star that acts on it, with hover text naming every such
star and its tooltip (damage_kinds.stars_for), the pattern the ability names
use: the hover tells, the click opens the page. Below the bars: the damage
types behind the sides, the amounts outside them (Oblivion, fall, drowning,
untyped), what got through while blocking, what shields absorbed, hits
avoided, the healing received against the overheal, and the killing
blow's overkill. The same block draws a death's five seconds and the whole
fight, so the two read alike.

The order (issue #95). The event table is what the window is opened for, so
each death's table sits right under its "Killed by" line, that death's
kinds summary under the table as its footing, and the whole fight's block
closes the window; the first version opened with the fight block and put
each death's bars above its table, a screen of figures before the hits.
Damage over time is written DoT and healing over time HoT, the game's words
and the ones the Result column already used. The window's length is a
setting (5 to 10 seconds); each recap carries the one it was built with,
and window_seconds reads it, five for a recap from before the setting.
"""

import html
from typing import Dict, List, Optional

from damage_kinds import (
    FALL_LABEL,
    SIDE_LABELS,
    SPLITS,
    rows_have_kinds,
    stars_for,
    summary_of_rows,
    summary_of_taken,
    type_label,
)
from death_recap import RECAP_WINDOW_MS
from gui.name_mask import NO_MASK
from pull_outcome import dead_hover_text
from gui.text_size import scaled_px

DEATHS_HREF = "esolog:deaths/"  # + the player's unit id
SKULL = "☠"
ICON_PX = 20  # ability icon edge in the recap table
NOT_RECORDED = "Damage kinds were not recorded for this fight."
NO_DAMAGE_IN_WINDOW = "No damage other than the killing blow was logged in the window."
NO_DAMAGE_TAKEN = "This player took no damage in this fight."
FIGHT_BLOCK_TITLE = "Damage taken this fight"
TOP_ABILITIES = 5  # the fight block lists this many abilities
# The link beside the fight block's title to the damage taken window
# (taken_render, issue #98), which has every ability, the sources and the
# healers; the recap keeps its top few
TAKEN_WINDOW_LINK = "every ability, by source and by healer, in its own window"
# A side narrower than this keeps its percentage off the bar (it would not fit)
MIN_BAR_TEXT_PCT = 8
# The words for the over-time sides: damage over time as the bars label it
# (damage_kinds.SIDE_LABELS), healing over time beside it
DOT_LABEL = SIDE_LABELS["dot"]
HOT_LABEL = "HoT"
# What a healing side's star hover is headed with
HEAL_SIDE_WORDS = {"direct": "direct healing", "dot": f"healing over time ({HOT_LABEL})",
                   "landed": "healing received", "overheal": "overheal"}

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
        "text": "#e8eaed",
        "muted": "#9aa0a6",
        "damage": "#ef9a9a",
        "heal": "#81c784",
        "shield": "#4fc3f7",
        "health": ("#81c784", "#ffd54f", "#ffb74d", "#e57373"),
        "chip_fg": "#1b1b1b",
        "chip_bg": "#e57373",
        "rule": "#45494f",
        "final_bg": "#3a2a2a",
        # the two sides of a kinds bar, and the text drawn on them
        "bar_left": "#8e4b43",
        "bar_right": "#3f6482",
        "bar_text": "#f1f3f4",
        "bar_empty": "#2a2e33",
    },
    # light background: darker, saturated accents
    False: {
        "text": "#202124",
        "muted": "#5f6368",
        "damage": "#c62828",
        "heal": "#2e7d32",
        "shield": "#1565c0",
        "health": ("#2e7d32", "#856900", "#aa5600", "#c62828"),
        "chip_fg": "#ffffff",
        "chip_bg": "#c62828",
        "rule": "#d6d9dc",
        "final_bg": "#fdecea",
        "bar_left": "#e9a59c",
        "bar_right": "#a7c6e2",
        "bar_text": "#202124",
        "bar_empty": "#eceff1",
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


def _player_for(entry, unit_id) -> Optional[dict]:
    for p in getattr(entry, "players", None) or []:
        if str(p.get("unit_id", "")) == str(unit_id):
            return p
    return None


def _clock(ms) -> str:
    seconds = max(0, int(ms)) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def window_seconds(recap: dict) -> int:
    """The seconds the recap's window covered: what the recorder wrote on
    it, or the fixed five of a recap from before the setting (issue #95)."""
    return int(recap.get("window_ms") or RECAP_WINDOW_MS) // 1000


def _killed_by(recap: dict, names=NO_MASK) -> str:
    """'Slap (Sharpfang)', or just the ability when the log names no killer.
    The killer goes through the Hide names mask: an enemy passes, a player
    (a PvP log, friendly fire) is hidden."""
    ability = str(recap.get("ability", ""))
    killer = names.text(str(recap.get("killer") or ""))
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


def death_tooltips(entry, names=None) -> Dict[str, str]:
    """Hover text per death-recap button: when and to what the player
    died; *names* is the Hide names mask (gui.name_mask)."""
    names = names or NO_MASK
    e = html.escape
    tips = {}
    for unit_id, deaths in deaths_by_unit(entry).items():
        name = e(names.text(str(deaths[0].get("name", ""))))
        noun = "death" if len(deaths) == 1 else "deaths"
        lines = [f"<b>{name}: {len(deaths)} {noun}</b>"]
        lines.extend(f"{_clock(d.get('time_ms', 0))} &nbsp;{e(_killed_by(d, names))}"
                     for d in deaths)
        # How long they stayed down in the fight (pull_outcome, issue #169)
        dead = dead_hover_text(entry, unit_id)
        if dead:
            lines.append(e(dead))
        lines.append("<span style='font-size:85%'>Click for the death recap</span>")
        tips[death_href(unit_id)] = "<br>".join(lines)
    return tips


# ----------------------------------------------------------- the kinds --

def _star_href(scope: str, side: str) -> str:
    """The link a side's label carries: the first star's ESO-Hub page."""
    stars = stars_for(scope, side)
    return stars[0]["url"] if stars else ""


def kind_tooltips() -> Dict[str, str]:
    """Hover text per star link in the kinds summaries, for every scope
    (damage dealt, damage taken, healing) and side: the Warfare stars that
    act on that side, each with the game's tooltip text, and where the
    link leads. Static: the windows set it once per render."""
    e = html.escape
    tips: Dict[str, str] = {}
    scope_words = {"dealt": "damage dealt", "taken": "damage taken", "heal": "healing"}
    for scope, scope_word in scope_words.items():
        sides = ["direct", "dot", "area", "single", "martial", "magical"]
        if scope == "heal":
            sides = ["direct", "dot", "landed", "overheal"]
        for side in sides:
            stars = stars_for(scope, side)
            if not stars:
                continue
            what = (HEAL_SIDE_WORDS.get(side, side) if scope == "heal"
                    else f"{SIDE_LABELS.get(side, side)} {scope_word}")
            lines = [f"<b>Warfare stars for {e(what)}</b>"]
            for star in stars:
                lines.append(f"<b>{e(star['name'])}</b>: {e(star['text'])}")
            lines.append(f"<span style='font-size:85%'>Click to open {e(stars[0]['name'])} "
                         f"on eso-hub.com · the log does not say which stars a player has</span>")
            tips[stars[0]["url"]] = "<br>".join(lines)
    return tips


def _side_html(scope: str, side: str, amount: int, pct: int, theme: dict, e,
               align: str) -> str:
    """A side's label with its amount and percentage, linked to its star."""
    label = e(SIDE_LABELS.get(side, side))
    href = _star_href(scope, side)
    if href:
        label = (f'<a href="{e(href, quote=True)}" style="text-decoration:none;'
                 f'color:{theme["text"]}">{label}</a>')
    figures = f"<span style='color:{theme['muted']}'>{amount:,} · {pct}%</span>"
    return f"{label} {figures}" if align == "left" else f"{figures} {label}"


def _bar_cells(left_pct: int, right_pct: int, theme: dict) -> str:
    """The two coloured cells of a bar, the percentage on a side wide enough."""
    def cell(pct, color, text_align):
        text = f"{pct}%" if pct >= MIN_BAR_TEXT_PCT else "&nbsp;"
        return (f"<td width='{pct}%' bgcolor='{color}' align='{text_align}' "
                f"style='color:{theme['bar_text']};font-size:85%'>{text}</td>")
    if left_pct + right_pct == 0:
        return (f"<td width='100%' bgcolor='{theme['bar_empty']}' "
                f"style='color:{theme['muted']};font-size:85%'>&nbsp;</td>")
    cells = []
    if left_pct:
        cells.append(cell(left_pct, theme["bar_left"], "left"))
    if right_pct:
        cells.append(cell(right_pct, theme["bar_right"], "right"))
    return "".join(cells)


def _bars_html(summary: dict, scope: str, theme: dict, e) -> str:
    """The three splits as rows: left label and figures, the bar, right
    label and figures."""
    parts = ["<table cellpadding='2' cellspacing='0' width='99%'>"]
    for key, (left, right) in zip(("time", "target", "school"), SPLITS):
        left_amount, right_amount = summary["sides"][key]
        left_pct, right_pct = summary["pcts"][key]
        bar = (f"<table cellpadding='1' cellspacing='0' width='100%'><tr>"
               f"{_bar_cells(left_pct, right_pct, theme)}</tr></table>")
        parts.append(
            "<tr>"
            f"<td width='26%' align='right' valign='middle'>"
            f"{_side_html(scope, left, left_amount, left_pct, theme, e, 'right')}</td>"
            f"<td width='48%' valign='middle'>{bar}</td>"
            f"<td width='26%' valign='middle'>"
            f"{_side_html(scope, right, right_amount, right_pct, theme, e, 'left')}</td>"
            "</tr>")
    parts.append("</table>")
    return "".join(parts)


def _heal_link(side: str, text: str, theme: dict, e) -> str:
    href = _star_href("heal", side)
    if not href:
        return e(text)
    return (f'<a href="{e(href, quote=True)}" style="text-decoration:none;'
            f'color:{theme["heal"]}">{e(text)}</a>')


def kinds_block_html(summary: dict, scope: str, theme: dict, e, base_pt: float,
                     lead: str = "", empty_text: str = NO_DAMAGE_IN_WINDOW) -> str:
    """One kinds summary: the total (with *lead*, a clause after it such as
    'in the last 5 seconds'), the three bars, the types, the amounts outside
    the two schools, what blocks let through, shields and avoided hits, the
    healing against the overheal, the overkill. A summary with no damage
    is *empty_text* and the healing figures alone."""
    muted = theme["muted"]
    small = f"font-size:{base_pt * 0.9:.2f}pt"
    total = summary["total"]
    parts = []
    heal_bits = []
    healed = summary["healed"]
    if healed or summary["overheal"] or summary["heal_absorbed"]:
        if healed:
            shares = []
            if summary["heal_direct"]:
                shares.append(_heal_link("direct", f"direct {summary['heal_direct']:,}", theme, e))
            if summary["heal_hot"]:
                shares.append(_heal_link("dot", f"{HOT_LABEL} {summary['heal_hot']:,}", theme, e))
            heal_bits.append(_heal_link("landed", f"healed {healed:,}", theme, e)
                             + (f" <span style='color:{muted}'>({' · '.join(shares)})</span>"
                                if len(shares) > 1 else ""))
        else:
            heal_bits.append(_heal_link("landed", "nothing healed", theme, e))
        if summary["overheal"]:
            heal_bits.append(_heal_link("overheal", f"{summary['overheal']:,} overheal", theme, e))
        if summary["heal_absorbed"]:
            heal_bits.append(f"<span style='color:{theme['shield']}'>"
                             f"{summary['heal_absorbed']:,} healing absorbed</span>")
    if total <= 0:
        parts.append(f"<p style='margin:2px 0;color:{muted}'>{e(empty_text)}"
                     + (f" {' · '.join(heal_bits)}" if heal_bits else "") + "</p>")
        return "".join(parts)

    head = f"<b>{total:,}</b> damage"
    if lead:
        head += f" {e(lead)}"
    if summary["overkill"]:
        head += f" <span style='color:{muted}'>· {summary['overkill']:,} overkill</span>"
    parts.append(f"<p style='margin:4px 0 2px 0'>{head}</p>")
    parts.append(_bars_html(summary, scope, theme, e))
    lines = []
    types = [f"{e(label)} {round(100.0 * amount / total)}%"
             for label, amount in summary["types"] if amount]
    if types:
        lines.append(" · ".join(types))
    outside = summary.get("outside") or {}
    if outside:
        lines.append("outside both: " + " · ".join(
            f"{e(label)} {amount:,}" for label, amount in outside.items()))
    mitigation = []
    if summary["blocked_through"]:
        mitigation.append(f"{summary['blocked_through']:,} got through while blocking")
    if summary["absorbed"]:
        mitigation.append(f"<span style='color:{theme['shield']}'>"
                          f"{summary['absorbed']:,} absorbed by shields</span>")
    if summary["avoided"]:
        noun = "hit" if summary["avoided"] == 1 else "hits"
        mitigation.append(f"{summary['avoided']} {noun} avoided")
    if mitigation:
        lines.append(" · ".join(mitigation))
    if heal_bits:
        lines.append(" · ".join(heal_bits))
    for line in lines:
        parts.append(f"<p style='margin:1px 0;color:{muted};{small}'>{line}</p>")
    return "".join(parts)


def _kind_words(row: dict) -> str:
    """'direct · area · fire' for an ability row of the fight block: the
    larger side of each split, and the types largest first."""
    words = []
    direct, dot, fall = row.get("direct", 0), row.get("dot", 0), row.get("fall", 0)
    if fall and fall >= max(direct, dot):
        words.append("fall")
    elif direct and dot:
        words.append(f"direct and {DOT_LABEL}" if min(direct, dot) * 4 >= max(direct, dot)
                     else ("direct" if direct > dot else DOT_LABEL))
    elif dot:
        words.append(DOT_LABEL)
    elif direct:
        words.append("direct")
    if not fall or fall < max(direct, dot):
        words.append("area" if row.get("area", 0) > row.get("single", 0) else "single target")
    types = sorted((row.get("types") or {}).items(), key=lambda kv: -kv[1])
    if words and words[0] == "fall":
        # The fall type label is the word already written
        types = [kv for kv in types if kv[0] != FALL_LABEL]
    if types:
        total = sum(amount for _label, amount in types) or 1
        words.append(", ".join(label for label, amount in types if amount * 10 >= total))
    return " · ".join(words)


def fight_block_html(player: Optional[dict], theme: dict, icons, e, names,
                     base_pt: float) -> str:
    """The whole fight's damage taken for *player* (their dict's 'taken'
    key), with the abilities that did most of it, which closes the window;
    the not-recorded line for an entry from before the kinds were kept."""
    muted = theme["muted"]
    link = ""
    unit_id = str(player.get("unit_id") or "") if isinstance(player, dict) else ""
    if unit_id:
        # fight_render imports this module, so its href helper is taken here
        from gui.fight_render import taken_href
        link = (f" <span style='font-size:{base_pt * 0.85:.2f}pt;font-weight:normal'>"
                f"<a href='{e(taken_href(unit_id), quote=True)}' style='text-decoration:none;"
                f"color:{muted}'>{TAKEN_WINDOW_LINK}</a></span>")
    title = f"<p style='margin:14px 0 2px 0'><b>{FIGHT_BLOCK_TITLE}</b>{link}</p>"
    taken = player.get("taken") if isinstance(player, dict) else None
    if not isinstance(taken, dict) or "total" not in taken:
        return title + f"<p style='margin:0;color:{muted}'>{NOT_RECORDED}</p>"
    summary = summary_of_taken(taken)
    lead = ""
    if taken.get("first_ms") is not None and taken.get("last_ms") is not None:
        span_s = (int(taken["last_ms"]) - int(taken["first_ms"])) / 1000.0
        if span_s >= 1:
            lead = f"over {_clock(span_s * 1000)} of hits, first to last"
    parts = [title, kinds_block_html(summary, "taken", theme, e, base_pt, lead, NO_DAMAGE_TAKEN)]
    rows = (taken.get("abilities") or [])[:TOP_ABILITIES]
    if rows and summary["total"]:
        head = (f"style='color:{muted};border-bottom-style:solid;"
                f"border-bottom-width:1px;border-bottom-color:{theme['rule']}'")
        parts.append(
            "<table cellpadding='3' cellspacing='0' width='99%'>"
            f"<tr><td width='{scaled_px(ICON_PX)}' {head}></td><td width='24%' {head}>Ability</td>"
            f"<td width='10%' align='right' {head}>Damage</td>"
            f"<td width='6%' align='right' {head}>%</td>"
            f"<td {head}>Kind</td><td width='18%' {head}>Source</td></tr>")
        for row in rows:
            icon = _icon_html(row, icons)
            pad = "" if icon else "padding-top:5px;padding-bottom:5px;"
            source = str(row.get("source") or "")
            damage = int(row.get("damage") or 0)
            cells = (
                (f" width='{scaled_px(ICON_PX)}'", icon),
                ("", e(str(row.get("name", "")))),
                (" align='right'", f"<span style='color:{theme['damage']}'>{damage:,}</span>"),
                (" align='right'", f"{round(100.0 * damage / summary['total'])}%"),
                ("", f"<span style='color:{muted}'>{e(_kind_words(row))}</span>"),
                ("", names.html(source, theme["text"], base_pt) if source else "–"),
            )
            parts.append("<tr>" + "".join(
                f"<td{attrs} valign='middle' style='{pad}'>{content}</td>"
                for attrs, content in cells) + "</tr>")
        parts.append("</table>")
        more = int(taken.get("ability_count") or 0) - len(rows)
        if more > 0:
            parts.append(f"<p style='margin:0;color:{muted};font-size:{base_pt * 0.85:.2f}pt'>"
                         f"and {more} more {'ability' if more == 1 else 'abilities'}</p>")
    return "".join(parts)


def _death_kinds_html(recap: dict, rows: List[dict], theme: dict, e, base_pt: float) -> str:
    """The summary of one death's window, or the not-recorded line."""
    muted = theme["muted"]
    if not rows_have_kinds(rows):
        return f"<p style='margin:0 0 4px 0;color:{muted}'>{NOT_RECORDED}</p>"
    summary = summary_of_rows(rows, recap.get("overheal"))
    return kinds_block_html(summary, "taken", theme, e, base_pt,
                            f"in the last {window_seconds(recap)} seconds")


# ------------------------------------------------------------- the table --

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
    """'Blocked · fire · area · hit 8 players · 5,603 absorbed by Bone
    Shield · 1,224 overkill'."""
    kind = row.get("kind")
    result = str(row.get("result", ""))
    label = RESULT_LABELS.get(result, result)
    color = {"heal": theme["heal"], "avoided": theme["muted"],
             "absorbed": theme["shield"], "heal_absorbed": theme["shield"]}.get(kind)
    parts = [f"<span style='color:{color}'>{e(label)}</span>" if color else e(label)]
    if kind == "damage" and "damage_type" in row and result != "FALL_DAMAGE":
        parts.append(e(type_label(str(row.get("damage_type") or ""), result)))
        if row.get("area"):
            targets = int(row.get("targets_hit") or 0)
            parts.append("area" + (f" · hit {targets} players" if targets >= 2 else ""))
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
    return (f'<img src="icon:{stem}" width="{scaled_px(ICON_PX)}" height="{scaled_px(ICON_PX)}" '
            f'alt="" style="vertical-align:middle">')


def _death_html(recap: dict, index: int, total: int, theme: dict, icons, e,
                names, base_pt: float) -> str:
    muted = theme["muted"]
    max_health = recap.get("max_health") or 0
    facts = [f"{_clock(recap.get('time_ms', 0))} into the fight"]
    if max_health:
        facts.append(f"{max_health:,} max health")
    # The killer, normally an enemy; a player in a PvP log, hidden like
    # any other player's name
    killer = names.html(str(recap.get("killer") or ""), theme["text"], base_pt)
    icon = _icon_html(recap, icons)
    ability = e(str(recap.get("ability", "")))
    killed_by = f"{icon}&nbsp;{ability}" if icon else ability
    parts = [
        f"<p style='margin:14px 0 2px 0'><b>Death {index} of {total}</b>"
        f" <span style='color:{muted}'>· {' · '.join(facts)}</span></p>",
        f"<p style='margin:0 0 4px 0'>Killed by <b>{killed_by}</b>"
        + (f" <span style='color:{muted}'>from</span> {killer}" if killer else "")
        + "</p>",
    ]
    rows = recap.get("events") or []
    if not rows:
        parts.append(f"<p style='margin:0;color:{muted}'>No damage or healing was logged "
                     f"in the {window_seconds(recap)} seconds before this death.</p>")
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
        # The source, a player's handle for a heal, through the Hide names
        # mask (gui.name_mask); an enemy's name passes as it is
        source = str(row.get("source") or "")
        cells = (
            (" align='right'", f"color:{muted};", _offset_text(row.get("offset_ms", 0))),
            (" align='right'", "", _health_html(row, theme)),
            (f" width='{scaled_px(ICON_PX)}'", "", icon),
            (" width='20%'", bold, e(str(row.get("ability", "")))),
            ("", bold, names.html(source, theme["text"], base_pt, bool(final)) if source else "–"),
            (" align='right'", bold, _amount_html(row, theme)),
            ("", "", _result_html(row, theme, e)),
        )
        parts.append(tr + "".join(
            f"<td{attrs} valign='middle' style='{pad}{style}'>{content}</td>"
            for attrs, style, content in cells) + "</tr>")
    parts.append("</table>")
    # The window's summary, under the table it sums (issue #95)
    parts.append(_death_kinds_html(recap, rows, theme, e, base_pt))
    return "".join(parts)


def render_death_recap_html(entry, unit_id, dark: bool = False, icons=None,
                            base_pt: float = 9.0, names=None,
                            text_color: str | None = None) -> str:
    """One player's deaths in a fight as HTML for the recap window: each
    death, then the whole fight's damage taken.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    leaves the abilities as names. base_pt: the pane's font size, which the
    title is scaled from (Qt rich text ignores percentage sizes). names:
    the Hide names mask (gui.name_mask) for the title and the heal sources;
    text_color: the pane's own text colour, which a hidden name is drawn in.
    The hover text for the star links is kind_tooltips().
    """
    theme = dict(_THEMES[bool(dark)])
    if text_color:
        theme["text"] = text_color
    names = names or NO_MASK
    e = html.escape
    deaths = deaths_by_unit(entry).get(str(unit_id), [])
    muted = theme["muted"]
    where = " · ".join(e(str(part)) for part in (
        getattr(entry, "boss_name", ""), getattr(entry, "zone_name", ""),
        getattr(entry, "timestamp", "")) if part)
    name = (names.html(str(deaths[0].get("name", "")), theme["text"], base_pt * 1.3, bold=True)
            if deaths else "")
    parts = [
        f"<p style='margin:0'>"
        f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{name}</span>"
        f"&nbsp;&nbsp; <span style='color:{muted}'>{where}</span></p>",
    ]
    if not deaths:
        parts.append(f"<p style='color:{muted}'>No deaths recorded for this player.</p>")
        return "".join(parts)
    parts.append(f"<p style='margin:8px 0 2px 0;color:{muted}'>Damage and healing in the "
                 f"{window_seconds(deaths[0])} seconds before each death, oldest first. "
                 f"Health is the value after each event.</p>")
    for index, recap in enumerate(deaths, 1):
        parts.append(_death_html(recap, index, len(deaths), theme, icons, e, names, base_pt))
    # The whole fight closes the window: the deaths are what it is opened
    # for (issue #95)
    parts.append(fight_block_html(_player_for(entry, unit_id), theme, icons, e, names, base_pt))
    return "".join(parts)
