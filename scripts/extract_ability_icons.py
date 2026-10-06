#!/usr/bin/env python3
"""
Extract ESO ability icons from the installed game and convert them to PNG.

Why: the encounter log names every ability's icon
(ABILITY_INFO ... "/esoui/art/icons/ability_arcanist_002_b.dds"), so the app
can show icons offline if it ships one PNG per icon found in the game files.
Two families are extracted: ability_*.dds (player skills, for the ability
bars) and death_recap_*.dds (what monster attacks use, for death recaps).
Run this after each ESO update to refresh that set.

Requirements (Windows):
  * EsoExtractData v0.53+ by UESP: https://en.uesp.net/wiki/ESO_Mod:EsoExtractData
    Pass --extractor, set ESO_EXTRACT_DATA, or keep it at D:\\extract-eso\\.
  * Pillow for the DDS -> PNG conversion (pip install -r requirements-build.txt).
  * An installed, patched ESO client (its depot\\eso.mnf). Pass --eso-dir, set
    ESO_INSTALL_DIR, or let the script probe the usual Steam/Zenimax paths.

Pipeline:
  1. Dump eso.mnf's file table without extracting anything (-k -m, ~4 s).
  2. Find every \\esoui\\art\\icons\\<prefix>*.dds row and merge their table
     indexes into a few dozen -s/-e ranges (a small gap of unrelated files is
     cheaper than another ~3 s MNF reload; -n only matches exact names).
     The extractor's -s/-e counter is offset from the table's Index column
     (2,337 on the Update 49 client), so two one-file probes calibrate it.
  3. Extract those ranges to a temp folder. Extracted files are numbered by
     table Index (<archive>\\<Index>.dds), which the table maps back to names.
     Convert the matching .dds files to PNG at --size px, write
     <out>/manifest.json and report what changed against the previous
     manifest. Optionally (--check-log) verify that every icon slotted on a
     bar in an Encounter.log exists in the output.

The game folder is only read. Temp output is deleted unless --keep-temp.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXTRACTOR = Path(r"D:\extract-eso\EsoExtractData.exe")
ESO_DIR_CANDIDATES = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Zenimax Online\The Elder Scrolls Online",
    r"C:\Program Files (x86)\Zenimax Online\The Elder Scrolls Online",
    r"C:\Program Files\Zenimax Online\The Elder Scrolls Online",
    r"D:\Steam\steamapps\common\Zenimax Online\The Elder Scrolls Online",
    r"D:\SteamLibrary\steamapps\common\Zenimax Online\The Elder Scrolls Online",
]
ICON_DIR = "\\esoui\\art\\icons\\"
DEFAULT_PREFIXES = ("ability_", "death_recap_")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "icons" / "abilities"

ABILITY_INFO_RE = re.compile(r'^\d+,ABILITY_INFO,(\d+),"((?:[^"]|"")*)","([^"]*)",')


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- discovery --

def find_eso_dir(explicit: str) -> Path:
    candidates = [explicit, os.environ.get("ESO_INSTALL_DIR")] + ESO_DIR_CANDIDATES
    for c in candidates:
        if c and (Path(c) / "depot" / "eso.mnf").is_file():
            return Path(c)
    sys.exit("eso.mnf not found. Pass --eso-dir <ESO install folder> or set "
             "ESO_INSTALL_DIR (the folder that contains depot\\eso.mnf).")


def find_extractor(explicit: str) -> Path:
    for c in (explicit, os.environ.get("ESO_EXTRACT_DATA"), str(DEFAULT_EXTRACTOR)):
        if c and Path(c).is_file():
            return Path(c)
    sys.exit("EsoExtractData.exe not found. Pass --extractor or set ESO_EXTRACT_DATA. "
             "Download: https://en.uesp.net/wiki/ESO_Mod:EsoExtractData")


# ---------------------------------------------------------------- extractor --

def run_extractor(exe: Path, args, cwd: Path, timeout: int = 900) -> str:
    """Run EsoExtractData; its own exportmnf.log lands in *cwd*."""
    proc = subprocess.run([str(exe), *args], cwd=str(cwd), capture_output=True,
                          text=True, errors="replace", timeout=timeout)
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-8:])
        sys.exit(f"EsoExtractData failed (exit {proc.returncode}) for {args[:1]}...:\n{tail}")
    return output


def read_file_table(mnf_txt: Path):
    """Rows of (table_index, size_bytes, filename) from the -m dump, by index."""
    rows = []
    with open(mnf_txt, encoding="utf-8", errors="replace") as fh:
        next(fh)  # header: Index, ID1, FileIndex, Unk1, Size, ZSize, Hash, Offset, ZTyp, Arch, Unk2, Filename
        for line in fh:
            cols = [c.strip() for c in line.rstrip("\n").split(",", 11)]
            if len(cols) < 12:
                continue
            try:
                rows.append((int(cols[0]), int(cols[4], 16), cols[11]))
            except ValueError:
                continue
    rows.sort()
    return rows


def dump_file_table(exe: Path, mnf: Path, temp: Path):
    """eso.mnf's file table as rows, dumped without extracting anything."""
    mnf_txt = temp / "mnf.txt"
    run_extractor(exe, [str(mnf), str(temp / "list") + os.sep, "-k", "-m", str(mnf_txt)], temp)
    return read_file_table(mnf_txt)


def icon_positions(rows, prefixes=(), stems=()):
    """Positions in *rows* of the icons whose filename starts with one of
    *prefixes*, or whose name without .dds is one of *stems* (lowercase)."""
    targets = tuple(ICON_DIR + p for p in prefixes)
    exact = {ICON_DIR + s + ".dds" for s in stems}
    wanted = []
    for i, row in enumerate(rows):
        name = row[2].lower()
        if (targets and name.startswith(targets)) or name in exact:
            wanted.append(i)
    return wanted


def merge_ranges(rows, wanted, gap_bytes: int):
    """Merge the wanted rows (positions into *rows*) into (start_index, end_index)
    ranges, bridging gaps whose files total at most *gap_bytes*."""
    ranges = []
    for pos in wanted:
        if ranges:
            gap = sum(rows[i][1] for i in range(ranges[-1][1] + 1, pos))
            if gap <= gap_bytes:
                ranges[-1][1] = pos
                continue
        ranges.append([pos, pos])
    return [(rows[s][0], rows[e][0]) for s, e in ranges]


def numbered_outputs(extract_dir: Path):
    """{table Index: path} for every numbered file the extractor wrote."""
    found = {}
    if not extract_dir.is_dir():
        return found
    for arch_dir in extract_dir.iterdir():
        if arch_dir.is_dir() and arch_dir.name.isdigit():
            for f in arch_dir.iterdir():
                if f.is_file() and f.stem.isdigit():
                    found[int(f.stem)] = f
    return found


def probe_offset(exe: Path, mnf: Path, temp: Path, index: int, offset: int = 0) -> int:
    """Extract one sub-file at -s/-e (index + offset) and return the table Index
    of what actually came out, so the caller can compute/verify the offset."""
    probe_dir = temp / f"probe_{index}"
    run_extractor(exe, [str(mnf), str(probe_dir) + os.sep, "-s", str(index + offset), "-e", str(index + offset)], temp)
    got = numbered_outputs(probe_dir)
    if len(got) != 1:
        sys.exit(f"offset probe at {index + offset} produced {len(got)} files, expected 1")
    return next(iter(got))


def calibrate_offset(exe: Path, mnf: Path, temp: Path, first: int, last: int) -> int:
    """The extractor's -s/-e counter does not equal the dumped table Index; the
    numbered output files are named by table Index, so one probe reveals the
    offset and a second probe at the far end verifies it is constant."""
    got = probe_offset(exe, mnf, temp, first)
    offset = first - got
    check = probe_offset(exe, mnf, temp, last, offset)
    if check != last:
        sys.exit(f"-s/-e offset is not constant ({offset} at index {first}, "
                 f"{last - check + offset} at {last}); cannot extract by range safely")
    return offset


# --------------------------------------------------------------- conversion --

def convert_dds(src: Path, dst: Path, size: int) -> None:
    from PIL import Image
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        if rgba.size != (size, size):
            rgba = rgba.resize((size, size), Image.LANCZOS)
        rgba.save(dst, "PNG", optimize=True)


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def extract_icons(exe: Path, mnf: Path, rows, wanted, ranges, out: Path, size: int, temp: Path):
    """Extract the *wanted* rows (inside *ranges*) and write <out>/<stem>.png
    at *size* px. Returns ({stem: {dds_bytes, dds_sha1}}, [(basename, error)])."""
    offset = calibrate_offset(exe, mnf, temp, rows[wanted[0]][0], rows[wanted[-1]][0])
    log(f"-s/-e offset calibrated: extractor index = table Index + {offset}")

    extract_dir = temp / "x"
    t1 = time.time()
    for n, (s, e) in enumerate(ranges, 1):
        run_extractor(exe, [str(mnf), str(extract_dir) + os.sep,
                            "-s", str(s + offset), "-e", str(e + offset)], temp)
        if n % 10 == 0 or n == len(ranges):
            log(f"  extracted range {n}/{len(ranges)} ({time.time() - t1:.0f}s)")

    name_of = {rows[i][0]: rows[i][2].rsplit("\\", 1)[-1].lower() for i in wanted}
    produced = numbered_outputs(extract_dir)
    dds_files = []  # (basename, path)
    for index, basename in sorted(name_of.items()):
        if index in produced:
            dds_files.append((basename, produced[index]))
    if len(dds_files) != len(name_of):
        missing = sorted(set(name_of) - set(produced))
        log(f"WARNING: expected {len(name_of)} icons, extracted {len(dds_files)} "
            f"(missing table Index e.g. {missing[:5]})")

    out.mkdir(parents=True, exist_ok=True)
    icons = {}
    failed = []
    t2 = time.time()
    for basename, dds in dds_files:
        stem = basename.rsplit(".", 1)[0]
        png = out / f"{stem}.png"
        try:
            convert_dds(dds, png, size)
        except Exception as exc:  # noqa: BLE001 - report and carry on
            failed.append((basename, repr(exc)[:80]))
            continue
        icons[stem] = {"dds_bytes": dds.stat().st_size, "dds_sha1": sha1_of(dds)}
    log(f"converted {len(icons)} icons in {time.time() - t2:.1f}s"
        + (f"; {len(failed)} FAILED: {failed[:5]}" if failed else ""))
    return icons, failed


# ------------------------------------------------------------ log checking --

def bar_icons_in_log(log_path: Path):
    """Icon basenames of every ability slotted on a player bar in a log."""
    icon_of, names, bar_ids = {}, {}, set()
    with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if ",ABILITY_INFO," in line:
                m = ABILITY_INFO_RE.match(line)
                if m:
                    icon_of[m.group(1)] = m.group(3).rsplit("/", 1)[-1].lower()
                    names[m.group(1)] = m.group(2)
            elif ",PLAYER_INFO," in line:
                body = line.split(",PLAYER_INFO,", 1)[1]
                groups, depth, start = [], 0, None
                for i, ch in enumerate(body):
                    if ch == "[":
                        if depth == 0:
                            start = i
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                        if depth == 0 and start is not None:
                            groups.append(body[start + 1:i])
                if len(groups) >= 5:  # [abilities],[levels],[gear],[front],[back]
                    for g in groups[-2:]:
                        bar_ids.update(a.strip() for a in g.split(",") if a.strip().isdigit())
    used = {}
    for aid in bar_ids:
        icon = icon_of.get(aid)
        if icon:
            used.setdefault(icon, set()).add(names.get(aid, "?"))
    return used


# --------------------------------------------------------------------- main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eso-dir", default="", help="ESO install folder (contains depot\\eso.mnf)")
    ap.add_argument("--extractor", default="", help="path to EsoExtractData.exe")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"output folder (default {DEFAULT_OUT})")
    ap.add_argument("--size", type=int, default=40, help="PNG edge length in px (game icons are 64; default 40)")
    ap.add_argument("--prefix", action="append", metavar="PREFIX",
                    help="icon filename prefix to extract; repeat for several "
                         f"(default {' and '.join(DEFAULT_PREFIXES)})")
    ap.add_argument("--gap-mb", type=float, default=10.0,
                    help="bridge index gaps up to this many MB of unrelated files per range (default 10)")
    ap.add_argument("--dry-run", action="store_true", help="only list the icons and ranges, extract nothing")
    ap.add_argument("--keep-temp", action="store_true", help="keep the temp extraction folder")
    ap.add_argument("--check-log", default="", help="Encounter.log to verify every slotted icon has a PNG")
    args = ap.parse_args()

    eso_dir = find_eso_dir(args.eso_dir)
    extractor = find_extractor(args.extractor)
    mnf = eso_dir / "depot" / "eso.mnf"
    out = Path(args.out)
    prefixes = tuple(p.lower() for p in (args.prefix or DEFAULT_PREFIXES))
    log(f"eso.mnf:    {mnf}  ({mnf.stat().st_size:,} bytes, modified "
        f"{datetime.fromtimestamp(mnf.stat().st_mtime):%Y-%m-%d %H:%M})")
    log(f"extractor:  {extractor}")
    log(f"output:     {out}  ({args.size}x{args.size} PNG)")

    temp = Path(tempfile.mkdtemp(prefix="eso-icons-"))
    try:
        t0 = time.time()
        rows = dump_file_table(extractor, mnf, temp)
        wanted = icon_positions(rows, prefixes)
        if not wanted:
            sys.exit("no matching icon rows in the file table; is this the live eso.mnf?")
        ranges = merge_ranges(rows, wanted, int(args.gap_mb * 1_000_000))
        total_in_ranges = sum(e - s + 1 for s, e in ranges)
        log(f"file table: {len(rows):,} rows in {time.time() - t0:.1f}s; "
            f"{len(wanted):,} {'/'.join(p + '*.dds' for p in prefixes)} icons -> {len(ranges)} ranges "
            f"({total_in_ranges - len(wanted):,} extra files bridged)")
        if args.dry_run:
            for s, e in ranges:
                log(f"  -s {s} -e {e}  (table Index; add the calibrated offset when running by hand)")
            return 0

        previous = {}
        manifest_path = out / "manifest.json"
        if manifest_path.is_file():
            try:
                previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("icons", {})
            except ValueError:
                previous = {}
        icons, failed = extract_icons(extractor, mnf, rows, wanted, ranges, out, args.size, temp)

        stale = [p for p in out.glob("*.png") if p.stem.lower() not in icons]
        for p in stale:
            p.unlink()
        manifest = {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": {"eso_mnf": str(mnf), "bytes": mnf.stat().st_size,
                       "modified": datetime.fromtimestamp(mnf.stat().st_mtime).isoformat(timespec="seconds")},
            "size_px": args.size,
            "prefixes": list(prefixes),
            "count": len(icons),
            "icons": dict(sorted(icons.items())),
        }
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

        added = sorted(set(icons) - set(previous))
        removed = sorted(set(previous) - set(icons))
        changed = sorted(k for k in set(icons) & set(previous)
                         if icons[k]["dds_sha1"] != previous[k].get("dds_sha1"))
        log(f"manifest: {len(icons)} icons; vs previous: +{len(added)} -{len(removed)} ~{len(changed)}"
            f"{' (stale PNGs removed: %d)' % len(stale) if stale else ''}")
        for label, items in (("added", added), ("removed", removed), ("changed", changed)):
            if items:
                log(f"  {label}: {', '.join(items[:15])}{' ...' if len(items) > 15 else ''}")

        if args.check_log:
            used = bar_icons_in_log(Path(args.check_log))
            missing = {k: v for k, v in used.items() if not (out / k.replace(".dds", ".png")).is_file()}
            log(f"check-log: {len(used)} distinct icons slotted on bars in {args.check_log}; "
                f"{len(missing)} without a PNG")
            for icon, names in sorted(missing.items())[:25]:
                log(f"  MISSING {icon} <- {', '.join(sorted(names)[:3])}")
            if missing:
                return 2
        return 1 if failed else 0
    finally:
        if args.keep_temp:
            log(f"temp kept at {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
