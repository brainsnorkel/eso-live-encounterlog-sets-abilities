"""Settings dialog: log path, split files, archiving, startup, updates, the
text size, the death recap window, the tracked effects the timeline strip
draws, and the penetration and critical damage assumptions the build
window's sections use."""

import sys
import time
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QStyleOptionSpinBox, QVBoxLayout, QWidget,
)

import split_retention
from app_config import AppConfig
from death_recap import DEFAULT_WINDOW_S, MAX_WINDOW_S, MIN_WINDOW_S, recap_window_s
from effect_rules import DEFAULT_RULES, parse_rules
from gui import text_size
from gui.fight_render import _theme
from recycle_bin import TRASH_NAME
from update_check import CHANNEL_CHOICES, normalize_channel
from pen_crit import (
    FORCE_OF_NATURE_PER_EFFECT, PEN_CAP_INSTANCED, PEN_CAP_OVERLAND, SOLO_BOSS_ARMOUR,
)

# The facts a paragraph used to carry sit in the labels of the controls
# they describe (issue #187); the help says only what no label can
PEN_CRIT_HELP = ("The build window's Penetration and Critical damage sections read everything "
                 "else from the log. Champion Point stars that only change a stat are never "
                 "logged, so tick the ones to assume; they show as assumed rows. The cap is "
                 "also the armour estimate behind the timeline strip's Armour row.")
BY_ZONE = (f"By zone: {PEN_CAP_INSTANCED:,} instanced, {SOLO_BOSS_ARMOUR:,} solo dungeon bosses, "
           f"{PEN_CAP_OVERLAND:,} overland")
CAP_CHOICES = (("auto", BY_ZONE),
               (str(PEN_CAP_INSTANCED), f"Always {PEN_CAP_INSTANCED:,}"),
               (str(PEN_CAP_OVERLAND), f"Always {PEN_CAP_OVERLAND:,}"))

# The settings the engine reads when it is built or attached
# (app_startup.engine_settings) end their help with this sentence: a Save
# replays the session only when one of them changed (issue #187)
REPLAYS = "Saving a change here replays the session."

RULES_HELP = ("Name = ability ids on self | group | pets | boss | enemies, then stacks, each or "
              "dots; add expected solo | small | large | all. Every row of the timeline strip "
              "is a rule here: delete what you do not want, Examples… has them back. " + REPLAYS)

PRIVACY_HELP = ("For screenshots and sharing: every player but the one writing the log is "
                "pixelated in the fight pane and the windows, and reads as blocks in hover "
                "text, pop-ups and the copied fight. The same switch as the toolbar's Hide "
                "names button.")
HISTORY_HELP = ("Every boss fight is kept, kill or not, so a pull can be read against your "
                "group's earlier kills of the boss and a player against their own. The file "
                "is plain JSON Lines and holds the players' handles, as the logs do. Build "
                "from split logs reads the split folder's logs through the app, newest first, "
                "on the review thread: the status bar shows the progress, its Cancel stops it, "
                "and the next build carries on where it stopped. About a minute per 600 MB.")
COMPANION_HELP = ("A companion that is out has its own row under its owner. Off, the owner's "
                  "figures are their own, as in Combat Metrics; on, the owner's dps and share "
                  "include the companion's too, so the shares add up to more than 100%. "
                  + REPLAYS)
# Issue #134
CHANNEL_HELP = ("An Update button appears at the right end of the toolbar when a newer "
                "release exists. Beta gets every release as it is published. Stable gets a release once it "
                "has been used in real fights for a while with nothing found. Moving from Beta "
                "to Stable never takes you back a version: you keep the one you have until a "
                "Stable release is newer.")
RECAP_HELP = ("Each death's table and its summary in the death recap window cover this many "
              "seconds before the death. One shows the killing blow; three covers most deaths "
              "from half health; ten shows the lead-up. "
              + REPLAYS)

RETENTION_HELP = ("Zipped splits keep their name plus .zip and still open for review. Checked "
                  "at startup and daily; the newest session's split and the keep folder are "
                  f"left alone. A split the {TRASH_NAME} cannot take is left, never deleted "
                  "outright.")

SIZE_GUIDE = ("Sizing guide: a veteran trial run is typically 100–300 MB, "
              "a veteran dungeon roughly 25–75 MB. "
              "1024 MB (1 GB) ≈ five veteran trials.")

# "Warning:" in the text, so the warning is not its orange alone (#77, #187)
DELETE_WARNING = ("Warning: deletes Encounter.log after the archive is created and "
                  "verified. The data then exists only inside the zip.")


def _form(group: QGroupBox) -> QFormLayout:
    """A group's form with every field at its own size: only a field that
    asks to grow (a path row's line edit, the text size slider) takes the
    row's width. The Windows style's default grows every field, so a spin
    box for a number of weeks was 459 px wide for a 122 px hint and read
    as a text field with its arrows far from its label (issue #187)."""
    form = QFormLayout(group)
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    return form


class _SpinBox(QSpinBox):
    """A spin box whose size hint fits its widest value and suffix. The
    windows11 style's own hint does not at large text sizes: at 18 pt
    (200%) it gives "10 seconds" a 98 px field for a 119 px text, so the
    box at its hint showed "10 secon" (measured offscreen, issue #187;
    Fusion and 9 pt fit). The style's edit-field rect at the hint size is
    the field the box really gets, to the pixel, so the shortfall against
    the widest text is added to the hint. Layouts ask for the hint on
    every pass, so it is kept until the base hint, the font, the style,
    the range or the affixes change (22 µs a pair of hints measured,
    against 1 µs for the base class's cached one)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hint_key = None
        self._hint = QSize()

    def _widest(self) -> int:
        fm = self.fontMetrics()
        return max(fm.horizontalAdvance(self.prefix() + self.textFromValue(v) + self.suffix())
                   for v in (self.minimum(), self.maximum()))

    def _field_width(self, width: int, height: int) -> int:
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        option.rect = QRect(0, 0, width, height)
        return self.style().subControlRect(
            QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxEditField, self).width()

    def sizeHint(self):
        base = super().sizeHint()
        key = (base.width(), base.height(), self.font().key(), self.style().objectName(),
               self.minimum(), self.maximum(), self.prefix(), self.suffix())
        if key != self._hint_key:
            hint = QSize(base)
            # the line edit's own text margins, and a little slack
            need = self._widest() + 6
            field = self._field_width(base.width(), base.height())
            if field < need:
                hint.setWidth(base.width() + need - field)
            self._hint_key, self._hint = key, hint
        return QSize(self._hint)

    def minimumSizeHint(self):
        return self.sizeHint()


class _PathRow(QHBoxLayout):
    """Line edit + Browse button for a file or directory path. *name* is
    what a screen reader calls the edit ("Log file") and, as "Browse for
    the log file", its button: a field added to a form as a layout gets no
    buddy label, so Qt fell back to the group's title for the edit, and
    every button was "Browse…". *blank* is what a blank field means
    ("auto-detect"), the row label's parenthesis, which that label does
    not announce either; it opens the edit's description (issue #187)."""

    def __init__(self, value: str, directory: bool, name: str = "", blank: str = ""):
        super().__init__()
        self._directory = directory
        self.edit = QLineEdit(value or "")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        if name:
            self.edit.setAccessibleName(name)
            browse.setAccessibleName(f"Browse for the {name[0].lower()}{name[1:]}")
        if blank:
            self.edit.setAccessibleDescription(f"Blank = {blank}.")
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


TEXT_SIZE_HELP = ("The size of all the app's text, its windows and the timeline strip; the "
                  "ability icons grow with it. Ctrl+= and Ctrl+- change it a step from any "
                  "window, Ctrl+0 puts it back to 100%.")
COLORBLIND_HELP = ("The graph's player lines in a set of colours chosen to stay apart for red-green "
                   "and blue-yellow colour blindness, each player also drawn solid, dashed, dotted "
                   "or dash-dotted in turn, so lines can be told apart by shape as well as colour.")


class SettingsDialog(QDialog):
    """Edits the AppConfig; the caller saves and, when a setting the engine
    reads changed (app_startup.engine_settings), restarts monitoring.
    *history_status*: what the fight history holds and where;
    *on_build_history*: starts reading the split logs into it (the
    window's start_backfill), on the review thread, whatever the dialog
    then saves or cancels (fight_index, issue #170)."""

    def __init__(self, config: AppConfig, parent=None, history_status: str = "",
                 on_build_history=None):
        super().__init__(parent)
        self.config = config
        self._on_build_history = on_build_history
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
        # Sideways only when a large text size makes a line wider than the screen
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setWidget(content)
        outer.addWidget(self._scroll, 1)

        # Log file
        log_group = QGroupBox("Encounter log")
        log_form = _form(log_group)
        self.log_row = _PathRow(config.get("log_path") or "", directory=False, name="Log file",
                                blank="auto-detect")
        log_form.addRow("Log file (blank = auto-detect):", self.log_row)
        log_form.addRow(self._help(REPLAYS, self.log_row.edit))
        layout.addWidget(log_group)

        # Split files
        split_group = QGroupBox("Per-encounter split files")
        split_form = _form(split_group)
        self.split_enabled = QCheckBox("Create a split log file for each encounter")
        self.split_enabled.setChecked(bool(config.get("split.enabled", False)))
        self.split_dir = _PathRow(config.get("split.dir") or "", directory=True,
                                  name="Split folder", blank="log folder")
        split_form.addRow(self.split_enabled)
        split_form.addRow("Split folder (blank = log folder):", self.split_dir)
        # Read downwards this line heads the zip and Recycle Bin rows too,
        # which do not replay, so it says which two it covers
        split_form.addRow(self._help(
            "Saving a change to the split log or its folder replays the session; the "
            "zipping and moving below do not.", self.split_enabled, self.split_dir.edit))
        # Retention (split_retention, issue #86): what a run would do now is
        # counted from the same selection the run makes
        zip_row = QHBoxLayout()
        self.zip_enabled = QCheckBox("Zip split logs older than")
        self.zip_enabled.setChecked(bool(config.get("split.zip_enabled", False)))
        self.zip_weeks = _SpinBox()
        self.zip_weeks.setRange(1, 52)
        self.zip_weeks.setSuffix(" weeks")
        # A spin box beside a check box in a row has no buddy label: Qt
        # announced it by the group's title (issue #187)
        self.zip_weeks.setAccessibleName("Zip split logs older than, weeks")
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
        self.delete_weeks = _SpinBox()
        self.delete_weeks.setRange(1, 520)
        self.delete_weeks.setSuffix(" weeks")
        self.delete_weeks.setAccessibleName(
            f"Move split logs to the {TRASH_NAME} when older than, weeks")
        self.delete_weeks.setValue(int(config.get("split.delete_after_weeks", 52) or 52))
        delete_row.addWidget(self.delete_enabled)
        delete_row.addWidget(self.delete_weeks)
        delete_row.addStretch(1)
        split_form.addRow(delete_row)
        # What a run would do now is a consequence, not help: the normal
        # text colour, and no blank line while there is nothing to say
        self.retention_preview = QLabel("")
        self.retention_preview.setWordWrap(True)
        self.retention_preview.setStyleSheet(self._small_style("plain"))
        split_form.addRow(self.retention_preview)
        split_form.addRow(self._help(RETENTION_HELP, self.zip_enabled))
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
        archive_group = QGroupBox("Automatic log archiving")
        archive_form = _form(archive_group)
        self.threshold = _SpinBox()
        self.threshold.setRange(1, 1024 * 100)
        self.threshold.setSuffix(" MB")
        self.threshold.setValue(int(config.get("archive.size_threshold_mb", 1024) or 1024))
        archive_form.addRow("Archive when the log grows by:", self.threshold)
        archive_form.addRow(self._help("Checked when the app starts. " + SIZE_GUIDE,
                                       self.threshold))
        self.archive_dir = _PathRow(config.get("archive.dir") or "", directory=True,
                                    name="Archive folder", blank="log folder")
        archive_form.addRow("Archive folder (blank = log folder):", self.archive_dir)
        self.delete_original = QCheckBox("Delete Encounter.log after a verified archive")
        self.delete_original.setChecked(bool(config.get("archive.delete_original", False)))
        archive_form.addRow(self.delete_original)
        archive_form.addRow(self._help(DELETE_WARNING, self.delete_original, role="warning"))
        layout.addWidget(archive_group)

        # Startup
        import autostart
        startup_group = QGroupBox("Startup")
        startup_form = _form(startup_group)
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
        update_form = _form(update_group)
        # The toolbar button is in the help: this label set the dialog's
        # width at 200% (issue #187)
        self.update_check = QCheckBox("Check for a newer release at startup and every 15 minutes")
        self.update_check.setChecked(bool(config.get("update.check_enabled", True)))
        update_form.addRow(self.update_check)
        self.update_channel = QComboBox()
        for key, name, offers in CHANNEL_CHOICES:
            self.update_channel.addItem(f"{name}: {offers}", key)
        current = normalize_channel(config.get("update.channel"))
        index = next((i for i, (key, _name, _offers) in enumerate(CHANNEL_CHOICES)
                      if key == current), 0)
        self.update_channel.setCurrentIndex(index)
        # The channel means nothing while checks are off
        self.update_channel.setEnabled(self.update_check.isChecked())
        self.update_check.toggled.connect(self.update_channel.setEnabled)
        update_form.addRow("Channel:", self.update_channel)
        update_form.addRow(self._help(CHANNEL_HELP, self.update_check, self.update_channel))
        layout.addWidget(update_group)

        # Display: the app-wide text size (issue #77, gui.text_size), applied
        # when Settings is saved
        display_group = QGroupBox("Display")
        display_form = _form(display_group)
        size_row = QHBoxLayout()
        self.text_size = QSlider(Qt.Horizontal)
        self.text_size.setRange(text_size.MIN_PCT, text_size.MAX_PCT)
        self.text_size.setSingleStep(text_size.STEP_PCT)
        self.text_size.setPageStep(text_size.STEP_PCT)
        self.text_size.setTickInterval(text_size.STEP_PCT)
        self.text_size.setTickPosition(QSlider.TicksBelow)
        self.text_size_label = QLabel()
        self.text_size.setAccessibleName("Text size")  # the row's label is not its buddy
        self.text_size.valueChanged.connect(self._snap_text_size)
        self.text_size.setValue(text_size.clamp(
            config.get(text_size.CONFIG_KEY, text_size.DEFAULT_PCT)))
        self._snap_text_size(self.text_size.value())
        size_row.addWidget(self.text_size, 1)
        size_row.addWidget(self.text_size_label)
        display_form.addRow("Text size:", size_row)
        display_form.addRow(self._help(TEXT_SIZE_HELP, self.text_size))
        self.colorblind_graph = QCheckBox(
            "Colour-blind colours and line styles in the DPS graph")
        self.colorblind_graph.setChecked(bool(config.get("display.colorblind_graph", False)))
        display_form.addRow(self.colorblind_graph)
        display_form.addRow(self._help(COLORBLIND_HELP, self.colorblind_graph))
        self.reduce_motion = QCheckBox(
            "Reduce motion: the ring on a taunt skill's icon stays still instead of pulsing")
        self.reduce_motion.setChecked(bool(config.get("display.reduce_motion", False)))
        display_form.addRow(self.reduce_motion)
        layout.addWidget(display_group)

        # Privacy: the Hide names switch (issue #72, gui.name_mask), the
        # same state as the toolbar button and Ctrl+H
        privacy_group = QGroupBox("Privacy")
        privacy_form = _form(privacy_group)
        self.hide_names = QCheckBox(
            "Hide other players' handles and character names (Ctrl+H toggles it)")
        self.hide_names.setChecked(bool(config.get("privacy.hide_names", False)))
        privacy_form.addRow(self.hide_names)
        privacy_form.addRow(self._help(PRIVACY_HELP, self.hide_names))
        layout.addWidget(privacy_group)

        # The trial score banner captured from the screen (banner_capture,
        # issue #167): Windows only, so the group is not made elsewhere
        if sys.platform == "win32":
            banner_group = QGroupBox("Score banner")
            banner_form = _form(banner_group)
            self.banner_enabled = QCheckBox(
                "Capture the trial completion banner from the screen when a trial or arena ends")
            self.banner_enabled.setChecked(bool(config.get("banner.enabled", False)))
            self.banner_dir = _PathRow(config.get("banner.dir") or "", directory=True,
                                       name="Banner folder", blank="log folder\\Banners")
            banner_form.addRow(self.banner_enabled)
            banner_form.addRow("Banner folder (blank = log folder\\Banners):", self.banner_dir)
            banner_form.addRow(self._help(
                "Until 45 seconds after the log's END_TRIAL (at least 15) the screen is grabbed "
                "once a second. Of the grabs on which Windows' text recognition reads the run's "
                "final score, the one with the whole banner drawn is cropped to it and saved as "
                "a PNG; nothing is kept otherwise. The game must be on screen, in borderless or "
                "windowed mode. What each grab read is noted in banner.log beside the settings.",
                self.banner_enabled))
            layout.addWidget(banner_group)

        # Companions (issue #74, companions.py): each has its own row under
        # its owner; this adds its figures to the owner's as well
        companion_group = QGroupBox("Companions")
        companion_form = _form(companion_group)
        self.companion_accrual = QCheckBox(
            "Count a companion's damage and healing as its owner's too")
        self.companion_accrual.setChecked(bool(config.get("companions.accrue_to_owner", False)))
        companion_form.addRow(self.companion_accrual)
        companion_form.addRow(self._help(COMPANION_HELP, self.companion_accrual))
        layout.addWidget(companion_group)

        # The fight history across sessions (issue #170, fight_index): what
        # it holds, and the backfill from the split logs
        history_group = QGroupBox("Fight history")
        history_box = QVBoxLayout(history_group)
        self.history_status = QLabel(history_status or "")
        self.history_status.setWordWrap(True)
        self.history_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        history_box.addWidget(self.history_status)
        history_row = QHBoxLayout()
        self.build_history_button = QPushButton("Build from split logs")
        self.build_history_button.setEnabled(on_build_history is not None)
        self.build_history_button.clicked.connect(self._build_history)
        history_row.addWidget(self.build_history_button)
        history_row.addStretch(1)
        history_box.addLayout(history_row)
        history_box.addWidget(self._help(HISTORY_HELP, self.build_history_button))
        layout.addWidget(history_group)

        # Death recaps (issue #95, death_recap): the seconds kept before
        # each death; the engine reads it when a save rebuilds it
        recap_group = QGroupBox("Death recaps")
        recap_form = _form(recap_group)
        self.recap_window = _SpinBox()
        self.recap_window.setRange(MIN_WINDOW_S, MAX_WINDOW_S)
        self.recap_window.setValue(
            recap_window_s(config.get("death_recap.window_s", DEFAULT_WINDOW_S)))
        # "1 second", not "1 seconds" (issue #133)
        self._recap_suffix(self.recap_window.value())
        self.recap_window.valueChanged.connect(self._recap_suffix)
        recap_form.addRow("Window before each death:", self.recap_window)
        recap_form.addRow(self._help(RECAP_HELP, self.recap_window))
        layout.addWidget(recap_group)

        # Tracked effects: the rule text, with its parse result underneath;
        # the timeline strip above each fight draws them
        tracking_group = QGroupBox("Tracked effects")
        tracking_layout = QVBoxLayout(tracking_group)
        self.rules_edit = QPlainTextEdit()
        self.rules_edit.setAccessibleName("Tracked effect rules")
        self.rules_edit.setFont(text_size.fixed_font())
        self.rules_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Tab leaves the editor: inside it Tab inserted a tab character and
        # kept the focus, so a keyboard user could never reach Examples…
        # or Save from the rules; no rule needs one (parse_rules splits on
        # whitespace), and Ctrl+Tab still moves on (issue #187)
        self.rules_edit.setTabChangesFocus(True)
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
        tracking_layout.addWidget(self._help(RULES_HELP, self.rules_edit))
        self.rules_edit.textChanged.connect(self._check_rules)
        self._check_rules()
        layout.addWidget(tracking_group)

        # Penetration and critical damage: the Champion Point rows the build
        # window assumes, and the cap (pen_crit); read at render time, so no
        # restart is needed for them
        pen_group = QGroupBox("Penetration and critical damage")
        pen_form = _form(pen_group)
        self.assume_piercing = QCheckBox("Assume Piercing (700 penetration, a passive star)")
        self.assume_piercing.setChecked(bool(config.get("pen_crit.piercing", True)))
        pen_form.addRow(self.assume_piercing)
        self.assume_finesse = QCheckBox(
            "Assume Fighting Finesse (8% critical damage) in fights of up to four players")
        self.assume_finesse.setChecked(bool(config.get("pen_crit.fighting_finesse", True)))
        pen_form.addRow(self.assume_finesse)
        self.assume_backstabber = QCheckBox("Assume Backstabber (10% critical damage while flanking)")
        self.assume_backstabber.setChecked(bool(config.get("pen_crit.backstabber", False)))
        pen_form.addRow(self.assume_backstabber)
        fon_row = QHBoxLayout()
        self.assume_force_of_nature = QCheckBox("Assume Force of Nature:")
        self.assume_force_of_nature.setChecked(bool(config.get("pen_crit.force_of_nature", False)))
        fon_row.addWidget(self.assume_force_of_nature)
        self.force_of_nature_value = _SpinBox()
        self.force_of_nature_value.setAccessibleName("Force of Nature per status effect")
        self.force_of_nature_value.setRange(1, 5000)
        self.force_of_nature_value.setValue(
            int(config.get("pen_crit.force_of_nature_per_effect", FORCE_OF_NATURE_PER_EFFECT)
                or FORCE_OF_NATURE_PER_EFFECT))
        self.force_of_nature_value.setToolTip(
            "The tooltip's figure per unique status effect; Combat Metrics uses 660")
        fon_row.addWidget(self.force_of_nature_value)
        fon_row.addWidget(QLabel("per status effect measured on the boss"))
        fon_row.addStretch(1)
        pen_form.addRow(fon_row)
        self.pen_cap = QComboBox()
        for key, label in CAP_CHOICES:
            self.pen_cap.addItem(label, key)
        current = str(config.get("pen_crit.cap", "auto") or "auto")
        index = next((i for i, (key, _label) in enumerate(CAP_CHOICES) if key == current), 0)
        self.pen_cap.setCurrentIndex(index)
        pen_form.addRow("Penetration cap:", self.pen_cap)
        pen_form.addRow(self._help(PEN_CRIT_HELP, self.pen_cap))  # under its controls, as elsewhere
        layout.addWidget(pen_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._fit_to_screen(content)

    def _small_style(self, role: str) -> str:
        """The style of a helper line under a setting, a little smaller than
        the dialog's text and in points so it follows the text size: the
        theme's muted grey, or its warning orange (*role* 'warning'), both
        4.5:1 or more on either theme (#77; the fixed #888 and #d98a3d
        measured 3.2 and 2.5 on the light one); 'plain' is the small size
        in the normal text colour, for a line that states a consequence."""
        size = f"font-size: {text_size.small_pt()}pt;"
        if role == "plain":
            return size
        theme = _theme(self.palette().color(self.backgroundRole()).lightness() < 128)
        color = theme["vet"] if role == "warning" else theme["muted"]
        return f"color: {color}; {size}"

    def _help(self, text: str, *controls: QWidget, role: str = "muted") -> QLabel:
        """A wrapped helper paragraph under *controls*, the settings it
        explains, in the small muted style (or the warning one). The text
        is also each control's accessible description, after whatever the
        control already says of itself (a path field's "Blank = …"), so a
        screen reader says it with the control rather than as a paragraph
        on its own (issue #187)."""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(self._small_style(role))
        for control in controls:
            said = control.accessibleDescription()
            control.setAccessibleDescription(f"{said} {text}" if said else text)
        return label

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
            width = min(width, int(screen.availableGeometry().width() * 0.9))
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
        self.retention_preview.setVisible(bool(lines))

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

    def _build_history(self) -> None:
        """Start the backfill on the split folder these fields name (saved
        or not); the dialog stays open, its Save or Cancel leaves the
        backfill running, and a refusal is said here, not behind the
        dialog."""
        if self._on_build_history is None:
            return
        started, message = self._on_build_history(self.retention_folder())
        self.history_status.setText(message)
        if started:
            self.build_history_button.setEnabled(False)
            self.build_history_button.setText("Building: see the status bar")

    def _recap_suffix(self, value: int) -> None:
        self.recap_window.setSuffix(" second" if value == 1 else " seconds")

    def _snap_text_size(self, value: int) -> None:
        """Keep the slider on a step (a drag can stop between two) and
        show its percentage beside it."""
        snapped = text_size.clamp(round(value / text_size.STEP_PCT) * text_size.STEP_PCT)
        if snapped != value:
            self.text_size.setValue(snapped)
            return
        self.text_size_label.setText(f"{snapped}%")

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
            self.rules_status.setStyleSheet(self._small_style("warning"))
            self.rules_status.setText(f"{count}; skipped: " + "; ".join(errors))
        else:
            self.rules_status.setStyleSheet(self._small_style("muted"))
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
        self.config.set("update.channel", self.update_channel.currentData())
        self.config.set("privacy.hide_names", self.hide_names.isChecked())
        if hasattr(self, "banner_enabled"):  # the Windows-only group
            self.config.set("banner.enabled", self.banner_enabled.isChecked())
            self.config.set("banner.dir", self.banner_dir.value())
        self.config.set(text_size.CONFIG_KEY, self.text_size.value())
        self.config.set("display.colorblind_graph", self.colorblind_graph.isChecked())
        self.config.set("display.reduce_motion", self.reduce_motion.isChecked())
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
