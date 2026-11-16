#!/usr/bin/env python3
"""Start the built macOS app and see that it stays up (issue #32).

usage: smoke_macos.py <executable> [--seconds 20] [--log <file>] [--platform <name>]

<executable> is the bundle's own binary,
"ESO Log Tail.app/Contents/MacOS/esolog-gui". CI runs this on every macOS
it claims to support, on the zip expanded as a download would be
(.github/workflows/build-installers.yml, the smoke-macos job).

The app is given a scratch HOME. Its config there names a fixture log and
turns the update check off, so the run reads nothing in the real
~/Documents (where macOS would ask a question nobody is there to answer),
touches no real settings and calls no server.

The pass: after the wait the process is still running, it has written
crash.log (so Python started and the app reached its own start-up, not
only the bootloader), and crash.log names no crash. The app's output goes
to a file, not a pipe: a pipe nobody reads fills up, and an app blocked on
it would pass as running. The output and crash.log are printed either way.

Standard library only, and no syntax newer than Python 3.9: the smoke job
runs it with the runner's own python3.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_LOG = REPO_ROOT / "tests" / "fixtures" / "golden_fight.log"
# What esolog_gui's crash log writes for an unhandled exception, and what
# Python's faulthandler writes for a fault in native code
CRASH_MARKS = ("Unhandled exception", "Fatal Python error")
# Where platformdirs puts the app's config on macOS, under HOME
CONFIG_DIR = Path("Library") / "Application Support" / "esolog-tail"


def verdict(alive: bool, exit_code, crash_log, output: str = ""):
    """Why the start failed, or "" for a pass. *crash_log* is the text of
    crash.log, or None when the app wrote none; *output* is what the app
    printed, where a crash from before crash.log was opened would be."""
    if not alive:
        return f"the app exited (status {exit_code}) instead of staying up"
    if crash_log is None:
        return "the app wrote no crash.log: it never reached its own start-up"
    for mark in CRASH_MARKS:
        if mark in crash_log:
            return f"the app logged a crash while starting ({mark!r} in crash.log)"
        if mark in output:
            return f"the app printed a crash while starting ({mark!r} in its output)"
    return ""


def smoke(command, seconds: float = 20, log: Path = FIXTURE_LOG, platform: str = "",
          home=None):
    """Run *command* (the executable and any arguments) for *seconds* in a
    scratch HOME (*home*, or a new temporary folder that is left behind for
    whoever reads a failure). Returns (problem, report): the verdict, and
    what to print."""
    home = Path(home) if home else Path(tempfile.mkdtemp(prefix="esolog-smoke-"))
    config_dir = home / CONFIG_DIR
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({
        "log_path": str(log),
        # Read the fixture's fights at start-up: more of the app runs
        "history": {"load_recent_mb": 50, "backfill_offered": True},
        "update": {"check_enabled": False},
    }), encoding="utf-8")
    env = dict(os.environ, HOME=str(home))
    if platform:
        env["QT_QPA_PLATFORM"] = platform

    output_path = home / "output.txt"
    with open(output_path, "wb") as output:
        process = subprocess.Popen(list(command), env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=seconds)
            alive = False
        except subprocess.TimeoutExpired:
            alive = True
        exit_code = process.returncode
        if alive:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    crash_path = config_dir / "crash.log"
    crash_log = (crash_path.read_text(encoding="utf-8", errors="replace")
                 if crash_path.exists() else None)
    printed = output_path.read_text(encoding="utf-8", errors="replace")
    problem = verdict(alive, exit_code, crash_log, printed)
    report = "\n".join([
        f"scratch HOME: {home}",
        f"still running after {seconds:g} s: {alive}",
        "--- output ---",
        printed.rstrip(),
        "--- crash.log ---",
        "(none)" if crash_log is None else crash_log.rstrip(),
        "--- config folder ---",
        "  ".join(sorted(item.name for item in config_dir.iterdir())),
    ])
    return problem, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executable")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--log", type=Path, default=FIXTURE_LOG,
                        help="the log the app is pointed at (default: the fixture)")
    parser.add_argument("--platform", default="",
                        help="QT_QPA_PLATFORM for the app (default: its own choice, cocoa)")
    args = parser.parse_args(argv)
    if not args.log.is_file():
        print(f"no such log: {args.log}", file=sys.stderr)
        return 2
    problem, report = smoke([args.executable], args.seconds, args.log, args.platform)
    print(report)
    if problem:
        print(f"::error::{problem}")
        return 1
    print("passed: the app stayed up and logged no crash")
    return 0


if __name__ == "__main__":
    sys.exit(main())
