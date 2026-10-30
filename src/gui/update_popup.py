"""
The ⓘ popup beside the Update button: the release on offer, its date, its
notes as GitHub publishes them, links to the release page and the
changelog, and the way to skip the version. A Qt.Popup frame like
BuildIssuesPopup: it closes on a click elsewhere or Esc and deletes itself,
and nothing keeps a reference to it.

The notes are GitHub's generated release notes (one line per pull request
with its link, and a compare link), rendered from markdown; the
maintainer chose them on 2026-10-26 over the CHANGELOG entries, which run
to a dozen lines each and are one click away through the Changelog link.
The notes are the offered release's own, so someone several releases
behind (a Stable user, issue #134, skips every beta in between) would see
only the last step; the "Changes since" link compares the running version
with the offered one on GitHub, however many releases lie between.
"""

from PySide6.QtCore import QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QTextBrowser, QVBoxLayout

from gui.build_issues_popup import place_popup
from update_check import changelog_url, compare_url, format_release_date

POPUP_WIDTH = 520
NOTES_MAX_HEIGHT = 400
SKIP_HREF = "esolog:skip-version"
NO_NOTES = "No notes were published with this release."


class UpdateNotesPopup(QFrame):

    skip_requested = Signal()

    def __init__(self, info, current_version: str, dark: bool, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFrameShape(QFrame.StyledPanel)
        self.info = info
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        released = format_release_date(info.published)
        when = f" · released {released}" if released else ""
        self.heading = QLabel(
            f"<b>ESO Log Tail {info.version}</b>{when}"
            f"<span style='color: gray'> (you have {current_version})</span>")
        self.heading.setTextFormat(Qt.RichText)
        self.heading.setWordWrap(True)
        self.heading.setFixedWidth(POPUP_WIDTH)
        layout.addWidget(self.heading)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        self.notes.setFrameShape(QFrame.NoFrame)
        self.notes.setFixedWidth(POPUP_WIDTH)
        self.notes.setMarkdown((info.notes or "").strip() or NO_NOTES)
        # Height to fit the notes, scrolling past the cap
        self.notes.document().setTextWidth(POPUP_WIDTH - 8)
        height = int(self.notes.document().size().height()) + 8
        self.notes.setFixedHeight(max(24, min(NOTES_MAX_HEIGHT, height)))
        layout.addWidget(self.notes)

        self.links = QLabel(
            f"<a href='{info.page_url}'>Release page</a> · "
            f"<a href='{changelog_url(info.tag)}'>Changelog</a> · "
            f"<a href='{compare_url(current_version, info.tag)}'>"
            f"Changes since {current_version}</a> · "
            f"<a href='{SKIP_HREF}'>Don't show this version again</a>")
        self.links.setTextFormat(Qt.RichText)
        self.links.setWordWrap(True)
        self.links.setFixedWidth(POPUP_WIDTH)
        self.links.setOpenExternalLinks(False)
        self.links.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.links.linkActivated.connect(self._on_link)
        layout.addWidget(self.links)

    def _on_link(self, href: str) -> None:
        if href == SKIP_HREF:
            self.skip_requested.emit()
            self.close()
        elif href:
            QDesktopServices.openUrl(QUrl(href))

    def show_at(self, pos: QPoint) -> None:
        """Show with the top-left corner at *pos*, kept on the screen."""
        place_popup(self, pos)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)
