"""
Rendering of FightHistoryEntry data for the GUI: HTML for the detail pane,
plain text for clipboard copy, and one-line summaries for the history list.

Colors are theme-aware: the window passes dark=True/False from its palette,
and each theme gets colors with adequate contrast on its background.

Ability bars: with an icon cache the detail view draws each slot as the
game's icon (``<img src="icon:<stem>">``, served by the fight view) inside an
anchor, so hovering shows the name and clicking opens the skill's ESO-Hub
page when one is known. Without a cache, or for slots whose icon is not
bundled, the name is shown as text. The plain-text copy always uses names.

Scribed skills: a grimoire's icon and name say nothing about the signature
and affix scripts written into it, so the build card lists each scribed skill
under the bars as "Shocking Banner (Class Flourish / Heroism)", the hover on
its icon names all four parts, and the plain-text copy uses the same label
(see scribing.py for where the scripts come from and when they are unknown).

A player who died in the fight gets a death-recap button beside their name
(see death_render); the fight view opens the recap window when it is clicked.

A player's name is a link to their build window (see build_render): it looks
like the plain bold name it replaces, and the fight view underlines it in the
theme's link color while the pointer is over it.
"""

import html
import zlib
from typing import Optional

from ability_icons import slugify
from gui.death_render import death_chip_html, deaths_by_unit
from scribing import scribed_label, slot_label

ROLE_NAMES = {"T": "Tank", "H": "Healer", "D": "DPS"}

ICON_PX = 22  # rendered edge of an ability icon in the detail pane
SCRIBED_ICON_PX = 14  # grimoire icon beside a scribed skill's scripts
BAR_DIVIDER = "│"  # between bar 1 and bar 2 when both are icon rows
DEATH_CUE = "(d)"  # history-list mark on a fight in which a player died
SCRIPT_KINDS = ("Focus", "Signature", "Affix")  # order of a slot's 'scripts'
SCRIPTS_UNKNOWN = "scripts not in log"
BUILD_HREF = "esolog:build/"  # + the player's unit id

_THEMES = {
    # dark background: lighter accents
    True: {
        "text": "#e8eaed",
        "muted": "#9aa0a6",
        "detail": "#b8bcc0",
        "vet": "#ffb74d",
        "link": "#8ab4f8",
        "roles": {"T": "#4fc3f7", "H": "#81c784", "D": "#e57373"},
        # build card (skill lines + bars): faint lift off the dark pane
        "frame_border": "#45494f",
        "frame_bg": "#2a2e33",
        # the ring on, or the name of, an ability the player taunted with
        "taunt": "#ce93d8",
    },
    # light background: darker, saturated accents
    False: {
        "text": "#202124",
        "muted": "#5f6368",
        "detail": "#3c4043",
        "vet": "#b25a00",
        "link": "#1a73e8",
        "roles": {"T": "#1565c0", "H": "#2e7d32", "D": "#c62828"},
        "frame_border": "#d6d9dc",
        "frame_bg": "#f6f7f8",
        "taunt": "#7b1fa2",
    },
}


def _theme(dark: bool) -> dict:
    return _THEMES[bool(dark)]


def muted_color(dark: bool) -> str:
    """Secondary-text color with adequate contrast for the theme."""
    return _theme(dark)["muted"]


def link_color(dark: bool) -> str:
    """Color a player's name takes while the pointer is over it."""
    return _theme(dark)["link"]


def build_href(unit_id) -> str:
    return f"{BUILD_HREF}{unit_id}"


def build_unit_from_href(href: str) -> Optional[str]:
    """The player's unit id when *href* is a build link, else None."""
    if href and href.startswith(BUILD_HREF):
        return href[len(BUILD_HREF):]
    return None


def build_tooltips(entry) -> dict:
    """Hover text per player-name link: that a click opens the build window."""
    e = html.escape
    tips = {}
    for p in entry.players:
        unit_id = str(p.get("unit_id", ""))
        if unit_id:
            tips[build_href(unit_id)] = (
                f"<b>{e(_join(p.get('name', '')))}</b><br>"
                f"<span style='font-size:85%'>Click for the full build: bars, gear, "
                f"mundus and food</span>")
    return tips


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


def _resources_html(p) -> str:
    """'H 23.3k · M 14.9k · S 27.6k' with the largest pool in bold."""
    pools = [("H", p.get("h")), ("M", p.get("m")), ("S", p.get("s"))]
    values = []
    for _label, raw in pools:
        try:
            values.append(float(raw or 0))
        except (TypeError, ValueError):
            values.append(0.0)
    top = values.index(max(values)) if any(values) else -1
    parts = []
    for index, (label, raw) in enumerate(pools):
        text = f"{label} {_fmt_resource(raw)}"
        parts.append(f"<b>{text}</b>" if index == top else text)
    return " · ".join(parts)


def _short_line(name) -> str:
    """'Herald of the Tome' -> 'Herald', "Dawn's Wrath" -> 'Dawn'."""
    words = str(name).split()
    first = words[0] if words else str(name)
    return first[:-2] if first.endswith("'s") else first


def _subclass_text(p) -> str:
    """'Assassination/Shadow/Herald' when the detected skill lines include one
    outside the player's own class; '' for a stock build, where the class
    abbreviation already says it all."""
    lines = p.get("skill_lines") or []
    if isinstance(lines, str):
        lines = [lines]
    class_lines = set(p.get("class_lines") or [])
    if not lines or (class_lines and all(line in class_lines for line in lines)):
        return ""
    return "/".join(_short_line(line) for line in lines)


def summary_line(entry, death_cue: bool = False) -> str:
    """Fight line: boss · duration · gdps · zone · timestamp.

    death_cue: mark a fight in which a player died with DEATH_CUE after the
    boss or mob name. The history list asks for it; the clipboard copy,
    which is read without the app's legend, does not.
    """
    vet = " vet" if entry.is_vet else ""
    zone = entry.zone_name or "Unknown"
    parts = []
    if entry.boss_name:
        parts.append(entry.boss_name)
    parts.append(_fmt_duration(entry.duration_s))
    parts.append(f"{_fmt_dps(entry.group_dps)} gdps")
    parts.append(f"{zone}{vet}")
    parts.append(str(entry.timestamp))
    if death_cue and entry.deaths:
        parts[0] = f"{parts[0]} {DEATH_CUE}"
    return " · ".join(parts)


def _is_scribed(slot: dict) -> bool:
    return bool(slot.get("scribed"))


def _scribed_variant(slot: dict) -> str:
    """URL fragment naming a scribed slot's script combination, '' for any
    other slot. Hover text is looked up by anchor target, so two players'
    Shocking Banners with different scripts need different targets."""
    if not _is_scribed(slot):
        return ""
    scripts = slot.get("scripts")
    if scripts:
        return ".".join(slugify(str(script)) for script in scripts[1:3])
    options = slot.get("script_options")
    if options:
        return f"options-{zlib.crc32(repr(options).encode('utf-8')):08x}"
    return "scripts-unknown"


def _ability_href(slot: dict, links) -> str:
    """Anchor target for a bar slot: the ESO-Hub skill page when *links*
    knows one, else an internal esolog: URL that only carries the hover."""
    url = links(str(slot.get("name", ""))) if links else None
    href = url or f"esolog:ability/{slot.get('id', '')}"
    variant = _scribed_variant(slot)
    return f"{href}#{variant}" if variant else href


def _taunt_mark(slot: dict, taunt_color: Optional[str]) -> str:
    """The color an ability the player taunted with is marked in, '' for
    any other slot or when no color is given."""
    return taunt_color if taunt_color and slot.get("taunt") else ""


def _bar_html(slots, names, icons, links, e, px: int = ICON_PX,
              taunt_color: Optional[str] = None) -> str:
    """One ability bar. Slots render as icons where the cache has them and as
    names otherwise, each inside an anchor; the sixth slot (the ultimate)
    sits apart. With no icon cache the bar is the plain joined name list.
    px: the icons' edge (the build window draws them larger). taunt_color:
    an ability the player taunted with gets a ring of it on its icon (see
    the view's loadResource) or its name in it."""
    if icons is None or not slots:
        if slots and any(_taunt_mark(slot, taunt_color) for slot in slots):
            return _join([
                f"<span style='color:{taunt_color}'>{e(str(slot.get('name', '')))}</span>"
                if _taunt_mark(slot, taunt_color) else e(str(slot.get("name", "")))
                for slot in slots])
        return e(_join(names))
    parts = []
    for index, slot in enumerate(slots):
        stem = str(slot.get("icon") or "")
        mark = _taunt_mark(slot, taunt_color)
        if icons.has(stem):
            ring = f"?ring={mark.lstrip('#')}" if mark else ""
            body = (f'<img src="icon:{stem}{ring}" width="{px}" height="{px}" '
                    f'style="vertical-align:middle">')
        elif mark:
            body = f"<span style='color:{mark}'>{e(str(slot.get('name', '')))}</span>"
        else:
            body = e(str(slot.get("name", "")))
        href = e(_ability_href(slot, links), quote=True)
        chunk = f'<a href="{href}" style="text-decoration:none">{body}</a>'
        if index == 5:
            chunk = "&nbsp;&nbsp;&nbsp;" + chunk
        parts.append(chunk)
    return "&nbsp;".join(parts)


def anchor_names(entry, links=None) -> dict:
    """Plain ability name per anchor href in the detail view, so the in-fight
    search can match icons by the name they stand for."""
    names = {}
    for p in entry.players:
        for key in ("front_bar_slots", "back_bar_slots"):
            for slot in p.get(key) or []:
                names.setdefault(_ability_href(slot, links), str(slot.get("name", "")))
    return names


def _link_note(href: str, e) -> str:
    """Where an ESO-Hub anchor leads (without the fragment that only tells
    script combinations apart)."""
    return (f"<br><span style='font-size:85%'>"
            f"Click to open on ESO-Hub<br>{e(href.split('#', 1)[0])}</span>")


def _link_tip(name: str, href: str, e) -> str:
    return f"<b>{e(name)}</b>{_link_note(href, e)}"


def _scribed_tip(slot: dict, href: str, e) -> str:
    """Hover text for a scribed skill: its grimoire and three scripts, or
    why the scripts are missing (the log gave none for this player, or never
    tied one of several combinations to them)."""
    rows = [f"<b>{e(str(slot.get('name', '')))}</b>"]
    scripts, options = slot.get("scripts"), slot.get("script_options")
    if slot.get("grimoire") and not options:
        rows.append(f"Grimoire: {e(str(slot['grimoire']))}")
    if scripts:
        rows.extend(f"{kind}: {e(str(script))}"
                    for kind, script in zip(SCRIPT_KINDS, scripts) if script)
    elif options:
        rows.append("The log lists each script combination once, for the first "
                    "player seen with it. This player's is one of:")
        for option in options:
            rows.append(f"• {e(scribed_label(option[0], option[1:]))}" if any(option[1:])
                        else "• or one the log has without its scripts")
    else:
        rows.append("The log has this skill without its scripts.")
    tip = "<br>".join(rows)
    return tip + _link_note(href, e) if href.startswith("http") else tip


def _scribed_slots(p) -> list:
    """A player's scribed skills, front bar first; a skill slotted on both
    bars is listed once."""
    slots, seen = [], set()
    for key in ("front_bar_slots", "back_bar_slots"):
        for slot in p.get(key) or []:
            mark = _ability_href(slot, None)
            if _is_scribed(slot) and mark not in seen:
                seen.add(mark)
                slots.append(slot)
    return slots


def _scribed_html(p, icons, links, script_links, e, color: str) -> str:
    """'Shocking Banner (Class Flourish / Heroism) · Leashing Soul (...)': a
    player's scribed skills with their signature and affix scripts, linked to
    the skill's and the scripts' ESO-Hub pages where known."""
    def anchor(label, href):
        return (f'<a href="{e(href, quote=True)}" '
                f'style="text-decoration:none;color:{color}">{label}</a>')

    chunks = []
    for slot in _scribed_slots(p):
        stem = str(slot.get("icon") or "")
        icon = (f'<img src="icon:{stem}" width="{SCRIBED_ICON_PX}" '
                f'height="{SCRIBED_ICON_PX}" style="vertical-align:middle">&nbsp;'
                if icons is not None and icons.has(stem) else "")
        name = anchor(e(str(slot.get("name", ""))), _ability_href(slot, links))
        scripts = []
        for script in (slot.get("scripts") or [])[1:3]:
            url = script_links(str(script)) if script_links and script else None
            scripts.append(anchor(e(str(script)), url) if url else e(str(script)))
        detail = " / ".join(s for s in scripts if s) or SCRIPTS_UNKNOWN
        chunks.append(f"{icon}{name} ({detail})")
    return "&nbsp; · &nbsp;".join(chunks)


def _set_items(p):
    """(count, name, perfected) tuples from a player's gear list, or []."""
    items = p.get("all_sets") or p.get("sets")
    if not items or isinstance(items, str):
        return []
    out = []
    try:
        for item in items:
            out.append((item[0], str(item[1]), bool(len(item) > 2 and item[2])))
    except (TypeError, IndexError):
        return []
    return out


def anchor_tooltips(entry, links=None, set_links=None, script_links=None) -> dict:
    """Hover text per anchor href used by render_html's detail view: the
    ability, script or set name, plus where the anchor leads when it is an
    ESO-Hub page. A scribed skill's text names its grimoire and scripts."""
    e = html.escape
    tips = {}
    for p in entry.players:
        for key in ("front_bar_slots", "back_bar_slots"):
            for slot in p.get(key) or []:
                href = _ability_href(slot, links)
                if href in tips:
                    continue
                name = str(slot.get("name", ""))
                if _is_scribed(slot):
                    tips[href] = _scribed_tip(slot, href, e)
                else:
                    tips[href] = (_link_tip(name, href, e) if href.startswith("http")
                                  else f"<b>{e(name)}</b>")
                for kind, script in zip(SCRIPT_KINDS, slot.get("scripts") or []):
                    url = script_links(str(script)) if script_links and script else None
                    if url and url not in tips:
                        tips[url] = (f"<b>{e(str(script))}</b><br>{kind} script"
                                     f"{_link_note(url, e)}")
        if set_links:
            for _count, name, _perfected in _set_items(p):
                href = set_links(name)
                if href and href not in tips:
                    tips[href] = _link_tip(name, href, e)
    return tips


def _sets_html(p, set_links, e, color: str) -> str:
    """Gear list "5pc Name, 2pc Other"; each set name is an ESO-Hub link
    when the bundled map knows the set's page."""
    items = _set_items(p)
    if not items:
        raw = p.get("all_sets") or p.get("sets")
        return e(raw) if isinstance(raw, str) else ""
    chunks = []
    for count, name, _flag in items:
        label = e(name)
        url = set_links(name) if set_links else None
        if url:
            label = (f'<a href="{e(url, quote=True)}" '
                     f'style="text-decoration:none;color:{color}">{label}</a>')
        chunks.append(f"{count}x {label}")
    return ", ".join(chunks)


def render_html(entry, detailed: bool, dark: bool = False,
                icons=None, links=None, set_links=None,
                base_pt: float = 9.0, script_links=None,
                text_color: Optional[str] = None) -> str:
    """Render one fight as HTML for a QTextBrowser.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    keeps the bars as text. links / set_links / script_links: callables
    name -> ESO-Hub URL or None for abilities / gear sets / the scripts of
    scribed skills. base_pt: the pane's font size, which the scripts and gear
    lines are scaled from (Qt rich text ignores percentage sizes).
    text_color: the pane's own text color, which a player's name keeps
    although it is a link; the theme's default when not given.
    """
    theme = _theme(dark)
    name_color = text_color or theme["text"]
    e = html.escape
    zone = e(entry.zone_name or "Unknown")
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if entry.is_vet else "")
    # Order: boss name (title), then the fight stats beside it
    muted = theme["muted"]
    detail_color = theme["detail"]
    if entry.boss_name:
        title = e(entry.boss_name)
        subline_zone = f" · {zone}{vet}"
    else:
        title = f"{zone}{vet}"
        subline_zone = ""
    # Fight stats sit to the right of the boss name on the same line, in the
    # pane's normal size and weight: duration · gdps · zone · timestamp · deaths
    stats = (f"{_fmt_duration(entry.duration_s)}"
             f" · {_fmt_dps(entry.group_dps)} gdps"
             f"{subline_zone}"
             f" · {e(str(entry.timestamp))}"
             f" · Deaths {entry.deaths}")
    # Not an <h3>: Qt would scale the nested stats by the heading's size
    # adjustment on top of their point size
    parts = [
        f"<p style='margin:0'>"
        f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{title}</span>"
        f"&nbsp;&nbsp; <span style='color:{muted}'>{stats}</span></p>",
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
    deaths = deaths_by_unit(entry)
    for p in entry.players:
        role = p.get("role") or "D"
        color = theme["roles"].get(role, muted)
        name = e(_join(p.get("name", "")))
        unit_id = str(p.get("unit_id", ""))
        # The name opens the player's build window. It keeps the look of
        # plain text; the fight view restyles it while it is hovered
        if unit_id:
            name = (f'<a href="{e(build_href(unit_id), quote=True)}" '
                    f'style="text-decoration:none;color:{name_color}">{name}</a>')
        if first_dealer and unit_id == first_dealer:
            name = f"{name} <b>*</b>"
            starred = True
        # Death-recap button for a player who died in this fight
        recap_html = (f"&nbsp;&nbsp;{death_chip_html(unit_id, deaths[unit_id], dark)}"
                      if unit_id in deaths else "")
        class_abbr = e(_join(p.get("class_abbr", "")))
        # Subclass lines beside the class, only for builds that borrow a line
        # from another class
        subclass = _subclass_text(p)
        subclass_html = f" <span style='color:{muted}'>{e(subclass)}</span>" if subclass else ""
        dps = _fmt_dps(float(p.get("dps") or 0))
        pct = float(p.get("dmg_pct") or 0)
        row = (f"<tr><td style='color:{color};font-weight:bold'>{role}</td>"
               f"<td><b>{name}</b> <span style='color:{muted}'>{class_abbr}</span>"
               f"{subclass_html}{recap_html}</td>"
               f"<td align='right'>{dps}</td>"
               f"<td align='right'>{pct:.1f}%</td>"
               f"<td align='right' style='color:{muted}'>{_resources_html(p)}</td></tr>")
        parts.append(row)
        if detailed:
            front = _bar_html(p.get("front_bar_slots"), p.get("front_bar"), icons, links, e,
                              taunt_color=theme["taunt"])
            back = _bar_html(p.get("back_bar_slots"), p.get("back_bar"), icons, links, e,
                             taunt_color=theme["taunt"])
            # Icon bars are compact, so bar 1 sits left of bar 2 on one line;
            # text bars are long and stay stacked
            icon_bars = icons is not None and bool(
                p.get("front_bar_slots") or p.get("back_bar_slots"))
            lines = []
            if icon_bars and front and back:
                lines.append(f"{front}&nbsp;&nbsp;&nbsp;"
                             f"<span style='color:{muted}'>{BAR_DIVIDER}</span>"
                             f"&nbsp;&nbsp;&nbsp;{back}")
            else:
                lines.extend(bar for bar in (front, back) if bar)
            # Under the bars: what each scribed skill was scribed with
            scribed = _scribed_html(p, icons, links, script_links, e, detail_color)
            if scribed:
                lines.append(f"<span style='font-size:{base_pt * 0.85:.2f}pt'>"
                             f"{scribed}</span>")
            # The bars sit in a framed build card; the gear list follows it in
            # a smaller font. padding-top:0 pulls the card up under the
            # player's name row
            card = ""
            if lines:
                card = (f"<table cellpadding='4' cellspacing='0' width='100%' "
                        f"style='border-style:solid;border-width:1px;"
                        f"border-color:{theme['frame_border']};"
                        f"border-collapse:collapse;"
                        f"background-color:{theme['frame_bg']}'>"
                        f"<tr><td>{'<br>'.join(lines)}</td></tr></table>")
            # Full equipment: every set with piece counts, misc pieces
            # (monster sets, arena weapons, mythics) included — not just
            # the 5pc/mythic summary used elsewhere. Set names link to their
            # ESO-Hub pages
            sets = _sets_html(p, set_links, e, detail_color)
            gear = (f"<span style='font-size:{base_pt * 0.75:.2f}pt'>{sets}</span>"
                    if sets else "")
            detail = (f"<tr><td></td><td colspan='4' "
                      f"style='color:{detail_color};padding-top:0'>"
                      f"{card}"
                      f"{gear}"
                      f"</td></tr>")
            parts.append(detail)
    parts.append("</table>")
    if starred:
        parts.append(f"<p style='margin:2px 0;color:{muted};font-size:85%'>"
                     f"* dealt the first damage of the fight</p>")
    # Deaths of players the table does not list (their build never reached
    # the log) still get their recap button
    listed = {str(p.get("unit_id", "")) for p in entry.players}
    others = [death_chip_html(unit_id, recaps, dark,
                              label=str(recaps[0].get("name") or "unknown"))
              for unit_id, recaps in deaths.items() if unit_id not in listed]
    if others:
        parts.append(f"<p style='margin:4px 0;color:{muted}'>"
                     f"Also died: {' '.join(others)}</p>")
    return "".join(parts)


def _sets_text(sets_value) -> str:
    """Human-readable gear sets ("5x Name, 2x Other") from the entry's sets
    field: a preformatted string or a list of (piece_count, set_name, ...)
    tuples."""
    if not sets_value:
        return ""
    if isinstance(sets_value, str):
        return sets_value
    try:
        return ", ".join(f"{item[0]}x {item[1]}" for item in sets_value)
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
        skill_lines = _join(p.get("skill_lines"), sep="/")
        if skill_lines:
            lines.append(f"      {skill_lines}")
        for bar, slots in ((p.get("front_bar"), p.get("front_bar_slots")),
                           (p.get("back_bar"), p.get("back_bar_slots"))):
            # Slot labels carry a scribed skill's scripts; names alone do not
            bar_text = _join([slot_label(slot) for slot in slots] if slots else bar)
            if bar_text:
                lines.append(f"      {bar_text}")
        taunts = p.get("taunts") or []
        if taunts:
            lines.append("      taunted with " + ", ".join(
                f"{t.get('name', '')} ×{t.get('count', 0)}" for t in taunts))
        sets = _sets_text(p.get("all_sets") or p.get("sets"))
        if sets:
            lines.append(f"      {sets}")
    return "\n".join(lines)
