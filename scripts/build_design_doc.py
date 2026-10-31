#!/usr/bin/env python3
"""Assemble docs/design.md from the design notes kept in the code.

The explanation of each hard problem (what the log carries, which data
source is trusted, why a rule was chosen after measuring real logs) lives
in the docstring or a tagged comment block of the code that solves it, so
that a change to the code is made next to the reasoning it has to honour.
This script extracts those notes into one document; it never holds text of
its own. To add a topic, add an entry to TOPICS. To change the text, edit
the code and rerun:

    python scripts/build_design_doc.py

A source is either ``path:Qualified.name`` (that definition's docstring;
``path`` alone is the module docstring) or ``path#Title`` (the comment
block that starts with a line ``# Design: Title``, read until the first
line that is not a comment at the same indentation).
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "design.md"

# (heading, [sources])
TOPICS = [
    ("The encounter log: unit states and effects", [
        "src/esolog_tail.py:ESOLogAnalyzer._handle_effect_changed",
    ]),
    ("Fight boundaries: fights the game cuts in two", [
        "src/esolog_tail.py#Fights the game cuts in two",
        "src/esolog_tail.py:ESOLogAnalyzer._continues_last_fight",
        "src/esolog_tail.py:ESOLogAnalyzer._resume_last_fight",
        "src/esolog_tail.py#A death just after END_COMBAT",
    ]),
    ("Starting mid-session", [
        "src/esolog_tail.py:LogFileMonitor._load_latest_session",
    ]),
    ("Log freshness", [
        "src/log_freshness.py",
    ]),
    ("Roles", [
        "src/esolog_tail.py:infer_player_role",
    ]),
    ("Class skill lines and subclassing", [
        "src/eso_sets.py",
    ]),
    ("Ability icons and ESO-Hub links", [
        "src/ability_icons.py",
        "src/gui/icon_cache.py",
        "scripts/extract_ability_icons.py",
    ]),
    ("Scribed skills and their scripts", [
        "src/scribing.py",
    ]),
    ("Werewolf form: the bar the log never writes", [
        "src/werewolf.py",
    ]),
    ("Cast counts and casts per minute", [
        "src/casts.py",
    ]),
    ("Magicka, stamina and ultimate spent and gained", [
        "src/resources.py",
    ]),
    ("Companions: a row of their own under their owner", [
        "src/companions.py",
    ]),
    ("Members who leave, come back, or come back on another character", [
        "src/presence.py",
    ]),
    ("Builds: gear, weapon types, armor weights, mundus and food", [
        "src/player_build.py",
        "scripts/generate_weapon_types.py",
        "scripts/generate_armor_weights.py",
    ]),
    ("Set names", [
        "src/gear_set_database.py",
        "scripts/generate_gear_data.py",
        "scripts/check_client_names.py",
    ]),
    ("Set buffs: which set a Major or Minor buff came from", [
        "scripts/generate_set_buffs.py",
    ]),
    ("Solo dungeons: the run's Misfortunes", [
        "src/misfortunes.py",
    ]),
    ("Penetration and critical damage: the spreadsheet from the log", [
        "src/pen_crit.py",
        "scripts/generate_set_offense.py",
        "src/gui/build_render.py:_pen_crit_html",
    ]),
    ("Section headings: the one element Qt rich text draws a rule on", [
        "src/gui/build_render.py:_heading_html",
    ]),
    ("Possible build issues: what the log proves about a build", [
        "src/build_issues.py",
        "src/build_issues.py:BuildIssueTracker",
        "scripts/generate_weapon_skill_lines.py",
    ]),
    ("Tracked effects: the uptime line as rules anyone can paste", [
        "src/effect_rules.py",
        "src/effect_rules.py:EffectTracker",
        "src/effect_rules.py:EffectTracker.snapshot",
        "src/esolog_tail.py:CombatEncounter.fight_units",
        "src/app_config.py:AppConfig.reload",
    ]),
    ("Taunts", [
        "src/esolog_tail.py#Taunts",
        "src/esolog_tail.py:mark_taunt_slots",
    ]),
    ("What a boss is: the game's flag and its exceptions", [
        "src/boss_units.py",
    ]),
    ("What counts as damage", [
        "src/esolog_tail.py#What counts as damage",
    ]),
    ("Dps time and the damage window: parity with Combat Metrics", [
        "src/esolog_tail.py#Dps time",
        "src/damage_stats.py",
        "src/damage_stats.py:dps_time_s",
        "src/gui/damage_render.py",
        "src/gui/dps_graph.py",
    ]),
    ("Pets: whose damage and healing they are", [
        "src/esolog_tail.py:CombatEncounter.track_pet_ownership",
        "src/esolog_tail.py:CombatEncounter.add_damage_to_player",
    ]),
    ("Split files: one per session, continued rather than copied", [
        "src/esolog_tail.py:LogSplitter",
        "scripts/dedupe_splits.py",
    ]),
    ("A trial's result, and the fight list in blocks by instance", [
        "src/trial_result.py",
        "src/gui/fight_list.py",
    ]),
    ("Death recaps", [
        "src/death_recap.py",
    ]),
    ("Kinds of damage: direct or over time, area or single target, Martial or Magical", [
        "src/damage_kinds.py",
    ]),
    ("The damage taken window: by source and by healer, over the whole fight", [
        "src/gui/taken_render.py",
    ]),
    ("Experimental buff timeline", [
        "src/buff_timeline.py",
        "src/effect_rules.py:EffectTracker.record",
        "src/effect_summary.py",
        "src/gui/timeline_strip.py:paint_sparse_span",
    ]),
    ("Split log retention: zipping old splits and moving older ones to the Recycle Bin", [
        "src/split_retention.py",
        "src/recycle_bin.py",
        "src/log_open.py",
    ]),
    ("The GUI and the engine thread", [
        "src/gui/engine_worker.py",
        "src/gui/main_window.py:MainWindow._on_monitoring_restarting",
        "src/gui/main_window.py#Qt objects are freed on the UI thread",
    ]),
    ("Reviews: a thread of their own, and where a large log is cut", [
        "src/review_load.py",
        "src/gui/review_runner.py",
    ]),
    ("Updates: the schedule, the conditional request and the button", [
        "src/update_check.py",
        "src/gui/update_poller.py",
        "src/gui/update_popup.py",
    ]),
    ("Releases: every tag a beta, and a beta made Stable", [
        "scripts/release.py",
        "scripts/changelog_check.py",
        "scripts/release_guard.py",
        "scripts/promote_release.py",
        "scripts/build_site.py",
    ]),
    ("Taunt marks that pulse in a text page", [
        "src/gui/icon_cache.py:ringed",
        "src/gui/fight_view.py:FightView._pulse_step",
    ]),
    ("Hidden names: the stand-in behind the blur", [
        "src/gui/name_mask.py",
    ]),
    ("Links in the fight pane: the hover cue and the dps glyphs", [
        "src/gui/fight_view.py:FightView._show_hover_cue",
        "src/gui/glyphs.py",
    ]),
    ("The text size", [
        "src/gui/text_size.py",
    ]),
]


def _definition(tree, qualname):
    """The AST node for ``Class.method`` or ``function`` at module level."""
    parts = qualname.split(".")
    scope = tree
    node = None
    for part in parts:
        node = next((n for n in scope.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and n.name == part), None)
        if node is None:
            return None
        scope = node
    return node


def _comment_block(lines, title):
    """A tagged comment block: (start line number, text)."""
    tag = re.compile(r"^(\s*)#\s*Design:\s*" + re.escape(title) + r"\.?\s*(.*)$")
    for i, line in enumerate(lines):
        m = tag.match(line)
        if not m:
            continue
        indent = m.group(1)
        text = [m.group(2).strip()] if m.group(2).strip() else []
        for follow in lines[i + 1:]:
            if follow.startswith(indent + "#"):
                text.append(follow[len(indent) + 1:].strip())
            else:
                break
        return i + 1, " ".join(t for t in text if t)
    return None, None


def extract(source):
    """(title, relative path, line, text) for one source spec."""
    if "#" in source:
        path, title = source.split("#", 1)
        lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
        line, text = _comment_block(lines, title)
        if text is None:
            sys.exit(f"no comment block '# Design: {title}' in {path}")
        return title, path, line, text
    if ":" in source:
        path, qualname = source.split(":", 1)
    else:
        path, qualname = source, None
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    if qualname is None:
        text = ast.get_docstring(tree)
        if not text:
            sys.exit(f"{path} has no module docstring")
        return path, path, 1, text
    node = _definition(tree, qualname)
    if node is None:
        sys.exit(f"{qualname} not found in {path}")
    text = ast.get_docstring(node)
    if not text:
        sys.exit(f"{path}:{qualname} has no docstring")
    return qualname, path, node.lineno, text


def build() -> str:
    """The document's text, from the code as it stands."""
    out = [
        "# Design notes",
        "",
        "How ESO Log Tail solves the problems that are not obvious from the code's",
        "shape: what the encounter log really carries, which game data is trusted",
        "for what, and the rules chosen after measuring real logs. Every note here",
        "is the docstring or a tagged comment of the code it describes, collected by",
        "`scripts/build_design_doc.py`; edit the code, then rerun the script. The",
        "link under each note is where it lives.",
        "",
    ]
    for heading, sources in TOPICS:
        out += [f"## {heading}", ""]
        for source in sources:
            title, path, line, text = extract(source)
            label = title if title != path else path
            # The document sits in docs/, so links climb one level
            out += [f"### {label}", "",
                    f"*[{path}:{line}](../{path.replace(chr(92), '/')}#L{line})*", ""]
            # Docstrings are indented prose; keep paragraphs and code blocks
            for para in text.strip().split("\n\n"):
                stripped = para.strip("\n")
                if stripped.startswith("    "):
                    out += ["```", stripped, "```", ""]
                else:
                    out += [stripped, ""]
    return "\n".join(out).rstrip() + "\n"


def render():
    OUT.write_text(build(), encoding="utf-8")
    return len(TOPICS)


def is_current(path=OUT) -> bool:
    """True when *path* holds what the code would build now. The release
    commit rebuilds the document and the release job checks it (issue
    #134): between releases it may lag the docstrings, at a tag it may not."""
    return path.is_file() and path.read_text(encoding="utf-8") == build()


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        if not is_current():
            sys.exit(f"{OUT.relative_to(ROOT)} is not what the code builds: the release "
                     f"commit should have rebuilt it (python scripts/release.py, or "
                     f"python scripts/build_design_doc.py)")
        print(f"{OUT.relative_to(ROOT)} is current")
    else:
        n = render()
        print(f"wrote {OUT.relative_to(ROOT)} from {n} topics")
