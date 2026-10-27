"""
Damage taken window: one player's damage taken and healing received over a
whole fight, by kind, by source and by healer (see taken_render). Opened
from the shield after a player's name on the fight pane, for any player.

Modeless, so it can stay open beside the fight view; asking for another
player reuses the same window. It keeps the fight it was opened for: a new
fight arriving, or another one being selected, does not change it.
"""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from gui.death_render import kind_tooltips
from gui.fight_view import FightView
from gui.taken_render import render_taken_html, taken_title


class TakenDialog(QDialog):

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self.setWindowTitle("Damage taken")
        self.resize(900, 640)
        self._shown = None  # (entry, unit_id, dark, names) on display, for re-renders

        layout = QVBoxLayout(self)
        # A FightView serves the bundled ability icons to the rendered HTML
        self.view = FightView(icons=icons)
        layout.addWidget(self.view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @property
    def entry(self):
        """The fight on display, None before the first player."""
        return self._shown[0] if self._shown is not None else None

    def show_taken(self, entry, unit_id: str, dark: bool, names=None) -> None:
        """Show the damage taken by the player *unit_id* in the fight
        *entry*; *names* is the Hide names mask (gui.name_mask)."""
        self._shown = (entry, unit_id, dark, names)
        self.setWindowTitle(taken_title(entry, unit_id, names))
        # The kinds bars' star links carry their hover text (the Warfare
        # stars for each side); a click opens the ESO-Hub page
        self.view.set_tooltips(kind_tooltips())
        self.view.setHtml(render_taken_html(
            entry, unit_id, dark=dark, icons=self.view.icons,
            base_pt=self.view.font().pointSizeF(), names=names,
            text_color=self.view.palette().color(QPalette.Text).name()))

    def refresh(self, dark: bool, names=None) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors) or
        a flip of the Hide names switch (*names*, the new mask; None keeps
        the one shown)."""
        if self._shown is not None and self.isVisible():
            entry, unit_id, _dark, shown = self._shown
            scroll = self.view.verticalScrollBar().value()
            self.show_taken(entry, unit_id, dark, names=shown if names is None else names)
            self.view.restore_scroll(scroll)
