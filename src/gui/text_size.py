"""The app-wide text size (issue #77): one percentage of the system font,
saved as display.text_scale, set from Settings or with Ctrl+=, Ctrl+- and
Ctrl+0.

Design: the size is applied with QApplication.setFont, so every widget
that has not set a font of its own follows it, and every rendered page,
which sizes its text from its view's font (base_pt), follows it on the
next render. What is drawn in pixels rather than points (the timeline
strip's rows and label column, the dps graph's margins and legend, the
icons in rendered pages) asks scale() and grows with it, but never
shrinks below its size at 100%: icons and rows that small stay legible,
and at 100% everything is drawn exactly as before the setting existed.

The system font is read once, before the first change, and every
percentage is of that font, so stepping up and back down returns to the
same size rather than drifting with rounding. Qt is imported only where a
font is set, so the page renderers can ask scale() without it.

QApplication.setFont posts the change to each widget rather than sending
it, so straight after it every view still reports the old font, and a page
rendered then from its view's font comes out at the old size (the
Settings path did just that: Save, redraw, old size). apply() delivers the
posted font changes before it returns.
"""

MIN_PCT = 80
MAX_PCT = 200
STEP_PCT = 10
DEFAULT_PCT = 100
CONFIG_KEY = "display.text_scale"

_base_font = None  # the system font, read before the first change
_pct = DEFAULT_PCT


def clamp(pct) -> int:
    """*pct* as a whole percentage in range; anything unreadable is 100."""
    try:
        value = round(float(pct))
    except (TypeError, ValueError):
        return DEFAULT_PCT
    return max(MIN_PCT, min(MAX_PCT, value))


def percent() -> int:
    """The text size in force, as a percentage of the system font."""
    return _pct


def scale() -> float:
    """The factor for sizes drawn in pixels: the text size over 100%, and
    1.0 at or below it (see the module notes)."""
    return max(1.0, _pct / 100.0)


def scaled_px(px: int) -> int:
    """*px*, a size chosen at 100%, at the text size in force."""
    return round(px * scale())


def step(pct: int, direction: int) -> int:
    """The size one step up (*direction* 1) or down (-1) from *pct*, or
    100% for 0."""
    if direction == 0:
        return DEFAULT_PCT
    return clamp(clamp(pct) + STEP_PCT * (1 if direction > 0 else -1))


def apply(pct) -> int:
    """Set the application font to *pct* of the system font; returns the
    percentage applied."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    global _base_font, _pct
    app = QApplication.instance()
    if _base_font is None:
        _base_font = QFont(app.font())
    _pct = clamp(pct)
    font = QFont(_base_font)
    font.setPointSizeF(_base_font.pointSizeF() * _pct / 100.0)
    app.setFont(font)
    # Qt posts the change to each widget; deliver it now, so a page
    # rendered next from its view's font gets the new size
    QCoreApplication.sendPostedEvents(None, QEvent.ApplicationFontChange)
    return _pct


def fixed_font():
    """The fixed-pitch font at the text size in force, for the rule editor
    and the examples list: Consolas where it is installed, else the
    system's fixed font. Qt's fixed font is Courier New on the Windows
    desktop and, offscreen, Agency FB, which is why the guide's rules
    looked condensed (issue #187)."""
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
    font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    # QFontInfo resolves the one family; QFontDatabase.families() would
    # enumerate every installed font on each open of Settings
    if QFontInfo(QFont("Consolas")).family() == "Consolas":
        font.setFamily("Consolas")
    font.setPointSizeF(font.pointSizeF() * _pct / 100.0)
    return font


def small_pt() -> float:
    """The point size of the small helper text in Settings: what the 11 px
    labels were beside a 9 pt font, at the size in force."""
    from PySide6.QtWidgets import QApplication
    return round(QApplication.font().pointSizeF() * 11 / 12, 2)
