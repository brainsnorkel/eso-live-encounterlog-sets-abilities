"""
The (i) popup: one player's possible build issues, each with the rule
behind it, in a transient popup beside the pointer. The rules and the
texts are the engine's (build_issues); fight_render.issues_html lays them
out, and the build window shows the same HTML under its header.

Like the timeline strip's SummaryPopup it is a Qt.Popup frame: it closes on
a click elsewhere or Esc and deletes itself when closed, and nothing keeps
a reference to it, Qt owning it through its parent. The ESO-Hub links in
it open in the system browser.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout

POPUP_WIDTH = 460  # wide enough for a rule's sentence or two per line


class BuildIssuesPopup(QFrame):

    def __init__(self, html: str, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self.label = QLabel(html)
        self.label.setTextFormat(Qt.RichText)
        self.label.setWordWrap(True)
        self.label.setFixedWidth(POPUP_WIDTH)
        self.label.setOpenExternalLinks(True)
        self.label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(self.label)

    def show_at(self, pos: QPoint) -> None:
        """Show with the top-left corner at *pos* (the pointer), pulled onto
        the screen when it would overhang an edge. The frame's size is only
        settled once it is shown, so it is placed after showing."""
        self.move(pos)
        self.show()
        self.adjustSize()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            frame = self.frameGeometry()
            x = max(area.left(), min(pos.x(), area.right() - frame.width() + 1))
            y = max(area.top(), min(pos.y(), area.bottom() - frame.height() + 1))
            if (x, y) != (pos.x(), pos.y()):
                self.move(x, y)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)
