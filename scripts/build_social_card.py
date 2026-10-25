#!/usr/bin/env python3
"""Render the home page's social card and favicon into site/.

site/social-card.png (1280 x 640) is the picture a pasted link unfurls with:
the page's og:image, and the file to upload as the repository's social
preview (Settings > General > Social preview), so both show the same thing.
1280 x 640 is the size GitHub recommends for the preview; Discord, Slack and
X crop an og:image to about 1.91:1, so the text stays well inside the edges
and only the screenshot, which bleeds off the right, loses a sliver.

The card is the app's d12 icon (rendered by create_icon.py), the name and
the tagline on a slate background, with a crop of docs/screencaps/
main-window.png (the buff timeline, the fight header and the first rows,
with their ability bars) set in a framed window on the right.

site/favicon.png is the same icon at 128 px; icon.png at the repository
root is gitignored, so the page needs a copy under another name.

Both files are committed. Rerun this after scripts/capture_screenshots.py
changes the main-window screenshot. The text needs a TrueType font: Segoe UI
on Windows, DejaVu Sans on Linux, Helvetica on macOS by default; --font and
--font-bold name others.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT = ROOT / "docs" / "screencaps" / "main-window.png"
SITE_DIR = ROOT / "site"

CARD_SIZE = (1280, 640)
TITLE = "ESO Log Tail"
TAGLINE = ("Live fight summaries from your Elder Scrolls Online "
           "encounter log, the moment combat ends.")
FOOTNOTE = "Builds · DPS · deaths · buff uptimes   |   free, open source, Windows and Linux"
# The part of main-window.png the card shows: the right pane from the top
# of the buff timeline to the fourth player's set line (left, top, right,
# bottom), at the screenshot's own 1400 x 880
CROP = (460, 36, 1386, 600)
SHOT_X, SHOT_SCALE = 640, 0.78

BG_TOP = (22, 27, 43)
BG_BOTTOM = (31, 39, 64)
TEXT = (230, 234, 243)
MUTED = (154, 166, 192)
AMBER = (240, 176, 56)

_FONT_CANDIDATES = {
    "win32": (["segoeuib.ttf", "arialbd.ttf"], ["segoeui.ttf", "arial.ttf"]),
    "darwin": (["Helvetica.ttc", "Arial Bold.ttf"], ["Helvetica.ttc", "Arial.ttf"]),
    "linux": (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
              ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]),
}


def _icon_renderer():
    """create_icon.render, loaded by path so this runs from any cwd."""
    path = ROOT / "scripts" / "create_icon.py"
    spec = importlib.util.spec_from_file_location("create_icon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render


def _find_font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit(f"no font found among {names}; pass --font and --font-bold")


def default_fonts():
    key = "win32" if sys.platform == "win32" else (
        "darwin" if sys.platform == "darwin" else "linux")
    return _FONT_CANDIDATES[key]


def wrap(draw, text, font, width):
    """Greedy word wrap of *text* to *width* pixels."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _gradient(size, top, bottom):
    mask = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, bottom),
                           Image.new("RGB", size, top), mask)


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1),
                                           radius=radius, fill=255)
    return mask


def build_card(screenshot: Path, font_bold, font_regular, render_icon) -> Image.Image:
    card = _gradient(CARD_SIZE, BG_TOP, BG_BOTTOM).convert("RGBA")

    # A soft amber glow behind the icon, so the corner is not flat
    glow = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-140, -200, 520, 420), fill=AMBER + (46,))
    card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))

    # The screenshot in a window frame with a shadow, bleeding off the right
    shot = Image.open(screenshot).convert("RGB").crop(CROP)
    size = (round(shot.width * SHOT_SCALE), round(shot.height * SHOT_SCALE))
    shot = shot.resize(size, Image.LANCZOS)
    frame = Image.new("RGBA", (size[0] + 2, size[1] + 2), (60, 70, 100, 255))
    frame.paste(shot, (1, 1))
    mask = _rounded_mask(frame.size, 14)
    y = (CARD_SIZE[1] - frame.height) // 2
    shadow = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    shadow_box = Image.new("RGBA", frame.size, (0, 0, 0, 170))
    shadow.paste(shadow_box, (SHOT_X + 10, y + 16), mask)
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
    card.paste(frame, (SHOT_X, y), mask)

    # Icon, title, tagline, footnote
    icon = render_icon(120)
    card.alpha_composite(icon, (72, 72))
    draw = ImageDraw.Draw(card)
    title_font = font_bold(58)
    draw.text((212, 98), TITLE, font=title_font, fill=TEXT)

    body_font = font_regular(31)
    y = 232
    for line in wrap(draw, TAGLINE, body_font, 470):
        draw.text((72, y), line, font=body_font, fill=TEXT)
        y += 42

    small_font = font_regular(22)
    y += 18
    draw.rounded_rectangle((72, y, 132, y + 4), radius=2, fill=AMBER)
    y += 22
    for line in wrap(draw, FOOTNOTE, small_font, 480):
        draw.text((72, y), line, font=small_font, fill=MUTED)
        y += 30
    return card.convert("RGB")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--screenshot", type=Path, default=SCREENSHOT)
    parser.add_argument("--out-dir", type=Path, default=SITE_DIR)
    parser.add_argument("--font-bold", help="TrueType file for the title")
    parser.add_argument("--font", help="TrueType file for the other text")
    args = parser.parse_args(argv)

    bold_names, regular_names = default_fonts()
    if args.font_bold:
        bold_names = [args.font_bold]
    if args.font:
        regular_names = [args.font]

    def font_bold(size):
        return _find_font(bold_names, size)

    def font_regular(size):
        return _find_font(regular_names, size)

    render_icon = _icon_renderer()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    card = build_card(args.screenshot, font_bold, font_regular, render_icon)
    card_path = args.out_dir / "social-card.png"
    card.save(card_path, format="PNG", optimize=True)
    favicon_path = args.out_dir / "favicon.png"
    render_icon(128).save(favicon_path, format="PNG", optimize=True)
    print(f"Wrote {card_path} ({card_path.stat().st_size // 1024} KB) "
          f"and {favicon_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
