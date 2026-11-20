#!/usr/bin/env python3
"""The keys that differ on macOS (gui.keys, issue #32): which key is bound
and how a text names it, on each platform; Return and Enter on a table
row; the Alt letters; the window icon macOS is not given; and that no text
in the app names a key the Windows way.

A test that needs the other platform patches gui.keys.is_mac, which is all
gui.keys reads; sys.platform itself is left alone, since the rest of the
app reads it too. What only a Mac's Qt does (the ⌘ in a key's name, Return
on a table row) is tested on macOS only."""

import ast
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app

SRC = Path(__file__).parent.parent.parent / "src"
ON_MAC = sys.platform == "darwin"


def _as(mac: bool):
    """gui.keys answering as macOS (or as Windows and Linux)."""
    return mock.patch("gui.keys.is_mac", return_value=mac)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWhichKey(unittest.TestCase):

    def test_three_keys_move_on_macos(self):
        from gui.keys import keys_for
        with _as(True):
            self.assertEqual(keys_for("Ctrl+H"), "Ctrl+Shift+H")
            self.assertEqual(keys_for("Ctrl+,"), "Meta+,")
            self.assertEqual(keys_for("Ctrl+."), "Meta+.")
            self.assertEqual(keys_for("Ctrl+F"), "Ctrl+F")
        with _as(False):
            for keys in ("Ctrl+H", "Ctrl+,", "Ctrl+.", "Ctrl+F"):
                self.assertEqual(keys_for(keys), keys)

    def test_the_sequence_bound_is_the_moved_key(self):
        from PySide6.QtGui import QKeySequence

        from gui.keys import sequence
        with _as(True):
            self.assertEqual(sequence("Ctrl+H"), QKeySequence("Ctrl+Shift+H"))
            self.assertEqual(sequence("Ctrl+D"), QKeySequence("Ctrl+D"))
        with _as(False):
            self.assertEqual(sequence("Ctrl+H"), QKeySequence("Ctrl+H"))

    def test_a_key_qt_cannot_read_is_an_error(self):
        from gui.keys import key_text, sequence
        for bad in ("Ctrl+PgDn", "", "Ctrl+Nothing+Q"):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    sequence(bad)
                with self.assertRaises(ValueError):
                    key_text(bad)

    def test_the_platform_is_read_at_each_call(self):
        from gui import keys
        with mock.patch.object(keys.sys, "platform", "darwin"):
            self.assertTrue(keys.is_mac())
        for other in ("win32", "linux"):
            with mock.patch.object(keys.sys, "platform", other):
                self.assertFalse(keys.is_mac())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestKeyText(unittest.TestCase):

    def test_off_macos_the_texts_are_the_ones_the_app_has_always_had(self):
        from gui.keys import key_text
        with _as(False):
            for keys, text in (("Ctrl+F", "Ctrl+F"), ("Ctrl+H", "Ctrl+H"), ("Alt+I", "Alt+I"),
                               ("Ctrl+Shift+C", "Ctrl+Shift+C"), ("Ctrl+=", "Ctrl+="),
                               ("Ctrl+-", "Ctrl+-"), ("Ctrl+0", "Ctrl+0"), ("Ctrl+,", "Ctrl+,"),
                               ("Ctrl+.", "Ctrl+."), ("Ctrl+Up", "Ctrl+Up"),
                               ("Ctrl+Left", "Ctrl+Left"), ("Ctrl+PgUp", "Ctrl+PgUp"),
                               ("Ctrl+PgDown", "Ctrl+PgDn")):
                with self.subTest(keys):
                    self.assertEqual(key_text(keys), text)

    def test_on_macos_a_text_names_the_key_that_is_bound(self):
        # On any platform: the moved key is the one written, in Qt's
        # native form (which only a Mac's Qt writes with ⌘)
        from PySide6.QtGui import QKeySequence

        from gui.keys import key_text
        with _as(True):
            for keys, bound in (("Ctrl+H", "Ctrl+Shift+H"), ("Ctrl+,", "Meta+,"),
                                ("Ctrl+.", "Meta+."), ("Ctrl+F", "Ctrl+F")):
                with self.subTest(keys):
                    self.assertEqual(key_text(keys),
                                     QKeySequence(bound).toString(QKeySequence.NativeText))

    @unittest.skipUnless(ON_MAC, "the Mac's key symbols are written by a Mac's Qt only")
    def test_the_macs_symbols(self):
        from gui.keys import key_text
        for keys, text in (("Ctrl+F", "⌘F"), ("Ctrl+H", "⇧⌘H"), ("Ctrl+,", "⌃,"), ("Ctrl+.", "⌃."),
                           ("Alt+I", "⌥I"), ("Ctrl+Shift+C", "⇧⌘C"), ("Ctrl+PgDown", "⌘⇟"),
                           ("Ctrl+PgUp", "⌘⇞"), ("Ctrl+Up", "⌘↑"), ("Ctrl+=", "⌘=")):
            with self.subTest(keys):
                self.assertEqual(key_text(keys), text)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestRowActivated(unittest.TestCase):

    def setUp(self):
        from PySide6.QtGui import QStandardItem, QStandardItemModel
        from PySide6.QtWidgets import QAbstractItemView, QTableView
        _ensure_app()
        self.view = QTableView()
        self.addCleanup(self.view.deleteLater)
        self.model = QStandardItemModel(3, 2, self.view)
        for row in range(3):
            for column in range(2):
                self.model.setItem(row, column, QStandardItem(f"{row}.{column}"))
        self.view.setModel(self.model)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rows = []

    def _slot(self, index):
        self.rows.append(index.row())

    def _key(self, key):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.keyClick(self.view, key, Qt.NoModifier)

    def test_on_macos_return_and_enter_on_the_current_row_call_the_slot_once(self):
        # The key is taken, so the count is one on every platform: off
        # macOS the view's own `activated` never sees it
        from PySide6.QtCore import Qt

        from gui.keys import on_row_activated
        with _as(True):
            on_row_activated(self.view, self._slot)
        self.view.setCurrentIndex(self.model.index(1, 0))
        self._key(Qt.Key_Return)
        self.assertEqual(self.rows, [1])
        self.view.setCurrentIndex(self.model.index(2, 1))
        self._key(Qt.Key_Enter)
        self.assertEqual(self.rows, [1, 2])

    def test_on_macos_no_current_row_and_other_keys_call_nothing(self):
        from PySide6.QtCore import QModelIndex, Qt

        from gui.keys import on_row_activated
        with _as(True):
            on_row_activated(self.view, self._slot)
        self.view.setCurrentIndex(QModelIndex())
        self._key(Qt.Key_Return)
        self.assertEqual(self.rows, [])
        self.view.setCurrentIndex(self.model.index(0, 0))
        self._key(Qt.Key_Down)  # left to the view: the current row moves
        self.assertEqual(self.rows, [])
        self.assertEqual(self.view.currentIndex().row(), 1)

    def test_the_views_own_signal_is_connected_on_every_platform(self):
        # A double-click, and Return off macOS, arrive as `activated`
        from gui.keys import on_row_activated
        for mac in (True, False):
            with self.subTest(mac=mac):
                self.rows.clear()
                with _as(mac):
                    on_row_activated(self.view, self._slot)
                self.view.activated.emit(self.model.index(2, 0))
                self.assertEqual(set(self.rows), {2})
                self.view.activated.disconnect()

    def test_off_macos_nothing_is_put_before_the_views_keys(self):
        from gui import keys
        with _as(False):
            keys.on_row_activated(self.view, self._slot)
        self.assertEqual(self.view.findChildren(keys._ReturnActivates), [])

    @unittest.skipIf(ON_MAC, "off macOS the view answers Return itself")
    def test_off_macos_return_calls_the_slot_once(self):
        from PySide6.QtCore import Qt

        from gui.keys import on_row_activated
        on_row_activated(self.view, self._slot)
        self.view.setCurrentIndex(self.model.index(1, 0))
        self._key(Qt.Key_Return)
        self.assertEqual(self.rows, [1])


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestAltLetters(unittest.TestCase):

    def test_they_are_turned_on_on_macos_only(self):
        from gui import keys
        with mock.patch.object(keys, "qt_set_sequence_auto_mnemonic") as turn_on:
            with _as(False):
                keys.use_alt_letters()
            turn_on.assert_not_called()
            with _as(True):
                keys.use_alt_letters()
            turn_on.assert_called_once_with(True)

    def test_the_app_turns_them_on_before_its_first_window(self):
        # Read, not run: main() starts the event loop
        text = (SRC / "esolog_gui.py").read_text(encoding="utf-8")
        self.assertIn("use_alt_letters()", text)
        self.assertLess(text.index("use_alt_letters()"), text.index("MainWindow(config)"))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWindowIcon(unittest.TestCase):
    """macOS shows no icon in a title bar, and the call is documented to
    replace the Dock's icon with the .ico's picture."""

    def _set(self, platform):
        """The icon is asked for on *platform*, with an icon.ico where a
        frozen app keeps it: the repo's own is made by a script and is not
        in a fresh clone."""
        import esolog_gui
        app = mock.Mock()
        with tempfile.TemporaryDirectory() as bundle:
            (Path(bundle) / "icon.ico").write_bytes(b"")
            with mock.patch.object(esolog_gui.sys, "platform", platform), \
                    mock.patch.object(esolog_gui.sys, "_MEIPASS", bundle, create=True):
                esolog_gui._set_window_icon(app)
        return app

    def test_macos_is_given_no_window_icon(self):
        self._set("darwin").setWindowIcon.assert_not_called()

    def test_windows_and_linux_keep_theirs(self):
        _ensure_app()
        for platform in ("win32", "linux"):
            with self.subTest(platform):
                self._set(platform).setWindowIcon.assert_called_once()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheMovedShortcuts(unittest.TestCase):
    """Hide names and the positions window's speed keys, as each platform
    binds them."""

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _main_window(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        root = Path(self.tmp.name)
        config = AppConfig(path=root / "config.json")
        config.set("log_path", str(root / "Encounter.log"))
        config.set("update.check_enabled", False)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.addCleanup(win.close)
        return win

    def test_hide_names(self):
        for mac, keys in ((True, "Ctrl+Shift+H"), (False, "Ctrl+H")):
            with self.subTest(mac=mac), _as(mac):
                win = self._main_window()
                self.assertEqual(win.hide_names_action.shortcut().toString(), keys)

    def test_the_speed_keys(self):
        from PySide6.QtGui import QShortcut

        from gui.positions_window import PositionsWindow
        for mac, slower, faster in ((True, "Meta+,", "Meta+."), (False, "Ctrl+,", "Ctrl+.")):
            with self.subTest(mac=mac), _as(mac):
                window = PositionsWindow()
                self.addCleanup(window.deleteLater)
                bound = {shortcut.key().toString() for shortcut in window.findChildren(QShortcut)}
                self.assertLessEqual({slower, faster}, bound)
                # Never both: on macOS ⌘, and ⌘. stay the system's
                other = {"Ctrl+,", "Ctrl+."} if mac else {"Meta+,", "Meta+."}
                self.assertFalse(other & bound)


# ------------------------------------------------- no text names a key --

KEY_NAME = re.compile(r"(?:Ctrl|Alt|Meta)\+")
# The whole text is one key as the app writes it ("Ctrl+Shift+Left"): what
# is handed to key_text() and sequence()
BARE_KEY = re.compile(r"(?:(?:Ctrl|Alt|Shift|Meta)\+)+\S+")
TEXT_SETTERS = {"setToolTip", "setPlaceholderText", "setStatusTip", "setWhatsThis",
                "setAccessibleName", "setAccessibleDescription", "showMessage"}
TEXT_CONSTANT = re.compile(r".*_(?:TIP|CUE|DESCRIPTION)$")


def _docstrings(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                found.add(id(body[0].value))
    return found


def _strings(node):
    """The string literals in *node*, an f-string's fixed parts included."""
    return [n for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def key_names_in(source: str, name: str = "<source>") -> list:
    """Where *source* writes a key's name into a text itself, not through
    gui.keys (see TestNoTextNamesAKey)."""
    tree = ast.parse(source)
    docstrings = _docstrings(tree)
    found = []
    # A name the module gives a bare key (GRAPH_KEYS = "Ctrl+G"): fine to
    # bind, but written into a text it names the key the Windows way
    key_names = {target.id for node in tree.body if isinstance(node, ast.Assign)
                 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                 and BARE_KEY.fullmatch(node.value.value)
                 for target in node.targets if isinstance(target, ast.Name)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name)
                and node.value.id in key_names):
            found.append(f"{name}:{node.lineno}: a text is given the key {node.value.id}")
    for node in _strings(tree):
        if id(node) in docstrings or not KEY_NAME.search(node.value):
            continue
        if not BARE_KEY.fullmatch(node.value):
            found.append(f"{name}:{node.lineno}: a text names a key: {node.value!r}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = (node.func.attr if isinstance(node.func, ast.Attribute)
                      else getattr(node.func, "id", ""))
            literal = [a for a in node.args if isinstance(a, ast.Constant)
                       and isinstance(a.value, str) and BARE_KEY.fullmatch(a.value)]
            if called in TEXT_SETTERS and literal:
                found.append(f"{name}:{node.lineno}: {called} is given a key: {literal[0].value!r}")
            if called == "QKeySequence" and literal and name != "keys.py":
                found.append(f"{name}:{node.lineno}: QKeySequence({literal[0].value!r}) "
                             "is not bound through gui.keys.sequence")
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if (any(TEXT_CONSTANT.fullmatch(n) for n in names)
                    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                    and BARE_KEY.fullmatch(node.value.value)):
                found.append(f"{name}:{node.lineno}: {names[0]} is a key: {node.value.value!r}")
    return found


class TestNoTextNamesAKey(unittest.TestCase):
    """Every text of the app that names a key is built with
    gui.keys.key_text, so it names the Mac's key on a Mac, and every key
    given by name is bound with gui.keys.sequence, so the three keys macOS
    keeps for itself are moved. Read from the source, so it runs on every
    platform: outside docstrings, a string in src/gui that holds "Ctrl+",
    "Alt+" or "Meta+" must be one bare key, and a bare key must not be
    handed to a text setter, to a _TIP, _CUE or _DESCRIPTION constant, or
    straight to QKeySequence, nor a constant that holds one be written
    into an f-string."""

    def test_the_gui_source(self):
        found = []
        for path in sorted((SRC / "gui").glob("*.py")):
            found += key_names_in(path.read_text(encoding="utf-8"), path.name)
        self.assertEqual(found, [])

    def test_the_launcher(self):
        self.assertEqual(key_names_in((SRC / "esolog_gui.py").read_text(encoding="utf-8"),
                                      "esolog_gui.py"), [])

    def test_the_reading_finds_each_kind(self):
        # The check itself: each way a key's name can get into a text
        cases = {
            'button.setToolTip("Find (Ctrl+F)")': "a text names a key",
            'label = f"Next ({key}) or Alt+I"': "a text names a key",
            'action.setStatusTip("Ctrl+G")': "setStatusTip is given a key",
            'bar.showMessage("Meta+,")': "showMessage is given a key",
            'SPEED_TIP = "Ctrl+."': "SPEED_TIP is a key",
            'QShortcut(QKeySequence("Ctrl+H"), self)': "not bound through gui.keys.sequence",
            'GRAPH_KEYS = "Ctrl+G"\ntext = f"On the graph ({GRAPH_KEYS})"':
                "a text is given the key GRAPH_KEYS",
        }
        for source, message in cases.items():
            with self.subTest(source):
                found = key_names_in(source)
                self.assertEqual(len(found), 1, found)
                self.assertIn(message, found[0])

    def test_the_reading_leaves_these_alone(self):
        for source in ('"""Ctrl+F finds; Alt+I opens the instance."""',
                       'def f():\n    """Ctrl+F or the Find button."""',
                       'button.setToolTip(f"Find ({key_text(\'Ctrl+F\')})")',
                       'QShortcut(sequence("Ctrl+PgDown"), self, slot)',
                       'for keys, slot in (("Ctrl+Left", back), ("Ctrl+Shift+Left", tenth)): pass',
                       'GRAPH_KEYS = "Ctrl+G"\ntext = f"On the graph ({key_text(GRAPH_KEYS)})"',
                       'find.setShortcut(QKeySequence.Find)'):
            with self.subTest(source):
                self.assertEqual(key_names_in(source), [])


def _texts_of(widget):
    """(what, text) for every text *widget* shows, speaks or hovers."""
    from PySide6.QtCore import QModelIndex, Qt
    from PySide6.QtWidgets import QAbstractItemView
    texts = [("tooltip", widget.toolTip()), ("status tip", widget.statusTip()),
             ("what's this", widget.whatsThis()), ("accessible name", widget.accessibleName()),
             ("accessible description", widget.accessibleDescription())]
    for what in ("placeholderText", "text", "title"):
        value = getattr(widget, what, None)
        value = value() if callable(value) else None
        if isinstance(value, str):
            texts.append((what, value))
    if isinstance(widget, QAbstractItemView) and widget.model() is not None:
        model = widget.model()
        for row in range(model.rowCount(QModelIndex())):
            # Until a column has no cell: a list model keeps its column
            # count to itself
            for column in range(64):
                index = model.index(row, column)
                if not index.isValid():
                    break
                for role in (Qt.ToolTipRole, Qt.StatusTipRole, Qt.AccessibleTextRole,
                             Qt.AccessibleDescriptionRole):
                    value = model.data(index, role)
                    if isinstance(value, str):
                        texts.append((f"row {row} role {int(role)}", value))
    return texts


def windows_key_names(window) -> list:
    """The texts under *window* that name a key the Windows way."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QWidget
    found = []
    for widget in [window, *window.findChildren(QWidget)]:
        for what, text in _texts_of(widget):
            if KEY_NAME.search(text):
                found.append(f"{type(widget).__name__} {what}: {text!r}")
    for action in window.findChildren(QAction):
        for what, text in (("tooltip", action.toolTip()), ("status tip", action.statusTip()),
                           ("text", action.text())):
            if KEY_NAME.search(text):
                found.append(f"action {action.text()!r} {what}: {text!r}")
    return found


@unittest.skipUnless(HAVE_QT and ON_MAC, "only a Mac's Qt writes a key the Mac's way")
class TestNoWindowNamesAWindowsKey(unittest.TestCase):
    """On macOS, where the two wordings differ: no tooltip, placeholder,
    label or accessible text of the app's windows says "Ctrl+" or "Alt+"."""

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _main_window(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        from tests.unit.test_hide_names_gui import _entry
        root = Path(self.tmp.name)
        self.config = AppConfig(path=root / "config.json")
        self.config.set("log_path", str(root / "Encounter.log"))
        self.config.set("update.check_enabled", False)
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.addCleanup(win.close)
        win._on_fight_completed(_entry())
        win.history_list.select_fight(0)
        return win

    def test_the_main_window_and_the_player_window(self):
        from PySide6.QtCore import QUrl
        win = self._main_window()
        self.assertEqual(windows_key_names(win), [])
        # It did read the texts that name keys
        self.assertIn("⌘D", win.detail_action.toolTip())
        self.assertIn("⇧⌘H", win.hide_names_action.toolTip())
        self.assertIn("⌘F", win.search_field.placeholderText())
        win.fight_view.anchorClicked.emit(QUrl("esolog:build/2"))
        player = win._player_window
        self.assertIsNotNone(player)
        self.assertEqual(windows_key_names(player), [])
        self.assertIn("⌘↑", player.previous_player.toolTip())

    def test_the_hover_texts_of_the_fight_list_and_the_pages(self):
        from gui.death_render import FIGHT_DEATHS_TIP
        from gui.events_tab import GRAPH_KEYS_TEXT
        from gui.fight_list import INSTANCE_CUE, INSTANCE_DESCRIPTION
        from gui.instance_render import COPY_TIP
        from gui.positions_window import SPEED_TIP
        from gui.settings_dialog import TEXT_SIZE_HELP
        for text in (FIGHT_DEATHS_TIP, GRAPH_KEYS_TEXT, INSTANCE_CUE, INSTANCE_DESCRIPTION,
                     COPY_TIP, SPEED_TIP, TEXT_SIZE_HELP):
            with self.subTest(text):
                self.assertIsNone(KEY_NAME.search(text))
        self.assertIn("⌥I", INSTANCE_CUE)
        self.assertIn("⌥E", FIGHT_DEATHS_TIP)
        self.assertIn("⌃,", SPEED_TIP)
        self.assertEqual(GRAPH_KEYS_TEXT, "⌘G")

    def test_the_settings_dialog(self):
        from gui.settings_dialog import SettingsDialog
        win = self._main_window()
        dialog = SettingsDialog(self.config, win)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(windows_key_names(dialog), [])
        self.assertIn("⇧⌘H", dialog.hide_names.text())

    def test_the_positions_window(self):
        from gui.positions_window import PositionsWindow
        window = PositionsWindow()
        self.addCleanup(window.deleteLater)
        self.assertEqual(windows_key_names(window), [])
        self.assertIn("⌘⇟", window.next_death.toolTip())
        self.assertIn("⌃.", window.speed_box.toolTip())


if __name__ == "__main__":
    unittest.main()
