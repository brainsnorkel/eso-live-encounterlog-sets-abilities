"""Settings dialog: log path, split files, archiving, startup, updates, the
death recap window, the tracked effects the timeline strip draws, and the
penetration and critical damage assumptions the build window's sections
use."""

import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

import split_retention
from app_config import AppConfig
from death_recap import DEFAULT_WINDOW_S, MAX_WINDOW_S, MIN_WINDOW_S, recap_window_s
from effect_rules import DEFAULT_RULES, parse_rules
from recycle_bin import TRASH_NAME
from pen_crit import (
    FORCE_OF_NATURE_PER_EFFECT, PEN_CAP_INSTANCED, PEN_CAP_OVERLAND, SOLO_BOSS_ARMOUR,
)

PEN_CRIT_HELP = ("The build window's Penetration and Critical damage sections read everything "
                 "else from the log. Champion Point stars that only change a stat are never "
                 "logged, so tick the ones to assume; they show as assumed rows. Fighting "
                 "Finesse is assumed in solo and small-group fights (up to four players), never "
                 "in a group of five or more. Force of Nature's value is its per-effect figure "
                 "times the status effects measured on the boss. The penetration cap is also "
                 "the armour estimate behind the buff timeline's Armour row.")
BY_ZONE = (f"By zone: {PEN_CAP_INSTANCED:,} in dungeons, trials and arenas, "
           f"{SOLO_BOSS_ARMOUR:,} on a solo dungeon's bosses, {PEN_CAP_OVERLAND:,} overland")
CAP_CHOICES = (("auto", BY_ZONE),
               (str(PEN_CAP_INSTANCED), f"Always {PEN_CAP_INSTANCED:,}"),
               (str(PEN_CAP_OVERLAND), f"Always {PEN_CAP_OVERLAND:,}"))

RULES_HELP = ("One rule per line: Name = ability ids on self | group | pets | boss | enemies, "
              "then stacks for a stacking effect, each for the mean over the units "
              "(the taunt's measure), or dots for Touch of Z'en's count. A rule shows when "
              "its effect was up; add expected solo | small | large | all to show it at 0% "
              "in those group sizes when it was not. Every row of the timeline strip is a rule here, the group "
              "buffs and the taunt included: delete what you do not want, Examples… has them "
              "back. In a fight without a boss, a boss rule measures the pack and says how many "
              "mobs it reached. A line that starts with $ is a HyperTools tracker export. Copy "
              "these lines to share them.")

PRIVACY_HELP = ("For screenshots and sharing: every player but the one writing the log is "
                "pixelated in the fight pane and the windows, and reads as blocks in hover "
                "text, pop-ups and the copied fight. The same switch as the toolbar's Hide "
                "names button.")
COMPANION_HELP = ("A companion that is out has its own row under its owner. Off, the owner's "
                  "figures are their own, as in Combat Metrics; on, the owner's dps and share "
                  "include the companion's too, so the shares add up to more than 100%. "
                  "Applies when Settings is saved, to the fights already listed.")
RECAP_HELP = ("Each death's table and its summary in the death recap window cover this many "
              "seconds before the death. Five is usually one mechanic; ten shows the lead-up. "
              "Saving replays the session, so the fights already listed are rebuilt with the "
              "new window.")

RETENTION_HELP = ("Zipped splits keep their name plus .zip and still open for review. Checked "
                  "at startup and daily; the newest session's split and the keep folder are "
                  f"left alone. A split the {TRASH_NAME} cannot take is left, never deleted "
                  "outright.")

SIZE_GUIDE = ("Sizing guide: a veteran trial run is typically 100–300 MB, "
              "a veteran dungeon roughly 25–75 MB. "
              "1024 MB (1 GB) ≈ five veteran trials.")

DELETE_WARNING = ("Deletes Encounter.log after the archive is created and "
                  "verified. The data then exists only inside the zip.")


class _PathRow(QHBoxLayout):
    """Line edit + Browse button for a file or directory path."""

    def __init__(self, value: str, directory: bool):
        super().__init__()
        self._directory = directory
        self.edit = QLineEdit(value or "")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.addWidget(self.edit, 1)
        self.addWidget(browse)

    def _browse(self):
        # The file dialog's parent is the settings window the edit sits in.
        # No reference to it is kept here: a row that pointed back at its
        # dialog made a reference cycle, so the dialog was freed by the
        # garbage collector on whichever thread happened to be allocating,
        # once the engine thread mid-replay, and freeing Qt objects off the
        # UI thread aborts the process
        window = self.edit.window()
        if self._directory:
            path = QFileDialog.getExistingDirectory(window, "Select folder",
                                                    self.edit.text() or str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(window, "Select Encounter.log",
                                                  self.edit.text() or str(Path.home()),
                                                  "Log files (*.log);;All files (*)")
        if path:
            self.edit.setText(path)

    def value(self):
        text = self.edit.text().strip()
        return text or None


class SettingsDialog(QDialog):
    """Edits the AppConfig; caller saves and restarts monitoring on accept."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        # The groups scroll above fixed Save and Cancel buttons: the dialog
        # is taller than a 1080p screen, and without room Qt squeezed the
        # wrapped help labels until their lines overlapped
        outer = QVBoxLayout(self)
        content = QWidget()
        layout = QVBoxLayout(content)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidget(content)
        outer.addWidget(self._scroll, 1)

        # Log file
        log_group = QGroupBox("Encounter log")
        log_form = QFormLayout(log_group)
        self.log_row = _PathRow(config.get("log_path") or "", directory=False)
        log_form.addRow("Log file (blank = auto-detect):", self.log_row)
        layout.addWidget(log_group)

        # Split files
        split_group = QGroupBox("Per-encounter split files")
        split_form = QFormLayout(split_group)
        self.split_enabled = QCheckBox("Create a split log file for each encounter")
        self.split_enabled.setChecked(bool(config.get("split.enabled", False)))
        self.split_dir = _PathRow(config.get("split.dir") or "", directory=True)
        split_form.addRow(self.split_enabled)
        split_form.addRow("Split folder (blank = log folder):", self.split_dir)
        # Retention (split_retention, issue #86): what a run would do now is
        # counted from the same selection the run makes
        zip_row = QHBoxLayout()
        self.zip_enabled = QCheckBox("Zip split logs older than")
        self.zip_enabled.setChecked(bool(config.get("split.zip_enabled", False)))
        self.zip_weeks = QSpinBox()
        self.zip_weeks.setRange(1, 52)
        self.zip_weeks.setSuffix(" weeks")
        self.zip_weeks.setValue(int(config.get("split.zip_after_weeks", 4) or 4))
        zip_row.addWidget(self.zip_enabled)
        zip_row.addWidget(self.zip_weeks)
        zip_row.addStretch(1)
        split_form.addRow(zip_row)
        # Deleting (issue #87): to the Recycle Bin, M more than N while
        # zipping is on, and a question before saving a change that deletes
        delete_row = QHBoxLayout()
        self.delete_enabled = QCheckBox(f"Move split logs to the {TRASH_NAME} when older than")
        self.delete_enabled.setChecked(bool(config.get("split.delete_enabled", False)))
        self.delete_weeks = QSpinBox()
        self.delete_weeks.setRange(1, 520)
        self.delete_weeks.setSuffix(" weeks")
        self.delete_weeks.setValue(int(config.get("split.delete_after_weeks", 52) or 52))
        delete_row.addWidget(self.delete_enabled)
        delete_row.addWidget(self.delete_weeks)
        delete_row.addStretch(1)
        split_form.addRow(delete_row)
        self.retention_preview = QLabel("")
        self.retention_preview.setWordWrap(True)
        self.retention_preview.setStyleSheet("color: #888; font-size: 11px;")
        split_form.addRow(self.retention_preview)
        retention_help = QLabel(RETENTION_HELP)
        retention_help.setWordWrap(True)
        retention_help.setStyleSheet("color: #888; font-size: 11px;")
        split_form.addRow(retention_help)
        layout.addWidget(split_group)
        self._splits = []
        self._initial_delete = (self.delete_enabled.isChecked(), self.delete_weeks.value(),
                                self.retention_folder())
        self._couple_weeks()
        self._scan_splits()
        self.split_dir.edit.textChanged.connect(self._scan_splits)
        self.log_row.edit.textChanged.connect(self._scan_splits)
        for changed in (self.zip_enabled.toggled, self.zip_weeks.valueChanged):
            changed.connect(self._couple_weeks)
        for changed in (self.zip_enabled.toggled, self.zip_weeks.valueChanged,
                        self.delete_enabled.toggled, self.delete_weeks.valueChanged):
            changed.connect(self._update_retention_preview)

        # Archive
        archive_group = QGroupBox("Automatic log archiving (checked at app startup)")
        archive_form = QFormLayout(archive_group)
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 1024 * 100)
        self.threshold.setSuffix(" MB")
        self.threshold.setValue(int(config.get("archive.size_threshold_mb", 1024) or 1024))
        archive_form.addRow("Archive when the log grows by:", self.threshold)
        guide = QLabel(SIZE_GUIDE)
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #888; font-size: 11px;")
        archive_form.addRow(guide)
        self.archive_dir = _PathRow(config.get("archive.dir") or "", directory=True)
        archive_form.addRow("Archive folder (blank = log folder):", self.archive_dir)
        self.delete_original = QCheckBox("Delete Encounter.log after a verified archive")
        self.delete_original.setChecked(bool(config.get("archive.delete_original", False)))
        archive_form.addRow(self.delete_original)
        warning = QLabel(DELETE_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d98a3d; font-size: 11px;")
        archive_form.addRow(warning)
        layout.addWidget(archive_group)

        # Startup
        import autostart
        startup_group = QGroupBox("Startup")
        startup_form = QFormLayout(startup_group)
        self.autostart = QCheckBox("Start ESO Log Tail when I sign in to Windows")
        self._autostart_available = autostart.autostart_command() is not None
        self._autostart_initial = autostart.is_enabled()
        self.autostart.setChecked(self._autostart_initial)
        if not self._autostart_available:
            self.autostart.setEnabled(False)
            self.autostart.setToolTip(
                "Available when running the installed app")
        startup_form.addRow(self.autostart)
        layout.addWidget(startup_group)
        # The login entry is a Windows Run key; nothing to offer elsewhere
        startup_group.setVisible(sys.platform == "win32")

        # Updates
        update_group = QGroupBox("Updates")
        update_form = QFormLayout(update_group)
        self.update_check = QCheckBox(
            "Check GitHub for a newer release at startup and every 15 minutes, "
            "and show an Update button in the toolbar")
        self.update_check.setChecked(bool(config.get("update.check_enabled", True)))
        update_form.addRow(self.update_check)
        layout.addWidget(update_group)

        # Privacy: the Hide names switch (issue #72, gui.name_mask), the
        # same state as the toolbar button and Ctrl+H
        privacy_group = QGroupBox("Privacy")
        privacy_form = QFormLayout(privacy_group)
        self.hide_names = QCheckBox(
            "Hide other players' handles and character names (Ctrl+H toggles it)")
        self.hide_names.setChecked(bool(config.get("privacy.hide_names", False)))
        privacy_form.addRow(self.hide_names)
        privacy_help = QLabel(PRIVACY_HELP)
        privacy_help.setWordWrap(True)
        privacy_help.setStyleSheet("color: #888; font-size: 11px;")
        privacy_form.addRow(privacy_help)
        layout.addWidget(privacy_group)

        # Companions (issue #74, companions.py): each has its own row under
        # its owner; this adds its figures to the owner's as well
        companion_group = QGroupBox("Companions")
        companion_form = QFormLayout(companion_group)
        self.companion_accrual = QCheckBox(
            "Count a companion's damage and healing as its owner's too")
        self.companion_accrual.setChecked(bool(config.get("companions.accrue_to_owner", False)))
        companion_form.addRow(self.companion_accrual)
        companion_help = QLabel(COMPANION_HELP)
        companion_help.setWordWrap(True)
        companion_help.setStyleSheet("color: #888; font-size: 11px;")
        companion_form.addRow(companion_help)
        layout.addWidget(companion_group)

        # Death recaps (issue #95, death_recap): the seconds kept before
        # each death; the engine reads it when a save rebuilds it
        recap_group = QGroupBox("Death recaps")
        recap_form = QFormLayout(recap_group)
        self.recap_window = QSpinBox()
        self.recap_window.setRange(MIN_WINDOW_S, MAX_WINDOW_S)
        self.recap_window.setSuffix(" seconds")
        self.recap_window.setValue(
            recap_window_s(config.get("death_recap.window_s", DEFAULT_WINDOW_S)))
        recap_form.addRow("Window before each death:", self.recap_window)
        recap_help = QLabel(RECAP_HELP)
        recap_help.setWordWrap(True)
        recap_help.setStyleSheet("color: #888; font-size: 11px;")
        recap_form.addRow(recap_help)
        layout.addWidget(recap_group)

        # Tracked effects: the rule text, with its parse result underneath;
        # the timeline strip above each fight draws them
        tracking_group = QGroupBox("Tracked effects (the timeline strip)")
        tracking_layout = QVBoxLayout(tracking_group)
        help_label = QLabel(RULES_HELP)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        tracking_layout.addWidget(help_label)
        self.rules_edit = QPlainTextEdit()
        self.rules_edit.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.rules_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.rules_edit.setPlainText(config.get("tracking.rules", DEFAULT_RULES) or "")
        self.rules_edit.setMinimumHeight(120)
        tracking_layout.addWidget(self.rules_edit)
        rules_row = QHBoxLayout()
        self.rules_status = QLabel("")
        self.rules_status.setWordWrap(True)
        rules_row.addWidget(self.rules_status, 1)
        self.examples_button = QPushButton("Examples…")
        self.examples_button.setToolTip(
            "Pick example rules to add to the box, or copy them to share")
        self.examples_button.clicked.connect(self._pick_examples)
        rules_row.addWidget(self.examples_button)
        tracking_layout.addLayout(rules_row)
        self.rules_edit.textChanged.connect(self._check_rules)
        self._check_rules()
        layout.addWidget(tracking_group)

        # Penetration and critical damage: the Champion Point rows the build
        # window assumes, and the cap (pen_crit); read at render time, so no
        # restart is needed for them
        pen_group = QGroupBox("Penetration and critical damage (the build window)")
        pen_form = QFormLayout(pen_group)
        pen_help = QLabel(PEN_CRIT_HELP)
        pen_help.setWordWrap(True)
        pen_help.setStyleSheet("color: #888; font-size: 11px;")
        pen_form.addRow(pen_help)
        self.assume_piercing = QCheckBox("Assume Piercing (700 penetration, a passive star)")
        self.assume_piercing.setChecked(bool(config.get("pen_crit.piercing", True)))
        pen_form.addRow(self.assume_piercing)
        self.assume_finesse = QCheckBox(
            "Assume Fighting Finesse (8% critical damage) in solo and small-group fights")
        self.assume_finesse.setChecked(bool(config.get("pen_crit.fighting_finesse", True)))
        pen_form.addRow(self.assume_finesse)
        self.assume_backstabber = QCheckBox("Assume Backstabber (10% critical damage while flanking)")
        self.assume_backstabber.setChecked(bool(config.get("pen_crit.backstabber", False)))
        pen_form.addRow(self.assume_backstabber)
        fon_row = QHBoxLayout()
        self.assume_force_of_nature = QCheckBox("Assume Force of Nature: per status effect on the target")
        self.assume_force_of_nature.setChecked(bool(config.get("pen_crit.force_of_nature", False)))
        fon_row.addWidget(self.assume_force_of_nature)
        self.force_of_nature_value = QSpinBox()
        self.force_of_nature_value.setRange(1, 5000)
        self.force_of_nature_value.setValue(
            int(config.get("pen_crit.force_of_nature_per_effect", FORCE_OF_NATURE_PER_EFFECT)
                or FORCE_OF_NATURE_PER_EFFECT))
        self.force_of_nature_value.setToolTip(
            "The tooltip's figure per unique status effect; Combat Metrics uses 660")
        fon_row.addWidget(self.force_of_nature_value)
        fon_row.addStretch(1)
        pen_form.addRow(fon_row)
        self.pen_cap = QComboBox()
        for key, label in CAP_CHOICES:
            self.pen_cap.addItem(label, key)
        current = str(config.get("pen_crit.cap", "auto") or "auto")
        index = next((i for i, (key, _label) in enumerate(CAP_CHOICES) if key == current), 0)
        self.pen_cap.setCurrentIndex(index)
        pen_form.addRow("Penetration cap:", self.pen_cap)
        layout.addWidget(pen_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._fit_to_screen(content)

    def _fit_to_screen(self, content: QWidget) -> None:
        """Open tall enough to show every group where the screen allows,
        and no taller than nine tenths of it; the rest scrolls."""
        content.adjustSize()
        width = max(self.minimumWidth(), content.sizeHint().width()
                    + self._scroll.verticalScrollBar().sizeHint().width() + 24)
        height = content.sizeHint().height() + 72  # the buttons and margins
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            height = min(height, int(screen.availableGeometry().height() * 0.9))
        self.resize(width, height)

    def retention_folder(self):
        """The split folder these settings name (blank: the log's folder)."""
        return split_retention.split_folder(
            self.split_dir.value(), split_retention.resolve_log(self.log_row.value()))

    def _scan_splits(self) -> None:
        folder = self.retention_folder()
        self._splits = split_retention.scan_splits(folder) if folder is not None else []
        self._update_retention_preview()

    def _couple_weeks(self) -> None:
        """While zipping is on, a split is zipped before it can be deleted:
        M stays above N, and raising N pushes M up with it."""
        self.delete_weeks.setMinimum(
            self.zip_weeks.value() + 1 if self.zip_enabled.isChecked() else 1)

    def retention_plan(self) -> split_retention.Plan:
        """What a run with these settings would do now: the run's own
        selection, sparing the folder's newest session as the run does."""
        return split_retention.plan(
            self._splits,
            self.zip_weeks.value() if self.zip_enabled.isChecked() else None,
            self.delete_weeks.value() if self.delete_enabled.isChecked() else None,
            time.time(), set())

    def _update_retention_preview(self) -> None:
        work = self.retention_plan()
        lines = []
        if self.delete_enabled.isChecked():
            noun = "log" if len(work.delete) == 1 else "logs"
            line = (f"Would move {len(work.delete)} split {noun} "
                    f"({split_retention.format_bytes(split_retention.total_size(work.delete))}) "
                    f"to the {TRASH_NAME} now")
            if work.delete:
                summary = split_retention.summarize(work.delete)
                line += f", sessions from {summary.first} to {summary.last}"
            lines.append(line + ".")
        if self.zip_enabled.isChecked():
            noun = "log" if len(work.zip) == 1 else "logs"
            lines.append(
                f"Would zip {len(work.zip)} split {noun} "
                f"({split_retention.format_bytes(split_retention.total_size(work.zip))}) now.")
        self.retention_preview.setText("\n".join(lines))

    def _delete_needs_asking(self) -> bool:
        """A change that deletes: turning it on, lowering M, or another folder."""
        if not self.delete_enabled.isChecked():
            return False
        was_on, was_weeks, was_folder = self._initial_delete
        return (not was_on or self.delete_weeks.value() < was_weeks
                or self.retention_folder() != was_folder)

    def confirm_delete(self, summary: split_retention.DeleteSummary) -> bool:
        """Ask before saving a change that deletes; the full list is under
        Show Details."""
        question, details, names = split_retention.describe_deletion(summary, TRASH_NAME)
        box = QMessageBox(QMessageBox.Warning, "Move old split logs", question,
                          QMessageBox.NoButton, self)
        box.setInformativeText(details)
        box.setDetailedText(names)
        move = box.addButton(f"Move to the {TRASH_NAME}", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        try:
            box.exec()
            return box.clickedButton() is move
        finally:
            box.deleteLater()  # on the UI thread, as the main window does

    def accept(self) -> None:
        if self._delete_needs_asking():
            doomed = self.retention_plan().delete
            if doomed and not self.confirm_delete(split_retention.summarize(doomed)):
                return  # stay in Settings
        super().accept()

    def _pick_examples(self) -> None:
        """The example picker; its ticked lines go under the user's rules."""
        from gui.examples_dialog import ExamplesDialog
        present = [rule.name for rule in parse_rules(self.rules_edit.toPlainText())[0]]
        dialog = ExamplesDialog(present, self)
        try:
            if dialog.exec() == ExamplesDialog.Accepted:
                self.append_rules(dialog.selected_lines())
        finally:
            dialog.deleteLater()  # on the UI thread, as the main window does

    def append_rules(self, lines) -> None:
        """Append rule lines whose names the box lacks, and say how many."""
        from effect_rules import lines_to_add
        text = self.rules_edit.toPlainText()
        new = lines_to_add(list(lines), text)
        if not new:
            self._check_rules()
            self.rules_status.setText("Nothing to add · " + self.rules_status.text())
            return
        joined = text if not text.strip() or text.endswith("\n") else text + "\n"
        self.rules_edit.setPlainText(joined + "\n".join(new) + "\n")
        self._check_rules()
        noun = "rule" if len(new) == 1 else "rules"
        self.rules_status.setText(f"{len(new)} {noun} added · " + self.rules_status.text())

    def _check_rules(self) -> None:
        """Say how many rules the text holds, and which lines will not parse."""
        rules, errors = parse_rules(self.rules_edit.toPlainText())
        count = f"{len(rules)} rule{'s' if len(rules) != 1 else ''}"
        if errors:
            self.rules_status.setStyleSheet("color: #d98a3d; font-size: 11px;")
            self.rules_status.setText(f"{count}; skipped: " + "; ".join(errors))
        else:
            self.rules_status.setStyleSheet("color: #888; font-size: 11px;")
            self.rules_status.setText(count)

    def apply_to_config(self) -> None:
        """Write the dialog values into the config (caller persists)."""
        self.config.set("tracking.rules", self.rules_edit.toPlainText())
        self.config.set("log_path", self.log_row.value())
        self.config.set("split.enabled", self.split_enabled.isChecked())
        self.config.set("split.dir", self.split_dir.value())
        self.config.set("split.zip_enabled", self.zip_enabled.isChecked())
        self.config.set("split.zip_after_weeks", self.zip_weeks.value())
        self.config.set("split.delete_enabled", self.delete_enabled.isChecked())
        self.config.set("split.delete_after_weeks", self.delete_weeks.value())
        self.config.set("archive.size_threshold_mb", self.threshold.value())
        self.config.set("archive.dir", self.archive_dir.value())
        self.config.set("archive.delete_original", self.delete_original.isChecked())
        self.config.set("update.check_enabled", self.update_check.isChecked())
        self.config.set("privacy.hide_names", self.hide_names.isChecked())
        self.config.set("companions.accrue_to_owner", self.companion_accrual.isChecked())
        self.config.set("death_recap.window_s", self.recap_window.value())
        self.config.set("pen_crit.piercing", self.assume_piercing.isChecked())
        self.config.set("pen_crit.fighting_finesse", self.assume_finesse.isChecked())
        self.config.set("pen_crit.backstabber", self.assume_backstabber.isChecked())
        self.config.set("pen_crit.force_of_nature", self.assume_force_of_nature.isChecked())
        self.config.set("pen_crit.force_of_nature_per_effect", self.force_of_nature_value.value())
        cap = self.pen_cap.currentData()
        self.config.set("pen_crit.cap", cap if cap == "auto" else int(cap))
        if self.update_check.isChecked():
            # Re-enabling checks also clears any skipped version
            self.config.set("update.skip_version", None)
        # Start-at-login lives in the registry, not the config file
        if (self._autostart_available
                and self.autostart.isChecked() != self._autostart_initial):
            import autostart
            autostart.set_enabled(self.autostart.isChecked())
