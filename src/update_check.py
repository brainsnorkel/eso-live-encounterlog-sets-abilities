"""
Update check against GitHub releases (stdlib only, no extra dependencies).

Queries the repository's latest release and compares its tag against the
running version. Network problems are never fatal: every failure is a
result the caller can read, and the app carries on.

Design: the check repeats every 15 minutes while the app runs (issue #56,
2026-10-26; gui/update_poller.py has the schedule), so it is conditional.
GitHub returns an ``ETag`` with every reply; sent back as
``If-None-Match``, an unchanged release is answered ``304 Not Modified``
with no body. GitHub limits unsigned requests to 60 an hour per address
and does not count a 304 against that limit, so four checks an hour cost
nothing while nothing changes, and a household of several copies behind
one address stays far under the limit; a plain GET each time would spend
four of the 60 per copy for a few KB of unchanged JSON. A limit reply
(403 or 429) names a reset time in ``X-RateLimit-Reset`` (epoch seconds)
or ``Retry-After`` (seconds); the result carries it, capped at an hour
from now, and the poller makes no request before then. The ETag is kept
for the run only, so each start sends one full request.

The release body is GitHub's generated notes (one line per pull request
and a compare link), shown in the ⓘ popup beside the Update button; the
release date comes from ``published_at``.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

GITHUB_REPO = "brainsnorkel/eso-live-encounterlog-sets-abilities"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
# Release asset that carries the update on each platform: (name prefix, suffix).
# Windows gets the installer; Linux the tarball. Other platforms have no build.
PLATFORM_ASSETS = {
    "win32": ("esolog-tail-windows-setup", ".exe"),
    "linux": ("esolog-tail-linux-x86_64", ".tar.gz"),
}
_TIMEOUT_S = 10
_MAX_WAIT_S = 3600          # the longest a rate-limit reply can hold checks off
_RATE_LIMIT_CODES = (403, 429)
_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


@dataclass
class UpdateInfo:
    version: str          # e.g. "0.4.0"
    tag: str              # e.g. "v0.4.0"
    installer_url: str    # browser_download_url of this platform's asset
    installer_name: str   # asset filename
    notes: str            # release body (may be empty)
    page_url: str         # html_url of the release
    published: str = ""   # published_at as GitHub gives it (ISO 8601), may be empty


@dataclass
class FetchResult:
    """What one request to the latest-release endpoint came back with."""
    release: Optional[dict] = None     # the JSON of a full reply
    etag: Optional[str] = None         # the validator to send next time
    not_modified: bool = False         # 304: the release is as it was
    retry_at: Optional[float] = None   # epoch seconds: no request before this
    error: Optional[str] = None        # anything else that went wrong


@dataclass
class CheckResult:
    """A fetch read against the running version."""
    info: Optional[UpdateInfo] = None  # a newer, unskipped release with this platform's asset
    etag: Optional[str] = None
    not_modified: bool = False
    retry_at: Optional[float] = None
    error: Optional[str] = None


def parse_version(text: str) -> Optional[tuple]:
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    return tuple(int(g) for g in match.groups())


def is_newer(candidate: str, current: str) -> bool:
    cand = parse_version(candidate)
    cur = parse_version(current)
    if cand is None or cur is None:
        return False
    return cand > cur


def release_to_update_info(release: dict,
                           platform: Optional[str] = None) -> Optional[UpdateInfo]:
    """Extract UpdateInfo from a GitHub release JSON dict, or None.

    None also when the release has no asset for *platform* (default: the
    running one).
    """
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name") or ""
    version = parse_version(tag)
    if version is None:
        return None
    wanted = PLATFORM_ASSETS.get(platform or sys.platform)
    if wanted is None:
        return None
    prefix, suffix = wanted
    installer = None
    for asset in release.get("assets") or []:
        name = asset.get("name") or ""
        if name.startswith(prefix) and name.endswith(suffix):
            installer = asset
            break
    if installer is None:
        return None
    return UpdateInfo(
        version=".".join(str(part) for part in version),
        tag=tag,
        installer_url=installer.get("browser_download_url") or "",
        installer_name=installer.get("name") or "",
        notes=(release.get("body") or "").strip(),
        page_url=release.get("html_url") or "",
        published=release.get("published_at") or "",
    )


def format_release_date(published: str) -> str:
    """'2026-10-26T00:23:57Z' -> '26 October 2026'; '' when unreadable."""
    try:
        day = datetime.strptime((published or "")[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{day.day} {day.strftime('%B %Y')}"


def changelog_url(tag: str) -> str:
    """The changelog as it stood at *tag*, on GitHub."""
    return f"https://github.com/{GITHUB_REPO}/blob/{tag or 'main'}/CHANGELOG.md"


def _retry_at(headers) -> Optional[float]:
    """When a limit reply says to come back, capped at an hour from now;
    None when it names no time (or one already past)."""
    now = time.time()
    retry_after = (headers.get("Retry-After") or "").strip() if headers else ""
    reset = (headers.get("X-RateLimit-Reset") or "").strip() if headers else ""
    try:
        if retry_after:
            when = now + float(retry_after)
        elif reset:
            when = float(reset)
        else:
            return None
    except ValueError:
        return None
    if when <= now:
        return None
    return min(when, now + _MAX_WAIT_S)


def fetch_latest_release(etag: Optional[str] = None) -> FetchResult:
    """One request for the latest release; conditional when *etag* is given."""
    headers = {"User-Agent": "esolog-tail-update-check",
               "Accept": "application/vnd.github+json"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(LATEST_RELEASE_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            body = json.loads(response.read().decode("utf-8", errors="replace"))
            return FetchResult(release=body,
                               etag=response.headers.get("ETag") or etag)
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return FetchResult(not_modified=True, etag=etag)
        if exc.code in _RATE_LIMIT_CODES:
            return FetchResult(retry_at=_retry_at(exc.headers),
                               error=f"rate limited ({exc.code})")
        return FetchResult(error=f"HTTP {exc.code}")
    except Exception as exc:
        return FetchResult(error=str(exc) or exc.__class__.__name__)


def check_for_update(current_version: str,
                     skip_version: Optional[str] = None,
                     etag: Optional[str] = None) -> CheckResult:
    """The latest release read against *current_version*: ``info`` is set
    when a newer, unskipped release with this platform's asset exists;
    ``not_modified`` when GitHub confirmed the release *etag* stood for;
    ``retry_at`` and ``error`` as the fetch reported them."""
    fetched = fetch_latest_release(etag)
    result = CheckResult(etag=fetched.etag, not_modified=fetched.not_modified,
                         retry_at=fetched.retry_at, error=fetched.error)
    if fetched.release is None:
        return result
    info = release_to_update_info(fetched.release)
    if info is None or not is_newer(info.version, current_version):
        return result
    if skip_version and parse_version(skip_version) == parse_version(info.version):
        return result
    result.info = info
    return result


def download_file(url: str, dest_path, progress=None) -> bool:
    """Stream *url* to *dest_path*; progress(done, total) per chunk.

    Returns True on success; on failure removes the partial file.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "esolog-tail-update-check"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(dest_path, "wb") as out:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
        return True
    except Exception:
        try:
            import os
            os.unlink(dest_path)
        except OSError:
            pass
        return False
