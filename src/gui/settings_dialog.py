"""Settings dialog: log path, split files, archiving, startup, updates, the
tracked effects the timeline strip draws, and the penetration and critical
damage assumptions the build window's sections use."""

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout,
)

from app_config import AppConfig
from effect_rules import DEFAULT_RULES, parse_rules
from pen_crit import FORCE_OF_NATURE_PER_EFFECT, PEN_CAP_INSTANCED, PEN_CAP_OVERLAND

PEN_CRIT_HELP = ("The build window's Penetration and Critical damage sections read everything "
                 "else from the log. Champion Point stars that only change a stat are never "
                 "logged, so tick the ones to assume; they show as assumed rows. Fighting "
                 "Finesse applies in dungeons, trials and arenas only. Force of Nature's value "
                 "is its per-effect figure times the status effects measured on the boss.")
BY_ZONE = (f"By zone: {PEN_CAP_INSTANCED:,} in dungeons, trials and arenas, "
           f"{PEN_CAP_OVERLAND:,} overland")
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
        layout = QVBoxLayout(self)

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
        layout.addWidget(split_group)

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
            "Check GitHub for a newer release at startup and offer to update")
        self.update_check.setChecked(bool(config.get("update.check_enabled", True)))
        update_form.addRow(self.update_check)
        layout.addWidget(update_group)

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
            "Assume Fighting Finesse (8% critical damage) in dungeons, trials and arenas")
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
        layout.addWidget(buttons)

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
        self.config.set("archive.size_threshold_mb", self.threshold.value())
        self.config.set("archive.dir", self.archive_dir.value())
        self.config.set("archive.delete_original", self.delete_original.isChecked())
        self.config.set("update.check_enabled", self.update_check.isChecked())
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
