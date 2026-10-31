#!/usr/bin/env python3
"""
Extract the game's map art for the fight pane's map (issue #148): one
stitched WebP image per map, under data/maps/, with a manifest.

Why: MAP_CHANGED names each map by its texture path
(2552,"Lucent Citadel","deadlands/U42TRI_LucentCitMap001"), and in lower
case that path is the art's in the client: \\art\\maps\\<path>_<n>.dds in
depot\\eso.mnf, 256 px DXT tiles numbered row by row from the top left
(3x3 for most maps, 4x4 and 5x5 for some). The positions in the log are
fractions of the stitched image, with no offset or scale, so the image is
all the fight pane needs. The art is ZeniMax's, like the ability icons: it
is extracted from the installed client and bundled, never downloaded.

Which maps: those of instanced content only (the maintainer's choice,
2026-11-01), the maps a log shows in a zone whose ZONE_CHANGED difficulty
is NORMAL or VETERAN (trials, dungeons, arenas, the Infinite Archive), in a
solo dungeon (pen_crit.SOLO_DUNGEON_ZONES), or in GROUP_ZONES, group
content that logs no difficulty. The client files its maps by region, not
by kind (2,481 maps in 55 folders, 26 of them under dungeons\\), so the
list comes from logs: --from-log scans a log, or a folder of split logs,
and adds what it finds to the manifest's list. A run without --from-log
refreshes the maps the manifest lists, after a patch. Over the 414 split
logs of 2026-11-01 that was 255 maps, 230 of them 3x3.

Each map is saved at its own size, 256 px a tile (768 px for a 3x3 map),
WebP at quality 80: a boss arena covers only 30 to 50 px of a 768 px map,
so the art is never shrunk.

Requirements (Windows): EsoExtractData and an installed client as for
extract_ability_icons.py, whose extraction this reuses, and Pillow.
"""

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "src"))
import extract_ability_icons as icon_extractor  # noqa: E402

from pen_crit import SOLO_DUNGEON_ZONES  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "data" / "maps"
MAP_DIR = "\\art\\maps\\"
TILE_RE = re.compile(r"^\\art\\maps\\(.+)_(\d+)\.dds$")
INSTANCED_DIFFICULTIES = ("NORMAL", "VETERAN")
# Group content whose ZONE_CHANGED gives no difficulty, by zone id: the
# Night Market, Update 49's event zone, and its areas (Opulent Ordeal is its
# twelve-player trial), and the Elinhir Private Arena of target dummies
GROUP_ZONES = {
    "1559": "Night Market", "1562": "Gossamer Crypt", "1563": "Mournful Catacomb",
    "1564": "Timeless Wallow", "1565": "Opulent Ordeal",
    "1126": "Elinhir Private Arena",
}
WEBP_QUALITY = 80


def log(msg: str) -> None:
    print(msg, flush=True)


def instanced(zone_id: str, difficulty: str) -> bool:
    """Whether a zone is instanced content, whose maps are bundled."""
    return (difficulty.upper() in INSTANCED_DIFFICULTIES or zone_id in SOLO_DUNGEON_ZONES
            or zone_id in GROUP_ZONES)


def maps_in_logs(paths):
    """{texture path in lower case: {'names', 'ids', 'zones'}} for every
    MAP_CHANGED of instanced content in the logs at *paths* (files, or
    folders of .log files)."""
    files = []
    for p in paths:
        p = Path(p)
        files.extend(sorted(p.glob("*.log")) if p.is_dir() else [p])
    found = {}
    for path in files:
        zone_id, zone_name, difficulty = "", "", ""
        with open(path, "rb") as fh:
            for raw in fh:
                head = raw[:40]
                if b",ZONE_CHANGED," in head:
                    fields = raw.decode("utf-8", "replace").rstrip("\r\n").split(",")
                    if len(fields) >= 5:
                        zone_id, difficulty = fields[2], fields[-1]
                        zone_name = ",".join(fields[3:-1]).strip('"')
                elif b",MAP_CHANGED," in head and instanced(zone_id, difficulty):
                    rest = raw.decode("utf-8", "replace").rstrip("\r\n").split(",", 3)
                    if len(rest) < 4:
                        continue
                    name, _, texture = rest[3].rpartition(",")
                    texture = texture.strip('"').lower()
                    if not texture:
                        continue
                    record = found.setdefault(texture, {"names": set(), "ids": set(), "zones": set()})
                    record["names"].add(name.strip('"'))
                    record["ids"].add(rest[2])
                    record["zones"].add(zone_name)
    return found


def map_tiles(rows):
    """{texture path: [(tile number, table position), ...]} of every map's
    tiles in the file table *rows*."""
    tiles = {}
    for pos, (_index, _size, name) in enumerate(rows):
        m = TILE_RE.match(name.lower())
        if m:
            tiles.setdefault(m.group(1).replace("\\", "/"), []).append((int(m.group(2)), pos))
    return tiles


def stitch(tile_files, out: Path) -> tuple[int, int, str]:
    """Stitch the tiles (paths in tile order) into one WebP at *out*:
    (grid, edge in px, sha1 of the tiles)."""
    from PIL import Image
    grid = math.isqrt(len(tile_files))
    digest = hashlib.sha1()
    images = []
    for f in tile_files:
        digest.update(f.read_bytes())
        with Image.open(f) as im:
            images.append(im.convert("RGB"))
    tile = images[0].size[0]
    canvas = Image.new("RGB", (tile * grid, tile * grid))
    for n, im in enumerate(images):
        if im.size != (tile, tile):
            im = im.resize((tile, tile), Image.LANCZOS)
        canvas.paste(im, ((n % grid) * tile, (n // grid) * tile))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "WEBP", quality=WEBP_QUALITY, method=6)
    return grid, tile * grid, digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eso-dir", default="", help="ESO install folder (contains depot\\eso.mnf)")
    ap.add_argument("--extractor", default="", help="path to EsoExtractData.exe")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"output folder (default {DEFAULT_OUT})")
    ap.add_argument("--from-log", action="append", metavar="PATH", default=[],
                    help="an Encounter.log, or a folder of split logs, whose instanced maps are added "
                         "to the list; repeat for several")
    ap.add_argument("--gap-mb", type=float, default=10.0,
                    help="bridge index gaps up to this many MB of unrelated files per range (default 10)")
    ap.add_argument("--dry-run", action="store_true", help="only list the maps, extract nothing")
    ap.add_argument("--keep-temp", action="store_true", help="keep the temp extraction folder")
    args = ap.parse_args()

    out = Path(args.out)
    manifest_path = out / "manifest.json"
    previous = {}
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("maps", {})
        except ValueError:
            previous = {}
    wanted = {path: {"names": set(info.get("names", ())), "ids": set(info.get("ids", ())),
                     "zones": set(info.get("zones", ()))}
              for path, info in previous.items()}
    if args.from_log:
        t0 = time.time()
        found = maps_in_logs(args.from_log)
        new = sorted(set(found) - set(wanted))
        for path, info in found.items():
            record = wanted.setdefault(path, {"names": set(), "ids": set(), "zones": set()})
            for key in ("names", "ids", "zones"):
                record[key] |= info[key]
        log(f"logs: {len(found)} instanced maps in {time.time() - t0:.0f}s, {len(new)} new to the list")
    if not wanted:
        sys.exit("no maps to extract: pass --from-log with a log or a folder of split logs")

    eso_dir = icon_extractor.find_eso_dir(args.eso_dir)
    extractor = icon_extractor.find_extractor(args.extractor)
    mnf = eso_dir / "depot" / "eso.mnf"
    temp = Path(tempfile.mkdtemp(prefix="eso-maps-"))
    try:
        rows = icon_extractor.dump_file_table(extractor, mnf, temp)
        tiles = map_tiles(rows)
        missing = sorted(p for p in wanted if p not in tiles)
        usable = {}
        for path in sorted(wanted):
            numbered = sorted(tiles.get(path, ()))
            grid = math.isqrt(len(numbered))
            if numbered and grid * grid == len(numbered) and [n for n, _ in numbered] == list(range(len(numbered))):
                usable[path] = [pos for _, pos in numbered]
            elif numbered:
                missing.append(path)
        log(f"file table: {len(rows):,} rows, {len(tiles):,} maps; {len(usable)} of {len(wanted)} "
            f"wanted maps have their tiles" + (f"; none for {', '.join(missing[:8])}" if missing else ""))
        if args.dry_run:
            for path in sorted(usable):
                log(f"  {path} ({len(usable[path])} tiles)")
            return 0
        positions = sorted(pos for poses in usable.values() for pos in poses)
        ranges = icon_extractor.merge_ranges(rows, positions, int(args.gap_mb * 1_000_000))
        offset = icon_extractor.calibrate_offset(extractor, mnf, temp, rows[positions[0]][0],
                                                 rows[positions[-1]][0])
        log(f"-s/-e offset calibrated: extractor index = table Index + {offset}; {len(ranges)} ranges")
        extract_dir = temp / "x"
        t1 = time.time()
        for n, (s, e) in enumerate(ranges, 1):
            icon_extractor.run_extractor(extractor, [str(mnf), str(extract_dir) + "\\",
                                                     "-s", str(s + offset), "-e", str(e + offset)], temp)
            if n % 10 == 0 or n == len(ranges):
                log(f"  extracted range {n}/{len(ranges)} ({time.time() - t1:.0f}s)")
        produced = icon_extractor.numbered_outputs(extract_dir)

        maps, failed = {}, []
        for path, poses in sorted(usable.items()):
            files = [produced.get(rows[pos][0]) for pos in poses]
            if any(f is None for f in files):
                failed.append((path, "tiles not extracted"))
                continue
            target = out.joinpath(*path.split("/")).with_suffix(".webp")
            try:
                grid, px, sha1 = stitch(files, target)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                failed.append((path, repr(exc)[:80]))
                continue
            info = wanted[path]
            maps[path] = {"names": sorted(info["names"]), "ids": sorted(info["ids"]),
                          "zones": sorted(info["zones"]), "grid": grid, "px": px,
                          "bytes": target.stat().st_size, "tiles_sha1": sha1}
        keep = {out.joinpath(*p.split("/")).with_suffix(".webp").resolve() for p in maps}
        stale = [f for f in out.rglob("*.webp") if f.resolve() not in keep]
        for f in stale:
            f.unlink()
        manifest = {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": {"eso_mnf": str(mnf), "bytes": mnf.stat().st_size,
                       "modified": datetime.fromtimestamp(mnf.stat().st_mtime).isoformat(timespec="seconds")},
            "webp_quality": WEBP_QUALITY,
            "count": len(maps),
            "maps": maps,
        }
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        added = sorted(set(maps) - set(previous))
        changed = sorted(p for p in set(maps) & set(previous)
                         if maps[p]["tiles_sha1"] != previous[p].get("tiles_sha1"))
        total = sum(m["bytes"] for m in maps.values())
        log(f"manifest: {len(maps)} maps, {total / 1e6:.1f} MB; vs previous: +{len(added)} "
            f"~{len(changed)}" + (f"; stale images removed: {len(stale)}" if stale else ""))
        if failed:
            log(f"FAILED: {failed[:8]}")
        return 1 if failed else 0
    finally:
        if args.keep_temp:
            log(f"temp kept at {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
