#!/usr/bin/env python3
"""
Extract the art of the trials and arenas from the installed game: one wide
strip of each instance's loading-screen painting, as a JPEG named by the
instance's zone id.

Design: instance art (issue #249). The fight list draws a strip of the
instance's art on a block's header row, and the Instance tab draws it above
its heading (gui.instance_art). The art is the painting the game shows while
the instance loads, \\esoui\\art\\loadingscreens\\loadscreen_<name>_01.dds in
depot\\eso.mnf, 1680 x 1052. The log names a zone by its id (ZONE_CHANGED),
and nothing the app can read ties a zone id to its painting, so INSTANCES
below is that table, kept by hand:

- The file names follow no rule. Sanctum Ophidia's is serpenttrial, the
  Infinite Archive's endless_archive, Dreadsail Reef's dreadsail_reef_trial,
  and Maw of Lorkhaj's is misspelt and has no number (maw_of_lorkaj). Of the
  74 zone names in a year of split logs, 57 found a file by their name with
  the punctuation taken out (measured 2026-11-21).
- The zone ids are the client's own (en.lang table 162658389, read
  2026-11-21 from the live client), and all but Maelstrom Arena's were also
  seen on ZONE_CHANGED lines in the split logs.
- The plain painting is used, not its _veteran copy, which has the veteran
  shield drawn into it as a watermark: the header beside the strip says
  Veteran in words.
- Trials and arenas only (the maintainer's choice, 2026-11-21): nineteen
  lines. The dungeons would be about sixty more, with new ones each year.

What is kept of a painting is one band across its whole width, WIDTH x
HEIGHT px, seven times as wide as it is high: the header strip and the
Instance tab's strip are both about that shape, and each is cut from the
band at the size it is drawn (gui.instance_art). Where the band lies is the
line's focus, from 0 (the painting's top) to 1 (its bottom); FOCUS suits
most paintings, whose subject sits a little above the middle, and a line
gives its own when the subject is elsewhere. --sheet writes one picture of
every strip, to check a focus by eye.

An instance with no line here, or whose file is missing, has no art: the
app then draws its header as it always did and nothing above the Instance
tab's heading. So a new trial needs nothing to work, and one line here (its
zone id, its name, its painting) to get its art, at the next run after a
game update. The run never removes the art of a line it could not extract;
it removes a picture only when its line has been taken out of the table,
and only one an earlier run's manifest lists (remove_stale).

Requirements and the way the files are found in eso.mnf are those of
extract_ability_icons.py, whose helpers this script uses. The game folder is
only read.

    python scripts/extract_instance_art.py --sheet build/instance-art.png
"""

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_ability_icons import (
    calibrate_offset,
    dump_file_table,
    find_eso_dir,
    find_extractor,
    log,
    merge_ranges,
    numbered_outputs,
    probe_offset,
    run_extractor,
    sha1_of,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "art" / "instances"
ART_DIR = "\\esoui\\art\\loadingscreens\\"
# The strip kept of each painting: its whole width, and a seventh of that
WIDTH, HEIGHT = 1680, 240
# Where the strip is cut when a line does not say: 0 the top, 1 the bottom
FOCUS = 0.42
JPEG_QUALITY = 82

# (zone id, the instance's name, its loading screen's file name without
# .dds[, focus]). The name is for the reader and the manifest; the app
# looks the art up by the zone id alone
INSTANCES = (
    # Trials
    (636, "Hel Ra Citadel", "loadscreen_helracitadel_01"),
    (638, "Aetherian Archive", "loadscreen_aetherianarchive_01"),
    (639, "Sanctum Ophidia", "loadscreen_serpenttrial_01"),
    (725, "Maw of Lorkhaj", "loadscreen_maw_of_lorkaj"),
    (975, "Halls of Fabrication", "loadscreen_hallsoffabrication_01"),
    (1000, "Asylum Sanctorium", "loadscreen_asylumsanctorium_01"),
    (1051, "Cloudrest", "loadscreen_cloudrest_01"),
    (1121, "Sunspire", "loadscreen_sunspire_01"),
    (1196, "Kyne's Aegis", "loadscreen_kynesaegis_01"),
    (1263, "Rockgrove", "loadscreen_rockgrove_01"),
    (1344, "Dreadsail Reef", "loadscreen_dreadsail_reef_trial_01"),
    (1427, "Sanity's Edge", "loadscreen_sanitysedge_01"),
    (1478, "Lucent Citadel", "loadscreen_lucentcitadel_01"),
    (1548, "Ossein Cage", "loadscreen_ossein_cage_01"),
    # Arenas
    (635, "Dragonstar Arena", "loadscreen_dragonstararena_01"),
    (677, "Maelstrom Arena", "loadscreen_maelstromarena_01"),
    (1082, "Blackrose Prison", "loadscreen_blackrose_prison_01"),
    (1227, "Vateshran Hollows", "loadscreen_vateshranhollows_01"),
    (1436, "Infinite Archive", "loadscreen_endless_archive_01"),
)


def instances() -> dict:
    """INSTANCES by zone id: {'1121': {'name', 'art', 'focus'}}. A zone id
    or a painting named twice is a mistake in the table and stops the run:
    a line copied for a new trial with its painting left as it was would
    ship the old trial's art under the new one's zone."""
    table, paintings = {}, {}
    for line in INSTANCES:
        zone_id, name, art = str(line[0]), line[1], line[2].lower()
        focus = float(line[3]) if len(line) > 3 else FOCUS
        if zone_id in table:
            raise ValueError(f"zone id {zone_id} is in INSTANCES twice")
        if art in paintings:
            raise ValueError(f"{art} is the painting of both {paintings[art]} and {name}")
        if not 0.0 <= focus <= 1.0:
            raise ValueError(f"{name}: focus {focus} is not between 0 and 1")
        table[zone_id] = {"name": name, "art": art, "focus": focus}
        paintings[art] = name
    return table


def extractor_offset(extractor: Path, mnf: Path, temp: Path, first: int, last: int) -> int:
    """What to add to a table Index for the extractor's -s/-e (see
    extract_ability_icons.calibrate_offset, which probes the first and the
    last file wanted). With one painting wanted, --only with one zone,
    those two are the same row, and its second probe wrote into the folder
    of the first and stopped the run on finding two files there (the
    review of PR #258): one probe gives the offset then."""
    if first == last:
        return first - probe_offset(extractor, mnf, temp, first)
    return calibrate_offset(extractor, mnf, temp, first, last)


def remove_stale(out: Path, previous: dict, table: dict) -> list:
    """Remove the pictures of lines taken out of the table; their names.
    Only a picture an earlier run wrote is touched, one the manifest of
    that run (*previous*) lists: --out may name a folder that holds other
    pictures, which are none of this script's."""
    removed = []
    for zone_id in previous:
        stale = out / f"{zone_id}.jpg"
        if zone_id not in table and stale.is_file():
            stale.unlink()
            removed.append(stale.name)
    return removed


def band_box(size: tuple, focus: float) -> tuple:
    """The (left, top, right, bottom) of the strip in a painting of *size*
    scaled to WIDTH px wide: its whole width, HEIGHT px high, *focus* of the
    way down the room there is."""
    width, height = size
    scaled_height = max(HEIGHT, round(height * WIDTH / width))
    top = round((scaled_height - HEIGHT) * min(1.0, max(0.0, focus)))
    return 0, top, WIDTH, top + HEIGHT


def strip_of(painting, focus: float):
    """The strip of *painting* (a PIL image) at *focus*, WIDTH x HEIGHT."""
    from PIL import Image
    rgb = painting.convert("RGB")
    scaled_height = max(HEIGHT, round(rgb.height * WIDTH / rgb.width))
    if rgb.size != (WIDTH, scaled_height):
        rgb = rgb.resize((WIDTH, scaled_height), Image.LANCZOS)
    return rgb.crop(band_box(painting.size, focus))


def art_positions(rows, wanted_names) -> dict:
    """{file name: position in *rows*} of the loading screens named in
    *wanted_names* (lower case, with .dds)."""
    found = {}
    for position, row in enumerate(rows):
        name = row[2].lower()
        if name.startswith(ART_DIR) and name[len(ART_DIR):] in wanted_names:
            found[name[len(ART_DIR):]] = position
    return found


def write_sheet(out: Path, table: dict, sheet: Path) -> None:
    """One picture of every strip in *out*, each under its name, at half
    size: what the app draws from, to judge a focus by eye."""
    from PIL import Image, ImageDraw
    rows = [(zone_id, entry) for zone_id, entry in table.items()
            if (out / f"{zone_id}.jpg").is_file()]
    if not rows:
        return
    width, height, label = WIDTH // 2, HEIGHT // 2, 16
    picture = Image.new("RGB", (width, len(rows) * (height + label)), "white")
    draw = ImageDraw.Draw(picture)
    for n, (zone_id, entry) in enumerate(rows):
        top = n * (height + label)
        draw.text((4, top + 2), f"{zone_id}  {entry['name']}  ({entry['art']}, focus "
                                f"{entry['focus']:.2f})", fill="black")
        with Image.open(out / f"{zone_id}.jpg") as strip:
            picture.paste(strip.resize((width, height), Image.LANCZOS), (0, top + label))
    sheet.parent.mkdir(parents=True, exist_ok=True)
    picture.save(sheet)
    log(f"sheet:      {sheet}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eso-dir", default="", help="ESO install folder (contains depot\\eso.mnf)")
    ap.add_argument("--extractor", default="", help="path to EsoExtractData.exe")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"output folder (default {DEFAULT_OUT})")
    ap.add_argument("--only", action="append", metavar="ZONE_ID",
                    help="extract this instance alone; repeat for several (the others' art "
                         "and manifest lines are kept)")
    ap.add_argument("--sheet", default="", metavar="PNG",
                    help="also write one picture of every strip, to check each focus by eye")
    ap.add_argument("--keep-temp", action="store_true", help="keep the temp extraction folder")
    args = ap.parse_args()

    table = instances()
    only = {str(z) for z in (args.only or ())}
    unknown = only - set(table)
    if unknown:
        sys.exit(f"not in INSTANCES: {', '.join(sorted(unknown))}")
    chosen = {z: e for z, e in table.items() if not only or z in only}

    eso_dir = find_eso_dir(args.eso_dir)
    extractor = find_extractor(args.extractor)
    mnf = eso_dir / "depot" / "eso.mnf"
    out = Path(args.out)
    # The client's date in UTC: the manifest is committed, and need not
    # say what time zone it was written in
    modified = datetime.fromtimestamp(mnf.stat().st_mtime, tz=timezone.utc)
    log(f"eso.mnf:    {mnf}  ({mnf.stat().st_size:,} bytes, modified "
        f"{modified:%Y-%m-%d %H:%M} UTC)")
    log(f"output:     {out}  ({WIDTH}x{HEIGHT} JPEG, {len(chosen)} of {len(table)} instances)")

    manifest_path = out / "manifest.json"
    previous = {}
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("instances", {})
        except ValueError:
            previous = {}

    temp = Path(tempfile.mkdtemp(prefix="eso-art-"))
    failed = []
    done = {}
    try:
        rows = dump_file_table(extractor, mnf, temp)
        positions = art_positions(rows, {e["art"] + ".dds" for e in chosen.values()})
        for zone_id, entry in chosen.items():
            if entry["art"] + ".dds" not in positions:
                failed.append((zone_id, entry["name"], f"no {entry['art']}.dds in eso.mnf"))
        if positions:
            wanted = sorted(positions.values())
            offset = extractor_offset(extractor, mnf, temp, rows[wanted[0]][0], rows[wanted[-1]][0])
            extract_dir = temp / "x"
            for start, end in merge_ranges(rows, wanted, 0):
                run_extractor(extractor, [str(mnf), str(extract_dir) + "\\",
                                          "-s", str(start + offset), "-e", str(end + offset)], temp)
            produced = numbered_outputs(extract_dir)
            from PIL import Image
            out.mkdir(parents=True, exist_ok=True)
            for zone_id, entry in chosen.items():
                position = positions.get(entry["art"] + ".dds")
                dds = produced.get(rows[position][0]) if position is not None else None
                if position is None:
                    continue
                if dds is None:
                    failed.append((zone_id, entry["name"], "not extracted"))
                    continue
                try:
                    with Image.open(dds) as painting:
                        size = painting.size
                        strip_of(painting, entry["focus"]).save(
                            out / f"{zone_id}.jpg", "JPEG", quality=JPEG_QUALITY, optimize=True)
                except Exception as exc:  # noqa: BLE001 - report and carry on
                    failed.append((zone_id, entry["name"], repr(exc)[:80]))
                    continue
                done[zone_id] = {**entry, "painting": list(size),
                                 "dds_bytes": dds.stat().st_size, "dds_sha1": sha1_of(dds)}
    finally:
        if args.keep_temp:
            log(f"temp kept at {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)

    # A line taken out of the table takes its file with it; a line that
    # could not be extracted keeps the file and the manifest line it had
    for name in remove_stale(out, previous, table):
        log(f"removed:    {name} (no line in INSTANCES)")
    kept = {z: e for z, e in previous.items() if z in table and z not in done
            and (out / f"{z}.jpg").is_file()}
    listed = {**kept, **done}
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"eso_mnf": str(mnf), "bytes": mnf.stat().st_size,
                   "modified": modified.isoformat(timespec="seconds")},
        "width": WIDTH,
        "height": HEIGHT,
        "count": len(listed),
        "instances": dict(sorted(listed.items(), key=lambda item: int(item[0]))),
    }
    out.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    changed = sorted(z for z in done if previous.get(z, {}).get("dds_sha1") not in (None, done[z]["dds_sha1"]))
    added = sorted(z for z in done if z not in previous)
    log(f"manifest:   {len(listed)} instances; extracted {len(done)}, new {len(added)}, "
        f"painting changed {len(changed)}")
    missing = sorted(z for z in table if not (out / f"{z}.jpg").is_file())
    for zone_id, name, why in failed:
        log(f"  FAILED {zone_id} {name}: {why}")
    if missing:
        log(f"  no art for: {', '.join(table[z]['name'] for z in missing)}")
    if args.sheet:
        write_sheet(out, table, Path(args.sheet))
    return 1 if failed or missing else 0


if __name__ == "__main__":
    sys.exit(main())
