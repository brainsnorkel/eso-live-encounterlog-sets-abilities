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

Werewolf form: the log never writes a werewolf's own bar, so the engine
rebuilds it from the skills the player cast in form (see werewolf.py). The
build card shows it on a line of its own after the human bars, "Werewolf",
with the share of the fight spent in form, and the plain-text copy adds the
same line. A Rampage the log listed in a human bar is drawn as the morph it
stands in for. The hover on either kind of slot says so, which is why such
a slot's anchor carries a fragment of its own, as a scribed skill's does.

In a solo dungeon a line under the header names the Misfortunes the run
was started with, each name's hover saying what it does, or reads
"Misfortunes: none" (see misfortunes.py); the plain-text copy adds the same
line. Nothing shows in any other zone.

A player who died in the fight gets a death-recap button beside their name
(see death_render); the fight view opens the recap window when it is clicked.

A player whose build has a possible issue (see build_issues) gets a circled
i after their class, in the link color, the same mark the fight list puts
on the fight; hovering it lists the findings and
clicking it opens a popup with each finding and the rule behind it
(issues_html, which the build window shows too). A player without findings
keeps a plain row.

A player's name is a link to their build window (see build_render): it looks
like the plain bold name it replaces, and the fight view underlines it in the
theme's link color while the pointer is over it. Their dps figure is the same
kind of link to their damage window (see damage_render), and its hover text
gives the dps time the figure divides by (see damage_stats). The dps figures,
a player's and the header's group figure, also carry a small glyph inside
their anchor that says they can be clicked (see gui.glyphs); the names do not.

Dps and share cells read 'boss / total' in a fight with a boss: the dps
against the units the game flags as bosses and against everything, and the
player's share of the group's boss damage and of all its damage.

After the shares, 'p:18199 cd:121%': the player's effective penetration and
critical damage over this fight's damage (pen_crit.cap_shares, the same
sums the build window's sections show, the Settings' assumed Champion Point
rows included; each second capped, so a figure at the cap reads as the
cap). It is muted and looks like text, as the dps figure does, and is a
link to the build window opened at those sections; its hover text gives
the caps, the shares of them and the share of damage dealt over them. A
player with no damage to weigh has none, and so does an entry built before
the figures existed. The plain-text copy adds the same token to the
player's line.
"""

import html
import zlib
from typing import List, Optional, Tuple

from ability_icons import slugify
from gui.death_render import death_chip_html, deaths_by_unit
from gui.name_mask import NO_MASK
from pen_crit import cap_shares
from scribing import scribed_label, slot_label

ROLE_NAMES = {"T": "Tank", "H": "Healer", "D": "DPS", "C": "Companion"}
COMPANION_INDENT = "↳ "  # before a companion's name, under its owner's row (companions.py)

ICON_PX = 22  # rendered edge of an ability icon in the detail pane
SCRIBED_ICON_PX = 14  # grimoire icon beside a scribed skill's scripts
BAR_DIVIDER = "│"  # between bar 1 and bar 2 when both are icon rows
DEATH_CUE = "☠"  # history-list mark on a fight in which a player died: skull and crossbones
ISSUES_LIST_CUE = "ⓘ"  # history-list mark on a fight with a player whose build has a finding: circled i
SCRIPT_KINDS = ("Focus", "Signature", "Affix")  # order of a slot's 'scripts'
SCRIPTS_UNKNOWN = "scripts not in log"
BUILD_HREF = "esolog:build/"  # + the player's unit id
DAMAGE_HREF = "esolog:damage/"  # + the player's unit id
GRAPH_HREF = "esolog:graph/"  # the header's group dps figure: the dps over time graph
ISSUES_HREF = "esolog:issues/"  # + the player's unit id: the cue of possible build issues
# + the player's unit id: the row's 'p:18199 cd:121%' token, their effective
# penetration and critical damage over the fight (pen_crit); a click opens
# the build window at its Penetration and Critical damage sections
PEN_CRIT_HREF = "esolog:pencrit/"
# + the Misfortune's place on the line: a solo dungeon run's Misfortune
# under the header, whose hover gives what it does (misfortunes.py)
MISFORTUNE_HREF = "esolog:misfortune/"
PEN_CRIT_TITLE = "Penetration and critical damage"
# The cue itself, a circled i like the fight list's mark (ISSUES_LIST_CUE),
# shown only on a player with a finding
ISSUES_CUE = "ⓘ"
ISSUES_TITLE = "Possible build issues"
# The glyph after a dps figure that says it can be clicked (see gui.glyphs):
# glyph:<kind>?color=rrggbb&px=<n>, drawn by the fight view
GLYPH_SCHEME = "glyph"
GRAPH_GLYPH = "graph"  # after the header's group dps figure
BREAKDOWN_GLYPH = "breakdown"  # after a player's dps figure
# A player's bars as the entry holds them: the two the log writes, then the
# werewolf bar rebuilt from casts (werewolf.py)
BAR_KEYS = ("front_bar_slots", "back_bar_slots", "werewolf_bar_slots")
WEREWOLF_LABEL = "Werewolf"
WEREWOLF_NOTE = ("Werewolf bar: the log does not record it, so it is rebuilt from the "
                 "skills this player cast in werewolf form, in the skill line's order")
STAND_IN_NOTE = "Listed as {stand_in} at the start of the fight, as the slot reads at full Fury"

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


def build_tooltips(entry, names=None) -> dict:
    """Hover text per player-name link: the handle, the character name
    under it when the log gave both (issue #71), and that a click opens
    the build window. *names*: the Hide names mask (gui.name_mask), which
    hides another player's handle and character name alike."""
    names = names or NO_MASK
    e = html.escape
    tips = {}
    for p in entry.players:
        unit_id = str(p.get("unit_id", ""))
        if not unit_id:
            continue
        name = _join(p.get("name", ""))
        character = str(p.get("character") or "")
        lines = [f"<b>{e(names.text(name))}</b>"]
        if character and character != name:
            lines.append(e(names.text(character)))
        if p.get("companion"):
            lines.append("<span style='font-size:85%'>Companion. Click for the skills it "
                         "was seen casting</span>")
        else:
            lines.append("<span style='font-size:85%'>Click for the full build: bars, gear, "
                         "mundus and food</span>")
        tips[build_href(unit_id)] = "<br>".join(lines)
    return tips


def glyph_px(base_pt: float) -> int:
    """Edge of a link glyph in a pane whose font is *base_pt* points: a
    little taller than the x-height (13 px at 9 pt)."""
    return max(8, round(float(base_pt) * 96 / 72 * 1.1))


def glyph_html(kind: str, color: str, px: int) -> str:
    """The <img> of a link glyph (see gui.glyphs) in *color* ('#rrggbb'),
    *px* pixels square."""
    return (f'<img src="{GLYPH_SCHEME}:{kind}?color={color.lstrip("#")}&amp;px={px}" '
            f'style="vertical-align:middle">')


def damage_href(unit_id) -> str:
    return f"{DAMAGE_HREF}{unit_id}"


def damage_unit_from_href(href: str) -> Optional[str]:
    """The player's unit id when *href* is a dps-figure link, else None."""
    if href and href.startswith(DAMAGE_HREF):
        return href[len(DAMAGE_HREF):]
    return None


def issues_href(unit_id) -> str:
    return f"{ISSUES_HREF}{unit_id}"


def issues_unit_from_href(href: str) -> Optional[str]:
    """The player's unit id when *href* is a build-issues (i), else None."""
    if href and href.startswith(ISSUES_HREF):
        return href[len(ISSUES_HREF):]
    return None


def issues_tooltips(entry) -> dict:
    """Hover text per (i): the findings' titles, and that a click gives the
    rules behind them (see build_issues)."""
    e = html.escape
    tips = {}
    for p in entry.players:
        unit_id = str(p.get("unit_id", ""))
        findings = p.get("build_issues") or []
        if unit_id and findings:
            titles = "<br>".join(f"• {e(str(f.get('title', '')))}" for f in findings)
            tips[issues_href(unit_id)] = (
                f"<b>{ISSUES_TITLE}</b><br>{titles}<br>"
                f"<span style='font-size:85%'>Click for the rules behind them</span>")
    return tips


def misfortunes_text(entry) -> str:
    """'Misfortunes: Warm Welcome · Revoke of Respite' for a solo dungeon
    run, 'Misfortunes: none' for one without any, '' anywhere else and on
    an entry built before the line existed (issue #70)."""
    items = getattr(entry, "misfortunes", None)
    if items is None:
        return ""
    return "Misfortunes: " + (" · ".join(str(name) for name, _text in items) or "none")


def misfortunes_tooltips(entry) -> dict:
    """Hover text per Misfortune on the line: its name and what it does; one
    named only by the log (no text) has none."""
    e = html.escape
    return {f"{MISFORTUNE_HREF}{i}": f"<b>{e(str(name))}</b><br>{e(str(text))}"
            for i, (name, text) in enumerate(getattr(entry, "misfortunes", None) or [])
            if text}


def pen_crit_href(unit_id) -> str:
    return f"{PEN_CRIT_HREF}{unit_id}"


def pen_crit_unit_from_href(href: str) -> Optional[str]:
    """The player's unit id when *href* is a row's pen/crit token, else None."""
    if href and href.startswith(PEN_CRIT_HREF):
        return href[len(PEN_CRIT_HREF):]
    return None


def pen_crit_shares(entry, p, options) -> Optional[dict]:
    """The row's cap shares for a player (pen_crit.cap_shares), None when
    the entry has no figures or the player dealt no damage."""
    return cap_shares(p.get("pen_crit"), getattr(entry, "pen_crit", None), options)


def pen_crit_text(shares: Optional[dict]) -> str:
    """'p:18199 cd:121%': the player's effective penetration and critical
    damage over this fight (Chris's format, 2026-10-24: the raw figures,
    nothing spelled out); '' without figures."""
    if not shares:
        return ""
    return f"p:{shares['pen']:.0f} cd:{shares['crit']:.0f}%"


def pen_crit_tooltips(entry, options=None) -> dict:
    """Hover text per row token: the effective figures against the caps and
    the share of damage dealt over each, that they are estimates, and that
    a click opens the build window's sections."""
    tips = {}
    for p in entry.players:
        unit_id = str(p.get("unit_id", ""))
        shares = pen_crit_shares(entry, p, options) if unit_id else None
        if not shares:
            continue
        tips[pen_crit_href(unit_id)] = (
            f"<b>{PEN_CRIT_TITLE}</b><br>"
            f"Effective penetration {shares['pen']:,.0f} of {shares['pen_cap']:,} "
            f"({shares['pen_pct']}% of the cap), {shares['pen_over_pct']:.0f}% of the damage "
            f"dealt over it<br>"
            f"Effective critical damage {shares['crit']:.1f}% of {shares['crit_cap']}% "
            f"({shares['crit_pct']}% of the cap), {shares['crit_over_pct']:.0f}% of the damage "
            f"dealt over it<br>"
            f"<span style='font-size:85%'>Estimated from the build, the fight's effects and "
            f"the Champion Point rows Settings assumes. Click for every source</span>")
    return tips


def issues_html(p, dark: bool = False, set_links=None, links=None,
                base_pt: float = 9.0) -> str:
    """A player's possible build issues as HTML: the heading, then each
    finding's title in bold over the rule behind it, with an ESO-Hub link
    for the set or skill it names when the maps know the page. '' for a
    player without findings. Shown in the (i) popup and the build window."""
    findings = (p or {}).get("build_issues") or []
    if not findings:
        return ""
    theme = _theme(dark)
    e = html.escape
    rows = []
    for finding in findings:
        extras = []
        for key, lookup in (("set", set_links), ("skill", links)):
            name = str(finding.get(key) or "")
            url = lookup(name) if lookup and name else None
            if url:
                extras.append(f'<a href="{e(url, quote=True)}" style="color:{theme["link"]}">'
                              f'{e(name)} on ESO-Hub</a>')
        extra = (f"<br><span style='font-size:{base_pt * 0.85:.2f}pt'>"
                 f"{' · '.join(extras)}</span>" if extras else "")
        rows.append(
            f"<tr><td valign='top' style='color:{theme['link']}'>{ISSUES_CUE}</td>"
            f"<td style='padding-bottom:6px'><b>{e(str(finding.get('title', '')))}</b><br>"
            f"<span style='color:{theme['detail']}'>{e(str(finding.get('detail', '')))}</span>"
            f"{extra}</td></tr>")
    return (f"<p style='margin:6px 0 2px 0'><b>{ISSUES_TITLE}</b></p>"
            f"<table cellpadding='2' cellspacing='0'>{''.join(rows)}</table>")


def _dps_time_text(seconds: float) -> str:
    """A dps time for the fight pane: never under its one-second floor."""
    return _fmt_duration(max(float(seconds or 0), 1.0))


def damage_tooltips(entry, names=None) -> dict:
    """Hover text per dps-figure link: the dps time each figure divides by
    (see damage_stats), the figures over the whole fight for comparison,
    and that a click opens the damage window; for the header's group
    figure, that a click opens the dps over time graph. *names*: the Hide
    names mask (gui.name_mask)."""
    names = names or NO_MASK
    e = html.escape
    tips = {}
    fight_s = float(getattr(entry, "duration_s", 0) or 0)
    boss_fight = _is_boss_fight(entry)
    if float(getattr(entry, "group_dps", 0) or 0) > 0:
        dps_time = float(getattr(entry, "dps_time_s", 0) or 0)
        lines = [f"Group damage over {_dps_time_text(dps_time)} dps time (first hit to last) "
                 f"of a {_fmt_duration(fight_s)} fight"]
        if boss_fight:
            boss_time = float(getattr(entry, "boss_dps_time_s", 0) or 0)
            lines.append(f"Boss damage over {_dps_time_text(boss_time)} of hits on the bosses")
        lines.append("Click for the dps over time graph")
        tips[GRAPH_HREF] = (f"<b>Group dps</b><br><span style='font-size:85%'>"
                            f"{'<br>'.join(e(line) for line in lines)}</span>")
    for p in entry.players:
        unit_id = str(p.get("unit_id", ""))
        if not unit_id:
            continue
        lines = []
        damage = p.get("damage") if isinstance(p.get("damage"), dict) else None
        if damage:
            total = int(damage.get("total") or 0)
            span_s = (damage.get("window") or {}).get("span_ms", 0) / 1000.0
            lines.append(f"{total:,} damage in {_dps_time_text(span_s)} dps time "
                         f"(first hit to last) of a {_fmt_duration(fight_s)} fight")
            boss = int(damage.get("boss") or 0)
            if boss_fight and boss:
                boss_span_s = (damage.get("boss_window") or {}).get("span_ms", 0) / 1000.0
                lines.append(f"{boss:,} to the bosses in {_dps_time_text(boss_span_s)}")
            if fight_s > 0 and total:
                whole = _fmt_dps(total / fight_s)
                if boss_fight:
                    whole = f"{_fmt_dps(boss / fight_s)} / {whole}"
                lines.append(f"Over the whole fight: {whole}")
        lines.append("Click for the damage breakdown by ability and target")
        tips[damage_href(unit_id)] = (
            f"<b>{e(names.text(_join(p.get('name', ''))))}</b><br>"
            f"<span style='font-size:85%'>{'<br>'.join(e(line) for line in lines)}</span>")
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


def _dps_text(p, boss_fight: bool) -> str:
    """A player's dps cell: 'boss / total' in a fight with a boss, the
    total alone in one without (there, boss dps would read 0 for all)."""
    total = _fmt_dps(float(p.get("dps") or 0))
    if not boss_fight:
        return total
    return f"{_fmt_dps(float(p.get('boss_dps') or 0))} / {total}"


def _pct_text(p, boss_fight: bool) -> str:
    """A player's share cell: 'boss % / total %' in a fight with a boss (their
    share of the group's boss damage, then of all its damage), the total
    share alone in one without."""
    total = f"{float(p.get('dmg_pct') or 0):.1f}%"
    if not boss_fight:
        return total
    return f"{float(p.get('boss_pct') or 0):.1f}% / {total}"


def _is_boss_fight(entry) -> bool:
    """Whether the group dealt any damage to a unit the game flags as a boss."""
    return float(getattr(entry, "group_boss_dps", 0) or 0) > 0


def _resources_html(p) -> str:
    """'H 23.3k · M 14.9k · S 27.6k' with the largest pool in bold; a
    companion has a health pool only ('H 33k')."""
    if p.get("companion"):
        return f"H {_fmt_resource(p.get('h'))}" if p.get("h") else ""
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


def _borrowed_lines(p) -> Tuple[List[str], bool]:
    """(the skill lines to show, whether they are borrowed): the lines
    outside the player's own class, or every line when the class is unknown.
    Nothing for a stock build, where the class abbreviation says it all."""
    lines = p.get("skill_lines") or []
    if isinstance(lines, str):
        lines = [lines]
    class_lines = set(p.get("class_lines") or [])
    if not class_lines:
        return list(lines), False
    return [line for line in lines if line not in class_lines], True


def _subclass_text(p, short: bool = True) -> str:
    """'+Herald +Animal' for a build that borrows Herald of the Tome and
    Animal Companions from other classes (full names with short=False);
    'Dawn/Bone' for a player whose class is unknown; '' for a stock build."""
    lines, borrowed = _borrowed_lines(p)
    names = [_short_line(line) if short else str(line) for line in lines]
    if borrowed:
        return " ".join(f"+{name}" for name in names)
    return "/".join(names)


def _mastery_text(p) -> str:
    """'An Eye for Exploitation, Above and Beyond' for a pure-class build
    with Class Mastery passives; '' without."""
    return ", ".join(str(name) for name in (p.get("masteries") or []) if name)


def summary_line(entry, death_cue: bool = False, issue_cue: bool = False) -> str:
    """Fight line: boss · duration · gdps · zone · timestamp.

    death_cue: mark a fight in which a player died with DEATH_CUE after the
    boss or mob name; issue_cue: mark a fight in which a player's build has
    a possible issue (build_issues) with ISSUES_LIST_CUE after that. The
    history list asks for both; the clipboard copy, which is read without
    the app's legend, does not.
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
    if issue_cue and any(p.get("build_issues") for p in entry.players):
        parts[0] = f"{parts[0]} {ISSUES_LIST_CUE}"
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


def _slot_note(slot: dict) -> str:
    """The hover's note on a slot the log did not list as drawn: a morph the
    log listed as Rampage, or a skill of the rebuilt werewolf bar; '' for
    any other slot."""
    if slot.get("stand_in"):
        return STAND_IN_NOTE.format(stand_in=slot["stand_in"])
    if slot.get("werewolf"):
        return WEREWOLF_NOTE
    return ""


def _note_variant(slot: dict) -> str:
    """URL fragment for a slot whose hover carries a note (_slot_note), ''
    for any other: hover text is looked up by anchor target."""
    if slot.get("stand_in"):
        return f"shown-as-{slugify(str(slot['stand_in']))}"
    if slot.get("werewolf"):
        return "werewolf-bar"
    return ""


def _ability_href(slot: dict, links) -> str:
    """Anchor target for a bar slot: the ESO-Hub skill page when *links*
    knows one, else an internal esolog: URL that only carries the hover."""
    url = links(str(slot.get("name", ""))) if links else None
    href = url or f"esolog:ability/{slot.get('id', '')}"
    variant = _scribed_variant(slot) or _note_variant(slot)
    return f"{href}#{variant}" if variant else href


def _taunt_mark(slot: dict, taunt_color: Optional[str]) -> str:
    """The color an ability the player taunted with is marked in, '' for
    any other slot or when no color is given."""
    return taunt_color if taunt_color and slot.get("taunt") else ""


def _bar_html(slots, names, icons, links, e, px: int = ICON_PX,
              taunt_color: Optional[str] = None) -> str:
    """One ability bar. Slots render as icons where the cache has them and as
    names otherwise, each inside an anchor; the ultimate sits apart: the
    sixth slot, or one marked 'ultimate' (a rebuilt werewolf bar can have
    fewer than five skills). With no icon cache the bar is the plain joined
    name list.
    px: the icons' edge (the build window draws them larger). taunt_color:
    an ability the player taunted with gets a ring of it on its icon (see
    the view's loadResource) or its name in it."""
    if icons is None or not slots:
        if slots and any(_taunt_mark(slot, taunt_color) for slot in slots):
            return _join([
                f"<span style='color:{taunt_color};font-weight:bold'>{e(str(slot.get('name', '')))}</span>"
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
            body = f"<span style='color:{mark};font-weight:bold'>{e(str(slot.get('name', '')))}</span>"
        else:
            body = e(str(slot.get("name", "")))
        href = e(_ability_href(slot, links), quote=True)
        chunk = f'<a href="{href}" style="text-decoration:none">{body}</a>'
        if index == 5 or (index and slot.get("ultimate")):
            chunk = "&nbsp;&nbsp;&nbsp;" + chunk
        parts.append(chunk)
    return "&nbsp;".join(parts)


def anchor_names(entry, links=None) -> dict:
    """Plain ability name per anchor href in the detail view, so the in-fight
    search can match icons by the name they stand for."""
    names = {}
    for p in entry.players:
        for key in BAR_KEYS:
            for slot in p.get(key) or []:
                names.setdefault(_ability_href(slot, links), str(slot.get("name", "")))
    return names


def form_share_text(share) -> str:
    """'in form 100%': the share of a fight spent in werewolf form. Any
    share under 1% reads '<1%', never '0%' (format rounds 0.5 to 0)."""
    pct = float(share or 0) * 100
    return "in form <1%" if 0 < pct < 1 else f"in form {pct:.0f}%"


def werewolf_bar_html(p, icons, links, e, theme, px: int = ICON_PX) -> str:
    """The rebuilt werewolf bar and 'in form 100%' for a player who spent
    some of the fight in werewolf form, '' for any other."""
    share = p.get("werewolf_share")
    if not share:
        return ""
    muted = theme["muted"]
    slots = p.get("werewolf_bar_slots") or []
    bar = (_bar_html(slots, [str(slot.get("name", "")) for slot in slots], icons, links, e,
                     px, taunt_color=theme["taunt"]) if slots else "")
    note = f"<span style='color:{muted}'>{e(form_share_text(share))}</span>"
    return f"{bar}&nbsp;&nbsp;&nbsp;{note}" if bar else note


def _werewolf_text(p) -> str:
    """'Werewolf (in form 100%): Feral Pounce, ..., Werewolf Berserker' for
    the plain copy, '' for a player never in form."""
    share = p.get("werewolf_share")
    if not share:
        return ""
    head = f"{WEREWOLF_LABEL} ({form_share_text(share)})"
    names = _join([str(slot.get("name", "")) for slot in p.get("werewolf_bar_slots") or []])
    return f"{head}: {names}" if names else head


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
        for key in BAR_KEYS:
            for slot in p.get(key) or []:
                href = _ability_href(slot, links)
                if href in tips:
                    continue
                name = str(slot.get("name", ""))
                if _is_scribed(slot):
                    tips[href] = _scribed_tip(slot, href, e)
                else:
                    note = _slot_note(slot)
                    tip = f"<b>{e(name)}</b>" + (f"<br>{e(note)}" if note else "")
                    tips[href] = tip + _link_note(href, e) if href.startswith("http") else tip
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
                text_color: Optional[str] = None, pen_crit_options=None,
                names=None) -> str:
    """Render one fight as HTML for a QTextBrowser.

    icons: object with has(stem) -> bool (the fight view's IconCache); None
    keeps the bars as text. links / set_links / script_links: callables
    name -> ESO-Hub URL or None for abilities / gear sets / the scripts of
    scribed skills. base_pt: the pane's font size, which the scripts and gear
    lines are scaled from (Qt rich text ignores percentage sizes).
    pen_crit_options: the config's pen_crit section, for the row's cap
    shares (pen_crit.cap_shares); None assumes no Champion Point rows.
    text_color: the pane's own text color, which a player's name keeps
    although it is a link; the theme's default when not given.
    names: the Hide names mask (gui.name_mask): with it on, every player
    name but the logging player's is drawn as a pixelated stand-in.
    """
    theme = _theme(dark)
    names = names or NO_MASK
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
    # pane's normal size and weight: duration · gdps · zone · timestamp · deaths.
    # Dps figures read 'boss / total' in a fight with a boss, like the rows
    boss_fight = _is_boss_fight(entry)
    gdps = _fmt_dps(entry.group_dps)
    if boss_fight:
        gdps = f"{_fmt_dps(entry.group_boss_dps)} / {gdps}"
    # The fight time, and beside it the dps time the group figure divides
    # by (first hit to last, see damage_stats) when the two read differently
    duration = _fmt_duration(entry.duration_s)
    dps_time = float(getattr(entry, "dps_time_s", 0) or 0)
    if entry.group_dps > 0 and dps_time > 0 and _dps_time_text(dps_time) != duration:
        duration = f"{duration} (dps time {_dps_time_text(dps_time)})"
    # The group figure opens the dps over time graph. It keeps the look of
    # plain text, but a glyph of the graph's line in the link colour, inside
    # the anchor, says it is one (see gui.glyphs); 'gdps' is in the anchor
    # too, so the whole token is the hover and click target. The &nbsp;
    # keeps the glyph on the figure's line when the header wraps
    px = glyph_px(base_pt)
    if entry.group_dps > 0:
        gdps = (f'<a href="{GRAPH_HREF}" style="text-decoration:none;color:{muted}">'
                f'{gdps} gdps&nbsp;{glyph_html(GRAPH_GLYPH, theme["link"], px)}</a>')
    else:
        gdps = f"{gdps} gdps"
    stats = (f"{duration}"
             f" · {gdps}"
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
    # A solo dungeon run's Misfortunes, muted like the stats; each name with
    # a text carries an anchor for its hover, in the look of plain text
    misfortunes = getattr(entry, "misfortunes", None)
    if misfortunes is not None:
        names_html = " · ".join(
            (f'<a href="{MISFORTUNE_HREF}{i}" style="text-decoration:none;color:{muted}">'
             f'{e(str(name))}</a>') if text else e(str(name))
            for i, (name, text) in enumerate(misfortunes)) or "none"
        parts.append(f"<p style='margin:0;color:{muted}'>Misfortunes: {names_html}</p>")
    # No text uptime line: the timeline strip above the pane shows every
    # tracked rule, its label the rule's text (issue #25). The plain copy
    # keeps the line, since text is all a paste can carry

    parts.append("<table cellpadding='3' cellspacing='0' width='100%'>")
    first_dealer = str(entry.first_damage_dealer or "")
    starred = False
    deaths = deaths_by_unit(entry)
    for p in entry.players:
        role = p.get("role") or "D"
        color = theme["roles"].get(role, muted)
        # The name; with Hide names on, another player's pixelated
        # stand-in (gui.name_mask), bold like the row's text
        name = names.html(_join(p.get("name", "")), name_color, base_pt, bold=True)
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
        # A companion's row (companions.py) hangs under its owner's, and its
        # deaths are a muted mark: the log keeps no recap of them
        if p.get("companion"):
            name = f"<span style='color:{muted}'>{COMPANION_INDENT}</span>{name}"
            died = int(p.get("deaths") or 0)
            if died:
                recap_html = (f"&nbsp;&nbsp;<span style='color:{muted}'>{DEATH_CUE}"
                              f"{f' ×{died}' if died > 1 else ''}</span>")
        class_abbr = e(_join(p.get("class_abbr", "")))
        # Beside the class: the lines a build borrows from another class
        # ("NB +Herald"), or a pure-class build's Class Mastery passives
        # ("NB: An Eye for Exploitation, Above and Beyond"); nothing for a
        # stock build without them
        beside = _subclass_text(p)
        if not beside and _mastery_text(p):
            class_abbr += ":"
            beside = _mastery_text(p)
        subclass_html = f" <span style='color:{muted}'>{e(beside)}</span>" if beside else ""
        # The (i) of possible build issues (build_issues): only on a player
        # with at least one, in the link color so it reads as a cue
        issues_cue = ""
        if unit_id and p.get("build_issues"):
            issues_cue = (f' <a href="{e(issues_href(unit_id), quote=True)}" '
                          f'style="text-decoration:none;color:{theme["link"]}">{ISSUES_CUE}</a>')
        dps = _dps_text(p, boss_fight)
        # The dps figure opens the player's damage window. Like the name it
        # keeps the look of plain text; unlike the name it carries a glyph
        # (three bars, muted, as there may be twelve of them) that says it
        # can be clicked, since the window has no other way in
        if unit_id:
            dps = (f'<a href="{e(damage_href(unit_id), quote=True)}" '
                   f'style="text-decoration:none;color:{name_color}">{dps}&nbsp;'
                   f'{glyph_html(BREAKDOWN_GLYPH, muted, px)}</a>')
        # The player's effective penetration and crit damage over the fight
        # (pen_crit): muted, as plain-looking as the dps figure, and a link
        # to the build window's sections; the hover tooltip carries the
        # caps and shares. Empty for a player with no damage to weigh, and
        # on an entry built before the figures
        caps = pen_crit_text(pen_crit_shares(entry, p, pen_crit_options))
        if caps and unit_id:
            caps = (f'<a href="{e(pen_crit_href(unit_id), quote=True)}" '
                    f'style="text-decoration:none;color:{muted}">{caps}</a>')
        row = (f"<tr><td style='color:{color};font-weight:bold'>{role}</td>"
               f"<td><b>{name}</b> <span style='color:{muted}'>{class_abbr}</span>"
               f"{subclass_html}{issues_cue}{recap_html}</td>"
               f"<td align='right'>{dps}</td>"
               f"<td align='right'>{_pct_text(p, boss_fight)}</td>"
               f"<td align='right' style='color:{muted}'>{caps}</td>"
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
            # A werewolf's own bar, which the log never writes (werewolf.py)
            werewolf = werewolf_bar_html(p, icons, links, e, theme)
            if werewolf:
                lines.append(f"<span style='color:{muted}'>{WEREWOLF_LABEL}</span>"
                             f"&nbsp;&nbsp;&nbsp;{werewolf}")
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
            detail = (f"<tr><td></td><td colspan='5' "
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
                              label=names.text(str(recaps[0].get("name") or "unknown")))
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


def render_plain_text(entry, pen_crit_options=None, names=None) -> str:
    """Plain-text rendering for clipboard copy. *pen_crit_options* is the
    config's pen_crit section, so the cap shares on each line match the
    pane's; *names* the Hide names mask, so a pasted fight hides what the
    pane hides."""
    names = names or NO_MASK
    lines = [summary_line(entry)]
    misfortunes = misfortunes_text(entry)
    if misfortunes:
        lines.append(misfortunes)
    if entry.buff_summary:
        lines.append(_join(entry.buff_summary))
    first_dealer = str(entry.first_damage_dealer or "")
    boss_fight = _is_boss_fight(entry)
    for p in entry.players:
        role = p.get("role") or "D"
        dps = _dps_text(p, boss_fight)
        star = (" *" if first_dealer
                and str(p.get("unit_id", "")) == first_dealer else "")
        caps = pen_crit_text(pen_crit_shares(entry, p, pen_crit_options))
        indent = COMPANION_INDENT if p.get("companion") else ""
        lines.append(f"{indent}[{role}] {names.text(_join(p.get('name', '')))}{star} "
                     f"{_join(p.get('class_abbr', ''))} — {dps} ({_pct_text(p, boss_fight)})"
                     + (f" · {caps}" if caps else ""))
        skill_lines = _subclass_text(p, short=False)
        if skill_lines:
            lines.append(f"      {skill_lines}")
        masteries = _mastery_text(p)
        if masteries:
            lines.append(f"      {masteries}")
        for bar, slots in ((p.get("front_bar"), p.get("front_bar_slots")),
                           (p.get("back_bar"), p.get("back_bar_slots"))):
            # Slot labels carry a scribed skill's scripts; names alone do not
            bar_text = _join([slot_label(slot) for slot in slots] if slots else bar)
            if bar_text:
                lines.append(f"      {bar_text}")
        werewolf = _werewolf_text(p)
        if werewolf:
            lines.append(f"      {werewolf}")
        taunts = p.get("taunts") or []
        if taunts:
            lines.append("      taunted with " + ", ".join(
                f"{t.get('name', '')} ×{t.get('count', 0)}" for t in taunts))
        sets = _sets_text(p.get("all_sets") or p.get("sets"))
        if sets:
            lines.append(f"      {sets}")
    return "\n".join(lines)
