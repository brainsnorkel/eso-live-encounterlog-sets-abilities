#!/usr/bin/env python3
"""List the minimum macOS each binary of the built app was made for, and
fail when one asks for more than the app says it needs (issue #32).

usage: check_macos_stamps.py "dist/ESO Log Tail.app"

Every Mach-O file carries the oldest macOS it was built to run on (its
"minos"; `otool -l` prints it). The app's own floor is LSMinimumSystemVersion
in its Info.plist, which esolog-tail.spec writes. A binary stamped above the
floor may call what the floor's macOS lacks, and macOS does not refuse to
load it: the app would start and then fail somewhere.

So a binary above the floor fails the build. This is what catches a bundle
built with the wrong Python: Homebrew's Python and OpenSSL are stamped with
the macOS of the machine they were built on, and such a bundle is for that
machine only. CI builds with setup-python's Python, which is made for old
systems.

One exception is printed and not enforced: PySide6's and shiboken6's own
binding libraries. Their wheel is tagged macOS 14 and Qt's frameworks in it
are stamped 14.4, but the binding libraries are stamped 26.0. Whether they
run on an older macOS cannot be read from the stamp, so it is tested: the
build job runs the test suite on the oldest macOS, and the smoke-macos job
starts the app on each (.github/workflows/build-installers.yml).
"""
import plistlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Mach-O files start with one of these: thin 64-bit, thin 32-bit (either
# byte order), or a fat file of several architectures
MACH_O_MAGICS = {
    b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf",
}
# LC_BUILD_VERSION prints "minos 14.4"; the older LC_VERSION_MIN_MACOSX
# prints "version 10.13" on the line after "cmd LC_VERSION_MIN_MACOSX"
_MINOS = re.compile(r"^\s*minos\s+([0-9.]+)\s*$", re.MULTILINE)
_VERSION_MIN = re.compile(
    r"cmd LC_VERSION_MIN_MACOSX\s*\n\s*cmdsize \d+\s*\n\s*version\s+([0-9.]+)")
# The bindings' own libraries, in a PySide6 or shiboken6 folder: QtCore.abi3.so,
# libpyside6.abi3.6.12.dylib, libshiboken6.abi3.6.12.dylib, Shiboken.abi3.so
_BINDING_NAME = re.compile(r"(\.abi3\.so$|^libpyside6|^libshiboken6)")


def version_tuple(text: str) -> tuple:
    """"15" and "15.0" as the same version: three numbers, the missing ones 0."""
    parts = [int(part) for part in text.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def min_macos(otool_output: str) -> str:
    """The highest minimum macOS in `otool -arch all -l` output (one for each
    architecture of a fat file), or "" when it names none."""
    found = _MINOS.findall(otool_output) + _VERSION_MIN.findall(otool_output)
    return max(found, key=version_tuple) if found else ""


def is_binding(relative_path: str) -> bool:
    """Whether the file is one of PySide6's or shiboken6's binding libraries
    (printed, not enforced), and not one of Qt's own frameworks or plugins."""
    parts = Path(relative_path).parts
    if not any(part in ("PySide6", "shiboken6") for part in parts):
        return False
    if any(part in ("Qt", "plugins") or part.endswith(".framework") for part in parts):
        return False
    return bool(_BINDING_NAME.search(parts[-1]))


def judge(stamps: dict, floor: str) -> tuple:
    """Split {relative path: minimum macOS} into (too_new, bindings_above):
    the binaries that fail the check, and the binding libraries above the
    floor that are only reported."""
    too_new, bindings_above = {}, {}
    for path, stamp in stamps.items():
        if not stamp or version_tuple(stamp) <= version_tuple(floor):
            continue
        (bindings_above if is_binding(path) else too_new)[path] = stamp
    return too_new, bindings_above


def is_mach_o(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(4) in MACH_O_MAGICS
    except OSError:
        return False


def read_stamps(app: Path) -> tuple:
    """({path relative to the bundle: minimum macOS}, [paths otool could not
    read]) for every Mach-O file in the bundle. Symlinks are skipped: each
    points at a file that is listed itself. `-arch all` because otool
    otherwise prints a fat file's slice for this machine only."""
    stamps, unread = {}, []
    for path in sorted(app.rglob("*")):
        if path.is_symlink() or not path.is_file() or not is_mach_o(path):
            continue
        done = subprocess.run(["otool", "-arch", "all", "-l", str(path)],
                              capture_output=True, text=True)
        if done.returncode:
            unread.append(str(path.relative_to(app)))
        else:
            stamps[str(path.relative_to(app))] = min_macos(done.stdout)
    return stamps, unread


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    app = Path(args[0])
    with open(app / "Contents" / "Info.plist", "rb") as handle:
        floor = plistlib.load(handle)["LSMinimumSystemVersion"]
    stamps, unread = read_stamps(app)
    if unread:
        # A file that starts as a Mach-O file does and that otool refuses:
        # its stamp is unknown, and unknown is not a pass
        print("otool could not read:")
        for path in unread:
            print(f"  {path}")
        print(f"::error::otool could not read {len(unread)} binaries "
              f"(the first: {unread[0]})")
        return 1
    if not stamps:
        print(f"::error::no Mach-O file found in {app}")
        return 1

    print(f"{len(stamps)} binaries; the app's minimum macOS is {floor}")
    for stamp, count in sorted(Counter(stamps.values()).items(),
                               key=lambda item: version_tuple(item[0] or "0")):
        print(f"  {stamp or 'no stamp':>8}  {count} files")

    too_new, bindings_above = judge(stamps, floor)
    if bindings_above:
        print(f"PySide6's and shiboken6's binding libraries above {floor} "
              f"(reported only; the tests and the smoke job are their check):")
        for path, stamp in sorted(bindings_above.items()):
            print(f"  {stamp:>8}  {path}")
    if too_new:
        print(f"Above the app's minimum {floor}:")
        for path, stamp in sorted(too_new.items()):
            print(f"  {stamp:>8}  {path}")
        # One annotation, not one a file: a Homebrew build has about fifty
        print(f"::error::{len(too_new)} binaries need a newer macOS than the "
              f"app's minimum {floor} (the first: {min(too_new)}). Was the bundle "
              f"built with a Python made for this machine only, such as "
              f"Homebrew's? CI builds with setup-python's.")
        return 1
    print("passed: no other binary needs more than the app's minimum")
    return 0


if __name__ == "__main__":
    sys.exit(main())
