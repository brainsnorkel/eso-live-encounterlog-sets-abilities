#!/usr/bin/env python3
"""
Move the byte-identical copies of split logs to the Recycle Bin (issue #85).

Until 0.18.0 a session split again was written out again under the next
``-N`` suffix: the pre-GUI tool's ``--read-all-then-tail`` did that to every
session in the log at every start, and 513 of the 899 files in the
maintainer's split folder were copies of another file, several GB in all.
The splitter no longer makes them (see LogSplitter in src/esolog_tail.py);
this script clears the ones already on disk.

A copy is a file with the same session stamp as another, the same size and
the same bytes (whole-file SHA-256, not a head hash). Of each group the file
with the lowest suffix is kept, the plain name before ``-1`` before ``-2``,
and the rest go to the Recycle Bin, never deleted outright, so a mistake can
be undone. Zipped splits and the ``keep`` folder are left alone.

    python scripts/dedupe_splits.py                      # list what would move
    python scripts/dedupe_splits.py --recycle            # move the copies
    python scripts/dedupe_splits.py --dir D:/esologs/splits --recycle

Without --dir the split folder from the app's config is used.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

_SUFFIX_RE = re.compile(r"^(.*?)(?:-(\d+))?$")


def split_key(name: str):
    """(session prefix, suffix number) of a split's file name; None for a
    file that is not a split log."""
    if not name.endswith(".log") or name.endswith("-temp.log"):
        return None
    stem = name[:-len(".log")]
    match = _SUFFIX_RE.match(stem)
    prefix, suffix = match.group(1), match.group(2)
    return prefix, int(suffix) if suffix else 0


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_copies(folder: Path):
    """[(kept, [copies...])] for every group of byte-identical splits of one
    session stamp, hashing only the files whose stamp and size repeat."""
    by_prefix_size = defaultdict(list)
    for entry in os.scandir(folder):
        key = split_key(entry.name)
        if key is None or not entry.is_file():
            continue
        prefix, suffix = key
        by_prefix_size[(prefix, entry.stat().st_size)].append((suffix, Path(entry.path)))
    groups = []
    for (prefix, size), members in sorted(by_prefix_size.items()):
        if len(members) < 2:
            continue
        by_hash = defaultdict(list)
        for suffix, path in sorted(members):
            by_hash[sha256_of(path)].append(path)
        for paths in by_hash.values():
            if len(paths) > 1:
                groups.append((paths[0], paths[1:]))
    return groups


def config_split_dir() -> Path | None:
    try:
        from app_config import AppConfig
        folder = AppConfig().get("split.dir")
    except (ImportError, OSError, ValueError):
        return None
    return Path(folder) if folder else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, help="the split folder (default: the app's setting)")
    parser.add_argument("--recycle", action="store_true",
                        help="move the copies to the Recycle Bin (default: list them)")
    parser.add_argument("--json", action="store_true", help="print the groups as JSON")
    args = parser.parse_args(argv)
    folder = args.dir or config_split_dir()
    if folder is None or not folder.is_dir():
        print(f"No split folder: {folder}", file=sys.stderr)
        return 1
    groups = find_copies(folder)
    copies = [copy for _kept, found in groups for copy in found]
    total = sum(copy.stat().st_size for copy in copies)
    if args.json:
        print(json.dumps([{"kept": str(k), "copies": [str(c) for c in cs]} for k, cs in groups], indent=1))
    else:
        for kept, found in groups:
            print(f"{kept.name}: {len(found)} {'copy' if len(found) == 1 else 'copies'} "
                  f"({kept.stat().st_size / 1e6:.1f} MB each)")
    print(f"{len(groups)} sessions with copies, {len(copies)} copies, {total / 1e9:.2f} GB"
          + ("" if args.recycle else " (nothing moved; pass --recycle)"))
    if not args.recycle or not copies:
        return 0
    from recycle_bin import TrashUnavailable, move_to_trash
    moved = 0
    for copy in copies:
        try:
            move_to_trash(copy)
            moved += 1
        except TrashUnavailable as exc:
            print(f"  left {copy.name}: {exc}", file=sys.stderr)
    print(f"moved {moved} of {len(copies)} copies to the Recycle Bin")
    return 0 if moved == len(copies) else 1


if __name__ == "__main__":
    sys.exit(main())
