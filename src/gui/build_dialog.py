"""
Build window: one player's bars, gear, mundus stone and food for a fight, as
the log recorded them when combat started (see build_render).

Modeless, so it can stay open beside the fight view; asking for another
player's build reuses the same window. It keeps the fight it was opened for:
a new fight arriving, or another one being selected, does not change it.
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from ability_icons import esohub_ability_url, esohub_script_url, esohub_set_url
from gui.build_render import build_title, render_build_html
from gui.fight_render import anchor_tooltips
from gui.fight_view import FightView


class BuildDialog(QDialog):

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self.setWindowTitle("Build")
        self.resize(880, 760)  # a full build with both poison rows, unscrolled
        self._shown = None  # (entry, unit_id) on display, for theme switches

        layout = QVBoxLayout(self)
        # A FightView serves the bundled icons to the rendered HTML, shows
        # the hover text and opens the ESO-Hub links
        self.view = FightView(icons=icons)
        layout.addWidget(self.view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @property
    def entry(self):
        """The fight on display, None before the first build."""
        return self._shown[0] if self._shown is not None else None

    def show_build(self, entry, unit_id: str, dark: bool, pen_crit_options=None,
                   scroll_to: str = None, names=None) -> None:
        """Show the build of the player *unit_id* in the fight *entry*.
        *pen_crit_options* is the config's pen_crit section (the assumed
        Champion Point rows and the cap the sections use); *scroll_to* names
        an anchor in the page to open at (build_render.PEN_CRIT_ANCHOR);
        *names* is the Hide names mask (gui.name_mask)."""
        self._shown = (entry, unit_id, pen_crit_options, names)
        self.setWindowTitle(build_title(entry, unit_id, names))
        # The window's anchors use the fight view's targets, so its hover
        # text serves here too
        self.view.set_tooltips(anchor_tooltips(
            entry, links=esohub_ability_url, set_links=esohub_set_url,
            script_links=esohub_script_url))
        self.view.setHtml(render_build_html(
            entry, unit_id, dark=dark, icons=self.view.icons,
            links=esohub_ability_url, set_links=esohub_set_url,
            script_links=esohub_script_url,
            base_pt=self.view.font().pointSizeF(),
            text_color=self.view.palette().color(QPalette.Text).name(),
            pen_crit_options=pen_crit_options, names=names))
        if scroll_to:
            # Now, and once the view has laid the document out
            self.view.scrollToAnchor(scroll_to)
            QTimer.singleShot(0, lambda: self.view.scrollToAnchor(scroll_to))

    def refresh(self, dark: bool, names=None) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors) or
        a flip of the Hide names switch (*names*, the new mask; None keeps
        the one shown)."""
        if self._shown is not None and self.isVisible():
            entry, unit_id, options, shown = self._shown
            scroll = self.view.verticalScrollBar().value()
            self.show_build(entry, unit_id, dark, options,
                            names=shown if names is None else names)
            self.view.restore_scroll(scroll)
