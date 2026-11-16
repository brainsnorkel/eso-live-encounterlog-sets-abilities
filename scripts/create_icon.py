#!/usr/bin/env python3
"""
Render the app icon: a shaded 3D d12 (dodecahedron) on a transparent
background.

A real dodecahedron is projected orthographically; visible faces (convex
solid, so simple backface culling) get flat Lambertian shading in the app's
slate/amber palette, with edge strokes and a light keyline so the icon reads
on both dark and light taskbars. Rendered supersampled, then downscaled into
all Windows ico sizes.

macOS (issue #32) gets the same die on a rounded-square plate, as icon.icns:
macOS 26 and later put an icon that does not fill the rounded square on a
grey plate of their own.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PHI = (1 + math.sqrt(5)) / 2

# Slate-indigo face palette, amber accent light
BASE_COLOR = (64, 88, 138)         # steel indigo
LIGHT_DIR = _ = None  # placeholder replaced below (kept simple for clarity)


def _normalize(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


LIGHT_DIR = _normalize((-0.45, -0.55, 0.72))   # upper-left key light
RIM_DIR = _normalize((0.65, 0.55, 0.35))       # lower-right amber fill


def _dodecahedron():
    """Vertices and faces (each face = ordered vertex indices)."""
    inv = 1 / PHI
    verts = []
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                verts.append((x, y, z))
    for a in (-inv, inv):
        for b in (-PHI, PHI):
            verts.append((0.0, a, b))
            verts.append((a, b, 0.0))
            verts.append((b, 0.0, a))

    # Face-center directions: permutations of (0, +-phi, +-1)
    normals = []
    for a in (-PHI, PHI):
        for b in (-1, 1):
            normals.append((0.0, a, b))
            normals.append((a, b, 0.0))
            normals.append((b, 0.0, a))

    faces = []
    for n in normals:
        dots = [sum(vc * nc for vc, nc in zip(v, n)) for v in verts]
        top = max(dots)
        idx = [i for i, d in enumerate(dots) if d > top - 1e-6]
        # Order the 5 vertices around the face center
        center = tuple(sum(verts[i][c] for i in idx) / len(idx) for c in range(3))
        nn = _normalize(n)
        # Build an in-plane basis
        ref = (1.0, 0.0, 0.0) if abs(nn[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = _normalize(_cross(nn, ref))
        w = _cross(nn, u)

        def angle(i):
            d = tuple(verts[i][c] - center[c] for c in range(3))
            return math.atan2(_dot(d, w), _dot(d, u))

        faces.append(sorted(idx, key=angle))
    return verts, faces


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _rotate(v, ax, ay, az=0.0):
    x, y, z = v
    # X axis
    ca, sa = math.cos(ax), math.sin(ax)
    y, z = y * ca - z * sa, y * sa + z * ca
    # Y axis
    ca, sa = math.cos(ay), math.sin(ay)
    x, z = x * ca + z * sa, -x * sa + z * ca
    # Z axis
    ca, sa = math.cos(az), math.sin(az)
    x, y = x * ca - y * sa, x * sa + y * ca
    return (x, y, z)


def _shade(normal):
    """Face color from key light + warm amber rim accent."""
    lam = max(0.0, _dot(normal, LIGHT_DIR))
    rim = max(0.0, _dot(normal, RIM_DIR)) ** 3
    base = (0.42 + 1.05 * lam)
    r = BASE_COLOR[0] * base + 255 * 0.60 * rim
    g = BASE_COLOR[1] * base + 176 * 0.60 * rim
    b = BASE_COLOR[2] * base + 56 * 0.60 * rim
    return tuple(min(255, int(c)) for c in (r, g, b))


def render(size: int) -> Image.Image:
    """Render the d12 at the given square size, transparent background."""
    ss = 4  # supersample factor
    canvas = size * ss
    img = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    verts, faces = _dodecahedron()
    # Classic die pose: a face toward the viewer, tilted
    rot = [_rotate(v, math.radians(-24), math.radians(32),
                   math.radians(4)) for v in verts]

    # Fit with margin
    radius = max(math.sqrt(x * x + y * y) for x, y, _ in rot)
    pad = 0.065 * canvas
    scale = (canvas / 2 - pad) / radius
    cx = cy = canvas / 2

    def project(v):
        return (cx + v[0] * scale, cy - v[1] * scale)

    # Visible faces only (convex): normal.z > 0
    visible = []
    for face in faces:
        pts3 = [rot[i] for i in face]
        n = _normalize(_cross(
            tuple(pts3[1][c] - pts3[0][c] for c in range(3)),
            tuple(pts3[2][c] - pts3[0][c] for c in range(3))))
        center = tuple(sum(p[c] for p in pts3) / len(pts3) for c in range(3))
        if _dot(n, center) < 0:  # make normals outward
            n = tuple(-c for c in n)
        if n[2] > 0:
            visible.append((center[2], face, n))
    visible.sort()  # paint far to near (safe even though culled)

    edge_w = max(2, int(canvas * 0.006))
    for _, face, n in visible:
        pts = [project(rot[i]) for i in face]
        draw.polygon(pts, fill=_shade(n) + (255,))
        draw.line(pts + [pts[0]], fill=(16, 21, 33, 255), width=edge_w)

    # Light keyline around the silhouette so it reads on light taskbars
    silhouette = img.split()[3].filter(
        ImageFilter.MaxFilter(2 * (edge_w // 2) + 3))
    key = Image.new('RGBA', img.size, (168, 182, 210, 255))
    outlined = Image.new('RGBA', img.size, (0, 0, 0, 0))
    outlined.paste(key, mask=silhouette)
    outlined.alpha_composite(img)

    return outlined.resize((size, size), Image.LANCZOS)


# Apple's icon grid: on a 1024 px canvas the plate is 824 px square with
# corners of about 185 px, and the rest is left clear for the shadow
MAC_PLATE = 824 / 1024
MAC_CORNER = 185 / 1024
MAC_DIE = 0.84                     # the die's share of the plate's width
MAC_PLATE_TOP = (44, 56, 86)       # slate, lighter at the top
MAC_PLATE_BOTTOM = (18, 23, 37)
# Every size an .icns holds as a PNG: 16, 32, 128, 256 and 512 pt at 2x, and
# 128 pt and up at 1x
MAC_SIZES = [1024, 512, 256, 128, 64, 32]


def render_mac(size: int) -> Image.Image:
    """The d12 on the rounded-square plate macOS expects, at *size* px."""
    ss = 4
    canvas = size * ss
    plate = round(canvas * MAC_PLATE)
    edge = (canvas - plate) // 2

    fill = Image.new('RGBA', (canvas, canvas))
    draw = ImageDraw.Draw(fill)
    for y in range(canvas):
        t = min(1.0, max(0.0, (y - edge) / max(1, plate - 1)))
        draw.line([(0, y), (canvas, y)], fill=tuple(
            round(a + (b - a) * t) for a, b in zip(MAC_PLATE_TOP, MAC_PLATE_BOTTOM)) + (255,))
    mask = Image.new('L', (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [edge, edge, edge + plate - 1, edge + plate - 1],
        radius=round(canvas * MAC_CORNER), fill=255)
    img = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    img.paste(fill, mask=mask)
    img = img.resize((size, size), Image.LANCZOS)

    die = render(max(1, round(size * MAC_PLATE * MAC_DIE)))
    at = (size - die.width) // 2
    img.alpha_composite(die, (at, at))
    return img


def create_mac_icon(path="icon.icns"):
    """icon.icns for the macOS bundle. Each size is drawn at that size, not
    scaled down from the largest, so the small ones keep their edges."""
    images = {s: render_mac(s) for s in MAC_SIZES}
    images[MAC_SIZES[0]].save(path, format='ICNS',
                              append_images=[images[s] for s in MAC_SIZES[1:]])


def create_icon():
    sizes = [256, 128, 64, 48, 32, 24, 16]
    images = {s: render(s) for s in sizes}
    base = images[256]
    base.save("icon.ico", format='ICO',
              sizes=[(s, s) for s in sizes],
              append_images=[images[s] for s in sizes[1:]])
    base.save("icon.png", format='PNG')
    create_mac_icon()
    print("Icon created: icon.ico, icon.png and icon.icns (d12)")
    return True


if __name__ == "__main__":
    try:
        create_icon()
    except Exception as exc:  # icon failure must never break a build
        print(f"Icon creation failed: {exc}")
        raise SystemExit(0)
