"""Example tracking rules to pick from: a list with a checkbox per example,
its rule line underneath, and buttons to add the chosen lines to the
Settings box or to copy them for sharing (effect_rules.EXAMPLE_RULES).

Examples whose rule name the box already holds start unticked, so pressing
Add on a fresh install adds nothing twice.
"""

from typing import Iterable, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout,
)

from effect_rules import EXAMPLE_RULES, rule_name as _rule_name


class ExamplesDialog(QDialog):
    """Pick example rules. selected_lines() is what the user ticked."""

    def __init__(self, present_names: Iterable[str] = (), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Example tracking rules")
        self.setMinimumSize(640, 420)
        present = {name.lower() for name in present_names}
        layout = QVBoxLayout(self)
        intro = QLabel("Tick the rules to add to your tracked effects. Each one is a line "
                       "you can also edit afterwards; Copy puts the ticked lines on the "
                       "clipboard to share.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.list.setSpacing(3)
        for title, note, line in EXAMPLE_RULES:
            item = QListWidgetItem(f"{title}\n  {note}\n  {line}")
            item.setData(Qt.UserRole, line)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            already = _rule_name(line) in present
            item.setCheckState(Qt.Unchecked if already else Qt.Checked)
            if already:
                item.setToolTip("A rule with this name is already in the box")
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        self.buttons = QDialogButtonBox()
        self.add_button = self.buttons.addButton("Add to rules", QDialogButtonBox.AcceptRole)
        self.copy_button = self.buttons.addButton("Copy", QDialogButtonBox.ActionRole)
        self.buttons.addButton(QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.copy_button.clicked.connect(self.copy_selected)
        layout.addWidget(self.buttons)

    def selected_lines(self) -> List[str]:
        return [self.list.item(i).data(Qt.UserRole)
                for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]

    def copy_selected(self) -> None:
        """The ticked lines, one per line, on the clipboard."""
        lines = self.selected_lines()
        if lines:
            QGuiApplication.clipboard().setText("\n".join(lines) + "\n")
