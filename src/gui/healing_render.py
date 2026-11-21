"""
The Healing done tab (issue #242): one player's heals on the rest of the
group over a fight, by ability and by the player healed, from the player
dict's 'healing_done' (damage_kinds.healing_done).

Design. The fight pane's healing token says how much a healer healed (see
fight_render); this page says with what and on whom, as Damage done does for
damage. The figures follow a survey of the maintainer's 419 split logs
(2026-11-21; 2,547 healer-fights, the H rows of boss fights of 30 s or
more):

- The headline is the row's healing to others with its rate over the fight
  time and its share of the group's, the token's three figures, then the
  share of the player's heals on others that overflowed.
- Abilities are one row per name, a skill's ids added up, as on Healing
  received (taken_render.merged_abilities, which both pages use, says why
  with the numbers). Kind gives the mix, 'HoT 70% · direct 30%'. A pet's
  abilities (a Twilight Matriarch's) are rows of their own, marked.
- A healer had a median 8 abilities that landed (at most 17), so every one
  is listed. The abilities whose every heal on another player overflowed
  (a median 2, at most 8) are named on one line under the table, since a
  row of 0 healed says nothing but that.
- Overheal is a share of the row's heals on others, as on Healing received:
  about nine tenths of all healing in a trial overflows.
- The players healed follow, by what each received from this player: a
  median 11 in those fights, everyone else in a trial. A player without a
  row of the fight's (their build never reached the log) is listed too.
- Heals on themselves are not healing to others, as on the row: one line
  gives their total (a median 13% of an H row's own heals and heals on
  others together) and links to Healing received, which lists them by
  ability, marked own.

Names go through the Hide names mask (gui.name_mask), the players healed
included.
"""

import html

from gui.build_render import player_for
from gui.death_render import _THEMES, ICON_PX, _icon_html
from gui.fight_render import (
    _fmt_duration,
    _join,
    _theme,
    group_healing,
    healing_href,
    share_text,
)
from gui.name_mask import NO_MASK
from gui.taken_render import (
    DASH,
    _cells,
    _header_html,
    _heal_kind_words,
    _n,
    _pct,
    _rate,
    _section_title,
    _table_open,
    merged_abilities,
)
from gui.text_size import scaled_px

NO_PLAYER = "No player with this id was in the fight."
NOT_RECORDED = "Healing done was not recorded for this fight."
NO_HEALING_DONE = "This player healed nobody else in this fight."
ABILITIES_TITLE = "By ability"
TARGETS_TITLE = "Players healed"
OVERHEAL_ONLY = "All overheal on others"
PET_MARK = "(pet)"
COMPANION_MARK = "(companion)"
OWN_LINK_WORDS = "Healing received"
ABILITY_COLUMNS = (("", "left"), ("Ability", "left"), ("Healed", "right"), ("%", "right"),
                   ("Hits", "right"), ("Overheal", "right"), ("Kind", "left"))
TARGET_COLUMNS = (("Player", "left"), ("Healed", "right"), ("%", "right"), ("Hits", "right"),
                  ("Overheal", "right"))
# The small print under the tables
PER_SECOND_NOTE = ("Healing to others is what the player's heals, and their pets', restored to "
                   "other players, over the fight time, pull to end: not their heals on "
                   "themselves and not the overheal.")
SHIELD_NOTE = ("Damage shields are not in it: what a shield absorbs is counted on the hit it "
               "stopped, as the Damage taken tab's shields absorbed, never as a heal.")
SHARE_NOTE = ("Healers draw on one supply of missing health, so a share says who reached it "
              "first, not how well each healed; a pull with little damage to heal reads low.")
NOTES = (PER_SECOND_NOTE, SHIELD_NOTE, SHARE_NOTE)


def healing_done_title(entry, unit_id, names=None) -> str:
    """Window title: 'Healing done – @name'; *names* is the Hide names mask."""
    player = player_for(entry, unit_id)
    name = (names or NO_MASK).text(_join(player.get("name", ""))) if player else ""
    return f"Healing done – {name}" if name else "Healing done"


def _paragraphs(lines) -> str:
    return "".join(f"<p style='margin:{'0' if i == 0 else '2px'} 0 2px 0'>{text}</p>"
                   for i, text in enumerate(lines))


def _figure_lines(entry, p, done: dict, theme) -> list[str]:
    """The headline, healing to others with its rate and its share of the
    group's (the row's token), then the overheal share."""
    fight_s = float(getattr(entry, "duration_s", 0) or 0)
    healed = int(p.get("healing") or 0)
    group = group_healing(entry)
    line = f"<span style='color:{theme['heal']}'><b>{_n(healed)}</b> healing to others</span>"
    if fight_s > 0:
        line += f" · <b>{_rate(healed, fight_s)}</b> a second of the {_fmt_duration(fight_s)} fight"
    if group > 0:
        # Escaped: under one percent the share is '<1%', which Qt would
        # read as the start of a tag
        line += (f" · <b>{html.escape(share_text(100.0 * healed / group))}</b> "
                 f"of the group's {_n(group)}")
    lines = [line]
    landed, overheal = int(done.get("landed") or 0), int(done.get("overheal") or 0)
    if landed + overheal:
        lines.append(f"<span style='color:{theme['muted']}'>{_pct(overheal, landed + overheal)} "
                     f"of their healing on others was overheal</span>")
    return lines


def _own_lines(done: dict, theme, unit_id) -> list[str]:
    """The heals on themselves in one line, linking to Healing received,
    where they are listed by ability; none without any."""
    own = done.get("own") if isinstance(done.get("own"), dict) else {}
    if not int(own.get("landed") or 0):
        return []
    link = (f"<a href='{html.escape(healing_href(unit_id), quote=True)}' "
            f"style='text-decoration:none;color:{theme['link']}'>{OWN_LINK_WORDS}</a>")
    return [(f"<span style='color:{theme['muted']}'>Heals on themselves: "
             f"<b>{_n(own['landed'])}</b>, not in these figures; listed on {link}, marked own</span>")]


def _overheal_cell(row, muted: str) -> str:
    landed, over = int(row.get("landed") or 0), int(row.get("overheal") or 0)
    return f"<span style='color:{muted}'>{_pct(over, landed + over)}</span>" if landed + over else DASH


def _abilities_html(done: dict, theme, dark: bool, icons, e) -> str:
    """The abilities by healing to others, one row per name; the ones that
    only overflowed named on a line under the table."""
    muted = theme["muted"]
    parts = [_section_title(ABILITIES_TITLE, theme, dark, "abilities")]
    rows = merged_abilities(done.get("abilities"))
    total = int(done.get("landed") or 0)
    landed = [row for row in rows if row["landed"] > 0]
    if landed:
        parts.append(_table_open(ABILITY_COLUMNS, theme))
        for row in landed:
            icon = _icon_html(row, icons)
            pad = "" if icon else "padding-top:4px;padding-bottom:4px;"
            name = e(row["name"])
            mark = PET_MARK if row["via"] == "pet" else COMPANION_MARK if row["via"] else ""
            if mark:
                name += f" <span style='color:{muted}'>{mark}</span>"
            parts.append(_cells((
                (f" width='{scaled_px(ICON_PX)}'", "", icon),
                ("", "", name),
                (" align='right'", "", f"<span style='color:{theme['heal']}'>{_n(row['landed'])}</span>"),
                (" align='right'", "", _pct(row["landed"], total)),
                (" align='right'", "", _n(row["hits"])),
                (" align='right'", "", _overheal_cell(row, muted)),
                ("", "", f"<span style='color:{muted}'>{e(_heal_kind_words(row))}</span>"),
            ), pad=pad))
        parts.append("</table>")
    only = [row for row in rows if row["landed"] <= 0 and row["overheal"] > 0]
    if only:
        names = ", ".join(e(row["name"]) + (f" {PET_MARK}" if row["via"] == "pet" else "")
                          for row in only)
        parts.append(f"<p style='margin:4px 0 0 0;color:{muted}'>{OVERHEAL_ONLY}: {names}</p>")
    return "".join(parts)


def _targets_html(done: dict, theme, dark: bool, e, names, base_pt: float) -> str:
    """The players healed, by what each received from this player."""
    muted = theme["muted"]
    parts = [_section_title(TARGETS_TITLE, theme, dark, "players")]
    total = int(done.get("landed") or 0)
    targets = [t for t in done.get("targets") or [] if int(t.get("landed") or 0) > 0]
    if not targets:
        return ""
    parts.append(_table_open(TARGET_COLUMNS, theme))
    for target in targets:
        landed = int(target.get("landed") or 0)
        name = names.html(str(target.get("name") or ""), theme["text"], base_pt)
        parts.append(_cells((
            ("", "", name),
            (" align='right'", "", f"<span style='color:{theme['heal']}'>{_n(landed)}</span>"),
            (" align='right'", "", _pct(landed, total)),
            (" align='right'", "", _n(target.get("hits"))),
            (" align='right'", "", _overheal_cell(target, muted)),
        ), pad="padding-top:3px;padding-bottom:3px;"))
    parts.append("</table>")
    return "".join(parts)


def _notes_html(theme, base_pt: float) -> str:
    small = f"font-size:{base_pt * 0.85:.2f}pt"
    return "".join(f"<p style='margin:{'8px' if i == 0 else '1px'} 0 1px 0;"
                   f"color:{theme['muted']};{small}'>{html.escape(note)}</p>"
                   for i, note in enumerate(NOTES))


def render_healing_done_html(entry, unit_id, dark: bool = False, icons=None,
                             base_pt: float = 9.0, names=None, text_color: str | None = None,
                             header: bool = False) -> str:
    """One player's healing done in a fight as HTML for the Healing done
    tab.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    leaves the abilities as names. base_pt: the page's font size, which the
    small print is scaled from. names: the Hide names mask (gui.name_mask)
    for the players healed. text_color: the page's own text colour, which a
    hidden name is drawn in. header: the page's own header naming the
    player and the fight, for a page outside the player window (whose
    header names them)."""
    theme = dict(_THEMES[bool(dark)])
    if text_color:
        theme["text"] = text_color
    theme["link"] = _theme(dark)["link"]
    names = names or NO_MASK
    e = html.escape
    p = player_for(entry, unit_id)
    if p is None:
        return f"<p style='color:{theme['muted']}'>{NO_PLAYER}</p>"
    parts = [_header_html(entry, p, theme, _theme(dark)["vet"], base_pt, e, names)] if header else []
    done = p.get("healing_done")
    if not isinstance(done, dict):
        parts.append(f"<p style='margin:8px 0;color:{theme['muted']}'>{NOT_RECORDED}</p>")
        return "".join(parts)
    if int(p.get("healing") or 0) <= 0 and not int(done.get("landed") or 0):
        parts.append(_paragraphs([f"<span style='color:{theme['muted']}'>{NO_HEALING_DONE}</span>",
                                  *_own_lines(done, theme, unit_id)]))
        return "".join(parts)
    parts.append(_paragraphs(_figure_lines(entry, p, done, theme) + _own_lines(done, theme, unit_id)))
    parts.append(_abilities_html(done, theme, dark, icons, e))
    parts.append(_targets_html(done, theme, dark, e, names, base_pt))
    parts.append(_notes_html(theme, base_pt))
    return "".join(parts)
