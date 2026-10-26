#!/usr/bin/env python3
"""The Hide names mask (issue #72, gui.name_mask): who is hidden and who is
kept, the text and image forms of a hidden name, the stand-in word, the
mask: URL, and the engine's is_local stamp the mask reads."""

import os
import re
import unittest
from math import ceil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None
BLOCK = "▒"
IMG = re.compile(r'<img src="mask:([a-z_]+)\?color=([0-9a-f]{6})&amp;pt=([0-9.]+)&amp;b=([01])" '
                 r'style="vertical-align:middle">')


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _player(unit_id, name, character="", is_local=False):
    return {"unit_id": unit_id, "name": name, "character": character, "is_local": is_local}


def _entry(local="1"):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.players = [_player("1", "@me", "My Char", local == "1"),
                     _player("2", "@friend", "Friend Char", local == "2"),
                     _player("3", "Nameless One", "Nameless One", local == "3")]
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWhoIsHidden(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def test_the_switch_off_is_the_identity(self):
        from gui.name_mask import NO_MASK, NameMask
        for mask in (NameMask.for_entry(_entry(), False), NO_MASK, NameMask()):
            self.assertFalse(mask.active)
            for name in ("@me", "@friend", "Nameless One", "Sharpfang"):
                self.assertFalse(mask.hides(name))
                self.assertEqual(mask.text(name), name)
            self.assertEqual(mask.html("<b>", "#202124", 9.0), "&lt;b&gt;")

    def test_the_logging_player_is_kept_and_every_other_player_hidden(self):
        from gui.name_mask import NameMask
        mask = NameMask.for_entry(_entry(), True)
        self.assertTrue(mask.active)
        # The local player's handle and character name
        self.assertFalse(mask.hides("@me"))
        self.assertFalse(mask.hides("My Char"))
        # Another player's handle and character name, and a player the
        # log gave no handle (their character name is their name)
        for name in ("@friend", "Friend Char", "Nameless One"):
            self.assertTrue(mask.hides(name), name)
        # A handle the entry never listed: a heal source in a recap, a
        # caster in the penetration section, a strip interval's player
        self.assertTrue(mask.hides("@passerby"))
        # Never an enemy, a pet, an unknown or nothing
        for name in ("Sharpfang", "Blastbones", "anon", "unknown", "", None):
            self.assertFalse(mask.hides(name), repr(name))

    def test_a_reviewed_log_written_by_a_friend_keeps_the_friend(self):
        from gui.name_mask import NameMask
        mask = NameMask.for_entry(_entry(local="2"), True)
        self.assertFalse(mask.hides("@friend"))
        self.assertFalse(mask.hides("Friend Char"))
        self.assertTrue(mask.hides("@me"))
        self.assertTrue(mask.hides("My Char"))

    def test_an_entry_with_no_local_player_hides_everyone(self):
        from gui.name_mask import NameMask
        mask = NameMask.for_entry(_entry(local="none"), True)
        for name in ("@me", "My Char", "@friend", "Nameless One"):
            self.assertTrue(mask.hides(name), name)

    def test_text_form_keeps_the_at_and_blocks_every_character(self):
        from gui.name_mask import NameMask
        mask = NameMask.for_entry(_entry(), True)
        self.assertEqual(mask.text("@friend"), "@" + BLOCK * 6)
        self.assertEqual(mask.text("Nameless One"), BLOCK * 12)
        self.assertEqual(mask.text("@me"), "@me")
        self.assertEqual(mask.text("Sharpfang"), "Sharpfang")
        self.assertEqual(mask.text(None), "")

    def test_html_form_is_the_at_and_a_pixelated_image_or_the_escaped_name(self):
        from gui.name_mask import NameMask
        mask = NameMask.for_entry(_entry(), True)
        hidden = mask.html("@friend", "#202124", 9.0, bold=True)
        self.assertTrue(hidden.startswith("@<img"), hidden)
        match = IMG.fullmatch(hidden[1:])
        self.assertIsNotNone(match, hidden)
        word, color, pt, bold = match.groups()
        self.assertEqual((len(word), color, pt, bold), (6, "202124", "9.00", "1"))
        # A character name with a space: no leading @, the space an underscore
        no_handle = mask.html("Nameless One", "#e8eaed", 11.7)
        match = IMG.fullmatch(no_handle)
        self.assertIsNotNone(match, no_handle)
        self.assertEqual(len(match.group(1)), 12)
        self.assertEqual(match.group(1)[8], "_")
        self.assertEqual(match.group(2), "e8eaed")
        self.assertEqual(match.group(4), "0")
        # A kept name is text, escaped
        self.assertEqual(mask.html("@me", "#202124", 9.0), "@me")
        self.assertEqual(mask.html("Sharp<fang>", "#202124", 9.0), "Sharp&lt;fang&gt;")

    def test_a_player_without_a_row_is_known_from_the_roster(self):
        """A player whose build never reached the log has no row, but the
        entry's roster names them, so their character name is hidden in
        the strip, the casters and the recaps like anyone's; the engine's
        'anon' is no identity and passes."""
        from gui.name_mask import NameMask
        entry = _entry()
        entry.player_names = [dict(p) for p in entry.players] + [
            {"name": "Shy One", "character": "Shy One", "is_local": False},
            {"name": "anon", "character": "", "is_local": False}]
        mask = NameMask.for_entry(entry, True)
        self.assertTrue(mask.hides("Shy One"))
        self.assertEqual(mask.text("Shy One"), BLOCK * 7)
        self.assertFalse(mask.hides("anon"))
        self.assertFalse(mask.hides("@me"))
        self.assertTrue(mask.hides("@friend"))
        # The roster decides who is local too
        entry.player_names[0]["is_local"] = False
        entry.player_names[1]["is_local"] = True
        self.assertTrue(NameMask.for_entry(entry, True).hides("@me"))
        self.assertFalse(NameMask.for_entry(entry, True).hides("@friend"))
        # An entry without a roster (built before it existed) falls back to the rows
        entry.player_names = []
        self.assertFalse(NameMask.for_entry(entry, True).hides("Shy One"))
        self.assertTrue(NameMask.for_entry(entry, True).hides("@friend"))

    def test_the_engine_stamps_the_local_player_and_the_roster(self):
        """The build-session fixture: @brainsnorkel wrote the log."""
        entry = fights()[0]
        by_unit = {p["unit_id"]: p for p in entry.players}
        self.assertTrue(by_unit["1"]["is_local"])
        self.assertFalse(by_unit["2"]["is_local"])
        self.assertFalse(by_unit["3"]["is_local"])
        roster = {p["name"]: p for p in entry.player_names}
        self.assertEqual(len(entry.player_names), 3)
        self.assertTrue(roster["@brainsnorkel"]["is_local"])
        self.assertEqual(roster["@brainsnorkel"]["character"], "Pïque")
        self.assertFalse(roster["@dualwield"]["is_local"])
        self.assertEqual(roster["@dualwield"]["character"], "Stabby")


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestStandIn(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def test_same_length_letters_only_and_the_same_within_a_run(self):
        from gui.name_mask import stand_in
        word = stand_in("@friend")
        self.assertEqual(len(word), 6)
        self.assertTrue(word.isalpha() and word.islower(), word)
        self.assertEqual(word, stand_in("@friend"))
        self.assertNotEqual(stand_in("@friendly"), stand_in("@enemies"))
        # The handle's @ is not counted; a space stays a space
        self.assertEqual(len(stand_in("Nameless One")), 12)
        self.assertEqual(stand_in("Nameless One")[8], " ")
        self.assertEqual(len(stand_in("@")), 1)

    def test_nothing_of_the_name_survives(self):
        """The stand-in is a hash's letters: a name of one repeated letter
        gives no repeated letter back."""
        from gui.name_mask import stand_in
        self.assertNotEqual(stand_in("@aaaaaaaaaaaa"), "aaaaaaaaaaaa")

    def test_the_url_round_trips_and_refuses_a_malformed_one(self):
        from PySide6.QtCore import QUrl

        from gui.name_mask import image_html, mask_request
        html = image_html("abc def", "#1a73e8", 11.7, bold=True)
        src = IMG.fullmatch(html).group(0)
        url = src[len('<img src="'):src.index('" ')].replace("&amp;", "&")
        self.assertEqual(mask_request(QUrl(url)), ("abc def", "#1a73e8", 11.7, True))
        for bad in ("mask:abc?color=zzzzzz&pt=9&b=1", "mask:ABC?color=202124&pt=9&b=1",
                    "mask:abc?pt=9&b=1", "mask:abc?color=202124&pt=x&b=1",
                    "mask:abc?color=202124&pt=200&b=0", "mask:?color=202124&pt=9&b=0",
                    "glyph:abc?color=202124&pt=9&b=0"):
            self.assertIsNone(mask_request(QUrl(bad)), bad)

    def test_the_image_is_the_words_advance_wide_and_the_line_tall(self):
        from PySide6.QtGui import QFont, QFontMetricsF

        from gui.name_mask import mask_image
        base = QFont()
        font = QFont(base)
        font.setPointSizeF(9.0)
        font.setBold(True)
        metrics = QFontMetricsF(font)
        image = mask_image("abcdef", "#202124", 9.0, True, base)
        self.assertEqual((image.width(), image.height()),
                         (ceil(metrics.horizontalAdvance("abcdef")), ceil(metrics.height())))
        self.assertEqual(image.devicePixelRatio(), 1.0)
        # Something was drawn, in the asked colour
        painted = [image.pixelColor(x, y) for x in range(image.width())
                   for y in range(image.height()) if image.pixelColor(x, y).alpha() > 0]
        self.assertTrue(painted)
        self.assertTrue(all(c.red() < 80 and c.green() < 80 and c.blue() < 80 for c in painted))
        # Pixelated: whole blocks share one colour, so the image has far
        # fewer distinct colours than pixels
        distinct = {image.pixel(x, y) for x in range(image.width()) for y in range(image.height())}
        self.assertLess(len(distinct), image.width() * image.height() / 4)
        # A scaled display: twice the device pixels at the same logical size
        hidpi = mask_image("abcdef", "#202124", 9.0, True, base, dpr=2.0)
        self.assertEqual(hidpi.width(), image.width() * 2)
        self.assertEqual(hidpi.devicePixelRatio(), 2.0)
        # The same request is the same image
        self.assertIs(mask_image("abcdef", "#202124", 9.0, True, base), image)
        for word, color, pt in (("", "#202124", 9.0), ("abc", "no", 9.0), ("abc", "#202124", 99.0)):
            self.assertIsNone(mask_image(word, color, pt, False, base))
