"""
Build window: one player's bars, gear, mundus stone and food for a fight, as
the log recorded them when combat started (see build_render).

Modeless, so it can stay open beside the fight view; asking for another
player's build reuses the same window. It keeps the fight it was opened for:
a new fight arriving, or another one being selected, does not change it.
"""

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

    def show_build(self, entry, unit_id: str, dark: bool) -> None:
        """Show the build of the player *unit_id* in the fight *entry*."""
        self._shown = (entry, unit_id)
        self.setWindowTitle(build_title(entry, unit_id))
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
            text_color=self.view.palette().color(QPalette.Text).name()))

    def refresh(self, dark: bool) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors)."""
        if self._shown is not None and self.isVisible():
            self.show_build(self._shown[0], self._shown[1], dark)
