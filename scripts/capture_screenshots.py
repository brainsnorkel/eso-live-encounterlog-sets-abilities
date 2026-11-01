#!/usr/bin/env python3
"""Capture the screenshots the user guide and README show, from the real app
drawn offscreen over a log file.

    python scripts/capture_screenshots.py --log path/to/split.log --hide-names

The log is read, never written: the run uses a scratch config of its own
(split files and archiving off, no update check), so the user's settings are
untouched. The default log is the two-fight fixture the tests use; a
veteran trial split log from the app's split folder makes the pictures the
guide expects (twelve players, a death, taunts). Output goes to
docs/screencaps/ (--out to change), overwriting the same file names each
time, so the pictures stay in step with the app:

    main-window.png                 detail view and timeline strip, a boss fight selected
    compact-view.png                Detail view off
    search.png                      a search in the fight
    build-window.png                one player's build window
    build-damage-dealt.png          the same window scrolled to its Damage dealt section
    build-pen-crit.png              the same window scrolled to its penetration and crit sections
    build-resources.png             the same window scrolled to its Resources section, the last
    build-issues.png                the (i) popup of a player's possible build issues
    update-button.png               the toolbar with the Update button and its ⓘ (a crafted release)
    update-notes.png                the ⓘ popup with that release's notes
    damage-window.png               one player's damage by ability and target
    dps-graph.png                   the dps over time graph
    death-recap.png                 one player's death recap
    settings-general.png            the Settings dialog, one picture per page
    settings-fights.png
    settings-tracked-effects.png
    settings-history.png
    settings-display.png
    settings-files-and-splits.png
    examples-dialog.png             the example tracking rules picker
    review-mode.png                 a log opened for review

Needs PySide6 and, on Windows, the fonts under C:\\Windows\\Fonts (the
offscreen platform draws nothing without a font directory).
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZE = (1400, 880)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", default=str(ROOT / "tests" / "fixtures" / "golden_fight.log"),
                        help="encounter log or split file to show (read only)")
    parser.add_argument("--out", default=str(ROOT / "docs" / "screencaps"),
                        help="folder for the PNG files")
    parser.add_argument("--boss", default="",
                        help="select the first fight whose boss name contains this (default: the longest fight)")
    parser.add_argument("--hide-names", action="store_true",
                        help="capture with the Hide names switch on: every player but the one "
                             "who wrote the log is pixelated (the guide's pictures are taken so)")
    parser.add_argument("--text-size", type=int, default=100,
                        help="the app's text size in percent, 80 to 200 (Settings → Display)")
    parser.add_argument("--colorblind-graph", action="store_true",
                        help="the DPS graph's colour-blind colours and strokes (Settings → Display)")
    parser.add_argument("--dark", action="store_true",
                        help="the dark theme (the Windows 11 style's dark palette, set by hand)")
    args = parser.parse_args()
    log = Path(args.log).resolve()
    if not log.exists():
        sys.exit(f"no such log: {log}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    sys.path.insert(0, str(ROOT / "src"))

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    app.setFont(QFont("Segoe UI", 9))
    if args.dark:
        # The offscreen platform ignores the colour scheme hint, so the
        # dark palette of Qt's Windows 11 style is set by hand
        from PySide6.QtGui import QColor, QPalette
        palette = QPalette()
        for role, value in ((QPalette.Window, "#1e1e1e"), (QPalette.Base, "#2d2d2d"),
                            (QPalette.AlternateBase, "#353535"), (QPalette.Button, "#2d2d2d"),
                            (QPalette.WindowText, "#ffffff"), (QPalette.Text, "#ffffff"),
                            (QPalette.ButtonText, "#ffffff"), (QPalette.ToolTipBase, "#2d2d2d"),
                            (QPalette.ToolTipText, "#ffffff"), (QPalette.Highlight, "#4cc2ff"),
                            (QPalette.HighlightedText, "#000000"), (QPalette.Link, "#99ebff"),
                            (QPalette.PlaceholderText, "#9d9d9d")):
            palette.setColor(role, QColor(value))
        app.setPalette(palette)

    from app_config import AppConfig
    from gui.main_window import MainWindow
    from gui.settings_dialog import SettingsDialog

    scratch = tempfile.TemporaryDirectory()
    config_path = Path(scratch.name) / "config.json"
    config_path.write_text(json.dumps({
        "log_path": str(log),
        "split": {"enabled": False},
        "archive": {"delete_original": False, "size_threshold_mb": 1000000},
        "update": {"check_enabled": False},
        "display": {"text_scale": args.text_size, "colorblind_graph": args.colorblind_graph},
    }), encoding="utf-8")

    # The engine says "monitoring started" once it has replayed the log's
    # session; the fight list is complete only then (a long fight can take
    # seconds to replay, during which the list looks finished)
    started = {"flag": False}
    problems = []  # pictures that need another fight, reported at the end

    def pump(seconds, until_started=False):
        t0 = time.time()
        while time.time() - t0 < seconds:
            app.processEvents()
            time.sleep(0.05)
            if until_started and started["flag"]:
                pump(1)
                return
        if until_started:
            sys.exit("the engine did not finish loading the log in time")

    def save(widget, name):
        path = out / name
        widget.grab().save(str(path))
        print(f"  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")

    win = MainWindow(AppConfig(path=config_path))
    win.worker.monitoring_started.connect(lambda _path: started.__setitem__("flag", True))
    win.resize(*SIZE)
    win.show()
    pump(600, until_started=True)
    fights = win._current_fights()
    if not fights:
        sys.exit("no fights in that log")

    def pick(fights):
        if args.boss:
            for i, f in enumerate(fights):
                if args.boss.lower() in (f.boss_name or "").lower():
                    return i
        return max(range(len(fights)), key=lambda i: fights[i].duration_s)

    row = pick(fights)
    fight = fights[row]
    if args.hide_names:
        # The toolbar switch: saved to the scratch config, so the Settings
        # picture shows its box ticked too
        win.hide_names_action.setChecked(True)
    win.history_list.select_fight(row)
    # "Monitoring <path>" sits in the status bar for eight seconds after
    # the load; the guide's picture should show the freshness label instead
    pump(9)
    print(f"{len(fights)} fights; showing {fight.boss_name} ({fight.duration_s:.0f}s)")
    save(win, "main-window.png")

    # Compact view, then back
    win.detail_action.setChecked(False)
    pump(1)
    save(win, "compact-view.png")
    win.detail_action.setChecked(True)
    pump(1)

    # A search: the most common ability name on the bars
    names = [s.get("name") for p in fight.players for s in p.get("front_bar_slots", []) if s.get("name")]
    if names:
        term = max(set(names), key=names.count).split()[0]
        win.search_field.setText(term)
        pump(1)
        save(win, "search.png")
        win.search_field.clear()
        pump(0.5)

    # Build window for the top damage dealer
    players = sorted(fight.players, key=lambda p: -p.get("dps", 0))
    if players:
        win._show_build(players[0]["unit_id"])
        pump(1.5)
        save(win._build_dialog, "build-window.png")
        # Under the gear grid: Damage dealt, then the Penetration and
        # Critical damage sections, then Resources last (issue #143); the
        # Resources heading reaches the top of the view only when its
        # section is taller than the view, as a trial player's is
        from gui.build_render import DEALT_ANCHOR, PEN_CRIT_ANCHOR, RESOURCES_ANCHOR
        win._build_dialog.view.scrollToAnchor(DEALT_ANCHOR)
        pump(0.5)
        save(win._build_dialog, "build-damage-dealt.png")
        win._build_dialog.view.scrollToAnchor(PEN_CRIT_ANCHOR)
        pump(0.5)
        save(win._build_dialog, "build-pen-crit.png")
        win._build_dialog.view.scrollToAnchor(RESOURCES_ANCHOR)
        pump(0.5)
        save(win._build_dialog, "build-resources.png")
        bar = win._build_dialog.view.verticalScrollBar()
        top = _anchor_top(win._build_dialog.view.document(), RESOURCES_ANCHOR)
        if top is not None and bar.value() < int(top) - 1:
            problems.append("build-resources.png opens on the window's end, not on the Resources "
                            "heading: this player's Resources section is shorter than the window. "
                            "Pick a trial fight (--boss) for the guide's picture.")
        bar.setValue(0)
        win._build_dialog.hide()

    # The (i) popup: the first player of the fight with a possible build issue
    flagged = next((p for p in fight.players if p.get("build_issues")), None)
    if flagged is not None:
        from gui.build_issues_popup import BuildIssuesPopup
        win._show_issues(flagged["unit_id"])
        pump(1)
        popup = next((w for w in app.topLevelWidgets() if isinstance(w, BuildIssuesPopup)), None)
        if popup is not None:
            save(popup, "build-issues.png")
            popup.close()
            pump(0.5)
    else:
        print("  (no player with a build issue in this fight: build-issues.png not written)")

    # The Update button and its ⓘ popup, from a crafted release one patch up
    from PySide6.QtWidgets import QToolBar

    from gui.update_popup import UpdateNotesPopup
    from update_check import GITHUB_REPO, UpdateInfo
    from version import __version__
    parts = __version__.split(".")
    next_version = ".".join(parts[:-1] + [str(int(parts[-1]) + 1)])
    win._on_update_available(UpdateInfo(
        version=next_version, tag=f"v{next_version}", installer_url="",
        installer_name=f"esolog-tail-windows-setup-{next_version}.exe",
        notes=(f"## What's Changed\n"
               f"* Updates: a toolbar button, checked every 15 minutes, no pop-up (#56) "
               f"by @brainsnorkel in https://github.com/{GITHUB_REPO}/issues/56\n\n\n"
               f"**Full Changelog**: https://github.com/{GITHUB_REPO}/compare/"
               f"v{__version__}...v{next_version}"),
        page_url=f"https://github.com/{GITHUB_REPO}/releases/tag/v{next_version}",
        published=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    pump(1)
    save(win.findChild(QToolBar), "update-button.png")
    win._show_update_notes()
    pump(1)
    popup = next((w for w in app.topLevelWidgets() if isinstance(w, UpdateNotesPopup)), None)
    if popup is not None:
        save(popup, "update-notes.png")
        popup.close()
        pump(0.5)
    win._on_update_gone()
    pump(0.5)

    # Damage window for the same player
    if players:
        win._show_damage(players[0]["unit_id"])
        pump(1.5)
        save(win._damage_dialog, "damage-window.png")
        win._damage_dialog.hide()

    # Damage taken window for the fight's tank (the reader it is for), else
    # the same player
    if players:
        tank = next((p for p in players if p.get("role") == "T"), players[0])
        win._show_taken(tank["unit_id"])
        pump(1.5)
        save(win._taken_dialog, "taken-window.png")
        win._taken_dialog.hide()

    # The dps over time graph of the fight
    win._show_graph()
    pump(1.5)
    save(win._graph_dialog, "dps-graph.png")
    win._graph_dialog.hide()

    # Death recap: the first fight with a death, its first death
    dead = next(((f, r) for f in fights for r in f.death_recaps), None)
    if dead is not None:
        f, recap = dead
        win.history_list.select_fight(fights.index(f))
        pump(1)
        win._show_death_recap(recap["unit_id"])
        pump(1.5)
        save(win._death_dialog, "death-recap.png")
        win._death_dialog.hide()
        win.history_list.select_fight(row)
        pump(1)
    else:
        print("  (no death in this log: death-recap.png not written)")

    # Settings, and the example-rules picker it opens. The History page
    # shows the fight history's line without its folder (a path names the
    # machine's user, which the pictures keep out) and its button enabled
    status = win.history_status().replace(str(win.fight_index.path), win.fight_index.path.name)
    dialog = SettingsDialog(win.config, win, history_status=status,
                            on_build_history=win.start_backfill)
    # The box only, not the config (no check runs): the guide shows the
    # update channel as a user with checks on sees it
    dialog.update_check.setChecked(True)
    # The box only, again: the scratch config keeps archiving off with a
    # threshold at the spin box's maximum, which is not what a user sees
    dialog.threshold.setValue(1024)
    dialog.show()
    pump(1)
    # One picture per page, the dialog at its natural size (its tallest
    # page's, 579 px at 100%, under the 800 px virtual screen's cap)
    from gui.settings_dialog import PAGES
    for index, name in enumerate(PAGES):
        dialog.tabs.setCurrentIndex(index)
        pump(0.3)
        save(dialog, f"settings-{name.lower().replace(' ', '-')}.png")
    from effect_rules import parse_rules
    from gui.examples_dialog import ExamplesDialog
    present = [rule.name for rule in parse_rules(dialog.rules_edit.toPlainText())[0]]
    picker = ExamplesDialog(present, dialog)
    picker.resize(720, 520)
    picker.show()
    pump(1)
    save(picker, "examples-dialog.png")
    picker.deleteLater()
    dialog.deleteLater()
    pump(0.5)

    # Review mode: the same fights as a reviewed file
    win._on_review_loaded(str(log), list(fights))
    win.history_list.select_fight(row)
    pump(1)
    save(win, "review-mode.png")
    win._exit_review()
    pump(1)

    win.close()
    pump(1)
    scratch.cleanup()
    if problems:
        # The pictures are saved; say which one needs another fight
        sys.exit("\n".join(problems))


def _anchor_top(doc, name):
    """The top of the block that carries the named anchor, as
    QTextEdit.scrollToAnchor reads it, or None."""
    block = doc.begin()
    while block.isValid():
        if name in block.charFormat().anchorNames():
            return doc.documentLayout().blockBoundingRect(block).top()
        it = block.begin()
        while not it.atEnd():
            if name in it.fragment().charFormat().anchorNames():
                return doc.documentLayout().blockBoundingRect(block).top()
            it += 1
        block = block.next()
    return None


if __name__ == "__main__":
    main()
