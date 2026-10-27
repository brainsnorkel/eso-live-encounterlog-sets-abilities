"""
Damage taken window: one player's damage taken and healing received over a
whole fight, by kind, by the unit that did it and by the unit that healed
(issue #98). The death recap keeps the last seconds before each death and
is only there for a player who died; this window has no event table, only
the fight's totals, so it opens for any player.

Design. What a tank wants to know after a pull is what hit them, who hit
them and whether the healing kept up, none of which the fight pane or the
build window says. The data is the player dict's 'taken' key, as
damage_kinds.TakenTally.snapshot writes it for every player in every fight.
The shape follows a survey of three veteran trial logs (Dreadsail Reef,
Sunspire, Halls of Fabrication; 48 boss fights of a minute or more, 561
player-fights with damage taken; 2026-10-27):

- Every ability is listed, no cap. A tank took damage from a median 11
  distinct abilities (at most 26) and 8 units (at most 29), a DPS from 7
  and 5 or 6; the ten largest abilities carried everything in the median
  fight, so the table is short enough to read whole.
- Damage is grouped by the unit that did it, bosses first. The largest
  source carried about half the damage and the second a fifth, so "the
  boss against the adds" is the first question; units of one name are one
  row with their count, since adds come in packs (four Alkosh's Will on
  Nahviintaas). Bosses carried a median 44% of the damage taken in every
  role. The unit the log leaves unnamed (id 0: the environment, fall
  damage, some set procs) is its own row.
- The per-second figure divides by the fight time, pull to end, not the
  span of hits as the dps figures do: it is for comparing pulls, a quiet
  stretch is part of the answer, and the hits spanned only 64-80% of the
  fight (tanks most). Tanks took a median 1,016 a second, DPS 545, healers
  512.
- Healing is grouped by healer, with the healer's abilities under them.
  Six to eight units healed each player in the median fight (every group
  HoT counts) with 15-19 abilities between them; the largest healer gave
  51-65%, a tank's own heals 23% of what they received, a healer's own
  61%. A pet's heals (a Twilight Matriarch's) are a row of their own named
  after the owner, since the log names no pet.
- Overheal is a share per row, never an amount: 91-96% of all healing on a
  player overflowed, so the amounts would be ten to twenty times the received
  figures and bury them. Healing received is the headline; the share tells a
  healer which HoTs were wasted on this player.
- Shields absorbed 54-67% as much again as the damage that reached health
  (tanks most), so the header gives the absorbed amount with that ratio,
  and the blocked hits as a count of the direct hits that reached health
  (tanks blocked 1,818 of 5,729 in the survey). What a block, armour or
  resistances prevented is not in the log and is never stated.

The kinds bars are the death recap's block (death_render.kinds_block_html)
so the two windows read alike; the player names go through the Hide names
mask (gui.name_mask), the sources and healers included.
"""

import html

from damage_kinds import (
    AVOIDED_RESULTS,
    BLOCKED_RESULT,
    DIRECT_RESULTS,
    summary_of_taken,
)
from gui.build_render import player_for
from gui.death_render import (
    _THEMES,
    HOT_LABEL,
    ICON_PX,
    _icon_html,
    _kind_words,
    kinds_block_html,
)
from gui.fight_render import ROLE_NAMES, _fmt_duration, _join, _subclass_text, _theme
from gui.name_mask import NO_MASK

NO_PLAYER = "No player with this id was in the fight."
NOT_RECORDED = "Damage kinds were not recorded for this fight."
NO_DAMAGE_TAKEN = "This player took no damage in this fight."
NO_HEALING = "This player received no healing in this fight."
KINDS_TITLE = "Kinds of damage"
SOURCES_TITLE = "Damage by source"
HEALERS_TITLE = "Healing received"
UNNAMED_SOURCE = "No unit named in the log"  # unit id 0: environment, fall damage, set procs
BOSS_MARK = "boss"
PET_MARK = "pet"
SELF_MARK = "own"  # the player's heals on themselves
DASH = "–"
INDENT_PX = 14  # an ability row under its source or healer
# The small print under the tables
NOTES = (
    ("Per-second figures divide by the fight time, pull to end, so two pulls compare; "
     "the dps figures divide by the span of hits instead."),
    ("What a block, armour or resistances prevented is not in the log: a blocked hit's "
     "figure is what got through. What shields absorbed never reached health and sits "
     "outside the damage taken."),
    ("Overheal is the part of a heal past full health. A HoT ticking on a full bar is all "
     "overheal."),
)
SOURCE_COLUMNS = (("", "left"), ("Source · ability", "left"), ("Damage", "right"), ("%", "right"),
                  ("Hits", "right"), ("Max", "right"), ("Avg", "right"), ("Kind", "left"))
HEALER_COLUMNS = (("", "left"), ("Healer · ability", "left"), ("Received", "right"), ("%", "right"),
                  ("Hits", "right"), ("Overheal", "right"), ("Kind", "left"))


def taken_title(entry, unit_id, names=None) -> str:
    """Window title: 'Damage taken – @name'; *names* is the Hide names mask."""
    player = player_for(entry, unit_id)
    name = (names or NO_MASK).text(_join(player.get("name", ""))) if player else ""
    return f"Damage taken – {name}" if name else "Damage taken"


def _n(value) -> str:
    return f"{int(value or 0):,}"


def _rate(amount, seconds) -> str:
    """Amount per second, whole numbers: '1,016'."""
    return f"{amount / seconds:,.0f}" if seconds > 0 else DASH


def _pct(part, whole) -> str:
    return f"{round(100.0 * part / whole)}%" if whole else DASH


def _clock(ms) -> str:
    seconds = max(0, int(ms or 0) // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _header_html(entry, p, theme, vet_color: str, base_pt: float, e, names) -> str:
    """The player and the fight, as the damage window heads its page."""
    muted = theme["muted"]
    name = names.html(_join(p.get("name", "")), theme["text"], base_pt * 1.3, bold=True)
    facts = [ROLE_NAMES.get(p.get("role"), ""), str(p.get("class_name") or ""),
             _subclass_text(p)]
    vet = (f" <span style='color:{vet_color};font-weight:bold'>[VET]</span>"
           if getattr(entry, "is_vet", False) else "")
    zone = str(getattr(entry, "zone_name", "") or "")
    fight = [e(str(getattr(entry, "boss_name", "") or "")),
             f"{e(zone)}{vet}" if zone else "",
             e(str(getattr(entry, "timestamp", "") or ""))]
    return (f"<p style='margin:0'>"
            f"<span style='font-size:{base_pt * 1.3:.2f}pt;font-weight:bold'>{name}</span>"
            f"&nbsp;&nbsp; <span style='color:{muted}'>"
            f"{' · '.join(e(fact) for fact in facts if fact)}</span></p>"
            f"<p style='margin:2px 0;color:{muted}'>"
            f"{' · '.join(part for part in fight if part)}</p>")


def _figures_html(entry, taken: dict, theme, e) -> str:
    """The headline figures: damage taken and its rate over the fight, the
    healing received and its rate with the overheal share, and the
    mitigation the log does carry: shields, blocked hits, avoided hits."""
    muted = theme["muted"]
    fight_s = float(getattr(entry, "duration_s", 0) or 0)
    total = int(taken.get("total") or 0)
    healed = int(taken.get("healed") or 0)
    overheal = int(taken.get("overheal") or 0)
    absorbed = int(taken.get("absorbed") or 0)
    lines = []
    damage = f"<b>{_n(total)}</b> damage taken"
    if fight_s > 0 and total:
        damage += (f" · <b>{_rate(total, fight_s)}</b> a second of the "
                   f"{_fmt_duration(fight_s)} fight")
    first, last = taken.get("first_ms"), taken.get("last_ms")
    if total and first is not None and last is not None and int(last) - int(first) >= 1000:
        damage += (f" <span style='color:{muted}'>· hits over {_clock(int(last) - int(first))}, "
                   f"first to last</span>")
    lines.append(damage)
    heal = f"<span style='color:{theme['heal']}'><b>{_n(healed)}</b> healing received</span>"
    if fight_s > 0 and healed:
        heal += f" · <b>{_rate(healed, fight_s)}</b> a second"
    if healed + overheal:
        heal += (f" <span style='color:{muted}'>· {_pct(overheal, healed + overheal)} of all "
                 f"healing on this player was overheal</span>")
    lines.append(heal)
    bits = []
    if absorbed:
        ratio = f", {_pct(absorbed, total)} as much as reached health" if total else ""
        bits.append(f"<span style='color:{theme['shield']}'>shields absorbed "
                    f"<b>{_n(absorbed)}</b></span>{ratio}")
    results = taken.get("results")
    if isinstance(results, dict):
        direct_hits = sum(int(results.get(r) or 0) for r in DIRECT_RESULTS)
        blocked = int(results.get(BLOCKED_RESULT) or 0)
        if direct_hits:
            noun = "hit" if direct_hits == 1 else "hits"
            bits.append(f"blocked <b>{blocked}</b> of {direct_hits} direct {noun}")
        avoided = sum(int(results.get(r) or 0) for r in AVOIDED_RESULTS)
        if avoided:
            bits.append(f"dodged or missed by <b>{avoided}</b>")
    if bits:
        lines.append(" · ".join(bits))
    return "".join(f"<p style='margin:{'8px' if i == 0 else '2px'} 0 2px 0'>{line}</p>"
                   for i, line in enumerate(lines))


def _section_title(text: str, theme, dark: bool, anchor: str = "") -> str:
    rule = "#45494f" if dark else "#d6d9dc"
    name = f"<a name='{anchor}'></a>" if anchor else ""
    return (f"{name}<p style='margin:10px 0 2px 0;padding-top:7px;color:{theme['muted']};"
            f"font-weight:bold;border-bottom-style:solid;border-bottom-width:1px;"
            f"border-bottom-color:{rule}'>{text}</p>")


def _table_open(columns, theme) -> str:
    head = (f"style='color:{theme['muted']};border-bottom-style:solid;"
            f"border-bottom-width:1px;border-bottom-color:{theme['rule']}'")
    cells = []
    for title, align in columns:
        width = f" width='{ICON_PX}'" if not title else ""
        cells.append(f"<td align='{align}'{width} {head}>{title}</td>")
    return (f"<table cellpadding='3' cellspacing='0' width='99%'><tr>{''.join(cells)}</tr>")


def _cells(cells, pad: str = "") -> str:
    """One row: (attrs, style, content) per cell."""
    return "<tr>" + "".join(
        f"<td{attrs} valign='middle' style='{pad}{style}'>{content}</td>"
        for attrs, style, content in cells) + "</tr>"


def _unit_name(group: dict, marks, theme, e, names, base_pt: float) -> str:
    """A source's or healer's name through the mask, bold, with its muted
    marks ('boss', '×4', 'pet', 'own') after it; the unnamed unit's line."""
    muted = theme["muted"]
    if group.get("unnamed"):
        text = f"<span style='color:{muted}'>{UNNAMED_SOURCE}</span>"
    else:
        text = f"<b>{names.html(str(group.get('name') or ''), theme['text'], base_pt, bold=True)}</b>"
    marks = [m for m in marks if m]
    if marks:
        text += f" <span style='color:{muted}'>{' · '.join(e(m) for m in marks)}</span>"
    return text


def _sources_html(taken: dict, theme, dark: bool, icons, e, names, base_pt: float) -> str:
    """The damage by the unit that did it, bosses first, each unit's
    abilities under it (see the module notes)."""
    muted = theme["muted"]
    parts = [_section_title(SOURCES_TITLE, theme, dark, "sources")]
    sources = taken.get("sources")
    total = int(taken.get("total") or 0)
    if not isinstance(sources, list):
        parts.append(f"<p style='margin:0;color:{muted}'>{NOT_RECORDED}</p>")
        return "".join(parts)
    if not sources or not total:
        parts.append(f"<p style='margin:0;color:{muted}'>{NO_DAMAGE_TAKEN}</p>")
        return "".join(parts)
    parts.append(_table_open(SOURCE_COLUMNS, theme))
    indent = f"padding-left:{INDENT_PX}px;"
    for group in sources:
        units = int(group.get("units") or 0)
        marks = (BOSS_MARK if group.get("boss") else "", f"×{units}" if units > 1 else "")
        damage = int(group.get("damage") or 0)
        hits = int(group.get("hits") or 0)
        parts.append(_cells((
            (f" width='{ICON_PX}'", "", ""),
            ("", "", _unit_name(group, marks, theme, e, names, base_pt)),
            (" align='right'", "", f"<b><span style='color:{theme['damage']}'>{_n(damage)}</span></b>"),
            (" align='right'", "", f"<b>{_pct(damage, total)}</b>"),
            (" align='right'", "", f"<b>{_n(hits)}</b>"),
            (" align='right'", "", _n(group.get("max"))),
            (" align='right'", "", _n(damage / hits) if hits else DASH),
            ("", "", ""),
        ), pad="padding-top:5px;"))
        for row in group.get("abilities") or []:
            icon = _icon_html(row, icons)
            pad = "" if icon else "padding-top:4px;padding-bottom:4px;"
            row_damage = int(row.get("damage") or 0)
            row_hits = int(row.get("hits") or 0)
            parts.append(_cells((
                (f" width='{ICON_PX}'", "", icon),
                ("", indent, e(str(row.get("name") or ""))),
                (" align='right'", "", f"<span style='color:{theme['damage']}'>{_n(row_damage)}</span>"),
                (" align='right'", "", _pct(row_damage, total)),
                (" align='right'", "", _n(row_hits)),
                (" align='right'", "", _n(row.get("max"))),
                (" align='right'", "", _n(row_damage / row_hits) if row_hits else DASH),
                ("", "", f"<span style='color:{muted}'>{e(_kind_words(row))}</span>"),
            ), pad=pad))
    parts.append("</table>")
    return "".join(parts)


def _heal_kind_words(row: dict) -> str:
    """'HoT', 'direct', or 'HoT 70% · direct 30%' for a healer's mix."""
    hot = int(row.get("hot") or 0)
    direct = int(row.get("direct") or 0)
    if hot and direct:
        return f"{HOT_LABEL} {_pct(hot, hot + direct)} · direct {_pct(direct, hot + direct)}"
    if hot:
        return HOT_LABEL
    if direct:
        return "direct"
    return ""


def _healers_html(taken: dict, theme, dark: bool, icons, e, names, base_pt: float) -> str:
    """The healing by the unit that did it, by amount received, each unit's
    abilities under it; the overheal as a share of that row's healing."""
    muted = theme["muted"]
    parts = [_section_title(HEALERS_TITLE, theme, dark, "healers")]
    healers = taken.get("healers")
    healed = int(taken.get("healed") or 0)
    overheal = int(taken.get("overheal") or 0)
    if not isinstance(healers, list):
        parts.append(f"<p style='margin:0;color:{muted}'>{NOT_RECORDED}</p>")
        return "".join(parts)
    if not healers or not (healed or overheal):
        parts.append(f"<p style='margin:0;color:{muted}'>{NO_HEALING}</p>")
        return "".join(parts)
    parts.append(_table_open(HEALER_COLUMNS, theme))
    indent = f"padding-left:{INDENT_PX}px;"

    def overheal_cell(row):
        landed, over = int(row.get("landed") or 0), int(row.get("overheal") or 0)
        return f"<span style='color:{muted}'>{_pct(over, landed + over)}</span>" if landed + over else DASH

    for healer in healers:
        marks = (SELF_MARK if healer.get("self") else "", PET_MARK if healer.get("pet") else "")
        landed = int(healer.get("landed") or 0)
        parts.append(_cells((
            (f" width='{ICON_PX}'", "", ""),
            ("", "", _unit_name(healer, marks, theme, e, names, base_pt)),
            (" align='right'", "", f"<b><span style='color:{theme['heal']}'>{_n(landed)}</span></b>"),
            (" align='right'", "", f"<b>{_pct(landed, healed)}</b>"),
            (" align='right'", "", f"<b>{_n(healer.get('hits'))}</b>"),
            (" align='right'", "", overheal_cell(healer)),
            ("", "", f"<span style='color:{muted}'>{e(_heal_kind_words(healer))}</span>"),
        ), pad="padding-top:5px;"))
        for row in healer.get("abilities") or []:
            icon = _icon_html(row, icons)
            pad = "" if icon else "padding-top:4px;padding-bottom:4px;"
            row_landed = int(row.get("landed") or 0)
            parts.append(_cells((
                (f" width='{ICON_PX}'", "", icon),
                ("", indent, e(str(row.get("name") or ""))),
                (" align='right'", "", f"<span style='color:{theme['heal']}'>{_n(row_landed)}</span>"),
                (" align='right'", "", _pct(row_landed, healed)),
                (" align='right'", "", _n(row.get("hits"))),
                (" align='right'", "", overheal_cell(row)),
                ("", "", f"<span style='color:{muted}'>{e(_heal_kind_words(row))}</span>"),
            ), pad=pad))
    parts.append("</table>")
    return "".join(parts)


def _notes_html(taken: dict, theme, base_pt: float) -> str:
    muted = theme["muted"]
    small = f"font-size:{base_pt * 0.85:.2f}pt"
    notes = list(NOTES)
    rules = taken.get("rules") or {}
    total = int(taken.get("total") or 0)
    table_share = int(rules.get("table") or 0)
    if total and table_share:
        notes.append(f"Area or single target: {round(100.0 * table_share / total)}% of the damage "
                     f"classed by the skill table (a player's own skill), the rest by the casts.")
    return "".join(f"<p style='margin:{'8px' if i == 0 else '1px'} 0 1px 0;color:{muted};{small}'>"
                   f"{html.escape(note)}</p>" for i, note in enumerate(notes))


def render_taken_html(entry, unit_id, dark: bool = False, icons=None, base_pt: float = 9.0,
                      names=None, text_color: str | None = None) -> str:
    """One player's damage taken and healing received in a fight as HTML
    for the damage taken window.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    leaves the abilities as names. base_pt: the pane's font size, which the
    title and the small print are scaled from. names: the Hide names mask
    (gui.name_mask) for the title, the player sources and the healers.
    text_color: the pane's own text colour, which a hidden name is drawn
    in. The hover text for the star links is death_render.kind_tooltips().
    """
    theme = dict(_THEMES[bool(dark)])
    if text_color:
        theme["text"] = text_color
    names = names or NO_MASK
    e = html.escape
    p = player_for(entry, unit_id)
    if p is None:
        return f"<p style='color:{theme['muted']}'>{NO_PLAYER}</p>"
    parts = [_header_html(entry, p, theme, _theme(dark)["vet"], base_pt, e, names)]
    taken = p.get("taken")
    if not isinstance(taken, dict) or "total" not in taken:
        parts.append(f"<p style='margin:8px 0;color:{theme['muted']}'>{NOT_RECORDED}</p>")
        return "".join(parts)
    parts.append(_figures_html(entry, taken, theme, e))
    parts.append(_section_title(KINDS_TITLE, theme, dark, "kinds"))
    parts.append(kinds_block_html(summary_of_taken(taken), "taken", theme, e, base_pt,
                                  "taken in this fight", NO_DAMAGE_TAKEN))
    parts.append(_sources_html(taken, theme, dark, icons, e, names, base_pt))
    parts.append(_healers_html(taken, theme, dark, icons, e, names, base_pt))
    parts.append(_notes_html(taken, theme, base_pt))
    return "".join(parts)
