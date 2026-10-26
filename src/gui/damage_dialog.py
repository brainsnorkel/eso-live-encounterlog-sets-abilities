"""
Damage window: one player's damage in a fight, broken down by ability and by
target (see damage_render), with a switch to the boss units alone.

Modeless, so it can stay open beside the fight view; asking for another
player's damage reuses the same window. It keeps the fight it was opened
for: a new fight arriving, or another one being selected, does not change
it. The boss switch keeps its state from one player to the next while the
fight has a boss, and is hidden (and off) when it has none.
"""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QVBoxLayout

from gui.build_render import player_for
from gui.damage_render import damage_title, render_damage_html
from gui.fight_view import FightView

BOSS_ONLY_LABEL = "Boss targets only"


class DamageDialog(QDialog):

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self.setWindowTitle("Damage")
        self.resize(900, 640)
        self._shown = None  # (entry, unit_id, dark) on display, for re-renders

        layout = QVBoxLayout(self)
        # A FightView serves the bundled ability icons to the rendered HTML
        self.view = FightView(icons=icons)
        layout.addWidget(self.view, 1)
        bottom = QHBoxLayout()
        self.boss_only = QCheckBox(BOSS_ONLY_LABEL)
        self.boss_only.toggled.connect(self._rerender)
        bottom.addWidget(self.boss_only)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

    @property
    def entry(self):
        """The fight on display, None before the first player."""
        return self._shown[0] if self._shown is not None else None

    def show_damage(self, entry, unit_id: str, dark: bool, names=None) -> None:
        """Show the damage of the player *unit_id* in the fight *entry*;
        *names* is the Hide names mask (gui.name_mask)."""
        self._shown = (entry, unit_id, dark, names)
        self.setWindowTitle(damage_title(entry, unit_id, names))
        player = player_for(entry, unit_id) or {}
        damage = player.get("damage") if isinstance(player.get("damage"), dict) else {}
        has_boss = bool(damage and damage.get("boss"))
        if not has_boss and self.boss_only.isChecked():
            self.boss_only.blockSignals(True)
            self.boss_only.setChecked(False)
            self.boss_only.blockSignals(False)
        self.boss_only.setVisible(has_boss)
        self._rerender()

    def refresh(self, dark: bool, names=None) -> None:
        """Re-render for a theme switch (the HTML embeds theme colors) or
        a flip of the Hide names switch (*names*, the new mask; None keeps
        the one shown)."""
        if self._shown is not None and self.isVisible():
            entry, unit_id, _dark, shown = self._shown
            scroll = self.view.verticalScrollBar().value()
            self.show_damage(entry, unit_id, dark, names=shown if names is None else names)
            self.view.restore_scroll(scroll)

    def _rerender(self) -> None:
        if self._shown is None:
            return
        entry, unit_id, dark, names = self._shown
        self.view.setHtml(render_damage_html(
            entry, unit_id, boss_only=self.boss_only.isChecked(), dark=dark,
            icons=self.view.icons, base_pt=self.view.font().pointSizeF(), names=names,
            text_color=self.view.palette().color(QPalette.Text).name()))
