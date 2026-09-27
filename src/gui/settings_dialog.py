"""Settings dialog: log path, split files, reports, and archive options."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from app_config import AppConfig

SIZE_GUIDE = ("Sizing guide: a veteran trial run is typically 100–300 MB, "
              "a veteran dungeon roughly 25–75 MB. "
              "1024 MB (1 GB) ≈ five veteran trials.")

DELETE_WARNING = ("Deletes Encounter.log after the archive is created and "
                  "verified. The data then exists only inside the zip.")


class _PathRow(QHBoxLayout):
    """Line edit + Browse button for a file or directory path."""

    def __init__(self, value: str, directory: bool, parent: QDialog):
        super().__init__()
        self._parent = parent
        self._directory = directory
        self.edit = QLineEdit(value or "")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.addWidget(self.edit, 1)
        self.addWidget(browse)

    def _browse(self):
        if self._directory:
            path = QFileDialog.getExistingDirectory(self._parent, "Select folder",
                                                    self.edit.text() or str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self._parent, "Select Encounter.log",
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
        self.log_row = _PathRow(config.get("log_path") or "", directory=False, parent=self)
        log_form.addRow("Log file (blank = auto-detect):", self.log_row)
        layout.addWidget(log_group)

        # Split files
        split_group = QGroupBox("Per-encounter split files")
        split_form = QFormLayout(split_group)
        self.split_enabled = QCheckBox("Create a split log file for each encounter")
        self.split_enabled.setChecked(bool(config.get("split.enabled", False)))
        self.split_dir = _PathRow(config.get("split.dir") or "", directory=True, parent=self)
        split_form.addRow(self.split_enabled)
        split_form.addRow("Split folder (blank = log folder):", self.split_dir)
        layout.addWidget(split_group)

        # Reports
        reports_group = QGroupBox("Encounter reports")
        reports_form = QFormLayout(reports_group)
        self.reports_enabled = QCheckBox("Save a text report for each zone")
        self.reports_enabled.setChecked(bool(config.get("reports.enabled", False)))
        self.reports_dir = _PathRow(config.get("reports.dir") or "", directory=True, parent=self)
        reports_form.addRow(self.reports_enabled)
        reports_form.addRow("Reports folder (blank = log folder):", self.reports_dir)
        layout.addWidget(reports_group)

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
        self.archive_dir = _PathRow(config.get("archive.dir") or "", directory=True, parent=self)
        archive_form.addRow("Archive folder (blank = log folder):", self.archive_dir)
        self.delete_original = QCheckBox("Delete Encounter.log after a verified archive")
        self.delete_original.setChecked(bool(config.get("archive.delete_original", False)))
        archive_form.addRow(self.delete_original)
        warning = QLabel(DELETE_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d98a3d; font-size: 11px;")
        archive_form.addRow(warning)
        layout.addWidget(archive_group)

        # Updates
        update_group = QGroupBox("Updates")
        update_form = QFormLayout(update_group)
        self.update_check = QCheckBox(
            "Check GitHub for a newer release at startup and offer to update")
        self.update_check.setChecked(bool(config.get("update.check_enabled", True)))
        update_form.addRow(self.update_check)
        layout.addWidget(update_group)

        # Experimental
        experimental_group = QGroupBox("Experimental")
        experimental_form = QFormLayout(experimental_group)
        self.buff_timeline = QCheckBox(
            "Buff timeline: compact per-fight strip for Major Slayer / Force / "
            "Courage / Berserk / Vulnerability with hover attribution")
        self.buff_timeline.setChecked(
            bool(config.get("experimental.buff_timeline", False)))
        experimental_form.addRow(self.buff_timeline)
        layout.addWidget(experimental_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_config(self) -> None:
        """Write the dialog values into the config (caller persists)."""
        self.config.set("log_path", self.log_row.value())
        self.config.set("split.enabled", self.split_enabled.isChecked())
        self.config.set("split.dir", self.split_dir.value())
        self.config.set("reports.enabled", self.reports_enabled.isChecked())
        self.config.set("reports.dir", self.reports_dir.value())
        self.config.set("archive.size_threshold_mb", self.threshold.value())
        self.config.set("archive.dir", self.archive_dir.value())
        self.config.set("archive.delete_original", self.delete_original.isChecked())
        self.config.set("experimental.buff_timeline", self.buff_timeline.isChecked())
        self.config.set("update.check_enabled", self.update_check.isChecked())
        if self.update_check.isChecked():
            # Re-enabling checks also clears any skipped version
            self.config.set("update.skip_version", None)
