"""
Design: Hidden names. A screenshot of a fight, or a fight pasted into a
chat, shows the handles and character names of everyone in the group. The
Hide names switch (issue #72) keeps the name of the player whose client
writes the log and hides everyone else's, in every place the app shows a
name: the fight pane's rows and hover texts, the build, damage and
death-recap windows, the dps graph's legend, the timeline strip's hover
and pop-ups, and the Copy fight text. Enemy, pet, set and ability names
are never hidden.

Who is kept is read from the log, not configured: the game writes
``isLocalPlayer`` on every player's UNIT_ADDED line, ``T`` for the one
client writing the log (checked over 899 split logs: exactly one per log,
the same handle on 14 characters, the flag in the same place since the
oldest log of 2025). The engine puts it on each fight entry's player as
``is_local``. A reviewed log written by a friend therefore keeps the
friend, which is what "the handle of the person logging" means.

Which names are player names: a name is hidden when it is not the local
player's handle or character name and either starts with ``@`` or is the
character name of another player of the fight. The ``@`` rule reaches
every nested place a handle appears (the source of a heal in a death recap,
a caster in the penetration section, a timeline interval's source and
target) without threading the player list into each; the character-name
set reaches a player the log gave no handle. That set is read from the
entry's ``player_names``, every player unit the engine saw, rows or not:
a player whose PLAYER_INFO never reached the log has no row in the table
but still casts, heals and dies in the fight's other data (the review of
2026-10-27 found the gap when the set was read from the rows alone).
``anon`` (the engine's word for a player with neither handle nor name)
and enemy names fall through, as no enemy, pet, set or ability name
starts with ``@``. An entry with no local player at all hides every name,
the safe direction.

How a hidden name looks: the maintainer asked for a blurred or pixelated
name, the look of a screenshot with the names smudged out. The pages
drawn as rich text (the fight pane and the three windows) get a pixelated
word of the hidden name's length, its ``@`` left readable as text so the
row still reads as a handle. That word is **not** the real name pixelated.
Pixelated or blurred text can be read back when the font, the size and
the rendering are known (they are all public here) and the words are
short, so a picture meant to hide a handle would carry it. Instead the
mask makes a stand-in word from a keyed hash of the name (``stand_in``:
the key is random per run, so the same name gives the same word in every
row, window and pop-up of a run, and nothing persists), draws it in the
page's font at the requested size and weight, downscales it smoothly by
the block size and scales it back with nearest-neighbour. The result has
the blocky texture of a pixelated word, the ascender and descender
pattern of a word nobody has ever seen. The length is kept so the row's
columns stay where they were; a handle's length identifies nobody.

Where text is all there is (a tooltip, the strip's pop-up, the graph's
legend, a window title, the clipboard) a hidden name is ``@`` followed by
one shade block per hidden character: a QLabel cannot ask a view for an
image.

The page asks for the image by URL, ``mask:<word>?color=rrggbb&pt=<n>&b=<0|1>``
(``image_html``), answered by ``FightView.loadResource`` from
``mask_image`` with the view's font family and device pixel ratio, cached
for the run by its parameters, as the link glyphs are (see gui.glyphs).
The word is lower-case letters and underscores for spaces, so the URL
needs no escaping and a malformed one is refused.
"""

import hashlib
import html
import re
import secrets
from collections.abc import Iterable
from math import ceil

from PySide6.QtCore import QRectF, Qt, QUrl, QUrlQuery
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

MASK_SCHEME = "mask"
ANON = "anon"  # the engine's name for a player with neither handle nor name: no identity
BLOCK = "▒"  # medium shade: one per hidden character where text is all there is
# The pixel block is this share of the line height: 4 px at 9 pt. Finer
# and a letter shape shows through; coarser and the word becomes a bar
BLOCKS_PER_LINE = 4
# The letter pools a stand-in is drawn from, weighted like a word: most
# letters at x-height, some reaching up, a few hanging down
_X_HEIGHT = "acemnorsuvwxz"
_ASCENDERS = "bdfhklt"
_DESCENDERS = "gjpqy"
_WORD = re.compile(r"^[a-z_]{1,64}$")
_KEY = secrets.token_bytes(16)  # per run: a stand-in never outlives the process

_images: dict = {}


def _body(name: str) -> str:
    """The characters a hidden name stands for: the handle without its @."""
    return name.removeprefix("@")


def stand_in(name: str) -> str:
    """A word of *name*'s length (its @ not counted) that carries nothing
    of it: letters from a keyed hash of the name, the same for the same
    name within a run, with the name's spaces kept as spaces."""
    body = _body(str(name)) or "x"
    digest = hashlib.blake2b(str(name).encode("utf-8"), key=_KEY, digest_size=64).digest()
    letters = []
    for index, char in enumerate(body):
        if char == " ":
            letters.append(" ")
            continue
        byte = digest[index % len(digest)]
        pool = (_X_HEIGHT if byte % 10 < 6 else _ASCENDERS if byte % 10 < 9
                else _DESCENDERS)
        letters.append(pool[(byte >> 4) % len(pool)])
    return "".join(letters)


def image_html(word: str, color: str, pt: float, bold: bool = False) -> str:
    """The <img> a page uses to ask for the pixelated *word* (a stand_in)
    in *color* ('#rrggbb') at *pt* points, bold or not."""
    token = word.replace(" ", "_")
    return (f'<img src="{MASK_SCHEME}:{token}?color={color.lstrip("#")}'
            f'&amp;pt={float(pt):.2f}&amp;b={1 if bold else 0}" '
            f'alt="hidden name" style="vertical-align:middle">')


def mask_request(url: QUrl) -> tuple[str, str, float, bool] | None:
    """(word, color, pt, bold) from a mask: URL the page asked for, None
    when any part is malformed."""
    if url.scheme() != MASK_SCHEME:
        return None
    token = url.path()
    if not _WORD.match(token):
        return None
    query = QUrlQuery(url)
    color = query.queryItemValue("color")
    if len(color) != 6 or any(c not in "0123456789abcdefABCDEF" for c in color):
        return None
    try:
        pt = float(query.queryItemValue("pt") or 0)
    except ValueError:
        return None
    if not 3.0 <= pt <= 72.0:
        return None
    bold = query.queryItemValue("b") == "1"
    return token.replace("_", " "), f"#{color}", pt, bold


def mask_image(word: str, color: str, pt: float, bold: bool, base_font: QFont,
               dpr: float = 1.0) -> QImage | None:
    """The pixelated *word* at *pt* points in *base_font*'s family, drawn
    in *color* at device pixel ratio *dpr*, the line's height tall and the
    word's advance wide; None for an empty word, a colour that is not one
    or a size that is not one."""
    paint = QColor(color)
    if not word or not paint.isValid() or not 3.0 <= float(pt) <= 72.0:
        return None
    dpr = max(1.0, float(dpr))
    key = (word, paint.name(), round(float(pt), 2), bool(bold), base_font.family(), dpr)
    if key not in _images:
        _images[key] = _draw(word, paint, float(pt), bool(bold), base_font, dpr)
    return _images[key]


def _draw(word: str, color: QColor, pt: float, bold: bool, base_font: QFont,
          dpr: float) -> QImage:
    font = QFont(base_font)
    font.setPointSizeF(pt)
    font.setBold(bold)
    metrics = QFontMetricsF(font)
    width = max(1, ceil(metrics.horizontalAdvance(word)))
    height = max(1, ceil(metrics.height()))
    device_w, device_h = max(1, round(width * dpr)), max(1, round(height * dpr))
    image = QImage(device_w, device_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(dpr)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(QRectF(0, 0, width, height), Qt.AlignLeft | Qt.AlignVCenter, word)
    painter.end()
    # Pixelate: average each block, then blow the blocks back up
    block = max(2, round(height / BLOCKS_PER_LINE)) * dpr
    small = image.scaled(max(1, ceil(device_w / block)), max(1, ceil(device_h / block)),
                         Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    pixelated = small.scaled(device_w, device_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    pixelated.setDevicePixelRatio(dpr)
    return pixelated


class NameMask:
    """Which names a fight's rendering hides, and how. An inactive mask
    (the default everywhere) is the identity."""

    def __init__(self, active: bool = False, keep: Iterable[str] = (),
                 hidden: Iterable[str] = ()):
        self.active = bool(active)
        self._keep = frozenset(keep)
        self._hidden = frozenset(hidden)

    @classmethod
    def for_entry(cls, entry, hide: bool) -> "NameMask":
        """The mask for a fight entry: inactive unless *hide*; otherwise
        keeping the local player's handle and character name and knowing
        the other players' character names, from the entry's full roster
        (player_names) when it has one, else from its rows."""
        if not hide:
            return cls()
        keep, hidden = set(), set()
        roster = getattr(entry, "player_names", None) or getattr(entry, "players", None) or []
        for p in roster:
            names = {str(p.get("name") or ""), str(p.get("character") or "")} - {"", ANON}
            if p.get("is_local"):
                keep |= names
            else:
                hidden |= names
        return cls(True, keep, hidden - keep)

    def hides(self, name) -> bool:
        """Whether *name* is another player's and the mask is on."""
        if not self.active:
            return False
        name = str(name or "")
        if not name or name in self._keep:
            return False
        return name.startswith("@") or name in self._hidden

    def text(self, name) -> str:
        """*name* as plain text: itself, or @ and a block per character."""
        name = str(name or "")
        if not self.hides(name):
            return name
        return ("@" if name.startswith("@") else "") + BLOCK * len(_body(name))

    def html(self, name, color: str, pt: float, bold: bool = False) -> str:
        """*name* for a rich-text page: escaped, or @ and the pixelated
        stand-in in *color* at *pt* points (image_html)."""
        name = str(name or "")
        if not self.hides(name):
            return html.escape(name)
        at = "@" if name.startswith("@") else ""
        return at + image_html(stand_in(name), color, pt, bold)


NO_MASK = NameMask()  # the identity: what every renderer uses when given none
