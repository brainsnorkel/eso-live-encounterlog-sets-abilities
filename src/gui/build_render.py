"""
The build window's HTML: one player's build for a fight, as the encounter
log recorded it when combat started.

Top to bottom: who it is and which fight; mundus stone and food; both
ability bars, front above back, with the fight view's line of scribed skills;
and a gear grid with one row per slot (armor weight or weapon type, set,
pieces of that set active, quality, trait, enchant, enchant quality), a
poison row under a bar that has one slotted. The data is the fight entry's player dict as the
engine's player_build module filled it in, and the labels come from that
module too.

The anchors here (ability icons, scribed skills and their scripts, set names)
use the same targets as the fight view, so fight_render.anchor_tooltips
supplies this window's hover text as well. Colors are theme-aware like the
rest of the fight pane.
"""

import html
from typing import Optional

from gui.fight_render import (
    ROLE_NAMES, _bar_html, _join, _scribed_html, _subclass_text, _theme,
)
from player_build import (
    ARMOR_SLOTS, BACK_BAR_SLOTS, FRONT_BAR_SLOTS, POISON_SLOTS, SLOT_GROUPS, SLOT_LABELS,
    WEAPON_SLOTS, WEIGHT_LABELS, display_quality, enchant_label, level_label,
    quality_label, trait_label, weapon_type_label, weight_label,
)

BAR_ICON_PX = 36  # ability icons in the window (the bundled PNGs are 40 px)
MUNDUS_ICON_PX = 18
DASH = "–"  # a slot the log did not list, or a detail that is not known
SNAPSHOT_NOTE = "Build as logged at the start of this fight"
NO_MUNDUS = "none logged"
NO_FOOD = "no known food or drink at combat start"
NO_GEAR = "The log carried no gear for this player in this fight."
NO_BUILD = "No build was logged for this player in this fight."
POISON_NOTE = "weapon enchants on this bar do not fire while a poison is slotted"
PIECES_NOTE = ("Pcs: pieces of the row's set that are active. Two numbers are "
               "front bar / back bar, for a set whose weapons sit on one bar only.")
UNKNOWN_WEIGHT = "unknown"  # in the armor tally, a piece the bundled table lacks
# Type: an armor piece's weight, a weapon's or shield's kind
COLUMNS = (("Slot", 9, "left"), ("Type", 12, "left"), ("Set", 23, "left"),
           ("Pcs", 5, "center"), ("Quality", 13, "left"), ("Trait", 11, "left"),
           ("Enchant", 15, "left"), ("Enchant quality", 12, "left"))
# How each cell after the slot name opens
_CELLS = tuple("<td align='center'>" if align == "center" else "<td>"
               for _title, _width, align in COLUMNS[1:])

# The game's quality colors; the light theme gets darker variants, since the
# game's own are picked for a dark background
_QUALITY_COLORS = {
    True: {"TRASH": "#9aa0a6", "NORMAL": "#e8eaed", "MAGIC": "#5fd35f",
           "ARCANE": "#5aa9ff", "ARTIFACT": "#c58af9", "LEGENDARY": "#eeca2a",
           "MYTHIC_OVERRIDE": "#ff9d3c"},
    False: {"TRASH": "#80868b", "NORMAL": "#3c4043", "MAGIC": "#1e7e34",
            "ARCANE": "#1565c0", "ARTIFACT": "#7b1fa2", "LEGENDARY": "#8a6d00",
            "MYTHIC_OVERRIDE": "#c25e00"},
}
_RULES = {True: "#45494f", False: "#d6d9dc"}  # under the grid's header and groups


def player_for(entry, unit_id) -> Optional[dict]:
    """The fight entry's player dict for *unit_id*, None when not listed."""
    unit_id = str(unit_id)
    return next((p for p in getattr(entry, "players", None) or []
                 if str(p.get("unit_id", "")) == unit_id), None)


def build_title(entry, unit_id) -> str:
    """Window title: 'Build – @name'."""
    player = player_for(entry, unit_id)
    name = _join(player.get("name", "")) if player else ""
    return f"Build – {name}" if name else "Build"


def _quality_html(quality: str, dark: bool, e) -> str:
    """A quality under its in-game name, in its quality color."""
    label = quality_label(quality)
    if not label:
        return ""
    color = _QUALITY_COLORS[bool(dark)].get(quality)
    return f"<span style='color:{color}'>{e(label)}</span>" if color else e(label)


def _pieces_text(row: dict) -> str:
    """The pieces cell: a weapon shows its own bar's count; armor and jewelry
    show one number when both bars agree, else front/back."""
    pieces = row.get("pieces")
    if not pieces:
        return ""
    front, back = pieces[0], pieces[1]
    if row.get("slot") in BACK_BAR_SLOTS:
        return str(back if back is not None else front)
    if row.get("slot") in FRONT_BAR_SLOTS or back is None or back == front:
        return str(front)
    return f"{front}/{back}"


def _header_html(entry, p, theme, base_pt: float, e) -> str:
    muted = theme["muted"]
    name = _join(p.get("name", ""))
    character = str(p.get("character") or "")
    kind = " ".join(part for part in (str(p.get("race") or ""), str(p.get("class_name") or ""))
                    if part and part != "Unknown")
    cp = p.get("cp") or 0
    facts = [character if character != name else "", kind,
             f"CP {cp}" if cp else "", ROLE_NAMES.get(p.get("role"), ""),
             _subclass_text(p)]
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if getattr(entry, "is_vet", False) else "")
    zone = str(getattr(entry, "zone_name", "") or "")
    fight = [e(str(getattr(entry, "boss_name", "") or "")),
             f"{e(zone)}{vet}" if zone else "",
             e(str(getattr(entry, "timestamp", "") or "")),
             SNAPSHOT_NOTE]
    # Not an <h3>: Qt would scale the nested facts by the heading's size
    return (f"<p style='margin:0'>"
            f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{e(name)}</span>"
            f"&nbsp;&nbsp; <span style='color:{muted}'>"
            f"{' · '.join(e(fact) for fact in facts if fact)}</span></p>"
            f"<p style='margin:2px 0;color:{muted}'>"
            f"{' · '.join(part for part in fight if part)}</p>")


def _mundus_food_html(p, theme, icons, e) -> str:
    """'Mundus [icon] The Thief    Food Artaeum Takeaway Broth'. The food part
    is left out when the engine could not check for food at all."""
    muted = theme["muted"]
    stones = []
    for stone in p.get("mundus") or []:
        stem = str(stone.get("icon") or "")
        icon = (f'<img src="icon:{stem}" width="{MUNDUS_ICON_PX}" '
                f'height="{MUNDUS_ICON_PX}" style="vertical-align:middle">&nbsp;'
                if icons is not None and icons.has(stem) else "")
        stones.append(f"{icon}{e(str(stone.get('name', '')))}")
    mundus = ", ".join(stones) or f"<span style='color:{muted}'>{NO_MUNDUS}</span>"
    parts = [f"<span style='color:{muted}'>Mundus</span>&nbsp; {mundus}"]
    if "food" in p:
        food = p.get("food")
        if food:
            label = "Drink" if food.get("kind") == "drink" else "Food"
            value = e(str(food.get("name", "")))
        else:
            label, value = "Food", f"<span style='color:{muted}'>{NO_FOOD}</span>"
        parts.append(f"<span style='color:{muted}'>{label}</span>&nbsp; {value}")
    return (f"<p style='margin:8px 0 6px 0'>"
            f"{'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'.join(parts)}</p>")


def _bars_html(p, theme, icons, links, script_links, base_pt: float, e) -> str:
    """Front bar above back bar in a framed card, then the scribed skills
    with their scripts as the fight view lists them."""
    muted = theme["muted"]
    rows = []
    for label, slots_key, names_key in (("Front", "front_bar_slots", "front_bar"),
                                        ("Back", "back_bar_slots", "back_bar")):
        bar = _bar_html(p.get(slots_key), p.get(names_key), icons, links, e, BAR_ICON_PX,
                        taunt_color=theme["taunt"])
        if bar:
            rows.append(f"<tr><td width='8%' valign='middle' style='color:{muted}'>{label}</td>"
                        f"<td valign='middle'>{bar}</td></tr>")
    if not rows:
        return ""
    card = (f"<table cellpadding='4' cellspacing='0' width='99%' "
            f"style='border-style:solid;border-width:1px;"
            f"border-color:{theme['frame_border']};border-collapse:collapse;"
            f"background-color:{theme['frame_bg']}'>{''.join(rows)}</table>")
    scribed = _scribed_html(p, icons, links, script_links, e, theme["detail"])
    if scribed:
        card += (f"<p style='margin:4px 0;color:{theme['detail']};"
                 f"font-size:{base_pt * 0.85:.2f}pt'>{scribed}</p>")
    return card


def _weights_text(gear: dict) -> str:
    """The armor worn by weight, most pieces first: '5 medium, 1 light,
    1 heavy'. A piece the bundled table lacks is counted as unknown."""
    worn = [str(gear[slot].get("weight") or "") for slot in ARMOR_SLOTS if slot in gear]
    counts = sorted(((worn.count(weight), label.lower())
                     for weight, label in WEIGHT_LABELS.items()), key=lambda c: -c[0])
    counts.append((sum(weight not in WEIGHT_LABELS for weight in worn), UNKNOWN_WEIGHT))
    return ", ".join(f"{count} {name}" for count, name in counts if count)


def _item_cells(row: dict, dark: bool, theme, set_links, text_color: str, e):
    """The seven cells after the slot name for an armor, jewelry or weapon
    row. The type cell is an armor piece's weight or a weapon's kind (a
    shield's too), with a dash for a piece the bundled tables lack; jewelry
    leaves it empty."""
    dash = f"<span style='color:{theme['muted']}'>{DASH}</span>"
    slot = row.get("slot")
    if slot in ARMOR_SLOTS:
        kind = e(weight_label(row.get("weight"))) or dash
    elif slot in WEAPON_SLOTS:
        kind = e(weapon_type_label(row.get("weapon_type"))) or dash
    else:
        kind = ""
    name = str(row.get("set") or "")
    if name:
        url = set_links(name) if set_links else None
        set_html = (f'<a href="{e(url, quote=True)}" '
                    f'style="text-decoration:none;color:{text_color}">{e(name)}</a>'
                    if url else e(name))
    else:
        set_html = dash
    quality = _quality_html(display_quality(row), dark, e) or dash
    level = level_label(row.get("cp"), row.get("level"))
    if level:
        quality += f" <span style='color:{theme['muted']}'>{e(level)}</span>"
    enchant = enchant_label(row.get("enchant"))
    return (kind, set_html, _pieces_text(row), quality,
            e(trait_label(row.get("trait"))) or dash,
            e(enchant) if enchant else dash,
            (_quality_html(str(row.get("enchant_quality") or ""), dark, e) or dash)
            if enchant else dash)


def _gear_html(p, dark: bool, theme, set_links, text_color: str, base_pt: float, e) -> str:
    gear = {str(row.get("slot")): row for row in p.get("gear") or []}
    muted, rule = theme["muted"], _RULES[bool(dark)]
    if not gear:
        return f"<p style='margin:8px 0;color:{muted}'>{NO_GEAR}</p>"
    under = (f"border-bottom-style:solid;border-bottom-width:1px;"
             f"border-bottom-color:{rule}")
    # Not 100% wide: Qt rounds percentage columns up to a pixel past the pane
    parts = ["<table cellpadding='3' cellspacing='0' width='99%'><tr>"]
    parts.extend(f"<td width='{width}%' align='{align}' style='color:{muted};{under}'>"
                 f"{title}</td>" for title, width, align in COLUMNS)
    parts.append("</tr>")
    small = f"font-size:{base_pt * 0.85:.2f}pt"
    heading = f"padding-top:7px;color:{muted}"
    for group, slots in SLOT_GROUPS:
        # The armor heading carries the weights worn, from the Weight column on
        tally = _weights_text(gear) if slots == ARMOR_SLOTS else ""
        parts.append(
            f"<tr><td colspan='{1 if tally else len(COLUMNS)}' "
            f"style='{heading};font-weight:bold'>{group}</td>"
            + (f"<td colspan='{len(COLUMNS) - 1}' style='{heading}'>{tally}</td>"
               if tally else "") + "</tr>")
        for slot in slots:
            row = gear.get(slot)
            label = f"<td style='color:{muted}'>{SLOT_LABELS[slot]}</td>"
            if slot in POISON_SLOTS:
                if row is None:
                    continue  # no row for a bar without a poison
                parts.append(
                    f"<tr>{label}<td></td><td>{e(str(row.get('name', '')))}</td><td></td>"
                    f"<td>{_quality_html(str(row.get('quality') or ''), dark, e)}</td>"
                    f"<td colspan='3' style='color:{muted};{small}'>{POISON_NOTE}</td></tr>")
                continue
            if row is None:
                # The log lists equipped items only: an empty slot still gets
                # its row, so a missing off hand reads as such
                cells = ["", f"<span style='color:{muted}'>{DASH}</span>"] + [""] * 5
            else:
                cells = _item_cells(row, dark, theme, set_links, text_color, e)
            parts.append(f"<tr>{label}"
                         + "".join(f"{td}{cell}</td>" for td, cell in zip(_CELLS, cells))
                         + "</tr>")
    parts.append("</table>")
    parts.append(f"<p style='margin:6px 0;color:{muted};{small}'>{PIECES_NOTE}</p>")
    return "".join(parts)


def render_build_html(entry, unit_id, dark: bool = False, icons=None, links=None,
                      set_links=None, script_links=None, base_pt: float = 9.0,
                      text_color: Optional[str] = None) -> str:
    """One player's build in a fight as HTML for the build window.

    icons: object with has(stem) -> bool (the view's IconCache); None draws
    the bars as names. links / set_links / script_links: callables name ->
    ESO-Hub URL or None, as for fight_render.render_html. base_pt: the pane's
    font size, which the title and the small print are scaled from (Qt rich
    text ignores percentage sizes). text_color: the pane's own text color,
    which set names keep although they are links.
    """
    theme = _theme(dark)
    e = html.escape
    p = player_for(entry, unit_id)
    if p is None:
        return f"<p style='color:{theme['muted']}'>{NO_BUILD}</p>"
    return "".join((
        _header_html(entry, p, theme, base_pt, e),
        _mundus_food_html(p, theme, icons, e),
        _bars_html(p, theme, icons, links, script_links, base_pt, e),
        _gear_html(p, dark, theme, set_links, text_color or theme["text"], base_pt, e),
    ))
