"""
The build window's HTML: one player's build for a fight, as the encounter
log recorded it when combat started.

Top to bottom: who it is and which fight; mundus stone, food and Class
Mastery passives; the possible build issues the fight pane's (i) lists,
when there are any (build_issues, fight_render.issues_html); both ability
bars, front above back, then a werewolf's
own bar rebuilt from casts (see werewolf.py), each slot with the fight's
casts of it in small print under it, and a row of the casts no slot holds
(light and heavy attacks, bashes, swaps, dodges, synergies, potions, Break
Free) ending in every cast and the casts per minute (casts.py, issue #94);
then the fight view's line of scribed skills;
and a gear grid with one row per slot (armor weight or weapon type, set,
pieces of that set active, quality, trait, enchant, enchant quality), a
poison row under a bar that has one slotted; then Resources, the magicka,
stamina and ultimate spent and gained in the fight, the casts the most
went on and the gains that gave the most (resources.py, issue #125); then
Damage dealt; then the Penetration and
Critical damage sections (issue #37): the player's own sources from the
build, the Champion Point rows the Settings assume, the fight's debuffs on
the boss with uptime and casters and the buffs on the player, and the
totals against the caps, the effective figure being the damage-weighted
one pen_crit computes the way Combat Metrics does. The data is the fight
entry's player dict as the engine's player_build and pen_crit modules
filled it in, and the labels come from those modules too.

A companion's window is shorter (companions.py): its skills with this
fight's casts under each and its ultimate set apart, the casts no skill
holds by a companion's own kinds with its casts per minute, when it cast
its ultimate and the healing it did to others (issue #130), then Damage
dealt.

The anchors here (ability icons, scribed skills and their scripts, set names)
use the same targets as the fight view, so fight_render.anchor_tooltips
supplies this window's hover text as well. Colors are theme-aware like the
rest of the fight pane.
"""

import html
from typing import Optional

from damage_kinds import summary_of_taken
from gui.death_render import _THEMES as _KIND_THEMES, kinds_block_html
from gui.fight_render import (
    ROLE_NAMES, WEREWOLF_LABEL, _bar_html, _join, _scribed_html, _subclass_text, _theme,
    form_share_text, healing_text, issues_html, taken_href, ultimate_gap, ultimate_lines,
)
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px
from pen_crit import CRIT_BASE, CRIT_CAP, ENEMY_ARMOUR_CAP, SOLO_FINAL_BOSS_ARMOUR, player_totals
from player_build import (
    ARMOR_SLOTS, BACK_BAR_SLOTS, FRONT_BAR_SLOTS, POISON_SLOTS, SLOT_GROUPS, SLOT_LABELS,
    WEAPON_SLOTS, WEIGHT_LABELS, display_quality, enchant_label, level_label,
    quality_label, trait_label, weapon_type_label, weight_label,
)

BAR_ICON_PX = 36  # ability icons in the window (the bundled PNGs are 64 px)
MUNDUS_ICON_PX = 18
DASH = "–"  # a slot the log did not list, or a detail that is not known
SNAPSHOT_NOTE = "Build as logged at the start of this fight"
NO_MUNDUS = "none logged"
NO_FOOD = "no known food or drink at combat start"
NO_GEAR = "The log carried no gear for this player in this fight."
NO_BUILD = "No build was logged for this player in this fight."
COMPANION_NOTE = ("The encounter log writes no bar, gear or perks for a companion: these are "
                  "the skills it was seen casting this session, in the order first cast and "
                  "its ultimate last, with this fight's casts under each.")
NO_COMPANION_SKILLS = "No companion skill was seen cast yet this session."
POISON_NOTE = "weapon enchants on this bar do not fire while a poison is slotted"
PIECES_NOTE = ("Pcs: pieces of the row's set that are active. Two numbers are "
               "front bar / back bar, for a set whose weapons sit on one bar only.")
UNKNOWN_WEIGHT = "unknown"  # in the armor tally, a piece the bundled table lacks
CASTS_LABEL = "Other"  # the card's last row: the casts no slot holds
# That row's kinds (casts.EXTRA_KINDS) as labelled there
EXTRA_LABELS = (("light", "Light attacks"), ("heavy", "Heavy attacks"), ("bash", "Bashes"),
                ("swap", "Swaps"), ("dodge", "Dodges"), ("synergy", "Synergies"),
                ("potion", "Potions"), ("break_free", "Break Free"))
# A companion's (casts.COMPANION_EXTRA_KINDS): it never heavy attacks,
# swaps, takes a synergy or drinks a potion, and it blocks by casting
COMPANION_EXTRA_LABELS = (("light", "Light attacks"), ("bash", "Bashes"), ("block", "Blocks"),
                          ("dodge", "Dodges"), ("break_free", "Break Free"))
RESOURCES_TITLE = "Resources"
RESOURCES_ANCHOR = "resources"  # <a name>, where the section begins
RESOURCES_CAPTION = "as the log's unit states show them"
NO_RESOURCES = "No magicka, stamina or ultimate was logged for this player in this fight."
RESOURCES_NOT_RECORDED = "Resources were not recorded for this fight."
POOL_LABELS = ("Magicka", "Stamina", "Ultimate")
RESOURCES_NOTE = ("Spent and gained are the falls and rises between logged states, so a cost and "
                  "a gain in the same tenth of a second cancel. Other spending is blocking, "
                  "sprinting and costs logged after the cast.")
PEN_TITLE = "Penetration"
CRIT_TITLE = "Critical damage"
PEN_CRIT_ANCHOR = "pen-crit"  # <a name>, where the two sections begin
ASSUMED_MARK = "assumed"
NO_PEN_CRIT = "No penetration or critical damage figures for this fight."
DEALT_TITLE = "Damage dealt"
DEALT_ANCHOR = "damage-dealt"  # <a name>, where the section begins
NO_DEALT = "This player dealt no damage in this fight."
DEALT_NOT_RECORDED = "Damage kinds were not recorded for this fight."
TAKEN_LINK = "damage taken and healing received"  # opens the damage taken window
NO_DAMAGE_MEASURED = "no damage of this player's to weigh the fight's effects by"
PEN_CRIT_NOTE = ("After LunaCairu's PenCrit Calc sheet and the Hyperioxes calculators that "
                 "skinnycheeks.gg recommends; debuffs valued as Combat Metrics (Solinur) values them; "
                 "passive and set texts from UESP (CC-BY-SA). Assumed rows are Champion Point stars "
                 "the log cannot show, chosen in Settings. Effective figures weigh each second's "
                 "debuffs by this player's damage that second, as Combat Metrics weighs each hit; a "
                 "two-bar total reads front / back, and the effective figure uses the front bar.")
# Type: an armor piece's weight, a weapon's or shield's kind
COLUMNS = (("Slot", 9, "left"), ("Type", 12, "left"), ("Set", 23, "left"),
           ("Pcs", 5, "center"), ("Quality", 13, "left"), ("Trait", 11, "left"),
           ("Enchant", 15, "left"), ("Enchant quality", 12, "left"))
# How each cell after the slot name opens
_CELLS = tuple("<td align='center'>" if align == "center" else "<td>"
               for _title, _width, align in COLUMNS[1:])

# The game's quality colors; the light theme gets darker variants, since the
# game's own are picked for a dark background, each 4.5:1 or more (#77)
_QUALITY_COLORS = {
    True: {"TRASH": "#9aa0a6", "NORMAL": "#e8eaed", "MAGIC": "#5fd35f",
           "ARCANE": "#5aa9ff", "ARTIFACT": "#c58af9", "LEGENDARY": "#eeca2a",
           "MYTHIC_OVERRIDE": "#ff9d3c"},
    False: {"TRASH": "#686e72", "NORMAL": "#3c4043", "MAGIC": "#1e7e34",
            "ARCANE": "#1565c0", "ARTIFACT": "#7b1fa2", "LEGENDARY": "#856900",
            "MYTHIC_OVERRIDE": "#ae5400"},
}
_RULES = {True: "#45494f", False: "#d6d9dc"}  # under the grid's header and groups


def player_for(entry, unit_id) -> Optional[dict]:
    """The fight entry's player dict for *unit_id*, None when not listed."""
    unit_id = str(unit_id)
    return next((p for p in getattr(entry, "players", None) or []
                 if str(p.get("unit_id", "")) == unit_id), None)


def build_title(entry, unit_id, names=None) -> str:
    """Window title: 'Build – @name (Character)', the character name when
    the log gave one besides the handle (issue #71); *names* is the Hide
    names mask (gui.name_mask)."""
    player = player_for(entry, unit_id)
    if not player:
        return "Build"
    names = names or NO_MASK
    name = _join(player.get("name", ""))
    character = str(player.get("character") or "")
    title = names.text(name)
    if player.get("companion"):
        return f"Companion – {title}" if title else "Companion"
    if title and character and character != name:
        title += f" ({names.text(character)})"
    return f"Build – {title}" if title else "Build"


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


def _header_html(entry, p, theme, base_pt: float, e, names, text_color: str) -> str:
    """The title line: the handle in bold and, at the same size, the
    character name after it when the log gave both (issue #71; it was a
    muted fact until then); then race, class, champion points, role and
    borrowed lines, muted. Both names follow the Hide names mask."""
    muted = theme["muted"]
    name = _join(p.get("name", ""))
    character = str(p.get("character") or "")
    kind = " ".join(part for part in (str(p.get("race") or ""), str(p.get("class_name") or ""))
                    if part and part != "Unknown")
    cp = p.get("cp") or 0
    facts = [kind, f"CP {cp}" if cp else "", ROLE_NAMES.get(p.get("role"), ""),
             _subclass_text(p)]
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if getattr(entry, "is_vet", False) else "")
    zone = str(getattr(entry, "zone_name", "") or "")
    fight = [e(str(getattr(entry, "boss_name", "") or "")),
             f"{e(zone)}{vet}" if zone else "",
             e(str(getattr(entry, "timestamp", "") or "")),
             SNAPSHOT_NOTE]
    title_pt = base_pt * 1.3
    title = (f"<span style='font-size:{title_pt:.2f}pt;font-weight:bold'>"
             f"{names.html(name, text_color, title_pt, bold=True)}</span>")
    if character and character != name:
        title += (f"<span style='font-size:{title_pt:.2f}pt'> · "
                  f"{names.html(character, text_color, title_pt)}</span>")
    # Not an <h3>: Qt would scale the nested facts by the heading's size
    return (f"<p style='margin:0'>{title}"
            f"&nbsp;&nbsp; <span style='color:{muted}'>"
            f"{' · '.join(e(fact) for fact in facts if fact)}</span></p>"
            f"<p style='margin:2px 0;color:{muted}'>"
            f"{' · '.join(part for part in fight if part)}</p>")


def _companion_html(entry, p, theme, icons, links, base_pt: float, e, names,
                    text_color: str) -> str:
    """A companion's window (companions.py): its name, level and owner, the
    fight, and the skills it was seen casting this session with this
    fight's casts under each and its ultimate set apart, then the casts no
    skill holds and its casts per minute (issue #130); under the card,
    when it cast its ultimate this fight and the healing it did to others.
    The log writes no bar, gear or perks for a companion, so there is
    nothing else of a build; render_build_html adds the kinds of its damage
    under it."""
    muted = theme["muted"]
    owner = player_for(entry, p.get("owner_unit_id")) or {}
    owner_name = _join(owner.get("name", ""))
    level = p.get("level") or 0
    facts = ["Companion", f"level {level}" if level else ""]
    title_pt = base_pt * 1.3
    title = (f"<span style='font-size:{title_pt:.2f}pt;font-weight:bold'>"
             f"{e(_join(p.get('name', '')))}</span>")
    of_owner = (f" · of {names.html(owner_name, muted, base_pt)}" if owner_name else "")
    vet = (f" <span style='color:{theme['vet']};font-weight:bold'>[VET]</span>"
           if getattr(entry, "is_vet", False) else "")
    zone = str(getattr(entry, "zone_name", "") or "")
    fight = [e(str(getattr(entry, "boss_name", "") or "")),
             f"{e(zone)}{vet}" if zone else "",
             e(str(getattr(entry, "timestamp", "") or ""))]
    slots = p.get("front_bar_slots")
    # Counts under the icons once the entry has them (casts.py)
    if icons is not None and slots and any("casts" in slot for slot in slots):
        bar = _counted_bar_html(slots, theme, icons, links, base_pt, e)
    else:
        bar = _bar_html(slots, p.get("front_bar"), icons, links, e, scaled_px(BAR_ICON_PX),
                        taunt_color=theme["taunt"])
    rows = [(label, body) for label, body in (("Skills", bar),
                                              (CASTS_LABEL, _extras_html(p, theme, base_pt, e)))
            if body]
    card = (f"<table cellpadding='4' cellspacing='0' width='100%' "
            f"style='border-style:solid;border-width:1px;border-color:{theme['frame_border']};"
            f"border-collapse:collapse;background-color:{theme['frame_bg']}'>"
            + "".join(f"<tr><td width='8%' valign='middle' style='color:{muted};white-space:nowrap'>"
                      f"{label}</td><td valign='middle'>{body}</td></tr>" for label, body in rows)
            + "</table>" if rows else "")
    no_skills = "" if bar else f"<p style='color:{muted}'>{NO_COMPANION_SKILLS}</p>"
    # When it cast its ultimate this fight, and its healing to others
    # (fight_render's hover gives the same)
    after = [*ultimate_lines(p), healing_text(p, float(getattr(entry, "duration_s", 0) or 0))]
    after_html = (f"<p style='margin:4px 0;color:{muted}'>"
                  f"{' · '.join(e(line) for line in after if line)}</p>" if any(after) else "")
    return (f"<p style='margin:0'>{title}&nbsp;&nbsp; <span style='color:{muted}'>"
            f"{' · '.join(e(fact) for fact in facts if fact)}{of_owner}</span></p>"
            f"<p style='margin:2px 0;color:{muted}'>{' · '.join(part for part in fight if part)}</p>"
            f"<p style='margin:8px 0 6px 0;color:{muted}'>{COMPANION_NOTE}</p>"
            f"{no_skills}{card}{after_html}")


def _mundus_food_html(p, theme, icons, e) -> str:
    """'Mundus [icon] The Thief    Food Artaeum Takeaway Broth    Mastery An
    Eye for Exploitation, Above and Beyond'. The food part is left out when
    the engine could not check for food at all, the mastery part when the
    player has no Class Mastery passive (a subclassed build cannot)."""
    muted = theme["muted"]
    stones = []
    for stone in p.get("mundus") or []:
        stem = str(stone.get("icon") or "")
        icon = (f'<img src="icon:{stem}" width="{scaled_px(MUNDUS_ICON_PX)}" '
                f'height="{scaled_px(MUNDUS_ICON_PX)}" alt="" style="vertical-align:middle">&nbsp;'
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
    masteries = [str(name) for name in (p.get("masteries") or []) if name]
    if masteries:
        parts.append(f"<span style='color:{muted}'>Mastery</span>&nbsp; "
                     f"{e(', '.join(masteries))}")
    return (f"<p style='margin:8px 0 6px 0'>"
            f"{'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'.join(parts)}</p>")


def _counted_bar_html(slots, theme, icons, links, base_pt: float, e) -> str:
    """One ability bar with the fight's casts of each slot in small print
    under it (casts.py); a dash for none. The ultimate sits apart as on any
    bar: the sixth slot, or the one marked 'ultimate' (ultimate_gap)."""
    muted = theme["muted"]
    small = f"font-size:{base_pt * 0.8:.2f}pt;color:{muted}"
    cells = []
    marked = any(slot.get("ultimate") for slot in slots)
    for index, slot in enumerate(slots):
        if ultimate_gap(slot, index, marked):
            cells.append("<td width='10'></td>")
        icon = _bar_html([slot], [str(slot.get("name", ""))], icons, links, e, scaled_px(BAR_ICON_PX),
                         taunt_color=theme["taunt"])
        count = int(slot.get("casts") or 0)
        cells.append(f"<td align='center' valign='bottom'>{icon}<br>"
                     f"<span style='{small}'>{count if count else DASH}</span></td>")
    return f"<table cellpadding='1' cellspacing='0'><tr>{''.join(cells)}</tr></table>"


def _extras_html(p, theme, base_pt: float, e) -> str:
    """'Light attacks 52 · Heavy attacks 0 · … · 168 casts, 105 per minute':
    the fight's casts no slot holds, by kind (a companion's own kinds for a
    companion), then every cast and the cpm (casts.py); '' on an entry
    built before the counts."""
    summary = p.get("casts")
    if not isinstance(summary, dict):
        return ""
    muted = theme["muted"]
    labels = COMPANION_EXTRA_LABELS if p.get("companion") else EXTRA_LABELS
    parts = [f"{e(label)} {int(summary.get(kind) or 0)}" for kind, label in labels]
    parts.append(f"{int(summary.get('total') or 0)} casts, "
                 f"{float(summary.get('cpm') or 0):.0f} per minute")
    return (f"<span style='color:{muted};font-size:{base_pt * 0.9:.2f}pt'>"
            f"{' · '.join(parts)}</span>")


def _bars_html(p, theme, icons, links, script_links, base_pt: float, e) -> str:
    """Front bar above back bar in a framed card, then a werewolf's own bar
    when the player spent some of the fight in form, each slot with its
    casts under it, then the casts no slot holds; under the card the
    scribed skills with their scripts as the fight view lists them."""
    muted = theme["muted"]
    rows = []

    def bar_of(slots, names):
        # Counts under the icons once the entry has them (casts.py)
        if icons is not None and slots and any("casts" in slot for slot in slots):
            return _counted_bar_html(slots, theme, icons, links, base_pt, e)
        return _bar_html(slots, names, icons, links, e, scaled_px(BAR_ICON_PX), taunt_color=theme["taunt"])

    for label, slots_key, names_key in (("Front", "front_bar_slots", "front_bar"),
                                        ("Back", "back_bar_slots", "back_bar")):
        bar = bar_of(p.get(slots_key), p.get(names_key))
        if bar:
            rows.append(f"<tr><td width='8%' valign='middle' style='color:{muted};white-space:nowrap'>{label}</td>"
                        f"<td valign='middle'>{bar}</td></tr>")
    if p.get("werewolf_share"):
        slots = p.get("werewolf_bar_slots") or []
        bar = bar_of(slots, [str(slot.get("name", "")) for slot in slots])
        note = f"<span style='color:{muted}'>{e(form_share_text(p['werewolf_share']))}</span>"
        werewolf = (f"<table cellpadding='0' cellspacing='0'><tr><td valign='middle'>{bar}</td>"
                    f"<td valign='middle'>&nbsp;&nbsp;&nbsp;{note}</td></tr></table>"
                    if bar else note)
        rows.append(f"<tr><td width='8%' valign='middle' style='color:{muted};white-space:nowrap'>{WEREWOLF_LABEL}</td>"
                    f"<td valign='middle'>{werewolf}</td></tr>")
    extras = _extras_html(p, theme, base_pt, e)
    if rows and extras:
        rows.append(f"<tr><td width='8%' valign='middle' style='color:{muted};white-space:nowrap'>{CASTS_LABEL}</td>"
                    f"<td valign='middle'>{extras}</td></tr>")
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


def _num(value, pct: bool = False) -> str:
    """'14,095', or '82%' / '0.5%' for a percentage."""
    if value is None:
        return DASH
    if pct:
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}%"
    return f"{value:,.0f}"


def _pair_text(values, pct: bool = False) -> str:
    """One figure when both bars agree, else 'front / back'."""
    if not values:
        return DASH
    front, back = values[0], values[1] if len(values) > 1 else values[0]
    if back is None or abs(float(back) - float(front)) < 0.05:
        return _num(front, pct)
    return f"{_num(front, pct)} / {_num(back, pct)}"


def _casters_text(casters, e, names, color: str, pt: float) -> str:
    """'@tank via Infused Inferno Staff (back bar) 70%, @healer via Elemental
    Susceptibility 40%'; each name through the Hide names mask, drawn in
    *color* at *pt* points when hidden."""
    parts = []
    for caster in casters or []:
        text = names.html(str(caster.get("name") or "unknown"), color, pt)
        if caster.get("via"):
            text += f" <span style='opacity:0.8'>via {e(str(caster['via']))}</span>"
        parts.append(f"{text} {int(caster.get('pct') or 0)}%")
    return ", ".join(parts)


def _damage_dealt_html(p, dark: bool, theme, base_pt: float, e) -> str:
    """The Damage dealt section (damage_kinds, issue #73): the kinds of the
    player's damage in the fight from the damage record's 'kinds', drawn by
    the same block as the death recap window, so the two read alike; the
    shield absorbs sit outside the splits and are named; the hover on a
    side's label names the Warfare stars for damage dealt."""
    muted = theme["muted"]
    heading = f"padding-top:7px;color:{muted};font-weight:bold"
    under = (f"border-bottom-style:solid;border-bottom-width:1px;"
             f"border-bottom-color:{_RULES[bool(dark)]}")
    # Beside the heading, the way to the other side: the player's damage
    # taken window (taken_render, issue #98); not for a companion, which
    # has no tally
    unit_id = str(p.get("unit_id") or "")
    taken_link = ""
    if unit_id and not p.get("companion"):
        taken_link = (f" <span style='font-weight:normal;font-size:{base_pt * 0.85:.2f}pt'>"
                      f"<a href='{e(taken_href(unit_id), quote=True)}' style='text-decoration:none;"
                      f"color:{theme['link']}'>{TAKEN_LINK}</a></span>")
    title = (f"<a name='{DEALT_ANCHOR}'></a>"
             f"<p style='margin:6px 0 2px 0;{heading};{under}'>{DEALT_TITLE}{taken_link}</p>")
    damage = p.get("damage")
    if not isinstance(damage, dict) or not damage:
        return title + f"<p style='margin:0;color:{muted}'>{DEALT_NOT_RECORDED}</p>"
    kinds = damage.get("kinds")
    if not isinstance(kinds, dict) or "total" not in kinds:
        return title + f"<p style='margin:0;color:{muted}'>{DEALT_NOT_RECORDED}</p>"
    if not (damage.get("total") or 0):
        return title + f"<p style='margin:0;color:{muted}'>{NO_DEALT}</p>"
    summary = summary_of_taken(kinds)
    # The recap window's theme carries the bar colours; the pane's own
    # text colour for the labels
    kind_theme = dict(_KIND_THEMES[bool(dark)])
    kind_theme["text"] = theme["text"]
    parts = [title, kinds_block_html(summary, "dealt", kind_theme, e, base_pt,
                                     "dealt in this fight", NO_DEALT)]
    shielded = int(kinds.get("shielded") or 0)
    total = int(damage.get("total") or 0)
    if shielded and total:
        parts.append(f"<p style='margin:1px 0;color:{muted};font-size:{base_pt * 0.9:.2f}pt'>"
                     f"{shielded:,} absorbed by enemy shields, {round(100.0 * shielded / total)}% "
                     f"of the damage, outside the splits</p>")
    rules = kinds.get("rules") or {}
    table_share = int(rules.get("table") or 0)
    if summary["total"] and table_share:
        parts.append(f"<p style='margin:1px 0;color:{muted};font-size:{base_pt * 0.85:.2f}pt'>"
                     f"area or single target: {round(100.0 * table_share / summary['total'])}% "
                     f"of the damage classed by the skill table, the rest by the casts</p>")
    return "".join(parts)


def _rate(value) -> str:
    """'2,100/s', or '3.4/s' below a hundred."""
    value = float(value or 0)
    return f"{value:,.0f}/s" if value >= 100 else f"{value:.1f}/s"


def _resources_html(p, dark: bool, theme, base_pt: float, e, names) -> str:
    """The Resources section (resources.py, issue #125): magicka, stamina
    and ultimate spent (on casts and otherwise) and gained (logged and
    not), each with its rate over the fight, the logged gains over cap and
    the time at ultimate cap; then the casts the most went on and the
    gains that gave the most, each giver through the Hide names mask."""
    muted, rule = theme["muted"], _RULES[bool(dark)]
    small = f"font-size:{base_pt * 0.85:.2f}pt"
    heading = f"padding-top:7px;color:{muted};font-weight:bold"
    under = f"border-bottom-style:solid;border-bottom-width:1px;border-bottom-color:{rule}"
    title = (f"<a name='{RESOURCES_ANCHOR}'></a>"
             f"<p style='margin:6px 0 2px 0;{heading};{under}'>{RESOURCES_TITLE}"
             f" <span style='font-weight:normal;{small}'>· {RESOURCES_CAPTION}</span></p>")
    if "resources" not in p:
        return title + f"<p style='margin:0;color:{muted}'>{RESOURCES_NOT_RECORDED}</p>"
    data = p.get("resources")
    if not data:
        return title + f"<p style='margin:0;color:{muted}'>{NO_RESOURCES}</p>"
    pools = data["pools"]

    def cell(text, align="left", color=None, extra=""):
        style = ";".join(s for s in (f"color:{color}" if color else "", extra) if s)
        return f"<td align='{align}' style='{style}'>{text}</td>"

    def row(label, values, sub=False):
        label_cell = cell(label, color=muted if sub else None,
                          extra="padding-left:14px" if sub else "")
        return ("<tr>" + label_cell
                + "".join(cell(v, "right", extra="padding-left:18px") for v in values) + "</tr>")

    def share(part, whole):
        return f"{round(100.0 * part / whole)}%" if whole else DASH

    def total_rate(pool, kind):
        rate = f" <span style='color:{muted};{small}'>· {_rate(pool[kind + '_ps'])}</span>"
        return _num(pool[kind]) + rate

    head = ("<tr>" + cell("") + "".join(cell(label, "right", muted, f"{small};padding-left:18px")
                                        for label in POOL_LABELS) + "</tr>")
    body = [
        head,
        row("Spent", [total_rate(pool, "spent") for pool in pools]),
        row("on casts", [share(pool["on_casts"], pool["spent"]) for pool in pools], sub=True),
        row("other spending", [share(pool["spent"] - pool["on_casts"], pool["spent"])
                               for pool in pools], sub=True),
        row("Gained", [total_rate(pool, "gained") for pool in pools]),
        row("logged gains", [_num(pool["logged"]) for pool in pools], sub=True),
        row("regeneration and unlogged", [_num(max(0, pool["gained"] - pool["logged"]))
                                          for pool in pools], sub=True),
        row("Gained over cap", [_num(pools[0]["wasted"]), _num(pools[1]["wasted"]), DASH]),
        row("Time at cap", [DASH, DASH, _num(data.get("full_pct"), True)]),
    ]
    parts = [title, "<table cellpadding='3' cellspacing='0'>", *body, "</table>"]

    def list_table(label, rows, columns, cells_of):
        if not rows:
            return ""
        out = ["<table cellpadding='3' cellspacing='0'>",
               "<tr>" + cell(label, extra=heading)
               + "".join(cell(c, "right" if c != "from" else "left", muted, small) for c in columns)
               + "</tr>"]
        for r in rows:
            pool = POOL_LABELS[int(r.get("pool") or 0)].lower()
            if r.get("more"):
                name = f"<span style='color:{muted}'>{int(r['more'])} more</span>"
                out.append("<tr>" + cell(name) + cells_of(r, pool, True) + "</tr>")
            else:
                out.append("<tr>" + cell(e(str(r.get("name") or ""))) + cells_of(r, pool, False)
                           + "</tr>")
        out.append("</table>")
        return "".join(out)

    def spent_cells(r, pool, more):
        if more:
            return cell(pool, "right", muted, small) + cell("") + cell("") + cell(_num(r["total"]), "right")
        casts = int(r.get("casts") or 0)
        each = _num(r["total"] / casts) if casts else DASH
        return (cell(pool, "right", muted, small) + cell(_num(casts), "right")
                + cell(each, "right") + cell(_num(r["total"]), "right"))

    def gained_cells(r, pool, more):
        givers = ""
        if not more:
            # Each name once, the three who gave the most, then a count
            seen = list(dict.fromkeys(str(giver) for giver in r.get("givers") or []))
            givers = ", ".join(names.html(giver, muted, base_pt * 0.85) for giver in seen[:3])
            if len(seen) > 3:
                givers += f" +{len(seen) - 3}"
        return (cell(pool, "right", muted, small) + cell(givers, color=muted, extra=small)
                + cell(_num(r["total"]), "right"))

    parts.append(list_table("Spent on", data.get("spent_on") or [],
                            ("pool", "casts", "each", "total"), spent_cells))
    parts.append(list_table("Gained from", data.get("gained_from") or [],
                            ("pool", "from", "total"), gained_cells))
    parts.append(f"<p style='margin:6px 0;color:{muted};{small}'>{RESOURCES_NOTE}</p>")
    return "".join(parts)


def _pen_crit_html(entry, p, dark: bool, theme, options, base_pt: float, e, names) -> str:
    """The Penetration and Critical damage sections (pen_crit): the player's
    own rows and the assumed Champion Point rows, the fight's debuffs on
    the boss (uptime, value, casters) and the buffs on the player, then the
    totals: own, with every debuff at full uptime, and effective (each
    second of the player's damage capped, as Combat Metrics caps each
    hit), against the cap."""
    data = p.get("pen_crit") or {}
    group = getattr(entry, "pen_crit", None) or {}
    if not data and not group:
        return ""
    muted, rule = theme["muted"], _RULES[bool(dark)]
    small = f"font-size:{base_pt * 0.85:.2f}pt"
    heading = f"padding-top:7px;color:{muted};font-weight:bold"
    under = f"border-bottom-style:solid;border-bottom-width:1px;border-bottom-color:{rule}"
    # The same sums and effective figures the fight pane's row shows
    totals = player_totals(data, group, options)
    instanced, cap, crit_cap = totals["instanced"], totals["cap"], totals["crit_cap"]
    rows = list(data.get("rows") or []) + totals["assumed"]
    static_pen, static_crit = totals["static_pen"], totals["static_crit"]
    per_status = totals["per_status"]
    eff_pen, eff_crit = totals["pen"], totals["crit"]
    debuffs = group.get("debuffs") or []
    buffs = data.get("buffs") or []
    on = group.get("on") or ""
    on_text = {"boss": "on the boss", "enemies": "on the enemies"}.get(on, "")

    assumed_tag = f" <span style='color:{muted};{small}'>({ASSUMED_MARK})</span>"

    def cell(text, align="left", color=None, extra=""):
        style = ";".join(s for s in (f"color:{color}" if color else "", extra) if s)
        return f"<td align='{align}' style='{style}'>{text}</td>"

    def own_cells(row, stat):
        values = row.get(stat)
        name = e(str(row.get("name", "")))
        source = e(str(row.get("source", "")))
        note = e(str(row.get("note", "")))
        if row.get("kind") == "assumed":
            name += assumed_tag
        detail = " · ".join(part for part in (source, note) if part)
        gives = values is not None and not any(values) and "give" in str(row.get("note", ""))
        if gives:
            # The set is the reason for a buff counted or measured below
            value = ""
            if row.get("when"):
                detail = " · ".join(part for part in (source, note, e(str(row["when"]))) if part)
        elif row.get("when"):
            value = f"<span style='color:{muted}'>up to {_pair_text(values, stat == 'crit')}</span>"
            detail = f"{source} · {e(str(row['when']))}"
        elif row.get("measured"):
            value = f"<span style='color:{muted}'>{_pair_text(values, stat == 'crit')} × uptime, below</span>"
        elif values is None:
            value = ""
        else:
            value = _pair_text(values, stat == "crit")
        return (f"<tr>{cell(name)}{cell(value, 'right')}"
                f"{cell(detail, color=muted, extra=small)}</tr>")

    def table(title, cap_text, columns, body, totals):
        head = (f"<tr><td colspan='3' style='{heading};{under}'>{title}"
                f" <span style='font-weight:normal'>· {cap_text}</span></td></tr>")
        parts = ["<table cellpadding='3' cellspacing='0' width='99%'>", head]
        parts.extend(body)
        parts.append(f"<tr><td colspan='3' style='padding-top:6px'>{'<br>'.join(totals)}</td></tr>")
        parts.append("</table>")
        return "".join(parts)

    def group_header(label):
        return (f"<tr><td style='{heading}'>{label}</td>"
                f"<td align='right' style='color:{muted};{small}'>value</td>"
                f"<td style='color:{muted};{small}'>uptime · who</td></tr>")

    def group_row(d, stat, pct: bool):
        who = (f"{int(d.get('uptime_pct') or 0)}% · "
               f"{_casters_text(d.get('casters'), e, names, muted, base_pt * 0.85)}")
        return (f"<tr>{cell(e(str(d['name'])))}{cell(_num(d[stat], pct), 'right')}"
                f"{cell(who, color=muted, extra=small)}</tr>")

    # Penetration
    pen_body = [own_cells(row, "pen") for row in rows if row.get("pen") is not None]
    if per_status and eff_pen.get("damage"):
        status = eff_pen.get("status") or 0.0
        fon_note = e(f"{per_status:,.0f} × {status:.1f} status effects on the target, "
                     f"averaged over this player's damage")
        pen_body.append(f"<tr>{cell('Force of Nature' + assumed_tag)}{cell(_num(per_status * status), 'right')}"
                        f"{cell(fon_note, color=muted, extra=small)}</tr>")
    pen_debuffs = [d for d in debuffs if d.get("pen")]
    if pen_debuffs:
        pen_body.append(group_header(f"Group {on_text}".strip()))
        pen_body.extend(group_row(d, "pen", False) for d in pen_debuffs)
    full_pen = static_pen[0] + sum(d["pen"] for d in pen_debuffs if d.get("uptime_pct"))
    pen_totals = [f"Own {_pair_text(static_pen)}"]
    if pen_debuffs:
        gap = full_pen - cap
        pen_totals.append(f"With the group's debuffs at full uptime {_num(full_pen)}, "
                          + (f"over the cap by {_num(gap)}" if gap >= 0 else f"missing {_num(-gap)}"))
    if eff_pen.get("damage"):
        pen_totals.append(f"<b>Effective {_num(eff_pen['effective'])} of {_num(cap)}</b> over this player's damage, "
                          f"{eff_pen['over_pct']:.0f}% of it dealt over the cap")
    elif not pen_debuffs:
        pen_totals.append(f"<span style='color:{muted}'>{NO_DAMAGE_MEASURED}</span>")
    kind = group.get("kind") or ("instanced" if instanced else "overland")
    if group.get("dummy"):
        where = " at a trial dummy"
    elif kind == "solo_dungeon":
        # Every boss at 27,300 (pen_crit.SOLO_BOSS_ARMOUR); the final boss has more
        where = (f" on a solo dungeon's boss (the final boss has {SOLO_FINAL_BOSS_ARMOUR:,}; "
                 f"the game caps enemy armour at {ENEMY_ARMOUR_CAP:,})"
                 if on == "boss" else " on a solo dungeon's trash")
    elif instanced:
        where = " in instanced content"
    else:
        where = " overland"
    cap_text = f"cap {_num(cap)}{where}"
    pen_table = table(PEN_TITLE, cap_text, 3, pen_body, pen_totals)

    # Critical damage
    crit_body = [f"<tr>{cell('Base')}{cell(_num(CRIT_BASE, True), 'right')}{cell('every character', color=muted, extra=small)}</tr>"]
    crit_body.extend(own_cells(row, "crit") for row in rows if row.get("crit") is not None)
    if buffs:
        crit_body.append(group_header("Buffs on this player"))
        for b in buffs:
            uptime = f"{int(b.get('uptime_pct') or 0)}%"
            if b.get("via"):
                uptime += f" · {e(str(b['via']))}"
            crit_body.append(f"<tr>{cell(e(str(b['name'])))}{cell(_num(b['crit'], True), 'right')}"
                             f"{cell(uptime, color=muted, extra=small)}</tr>")
    crit_debuffs = [d for d in debuffs if d.get("crit")]
    if crit_debuffs:
        crit_body.append(group_header(f"Group {on_text}".strip()))
        crit_body.extend(group_row(d, "crit", True) for d in crit_debuffs)
    own_crit = [CRIT_BASE + v for v in static_crit]
    full_crit = own_crit[0] + sum(b["crit"] for b in buffs if b.get("uptime_pct")) \
        + sum(d["crit"] for d in crit_debuffs if d.get("uptime_pct"))
    crit_totals = [f"Own {_pair_text(own_crit, True)}"]
    if buffs or crit_debuffs:
        gap = full_crit - crit_cap
        crit_totals.append(f"With every buff and debuff at full uptime {_num(full_crit, True)}, "
                           + (f"over the cap by {_num(gap, True)}" if gap >= 0 else f"missing {_num(-gap, True)}"))
    if eff_crit.get("damage"):
        crit_totals.append(f"<b>Effective {_num(eff_crit['effective'], True)} of {_num(crit_cap, True)}</b> over this player's damage, "
                           f"{eff_crit['over_pct']:.0f}% of it dealt over the cap")
    elif not (buffs or crit_debuffs):
        crit_totals.append(f"<span style='color:{muted}'>{NO_DAMAGE_MEASURED}</span>")
    crit_cap_text = f"cap {_num(crit_cap, True)}" + (" with Above and Beyond" if crit_cap != CRIT_CAP else "")
    crit_table = table(CRIT_TITLE, crit_cap_text, 3, crit_body, crit_totals)

    # The named anchor lets a reader (the screenshot script) scroll to here
    return (f"<a name='{PEN_CRIT_ANCHOR}'></a>" + pen_table + crit_table
            + f"<p style='margin:6px 0;color:{muted};{small}'>{PEN_CRIT_NOTE}</p>")


def render_build_html(entry, unit_id, dark: bool = False, icons=None, links=None,
                      set_links=None, script_links=None, base_pt: float = 9.0,
                      text_color: Optional[str] = None, pen_crit_options: Optional[dict] = None,
                      names=None) -> str:
    """One player's build in a fight as HTML for the build window.

    icons: object with has(stem) -> bool (the view's IconCache); None draws
    the bars as names. links / set_links / script_links: callables name ->
    ESO-Hub URL or None, as for fight_render.render_html. base_pt: the pane's
    font size, which the title and the small print are scaled from (Qt rich
    text ignores percentage sizes). text_color: the pane's own text color,
    which set names keep although they are links. pen_crit_options: the
    config's pen_crit section (the assumed Champion Point rows and the cap);
    None assumes nothing and takes the cap from the zone. names: the Hide
    names mask (gui.name_mask) for the header and the casters.
    """
    theme = _theme(dark)
    names = names or NO_MASK
    e = html.escape
    p = player_for(entry, unit_id)
    if p is None:
        return f"<p style='color:{theme['muted']}'>{NO_BUILD}</p>"
    if p.get("companion"):
        # A companion's window: its skills, then the kinds of its damage
        # (damage_kinds), as the build window shows a player's
        return (_companion_html(entry, p, theme, icons, links, base_pt, e, names,
                                text_color or theme["text"])
                + _damage_dealt_html(p, dark, dict(theme, text=text_color or theme["text"]),
                                     base_pt, e))
    return "".join((
        _header_html(entry, p, theme, base_pt, e, names, text_color or theme["text"]),
        _mundus_food_html(p, theme, icons, e),
        # The possible build issues the fight pane's (i) shows, repeated
        # here where the build is read (build_issues)
        issues_html(p, dark, set_links, links, base_pt),
        _bars_html(p, theme, icons, links, script_links, base_pt, e),
        _gear_html(p, dark, theme, set_links, text_color or theme["text"], base_pt, e),
        # Magicka, stamina and ultimate spent and gained (resources)
        _resources_html(p, dark, theme, base_pt, e, names),
        # The kinds of the damage dealt (damage_kinds), before the
        # penetration and critical damage figures
        _damage_dealt_html(p, dark, dict(theme, text=text_color or theme["text"]), base_pt, e),
        _pen_crit_html(entry, p, dark, theme, pen_crit_options, base_pt, e, names),
    ))
