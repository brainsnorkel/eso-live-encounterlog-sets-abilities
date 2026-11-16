"""The keys that differ on macOS (issue #32).

The app's keys are written once, as Windows and Linux have them ("Ctrl+F",
"Alt+I"), and everything that binds one or names one in a text asks here.
Four things differ on a Mac:

The names. Qt maps Ctrl to Command there, so "Ctrl+F" is bound to ⌘F with
no change, but a tooltip that says "Ctrl+F" names a key the user must not
press. key_text() writes a key as the platform does: "⌘F" on macOS,
"Ctrl+F" elsewhere.

Three keys macOS gives a meaning of its own. Ctrl+H would be ⌘H (Hide
application), Ctrl+, would be ⌘, (Settings) and Ctrl+. would be ⌘.
(Cancel). MAC_KEYS moves them, and key_text() and sequence() both read it,
so a text can never name the key the app did not bind.

Return and Enter on a table row. Everywhere else a QAbstractItemView
answers them with `activated`; on macOS it keeps Return for editing a cell
and sends `activated` for ⌘O only. on_row_activated() connects the signal
and, on macOS, answers Return and Enter itself.

The Alt letters. Qt leaves the '&' mnemonics of tabs and buttons off on
macOS. use_alt_letters() turns them on (Option-letter there).

The platform is read at each call, not once at import, so a test can try
both by patching sys.platform. The constants other modules build from
key_text() are still made at import, which is right for an app that runs
on one platform.
"""

import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, qt_set_sequence_auto_mnemonic

# The app's key -> the key bound on macOS, written as Qt reads them: there
# "Ctrl" is Command and "Meta" is Control
MAC_KEYS = {
    "Ctrl+H": "Ctrl+Shift+H",  # ⇧⌘H: ⌘H hides the application
    "Ctrl+,": "Meta+,",        # ⌃,: ⌘, is Settings
    "Ctrl+.": "Meta+.",        # ⌃.: ⌘. is Cancel
}


def is_mac() -> bool:
    return sys.platform == "darwin"


def keys_for(keys: str) -> str:
    """The key bound for the app's *keys* on this platform."""
    return MAC_KEYS.get(keys, keys) if is_mac() else keys


def sequence(keys: str) -> QKeySequence:
    """The QKeySequence to bind for the app's *keys*. A name Qt cannot read
    ("Ctrl+PgDn" for "Ctrl+PgDown") makes a sequence of an unknown key,
    which would bind nothing without a word, so it is an error here."""
    bound = QKeySequence(keys_for(keys))
    if bound.isEmpty() or any(bound[i].key() == Qt.Key_unknown for i in range(bound.count())):
        raise ValueError(f"not a key Qt can read: {keys!r}")
    return bound


def key_text(keys: str) -> str:
    """The app's *keys* as this platform writes them, for a tooltip, a
    placeholder or an accessible name: "⌘F" on macOS, "Ctrl+F" elsewhere.

    Off macOS the text is Qt's own name for the key, with Page Down
    shortened to the "PgDn" the app's texts have always used."""
    bound = sequence(keys)
    if is_mac():
        return bound.toString(QKeySequence.NativeText)
    return bound.toString(QKeySequence.PortableText).replace("PgDown", "PgDn")


def use_alt_letters() -> None:
    """Turn the '&' mnemonics on where Qt leaves them off (macOS), so the
    tabs' Alt letters work there as Option-letter. Called before the first
    window is made; elsewhere they are already on."""
    if is_mac():
        qt_set_sequence_auto_mnemonic(True)


class _ReturnActivates(QObject):
    """Answers Return and Enter on *view*'s current row with *slot*, as the
    view's own `activated` does off macOS. The key is taken, not passed on:
    the view would only refuse to edit the cell."""

    def __init__(self, view, slot):
        super().__init__(view)
        self._view = view
        self._slot = slot

    def eventFilter(self, watched, event) -> bool:
        if (event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)):
            index = self._view.currentIndex()
            if index.isValid():
                self._slot(index)
                return True
        return False


def on_row_activated(view, slot) -> None:
    """Call *slot* with the row's index when a row of *view* is activated:
    a double-click, or Return or Enter on the current row, on every
    platform (see the module)."""
    view.activated.connect(slot)
    if is_mac():
        view.installEventFilter(_ReturnActivates(view, slot))
