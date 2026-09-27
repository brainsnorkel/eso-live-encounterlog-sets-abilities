"""
Update check against GitHub releases (stdlib only, no extra dependencies).

Queries the repo's latest release and compares its tag against the running
version. Network problems are never fatal: every failure path returns None
and the app carries on.
"""

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional

GITHUB_REPO = "brainsnorkel/eso-live-encounterlog-sets-abilities"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
INSTALLER_ASSET_PREFIX = "esolog-tail-windows-setup"
_TIMEOUT_S = 10
_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


@dataclass
class UpdateInfo:
    version: str          # e.g. "0.4.0"
    tag: str              # e.g. "v0.4.0"
    installer_url: str    # browser_download_url of the setup exe asset
    installer_name: str   # asset filename
    notes: str            # release body (may be empty)
    page_url: str         # html_url of the release


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


def release_to_update_info(release: dict) -> Optional[UpdateInfo]:
    """Extract UpdateInfo from a GitHub release JSON dict, or None."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name") or ""
    version = parse_version(tag)
    if version is None:
        return None
    installer = None
    for asset in release.get("assets") or []:
        name = asset.get("name") or ""
        if name.startswith(INSTALLER_ASSET_PREFIX) and name.endswith(".exe"):
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
    )


def fetch_latest_release() -> Optional[dict]:
    """Latest release JSON from GitHub, or None on any failure."""
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"User-Agent": "esolog-tail-update-check",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def check_for_update(current_version: str,
                     skip_version: Optional[str] = None) -> Optional[UpdateInfo]:
    """UpdateInfo when a newer, non-skipped release with an installer exists."""
    release = fetch_latest_release()
    if release is None:
        return None
    info = release_to_update_info(release)
    if info is None:
        return None
    if not is_newer(info.version, current_version):
        return None
    if skip_version and parse_version(skip_version) == parse_version(info.version):
        return None
    return info


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
