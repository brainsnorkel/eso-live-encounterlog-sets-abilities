"""
The (i) popup: one player's possible build issues, each with the rule
behind it, in a transient popup beside the pointer, or under the (i) when
Enter opened it from the keyboard (issue #196). The rules and the texts
are the engine's (build_issues); fight_render.issues_html lays them out,
and the build window shows the same HTML under its header.

Like the timeline strip's SummaryPopup it is a Qt.Popup frame: it closes on
a click elsewhere or Esc and deletes itself when closed, and nothing keeps
a reference to it, Qt owning it through its parent. The ESO-Hub links in
it open in the system browser, and a set's link shows on hover the lines
of the set the player has (fight_render.set_tooltips, issue #79).
"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QToolTip, QVBoxLayout

POPUP_WIDTH = 460  # wide enough for a rule's sentence or two per line


def place_popup(frame, pos: QPoint) -> None:
    """Show *frame* with its top-left corner at *pos* (the pointer, or a
    point under a link), pulled onto the screen when it would overhang an
    edge. A frame's size is only settled once it is shown, so it is placed
    after showing. Shared with the Update button's notes popup."""
    frame.move(pos)
    frame.show()
    frame.adjustSize()
    screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        geometry = frame.frameGeometry()
        x = max(area.left(), min(pos.x(), area.right() - geometry.width() + 1))
        y = max(area.top(), min(pos.y(), area.bottom() - geometry.height() + 1))
        if (x, y) != (pos.x(), pos.y()):
            frame.move(x, y)


class BuildIssuesPopup(QFrame):

    def __init__(self, html: str, parent=None, tooltips=None):
        """*tooltips*: hover text per link address, as the fight pane's."""
        super().__init__(parent, Qt.Popup)
        self._tooltips = dict(tooltips or {})
        self.current_tooltip = ""  # the hover text last shown, for tests
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
        self.label.linkHovered.connect(self._on_link_hovered)
        layout.addWidget(self.label)

    def _on_link_hovered(self, link: str) -> None:
        text = self._tooltips.get(link) if link else None
        self.current_tooltip = text or ""
        if text:
            QToolTip.showText(QCursor.pos(), text, self.label)
        else:
            QToolTip.hideText()

    def show_at(self, pos: QPoint) -> None:
        """Show with the top-left corner at *pos* (the pointer), kept on
        the screen (place_popup)."""
        place_popup(self, pos)

    def show_under(self, rect: QRect) -> None:
        """Show just under *rect* (a link, in screen coordinates), the left
        edges lined up, kept on the screen (place_popup)."""
        place_popup(self, QPoint(rect.left(), rect.bottom() + 1))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)
