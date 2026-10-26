"""
Death recap window: one player's deaths in a fight, each with the last
seconds of damage and healing before it (see death_render).

Modeless, so it can stay open beside the fight view; asking for another
player's recap reuses the same window.
"""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from gui.death_render import deaths_by_unit, kind_tooltips, render_death_recap_html
from gui.fight_view import FightView
from gui.name_mask import NO_MASK


class DeathRecapDialog(QDialog):

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self.setWindowTitle("Death recap")
        self.resize(900, 600)
        self._shown = None  # (entry, unit_id) on display, for theme switches

        layout = QVBoxLayout(self)
        # A FightView serves the bundled ability icons to the rendered HTML
        self.view = FightView(icons=icons)
        layout.addWidget(self.view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @property
    def entry(self):
        """The fight on display, None before the first recap."""
        return self._shown[0] if self._shown is not None else None

    def show_recap(self, entry, unit_id: str, dark: bool, names=None) -> None:
        """Show the deaths of the player *unit_id* in the fight *entry*;
        *names* is the Hide names mask (gui.name_mask)."""
        self._shown = (entry, unit_id, names)
        deaths = deaths_by_unit(entry).get(str(unit_id), [])
        name = (names or NO_MASK).text(str(deaths[0].get("name", ""))) if deaths else ""
        self.setWindowTitle(f"Death recap – {name}" if name else "Death recap")
        # The kinds summaries' star links carry their hover text (the
        # Warfare stars for each side); a click opens the ESO-Hub page
        self.view.set_tooltips(kind_tooltips())
        self.view.setHtml(render_death_recap_html(
            entry, unit_id, dark=dark, icons=self.view.icons,
            base_pt=self.view.font().pointSizeF(), names=names,
            text_color=self.view.palette().color(QPalette.Text).name()))

    def refresh(self, dark: bool, names=None) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors) or
        a flip of the Hide names switch (*names*, the new mask; None keeps
        the one shown)."""
        if self._shown is not None and self.isVisible():
            entry, unit_id, shown = self._shown
            scroll = self.view.verticalScrollBar().value()
            self.show_recap(entry, unit_id, dark, names=shown if names is None else names)
            self.view.restore_scroll(scroll)
