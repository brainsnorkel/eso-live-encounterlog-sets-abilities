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
    ("Builds: gear, weapon types, armor weights, mundus and food", [
        "src/player_build.py",
        "scripts/generate_weapon_types.py",
        "scripts/generate_armor_weights.py",
    ]),
    ("Set names", [
        "src/gear_set_database.py",
        "scripts/generate_gear_data.py",
    ]),
    ("Group buff uptimes", [
        "src/esolog_tail.py:CombatEncounter.track_buff",
        "src/esolog_tail.py:CombatEncounter.get_group_buff_uptime",
    ]),
    ("Taunts", [
        "src/esolog_tail.py#Taunts",
        "src/esolog_tail.py:CombatEncounter.track_taunt",
        "src/esolog_tail.py:CombatEncounter.taunt_uptime",
        "src/esolog_tail.py:mark_taunt_slots",
    ]),
    ("Pets: whose damage and healing they are", [
        "src/esolog_tail.py:CombatEncounter.track_pet_ownership",
        "src/esolog_tail.py:CombatEncounter.add_damage_to_player",
    ]),
    ("Death recaps", [
        "src/death_recap.py",
    ]),
    ("Experimental buff timeline", [
        "src/buff_timeline.py",
    ]),
    ("The GUI and the engine thread", [
        "src/gui/engine_worker.py",
        "src/gui/main_window.py:MainWindow._on_monitoring_restarting",
        "src/gui/main_window.py#Qt objects are freed on the UI thread",
    ]),
    ("Taunt marks that pulse in a text page", [
        "src/gui/icon_cache.py:ringed",
        "src/gui/fight_view.py:FightView._pulse_step",
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


def render():
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
    OUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return len(TOPICS)


if __name__ == "__main__":
    n = render()
    print(f"wrote {OUT.relative_to(ROOT)} from {n} topics")
