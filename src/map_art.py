"""
The fight pane's map (issue #148), the part without Qt: where a map's art
is, which part of the map a fight is drawn over, and the heat of the
group's positions on it. gui.fight_map draws what this computes.

Design: how much of the map to show. A fight covers very different shares
of its map. In Lucent Citadel on 2026-10-11 (the split
261011202110-Lucent-Citadel-vet.log), the box holding 98% of the players'
samples was 0.044 x 0.064 of the map for Count Ryelaz and Zilyesset, 0.035
x 0.037 for Cavot Agnan and 0.035 x 0.041 for the Orphic Shattered Shard,
30 to 50 px of the 768 px art, while the Arcane Knot gauntlet's was 0.28 x
0.54, about ten times as wide and tall. No single zoom suits both, so the
picture is cropped to each fight's own box (BOX_SHARE of the samples, so a
player who ran off for a moment does not set it), widened by MARGIN on
every side, and square, so thumbnails line up. The crop is at least
MIN_CROP of the map's width, 115 px of a 768 px map's art, enough to show
an arena's room and its doors, and at most the whole map; it is moved, not
shrunk, to stay inside the map.

The heat: the samples in the crop are counted on a grid of cells and
smoothed with a Gaussian whose width is a share of the crop (HEAT_SIGMA),
so a blot reads the same at any zoom, but never under a player's own
footprint on the map (MIN_SIGMA). Each cell's heat is a share of the
hottest cell's. The hottest area, the cells at HOT_LEVEL of the hottest or
more, is outlined by marching squares over the grid.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from ability_icons import bundle_root
from positions import SCALE

BOX_SHARE = 0.98  # the share of the samples the fight's box holds
MARGIN = 0.15  # added to every side of the box, as a share of its larger side
MIN_CROP = 0.15  # the crop's least side, as a share of the map
HEAT_SIGMA = 0.02  # the heat's smoothing, as a share of the crop's side
MIN_SIGMA = 0.003  # ... and never less than this share of the map
HOT_LEVEL = 0.5  # the outline: cells at this share of the hottest or more
FLOOR = 0.03  # heat under this share of the hottest is not drawn


def maps_dir() -> Path:
    return bundle_root() / "data" / "maps"


@lru_cache(maxsize=1)
def manifest() -> dict:
    """The bundled maps by texture path (scripts/extract_map_art.py), {}
    when the manifest is absent or malformed."""
    try:
        data = json.loads((maps_dir() / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    maps = data.get("maps") if isinstance(data, dict) else None
    return maps if isinstance(maps, dict) else {}


def art_path(texture_path: str) -> Path | None:
    """The bundled image of the map MAP_CHANGED names *texture_path*, None
    when the app has no art for it."""
    key = (texture_path or "").strip().lower()
    if not key or key not in manifest():
        return None
    path = maps_dir().joinpath(*key.split("/")).with_suffix(".webp")
    return path if path.is_file() else None


def points(xy) -> list[tuple[float, float]]:
    """A map record's samples (positions.PositionRecorder.fight_maps' xy)
    as (x, y) fractions of the map."""
    return [(xy[i] / SCALE, xy[i + 1] / SCALE) for i in range(0, len(xy) - 1, 2)]


def _quantile(sorted_values: list[float], share: float) -> float:
    if not sorted_values:
        return 0.0
    k = min(len(sorted_values) - 1, max(0, round(share * (len(sorted_values) - 1))))
    return sorted_values[k]


def fight_box(pts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the box holding BOX_SHARE of *pts*,
    as fractions of the map; the whole map when there are none."""
    if not pts:
        return 0.0, 0.0, 1.0, 1.0
    cut = (1.0 - BOX_SHARE) / 2
    xs = sorted(x for x, _ in pts)
    ys = sorted(y for _, y in pts)
    return (_quantile(xs, cut), _quantile(ys, cut),
            _quantile(xs, 1.0 - cut), _quantile(ys, 1.0 - cut))


def crop_square(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """(left, top, side) of the fight's crop, as fractions of the map (see
    the module's design note)."""
    left, top, right, bottom = fight_box(pts)
    side = max(right - left, bottom - top)
    side = min(1.0, max(MIN_CROP, side * (1.0 + 2 * MARGIN)))
    cx, cy = (left + right) / 2, (top + bottom) / 2
    x0 = min(max(cx - side / 2, 0.0), 1.0 - side)
    y0 = min(max(cy - side / 2, 0.0), 1.0 - side)
    return x0, y0, side


def _kernel(sigma_cells: float) -> list[float]:
    radius = max(1, math.ceil(3 * sigma_cells))
    weights = [math.exp(-(k * k) / (2 * sigma_cells * sigma_cells)) for k in range(-radius, radius + 1)]
    total = sum(weights)
    return [w / total for w in weights]


def _smooth(grid: list[list[float]], kernel: list[float]) -> list[list[float]]:
    """*grid* convolved with *kernel* along its rows, then its columns."""
    n = len(grid)
    radius = len(kernel) // 2
    rows = []
    for row in grid:
        out = [0.0] * n
        for i, value in enumerate(row):
            if value:
                for k, w in enumerate(kernel):
                    j = i + k - radius
                    if 0 <= j < n:
                        out[j] += value * w
        rows.append(out)
    columns = [[0.0] * n for _ in range(n)]
    for i, row in enumerate(rows):
        for c, value in enumerate(row):
            if value:
                for k, w in enumerate(kernel):
                    j = i + k - radius
                    if 0 <= j < n:
                        columns[j][c] += value * w
    return columns


def heat_grid(pts: list[tuple[float, float]], crop: tuple[float, float, float],
              cells: int) -> list[list[float]]:
    """The heat over *crop* (left, top, side) on a *cells* x *cells* grid,
    rows from the top, each cell a share of the hottest (0 to 1)."""
    x0, y0, side = crop
    grid = [[0.0] * cells for _ in range(cells)]
    for x, y in pts:
        i = int((x - x0) / side * cells)
        j = int((y - y0) / side * cells)
        if 0 <= i < cells and 0 <= j < cells:
            grid[j][i] += 1.0
    sigma = max(HEAT_SIGMA * side, MIN_SIGMA) / side * cells
    grid = _smooth(grid, _kernel(sigma))
    peak = max((max(row) for row in grid), default=0.0)
    if peak <= 0:
        return grid
    return [[value / peak for value in row] for row in grid]


def contour_segments(grid: list[list[float]], level: float = HOT_LEVEL):
    """The outline of the cells at *level* or more, by marching squares:
    ((x1, y1), (x2, y2)) segments in cell units, a cell's centre at its
    index plus a half, so they scale onto the grid's picture. The grid is
    taken as zero past its edges, so every outline closes."""
    n = len(grid)

    def value(i, j):
        return grid[j][i] if 0 <= i < n and 0 <= j < n else 0.0

    def cut(p, q):
        return 0.5 if q == p else (level - p) / (q - p)

    segments = []
    for j in range(-1, n):
        for i in range(-1, n):
            a, b = value(i, j), value(i + 1, j)
            c, d = value(i + 1, j + 1), value(i, j + 1)
            case = ((a >= level) | ((b >= level) << 1) | ((c >= level) << 2)
                    | ((d >= level) << 3))
            if case in (0, 15):
                continue
            cx, cy = i + 0.5, j + 0.5  # the centre of the cell at (i, j)
            top = (cx + cut(a, b), cy)
            right = (cx + 1, cy + cut(b, c))
            bottom = (cx + cut(d, c), cy + 1)
            left = (cx, cy + cut(a, d))
            for pair in _CASES[case]:
                segments.append(tuple({"t": top, "r": right, "b": bottom, "l": left}[e]
                                      for e in pair))
    return segments


# Marching squares: the edges joined for each case of the four corners at
# the level or above (top left 1, top right 2, bottom right 4, bottom left 8)
_CASES = {
    1: (("l", "t"),), 2: (("t", "r"),), 3: (("l", "r"),), 4: (("r", "b"),),
    5: (("l", "t"), ("r", "b")), 6: (("t", "b"),), 7: (("l", "b"),), 8: (("b", "l"),),
    9: (("t", "b"),), 10: (("t", "r"), ("b", "l")), 11: (("r", "b"),), 12: (("l", "r"),),
    13: (("t", "r"),), 14: (("l", "t"),),
}
