#!/usr/bin/env python3
"""Make a beta the Stable release, take a Stable release back, list the
betas that could be promoted, or open a reminder when Stable falls behind.

Design (issue #134, the maintainer's decisions of 2026-10-29): every tag is
published as a GitHub pre-release, a beta. Promoting turns that same
release into a full one and marks it latest, so Stable users run exactly
the build beta users ran, and ``/releases/latest``, which the app's Stable
channel and the home page read, moves to it. Nothing is rebuilt or
retagged.

A beta may be promoted when:

- it is newer than the Stable release and carries all three files;
- it was published at least 48 hours ago;
- the maintainer used it live, in at least one session with fights; the
  script cannot see that, so ``--used-live`` says so;
- no issue labelled ``regression`` affects it. A regression issue names the
  version that brought the fault in as the first ``X.Y.Z`` in its title
  (never its body, where a pasted "Python 3.14.10" would read as a
  version). While open it affects that version and every later one; once
  closed, those published before it was closed, since the fix can only be
  in a later release. So a fixed regression still marks the versions that
  carried it, which is the rule "no later beta fixes a fault in it". A
  regression whose title names no version affects every release until its
  title does: a rule that cannot be read must stop a promotion, not let it
  through. An issue that turns out not to be a regression loses the label.

``--force "<reason>"`` overrides the last three rules and writes the reason
into the release notes (a crash fix that cannot wait two days); the first
is never overridden.

The release notes are rewritten as the changes since the previous Stable
release: every pull request line of the releases in between, oldest first,
without repeats, and the compare link. The app's update popup shows a
Stable user these notes, and a Stable user skips every beta in between.

``/releases/latest`` can lag a minute behind a change (seen on
2026-10-28), so the check of it retries once. The script then starts the
Pages workflow, which rebuilds the home page's buttons on main: a
``release`` event would run on the tag, and the github-pages environment
deploys from main only.

``--demote`` pulls a bad Stable release: it becomes a draft again and the
previous Stable release is marked latest. A draft is invisible to the app
(both channels read without a login, which never sees drafts), to the home
page and to ``--candidates``; left a pre-release it would still be the
newest beta, offered on Beta and on the home page. Installs that already
updated keep it. ``gh release edit <tag> --draft=false --prerelease``
publishes it again as a beta.

``--candidates`` lists the betas newer than Stable and what each still
lacks: a session uses it to propose a promotion, never to make one.
``--remind`` (the weekly workflow) opens an issue when the oldest beta that
meets the time and regression rules was published more than 14 days ago,
which is a beta that has waited two weeks for a decision, unless one is
open already.

Needs the GitHub CLI, logged in (``GH_TOKEN`` in a workflow).

    python scripts/promote_release.py vX.Y.Z --used-live [--dry-run]
    python scripts/promote_release.py vX.Y.Z --force "crash fix" [--dry-run]
    python scripts/promote_release.py --demote vX.Y.Z [--dry-run]
    python scripts/promote_release.py --candidates
    python scripts/promote_release.py --remind [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

REPO = "brainsnorkel/eso-live-encounterlog-sets-abilities"
SOAK = timedelta(hours=48)
STALE = timedelta(days=14)
ASSETS = (("esolog-tail-windows-setup-", ".exe"),
          ("esolog-tail-windows-portable-", ".zip"),
          ("esolog-tail-linux-x86_64-", ".tar.gz"))
REMINDER_TITLE = "Stable is behind"
LATEST_RETRY_S = 60
_TAG_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
_VERSION_IN_TEXT_RE = re.compile(r"(?<![\d.])v?(\d+)\.(\d+)\.(\d+)(?![\d.])")
_NOTES_SECTIONS = ("## What's Changed", "## Changes since")


class PromotionError(Exception):
    """A refusal or a failed step; the message says which."""


# ---- reading releases and issues ----

def version_of(release):
    """(major, minor, patch) for an app release's tag, None for any other."""
    match = _TAG_RE.fullmatch((release or {}).get("tag_name") or "")
    return tuple(int(part) for part in match.groups()) if match else None


def parse_time(text):
    """GitHub's ISO 8601 time as an aware datetime; None when unreadable."""
    try:
        return datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def app_releases(releases):
    """The published app releases, oldest version first; drafts and data
    releases (tags that are not vX.Y.Z) left out."""
    found = [r for r in releases or [] if not r.get("draft") and version_of(r)]
    return sorted(found, key=version_of)


def has_all_assets(release) -> bool:
    version = release["tag_name"][1:]
    names = {asset.get("name") for asset in release.get("assets") or []}
    return all(f"{prefix}{version}{suffix}" in names for prefix, suffix in ASSETS)


def introduced_in(issue):
    """The version a regression issue names: the first X.Y.Z in its title;
    None when the title names none."""
    match = _VERSION_IN_TEXT_RE.search(issue.get("title") or "")
    return tuple(int(part) for part in match.groups()) if match else None


def regressions_affecting(release, issues):
    """The numbers of the regression issues that affect *release*; one that
    names no version affects every release."""
    version = version_of(release)
    published = parse_time(release.get("published_at"))
    hits = []
    for issue in issues:
        introduced = introduced_in(issue) or (0, 0, 0)
        if version < introduced:
            continue
        closed = parse_time(issue.get("closedAt")) if issue.get("state") == "CLOSED" else None
        if closed is None or published is None or published < closed:
            hits.append(issue["number"])
    return hits


# ---- the rules ----

def hard_problems(release, stable):
    """What no --force can override."""
    if release is None:
        return ["there is no such release"]
    if version_of(release) is None:
        return ["it is not an app release (vX.Y.Z)"]
    problems = []
    if release.get("draft"):
        problems.append("it is a draft")
    if not release.get("prerelease"):
        problems.append("it is already a full release")
    if not has_all_assets(release):
        problems.append("it lacks one of the three files")
    if stable is not None and version_of(release) <= version_of(stable):
        problems.append(f"it is not newer than the Stable release, {stable['tag_name']}")
    return problems


def soft_problems(release, now, issues, used_live=True):
    """The rules --force can override; *used_live* False adds the reminder
    that only the maintainer can confirm live use."""
    problems = []
    published = parse_time(release.get("published_at"))
    if published is None or now - published < SOAK:
        hours = (now - published).total_seconds() / 3600 if published else 0
        problems.append(f"published {hours:.0f} hours ago; the rule is "
                        f"{SOAK.total_seconds() / 3600:.0f}")
    hits = regressions_affecting(release, issues)
    if hits:
        problems.append("affected by regression issue " + ", ".join(f"#{n}" for n in hits))
    if not used_live:
        problems.append("not confirmed as used live in a session with fights (--used-live)")
    return problems


def candidates(releases, stable, now, issues):
    """[(beta, problems)] for every beta newer than *stable* with all three
    files, oldest first; live use is not judged here."""
    report = []
    for release in app_releases(releases):
        if not release.get("prerelease") or not has_all_assets(release):
            continue
        if stable is not None and version_of(release) <= version_of(stable):
            continue
        report.append((release, soft_problems(release, now, issues)))
    return report


# ---- the notes ----

def change_lines(body):
    """The pull request lines of a release's notes ('* ...' under GitHub's
    "What's Changed", or under an earlier promotion's "Changes since")."""
    lines, inside = [], False
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            inside = line.startswith(_NOTES_SECTIONS)
            continue
        if line.startswith("**Full Changelog**"):
            inside = False
            continue
        if inside and line.startswith("* "):
            lines.append(line)
    return lines


def combined_notes(releases, stable, target, now, reason=None) -> str:
    low = version_of(stable) if stable is not None else (-1, -1, -1)
    between = [r for r in app_releases(releases)
               if low < version_of(r) <= version_of(target)]
    seen, lines = set(), []
    for release in between:
        for line in change_lines(release.get("body")):
            if line not in seen:
                seen.add(line)
                lines.append(line)
    base = stable["tag_name"] if stable is not None else None
    out = [f"## Changes since {base}" if base else "## Changes", ""]
    out += lines or ["* No pull request lines in the notes of the releases in between."]
    if base:
        out += ["", (f"**Full Changelog**: https://github.com/{REPO}/compare/"
                     f"{base}...{target['tag_name']}")]
    published = (parse_time(target.get("published_at")) or now).date().isoformat()
    betas = sum(1 for r in between if r.get("prerelease"))
    out += ["", (f"Made Stable on {now.date().isoformat()}; published as a beta on "
                 f"{published}, one of {betas} beta release{'s' if betas != 1 else ''} "
                 f"since {base or 'the start'}.")]
    if reason:
        out += ["", f"Made Stable before meeting every rule: {reason}"]
    return "\n".join(out) + "\n"


# ---- GitHub, through the gh CLI ----

def gh(*args) -> str:
    # gh writes UTF-8; read as the Windows code page, a ⓘ in a beta's notes
    # would reach the Stable notes as mojibake
    done = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8",
                          check=False)
    if done.returncode != 0:
        raise PromotionError(f"gh {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout


def fetch_releases():
    return json.loads(gh("api", f"repos/{REPO}/releases?per_page=100"))


def fetch_latest_tag() -> str:
    return json.loads(gh("api", f"repos/{REPO}/releases/latest"))["tag_name"]


def fetch_regression_issues():
    return json.loads(gh("issue", "list", "--repo", REPO, "--label", "regression",
                         "--state", "all", "--limit", "200",
                         "--json", "number,title,body,state,closedAt"))


def _with_file(text, use):
    """Call *use* with the path of a temporary file holding *text*."""
    handle, path = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        return use(path)
    finally:
        os.unlink(path)


def wait_for_latest(tag):
    for attempt in range(2):
        if fetch_latest_tag() == tag:
            return
        if attempt == 0:
            time.sleep(LATEST_RETRY_S)
    raise PromotionError(f"/releases/latest does not name {tag} yet; check the releases page")


# ---- the actions ----

def _state():
    releases = fetch_releases()
    latest = fetch_latest_tag()
    by_tag = {r.get("tag_name"): r for r in releases}
    stable = by_tag.get(latest)
    if stable is not None and version_of(stable) is None:
        raise PromotionError(f"the latest release, {latest}, is not an app release; "
                             "mark the newest Stable app release latest first")
    return releases, by_tag, stable


def promote(tag, used_live=False, reason=None, dry_run=False, now=None):
    now = now or datetime.now(timezone.utc)
    releases, by_tag, stable = _state()
    target = by_tag.get(tag)
    problems = hard_problems(target, stable)
    if problems:
        raise PromotionError(f"{tag} cannot be made Stable: " + "; ".join(problems))
    problems = soft_problems(target, now, fetch_regression_issues(), used_live)
    if problems and not reason:
        raise PromotionError(f"{tag} does not meet the rules yet:\n  - "
                             + "\n  - ".join(problems)
                             + '\nPass --force "<reason>" to make it Stable anyway.')
    notes = combined_notes(releases, stable, target, now, reason if problems else None)
    print(f"{tag} becomes the Stable release (was {stable['tag_name'] if stable else 'none'}).")
    if dry_run:
        print("Dry run; the notes would read:\n")
        print(notes)
        return notes
    _with_file(notes, lambda path: gh("release", "edit", tag, "--repo", REPO,
                                      "--prerelease=false", "--latest", "--notes-file", path))
    wait_for_latest(tag)
    gh("workflow", "run", "pages.yml", "--repo", REPO)
    print(f"Done: {tag} is Stable; the Pages workflow was started.")
    return notes


def demote(tag, dry_run=False):
    releases, _by_tag, stable = _state()
    if stable is None or stable.get("tag_name") != tag:
        raise PromotionError(f"{tag} is not the Stable release "
                             f"({stable['tag_name'] if stable else 'there is none'})")
    earlier = [r for r in app_releases(releases)
               if not r.get("prerelease") and version_of(r) < version_of(stable)]
    if not earlier:
        raise PromotionError("there is no earlier Stable release to fall back to")
    previous = earlier[-1]["tag_name"]
    print(f"{tag} is pulled (a draft again); {previous} becomes the Stable release again.")
    if dry_run:
        print("Dry run; nothing changed.")
        return previous
    gh("release", "edit", tag, "--repo", REPO, "--draft")
    gh("release", "edit", previous, "--repo", REPO, "--latest")
    wait_for_latest(previous)
    gh("workflow", "run", "pages.yml", "--repo", REPO)
    print(f"Done: {previous} is Stable; the Pages workflow was started.")
    return previous


def describe_candidates(now=None) -> str:
    now = now or datetime.now(timezone.utc)
    releases, _by_tag, stable = _state()
    return format_candidates(stable, candidates(releases, stable, now,
                                                fetch_regression_issues()), now)


def format_candidates(stable, report, now) -> str:
    lines = [f"Stable: {stable['tag_name'] if stable else 'none'}"]
    if not report:
        lines.append("No beta newer than Stable.")
    for release, problems in report:
        published = parse_time(release.get("published_at"))
        age = f"{(now - published).total_seconds() / 86400:.1f} days" if published else "?"
        state = "; ".join(problems) if problems else "meets the rules, if it was used live"
        lines.append(f"  {release['tag_name']:<10} out {age:<10} {state}")
    return "\n".join(lines)


def remind(dry_run=False, now=None):
    """Open the reminder issue when it is due; returns its title, or None."""
    now = now or datetime.now(timezone.utc)
    releases, _by_tag, stable = _state()
    if stable is None:
        print("No Stable release.")
        return None
    report = candidates(releases, stable, now, fetch_regression_issues())
    ready = [release for release, problems in report if not problems]
    if not ready:
        print("No beta meets the time and regression rules.")
        return None
    oldest, newest = ready[0], ready[-1]
    waited = now - parse_time(oldest["published_at"])
    if waited <= STALE:
        print(f"The oldest beta that qualifies, {oldest['tag_name']}, has waited "
              f"{waited.days} days; not yet behind.")
        return None
    open_issues = json.loads(gh("issue", "list", "--repo", REPO, "--state", "open",
                                "--search", f'"{REMINDER_TITLE}" in:title',
                                "--json", "number,title"))
    if any(issue["title"].startswith(REMINDER_TITLE) for issue in open_issues):
        print("A reminder is open already.")
        return None
    title = f"{REMINDER_TITLE}: {newest['tag_name']} could be made Stable"
    body = (f"Stable is {stable['tag_name']}. {oldest['tag_name']} has met the time and "
            f"regression rules for a while and was published {waited.days} days ago; the "
            f"newest beta that meets them is {newest['tag_name']}.\n\n"
            f"If it has been used live in a session with fights, make it Stable:\n\n"
            f"    python scripts/promote_release.py {newest['tag_name']} --used-live\n\n"
            f"The betas newer than Stable:\n\n```\n{format_candidates(stable, report, now)}\n```\n\n"
            f"Opened by the weekly Stable reminder (issue #134); it opens another only "
            f"when none is open.\n")
    if dry_run:
        print(f"Dry run; would open: {title}\n\n{body}")
        return title
    _with_file(body, lambda path: gh("issue", "create", "--repo", REPO, "--title", title,
                                     "--body-file", path))
    print(f"Opened: {title}")
    return title


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tag", nargs="?", help="the beta to make Stable, vX.Y.Z")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--demote", metavar="TAG",
                        help="turn this Stable release back into a beta")
    action.add_argument("--candidates", action="store_true",
                        help="list the betas newer than Stable")
    action.add_argument("--remind", action="store_true",
                        help="open a reminder issue if Stable is behind")
    parser.add_argument("--used-live", action="store_true",
                        help="the beta was used live in a session with fights")
    parser.add_argument("--force", metavar="REASON",
                        help="promote despite the time, live-use and regression rules")
    parser.add_argument("--dry-run", action="store_true", help="change nothing")
    args = parser.parse_args(argv)
    try:
        if args.demote:
            demote(args.demote, args.dry_run)
        elif args.candidates:
            print(describe_candidates())
        elif args.remind:
            remind(args.dry_run)
        elif args.tag:
            promote(args.tag, args.used_live, args.force, args.dry_run)
        else:
            parser.error("name a beta to promote, or --demote, --candidates or --remind")
    except PromotionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Piped or redirected on Windows, print uses the code page, which has no ⓘ
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
