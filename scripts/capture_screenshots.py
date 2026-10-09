#!/usr/bin/env python3
"""Capture the screenshots the user guide and README show, from the real app
drawn offscreen over a log file.

    python scripts/capture_screenshots.py --log path/to/split.log

The log is read, never written: the run uses a scratch config of its own
(split files and archiving off, no update check), so the user's settings are
untouched. The default log is the two-fight fixture the tests use; a
veteran trial split log from the app's split folder makes the pictures the
guide expects (twelve players, a death, taunts). Output goes to
docs/screencaps/ (--out to change), overwriting the same file names each
time, so the pictures stay in step with the app:

    main-window.png                 detail view, a boss fight selected
    main-window-buff-timeline.png   the same with the experimental timeline strip
    compact-view.png                Detail view off
    search.png                      a search in the fight
    build-window.png                one player's build window
    death-recap.png                 one player's death recap
    settings.png                    the Settings dialog
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

    from app_config import AppConfig
    from gui.main_window import MainWindow
    from gui.settings_dialog import SettingsDialog

    scratch = tempfile.TemporaryDirectory()
    config_path = Path(scratch.name) / "config.json"
    config_path.write_text(json.dumps({
        "log_path": str(log),
        "split": {"enabled": False},
        "archive": {"delete_original": False, "size_threshold_mb": 1000000},
        "experimental": {"buff_timeline": False},
        "update": {"check_enabled": False},
    }), encoding="utf-8")

    # The engine says "monitoring started" once it has replayed the log's
    # session; the fight list is complete only then (a long fight can take
    # seconds to replay, during which the list looks finished)
    started = {"flag": False}

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
    win.history_list.setCurrentRow(row)
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
        win._build_dialog.hide()

    # Death recap: the first fight with a death, its first death
    dead = next(((f, r) for f in fights for r in f.death_recaps), None)
    if dead is not None:
        f, recap = dead
        win.history_list.setCurrentRow(fights.index(f))
        pump(1)
        win._show_death_recap(recap["unit_id"])
        pump(1.5)
        save(win._death_dialog, "death-recap.png")
        win._death_dialog.hide()
        win.history_list.setCurrentRow(row)
        pump(1)
    else:
        print("  (no death in this log: death-recap.png not written)")

    # Settings, and the example-rules picker it opens
    dialog = SettingsDialog(win.config, win)
    dialog.show()
    pump(1)
    save(dialog, "settings.png")
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
    win.history_list.setCurrentRow(row)
    pump(1)
    save(win, "review-mode.png")
    win._exit_review()
    pump(1)

    # The experimental timeline strip: what Save does in Settings
    win.config.set("experimental.buff_timeline", True)
    win.config.save()
    win._restart_pending = True
    started["flag"] = False
    win.request_restart.emit()
    pump(600, until_started=True)
    fights = win._current_fights()
    win.history_list.setCurrentRow(pick(fights))
    pump(9)  # the status message again, as above
    save(win, "main-window-buff-timeline.png")

    win.close()
    pump(1)
    scratch.cleanup()


if __name__ == "__main__":
    main()
