"""
Death recap window: one player's deaths in a fight, each with the last
seconds of damage and healing before it (see death_render).

Modeless, so it can stay open beside the fight view; asking for another
player's recap reuses the same window.
"""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from gui.death_render import deaths_by_unit, render_death_recap_html
from gui.fight_view import FightView


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

    def show_recap(self, entry, unit_id: str, dark: bool) -> None:
        """Show the deaths of the player *unit_id* in the fight *entry*."""
        self._shown = (entry, unit_id)
        deaths = deaths_by_unit(entry).get(str(unit_id), [])
        name = str(deaths[0].get("name", "")) if deaths else ""
        self.setWindowTitle(f"Death recap – {name}" if name else "Death recap")
        self.view.setHtml(render_death_recap_html(
            entry, unit_id, dark=dark, icons=self.view.icons,
            base_pt=self.view.font().pointSizeF()))

    def refresh(self, dark: bool) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors)."""
        if self._shown is not None and self.isVisible():
            self.show_recap(self._shown[0], self._shown[1], dark)
