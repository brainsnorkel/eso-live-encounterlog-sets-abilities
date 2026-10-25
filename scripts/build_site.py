#!/usr/bin/env python3
"""Build the home page (site/) into _site/ for GitHub Pages.

The page is a hand-written index.html whose download buttons need the
current release: the release assets carry the version in their names
(esolog-tail-windows-setup-0.13.3.exe), so no fixed link can point at the
latest installer. This script reads the latest release from the GitHub API,
fills the page's placeholders, and copies the page, its favicon and social
card, and the screenshots it uses from docs/screencaps/ into _site/.
.github/workflows/pages.yml runs it and publishes _site/.

Placeholders in index.html are {{name}} for the names in release_values()
plus {{site_url}}. A placeholder left unfilled, a missing asset or an
unreadable release fails the build: a page with holes must not be published.

Standard library only, so the Pages job installs nothing.
"""

import argparse
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
SCREENCAPS_DIR = ROOT / "docs" / "screencaps"
DEFAULT_OUT = ROOT / "_site"

GITHUB_REPO = "brainsnorkel/eso-live-encounterlog-sets-abilities"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
# Where GitHub serves the page: the account's user site carries the custom
# domain xop.co, so every project site of the account lives under it, and
# the github.io path redirects there. Absolute URLs (canonical, og:image)
# must use this; --site-url overrides it if the site gets a domain of its own.
SITE_URL = "https://xop.co/eso-live-encounterlog-sets-abilities/"

# Placeholder name -> (asset name prefix, suffix), as src/update_check.py
# picks the update asset for each platform
ASSETS = {
    "windows_setup_url": ("esolog-tail-windows-setup", ".exe"),
    "windows_portable_url": ("esolog-tail-windows-portable", ".zip"),
    "linux_url": ("esolog-tail-linux-x86_64", ".tar.gz"),
}
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
_IMG_RE = re.compile(r"""(?:src|href)=["']img/([^"']+)["']""")
_TIMEOUT_S = 20


class SiteBuildError(Exception):
    """Anything that must stop the build rather than publish a wrong page."""


def fetch_latest_release(url: str = LATEST_RELEASE_URL) -> dict:
    """The latest release's JSON from GitHub; GITHUB_TOKEN raises the rate
    limit when set (the Pages job passes the workflow token)."""
    headers = {"User-Agent": "esolog-tail-site-build",
               "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # any failure stops the build
        raise SiteBuildError(f"could not read the latest release: {exc}") from exc


def release_values(release: dict) -> dict:
    """The placeholder values a release provides: version, release_url and
    one URL per entry of ASSETS. Raises SiteBuildError when the release is
    a draft or prerelease, has no version tag, or lacks an asset."""
    if not isinstance(release, dict):
        raise SiteBuildError("the release is not a JSON object")
    if release.get("draft") or release.get("prerelease"):
        raise SiteBuildError("the latest release is a draft or prerelease")
    tag = release.get("tag_name") or ""
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    if not match:
        raise SiteBuildError(f"release tag {tag!r} is not vX.Y.Z")
    values = {
        "version": match.group(1),
        "release_url": release.get("html_url")
        or f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}",
    }
    assets = release.get("assets") or []
    for key, (prefix, suffix) in ASSETS.items():
        for asset in assets:
            name = asset.get("name") or ""
            if name.startswith(prefix) and name.endswith(suffix):
                url = asset.get("browser_download_url")
                if not url:
                    raise SiteBuildError(f"asset {name} has no download URL")
                values[key] = url
                break
        else:
            raise SiteBuildError(
                f"release {tag} has no asset {prefix}*{suffix}")
    return values


def render(template: str, values: dict) -> str:
    """Fill every {{name}} in *template*; an unknown name is an error."""
    missing = sorted(set(_PLACEHOLDER_RE.findall(template)) - set(values))
    if missing:
        raise SiteBuildError(
            "index.html has placeholders without a value: " + ", ".join(missing))
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def page_images(html: str) -> list:
    """The img/<name> files the page refers to, in order, without repeats."""
    seen = []
    for name in _IMG_RE.findall(html):
        if name not in seen:
            seen.append(name)
    return seen


def build(out_dir: Path, release: dict, site_url: str = SITE_URL,
          site_dir: Path = SITE_DIR,
          screencaps_dir: Path = SCREENCAPS_DIR) -> Path:
    """Write the finished site to *out_dir* (emptied first) and return it."""
    if not site_url.endswith("/"):
        site_url += "/"
    values = release_values(release)
    values["site_url"] = site_url
    html = render((site_dir / "index.html").read_text(encoding="utf-8"), values)

    # Empty the folder rather than remove it: a local server left serving
    # it (python -m http.server in _site/) holds the folder open on Windows
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.iterdir():
        if stale.is_dir():
            shutil.rmtree(stale)
        else:
            stale.unlink()
    for path in site_dir.iterdir():
        if path.name == "index.html" or path.name.startswith("."):
            continue
        if path.is_file():
            shutil.copy2(path, out_dir / path.name)
    (out_dir / "index.html").write_text(html, encoding="utf-8", newline="\n")
    # Pages is deployed from an Actions artifact, which skips Jekyll anyway;
    # the marker keeps it that way if the source is ever switched to a branch
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    img_dir = out_dir / "img"
    img_dir.mkdir()
    for name in page_images(html):
        source = screencaps_dir / name
        if not source.is_file():
            raise SiteBuildError(f"index.html uses img/{name}, "
                                 f"not found in {screencaps_dir}")
        shutil.copy2(source, img_dir / name)
    return out_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output folder (default: _site/)")
    parser.add_argument("--release-json", type=Path,
                        help="build from a saved release JSON instead of "
                             "asking the GitHub API")
    parser.add_argument("--site-url", default=SITE_URL,
                        help=f"the page's absolute URL (default: {SITE_URL})")
    args = parser.parse_args(argv)
    try:
        if args.release_json:
            release = json.loads(args.release_json.read_text(encoding="utf-8"))
        else:
            release = fetch_latest_release()
        out = build(args.out, release, args.site_url)
    except SiteBuildError as exc:
        print(f"site build failed: {exc}", file=sys.stderr)
        return 1
    values = release_values(release)
    print(f"Site built in {out} for release {values['version']} "
          f"at {args.site_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
