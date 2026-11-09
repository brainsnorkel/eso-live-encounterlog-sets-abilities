"""
The trial completion banner, captured from the screen after END_TRIAL (issue #167).

Design: The score banner. When a trial or a veteran arena completes, the game
shows "COMPLETED: SUNSPIRE (VETERAN)" with the final score, the time, the
vitality bonus and the revives used, for ten seconds (TRIAL_COMPLETE_LIFESPAN_MS
in the game's centerscreenannouncehandlers.lua; one handler,
EVENT_RAID_TRIAL_COMPLETE, serves trials and arenas alike). Keeping a picture
of it is the traditional record of a run. The log writes END_TRIAL at the same
moment (the engine's _handle_end_trial), so the app can take the picture
itself, on Windows: it grabs the screen once a second, reads each grab with
Windows' own text recognition, and keeps a grab in which the run's score
appears, cropped to the banner, as a PNG. The score makes the capture
*verified*: the digits of the log's finalScore must be read off the picture,
so the file can only be this run's banner, whatever the client language. The
game's own timer text (trial_result.duration_text) is the fallback for a score
the recognition split badly. Nothing is kept when no grab verifies (the game
in exclusive fullscreen, alt-tabbed away, no recognition language installed,
the banner never shown); the app's diagnostic line says so.

When the banner comes (issue #183): it waits in the game's announcement queue
behind higher priorities (champion points, experience, objectives, quest
updates; 3.5 s each), so a trial's showed 0.5 to 4 s after END_TRIAL and
Maelstrom Arena's about 25 s after it, at the end of an arena that queues
several. The burst therefore runs until END_TRIAL's own time plus
BURST_UNTIL_S, and for at least BURST_MIN_SECONDS when the line is read late
(burst_seconds): Vateshran Hollows' line, read 1 s late, was given only 15 s
and its banner came after; Maelstrom's, read 21.5 s late, was caught as it
appeared.

Keeping a whole banner: the banner is drawn in left to right over 1,700 ms
(CenterScreenLargeTextWipe in centerscreenannounce.xml) and drawn out over
2,000 ms at the end, so the first grab that verifies can hold part of it (the
Maelstrom file of 2026-11-01 stops at "Vita"). After it, FOLLOW_UP_GRABS more
are taken of the same monitor, a second apart, and the most complete one is
kept (more_complete): the one that reads the vitality bonus's digits, then the
one whose stats row reaches furthest right, a later one on a tie.

Why text recognition rather than a fixed rectangle: the banner's position is
in the game's UI units (230 from the top, centred, in centerscreenannounce.xml),
which scale with the resolution and the UI scale setting, so the crop comes
from the boxes the recognition returns for the title and the stats row. The
banner is centred on the screen, so the crop is made symmetric about the
screen's centre line: the left edge the words give fixes the right edge too,
which keeps the vitality icon and the revives count the recognition never
reads, and the undrawn part of a banner caught mid-wipe. (A game in a window
off the screen's centre is the case this misjudges.) Only the top-centre of
the screen (REGION_WIDTH_FRACTION by REGION_HEIGHT_FRACTION, centred, so its
centre is the screen's) is read and only the banner band is kept, so the
group frames and the chat stay out of the picture and the Hide names switch
needs no change.

What each burst saw goes into banner.log beside crash.log (burst_log_text,
append_burst_log): the run, when END_TRIAL was written and read, the outcome
line, and one line per grab with the monitor, frame, how many lines were read
and whether the score or the time matched. Of the recognised text only the
lines holding a digit are kept in full (the stats line, the timer); other
announcements pass through the region, so the rest is only counted (Chris,
2026-11-01). No pictures: an unverified grab is never kept. The newest
BANNER_LOG_BURSTS bursts are kept.

Why Windows PowerShell: Windows.Media.Ocr is a WinRT API that Windows
PowerShell 5.1 (on every Windows 10 and 11) can call, so no package is needed;
pwsh 7 cannot, lacking the WinRT projection. One process serves a whole
burst, fed file paths on its standard input, which saves the 1.3 s start per
grab. The paths must be long paths: the WinRT StorageFile refuses 8.3 short
names. The engine is the user's profile language, or the first installed
recognition language; none at all is the unverified case.

Why Desktop Duplication (desktop_duplication) rather than Qt's screen grab:
on an HDR desktop every 8-bit grab comes out washed-out, the desktop being
composed in linear scRGB. Duplication hands the FP16 desktop over as it is,
and gui.banner_burst.frame_to_image turns it into sRGB: divide by the display's SDR white level
(DisplayConfig's DISPLAYCONFIG_SDR_WHITE_LEVEL, in units of 80 nits), so the
brightness Windows shows SDR white at lands on white, then Qt's colour-space
conversion from linear to sRGB. Qt's grab (QScreen.grabWindow) is the fallback
when duplication is refused, as it is in a remote session.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from trial_result import POINTS_PER_VITALITY, duration_text

__all__ = [
    "BANNER_LOG_BURSTS",
    "BURST_INTERVAL_MS",
    "BURST_MIN_SECONDS",
    "BURST_UNTIL_S",
    "FOLLOW_UP_GRABS",
    "LIVE_WINDOW_S",
    "BannerTarget",
    "GrabRecord",
    "OcrLine",
    "OcrSession",
    "append_burst_log",
    "banner_file_name",
    "burst_log_text",
    "burst_seconds",
    "completeness",
    "crop_rect",
    "display_sdr_white",
    "existing_banner",
    "long_path",
    "more_complete",
    "ocr_available",
    "parse_ocr_output",
    "region_rect",
    "verify",
]

# The burst: one grab a second (Chris, 2026-11-01) until END_TRIAL's own
# time plus BURST_UNTIL_S (Chris, 2026-11-01: an arena's banner came about
# 25 s after it and stays 10 s), and never less than BURST_MIN_SECONDS
BURST_UNTIL_S = 45
BURST_MIN_SECONDS = 15
BURST_INTERVAL_MS = 1000
# Grabs taken after the first verified one, for a banner still drawing in
FOLLOW_UP_GRABS = 2
# A result older than this when it reaches the GUI is a replayed one (the
# session replayed at attach, a split opened for review): no capture.
LIVE_WINDOW_S = 90
# The part of the screen read: the central share of the width, the top share
# of the height. The banner sits 230 UI units from the top, centred.
REGION_WIDTH_FRACTION = 0.60
REGION_HEIGHT_FRACTION = 0.45
# Padding round the recognised band, as shares of the band's width (each
# side) and of its height (above and below)
PAD_SIDE = 0.04
PAD_VERTICAL = 0.40
# The bursts banner.log keeps
BANNER_LOG_BURSTS = 50
# A title line is taken into the band when its bottom lies within this many
# stats-line heights above the stats line
TITLE_REACH = 3.0
# scRGB's reference white: an FP16 value of 1.0 on an HDR desktop
SDR_REFERENCE_NITS = 80.0


@dataclass
class OcrLine:
    """One line the recognition read: its text and its box in the image's
    pixels."""
    text: str
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass
class BannerTarget:
    """What the capture looks for and names the file after: the run the
    END_TRIAL line recorded."""
    name: str
    is_vet: bool
    score: int
    duration_ms: int
    ended_epoch: float
    trial_id: int = 0
    vitality: int | None = None

    @classmethod
    def from_result(cls, result, fallback_epoch: float | None = None) -> BannerTarget | None:
        """The target for a trial_result dict, else None. The run ended at
        the END_TRIAL line's own moment, which the engine puts on the dict
        as 'ended_epoch'; *fallback_epoch* (or now) stands in when the
        log's start was unknown."""
        if not result:
            return None
        ended = result.get("ended_epoch")
        if not ended:
            ended = fallback_epoch if fallback_epoch else time.time()
        return cls(
            name=str(result.get("name") or "Trial"),
            is_vet=bool(result.get("is_vet")),
            score=int(result.get("score") or 0),
            duration_ms=int(result.get("duration_ms") or 0),
            ended_epoch=float(ended),
            trial_id=int(result.get("trial_id") or 0),
            vitality=result.get("vitality"),
        )

    @classmethod
    def from_entry(cls, entry) -> BannerTarget | None:
        """The target for a fight entry carrying a trial_result, else None.
        Without the line's own moment on the result, the fight's log start
        plus its duration stands in, then the wall clock the engine stamped
        (ended_at)."""
        result = getattr(entry, "trial_result", None)
        if not result:
            return None
        start = _parse_timestamp(getattr(entry, "timestamp", ""))
        if start is not None:
            fallback = start + float(getattr(entry, "duration_s", 0.0) or 0.0)
        else:
            fallback = float(getattr(entry, "ended_at", 0.0) or 0.0)
        return cls.from_result(result, fallback_epoch=fallback)

    @property
    def key(self) -> tuple:
        """What identifies the run: the result alone, which never changes,
        where the fight's span can (a fight the game cut in two is rebuilt
        longer when it really ends)."""
        return (self.trial_id, self.score, self.duration_ms)

    @property
    def file_name(self) -> str:
        return banner_file_name(self.name, self.is_vet, self.score, self.ended_epoch)

    @property
    def time_text(self) -> str:
        return duration_text(self.duration_ms)

    @property
    def bonus_text(self) -> str | None:
        """The vitality bonus as the banner writes it ('35000'), if known."""
        if self.vitality is None:
            return None
        return str(int(self.vitality) * POINTS_PER_VITALITY)

    def is_live(self, now: float | None = None) -> bool:
        """Whether the result is fresh enough for the banner to be on screen."""
        now = time.time() if now is None else now
        return (now - self.ended_epoch) <= LIVE_WINDOW_S


def burst_seconds(ended_epoch: float, now: float | None = None) -> float:
    """How long a burst starting *now* runs: until END_TRIAL's own time
    *ended_epoch* plus BURST_UNTIL_S, and at least BURST_MIN_SECONDS."""
    now = time.time() if now is None else now
    return max(float(BURST_MIN_SECONDS), ended_epoch + BURST_UNTIL_S - now)


def _parse_timestamp(text: str) -> float | None:
    try:
        return _dt.datetime.strptime(str(text), "%Y-%m-%d %H:%M:%S").timestamp()  # noqa: DTZ007  local, as the engine writes it
    except (ValueError, TypeError):
        return None


_BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def banner_file_name(name: str, is_vet: bool, score: int, ended_epoch: float) -> str:
    """'Sunspire Veteran 253117 2026-11-01 2131.png': trial, difficulty, score,
    local date and time the run ended."""
    when = _dt.datetime.fromtimestamp(ended_epoch).strftime("%Y-%m-%d %H%M")  # noqa: DTZ006  local, like the fight list
    clean = re.sub(r"\s+", " ", _BAD_NAME_CHARS.sub(" ", name)).strip() or "Trial"
    return f"{clean} {'Veteran' if is_vet else 'Normal'} {score} {when}.png"


def existing_banner(folder: Path | None, target: BannerTarget) -> Path | None:
    """The banner already saved for *target* in *folder*, if any (the history
    is rebuilt from the log at every start, so the link is found again by
    the file's name)."""
    if folder is None:
        return None
    path = Path(folder) / target.file_name
    return path if path.is_file() else None


# ---- verification and crop ----

# A thousands gap the recognition or the game puts in a number: a space,
# comma or point before a group of exactly three digits ('253 117',
# '253,117'); '1 253117' is two numbers
_DIGIT_GAP = re.compile(r"(?<=\d)[ ,.](?=\d{3}\b)")
_TIME_TOKEN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")


def _number_tokens(text: str) -> list[str]:
    """The numbers in *text*, with the spaces, commas and points the
    recognition puts between digit groups removed ('253 117' -> '253117')."""
    return re.findall(r"\d+", _DIGIT_GAP.sub("", text))


def verify(lines: Sequence[OcrLine], target: BannerTarget) -> tuple[int, str] | None:
    """The index of the line that proves the picture is *target*'s banner and
    how: ('score') the run's final score read as a number on it, or ('time')
    the run's timer text on a line that also carries a word. None when
    neither is there."""
    score = str(target.score)
    for i, line in enumerate(lines):
        if score in _number_tokens(line.text):
            return i, "score"
    timer = target.time_text
    for i, line in enumerate(lines):
        if timer in _TIME_TOKEN.findall(line.text) and re.search(r"[A-Za-z]{3,}", line.text):
            return i, "time"
    return None


def crop_rect(lines: Sequence[OcrLine], stats_index: int, width: int, height: int,
              centre_x: int | None = None) -> tuple[int, int, int, int]:
    """The band to keep, in the image's pixels: the stats line and the title
    line(s) within TITLE_REACH above it, padded, and made symmetric about
    *centre_x*, the banner's centre line (by default the image's middle,
    which region_rect makes the screen's), clamped to the image."""
    stats = lines[stats_index]
    x0, y0, x1, y1 = stats.x, stats.y, stats.right, stats.bottom
    reach = stats.h * TITLE_REACH
    for i, line in enumerate(lines):
        if i == stats_index or line.bottom > stats.y or stats.y - line.bottom > reach:
            continue
        x0, y0 = min(x0, line.x), min(y0, line.y)
        x1, y1 = max(x1, line.right), max(y1, line.bottom)
    band_w, band_h = x1 - x0, y1 - y0
    centre = width // 2 if centre_x is None else int(centre_x)
    half = max(centre - x0, x1 - centre) + int(band_w * PAD_SIDE)
    x0, x1 = centre - half, centre + half
    y0 -= int(band_h * PAD_VERTICAL)
    y1 += int(band_h * PAD_VERTICAL)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width, x1), min(height, y1)
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def _stats_row(lines: Sequence[OcrLine], stats_index: int) -> list[OcrLine]:
    """The lines on the stats line's row, itself included: those whose
    vertical middle lies within its box (the recognition can split a row)."""
    stats = lines[stats_index]
    return [line for line in lines if stats.y <= line.y + line.h / 2 <= stats.bottom]


def completeness(lines: Sequence[OcrLine], stats_index: int, target: BannerTarget) -> tuple[bool, int, int]:
    """How much of the banner a verified grab holds: whether its stats row
    reads the vitality bonus's digits (beside the score's own), how far right
    the row reaches (the banner is drawn in and out from the left), and the
    row's height, the slack more_complete allows."""
    row = _stats_row(lines, stats_index)
    tokens = [token for line in row for token in _number_tokens(line.text)]
    score = str(target.score)
    if score in tokens:
        tokens.remove(score)
    bonus = target.bonus_text
    return (bonus is not None and bonus in tokens,
            max(line.right for line in row),
            lines[stats_index].h)


def more_complete(new: tuple[bool, int, int], old: tuple[bool, int, int]) -> bool:
    """Whether a later grab's completeness *new* is to be kept over *old*:
    the one that reads the bonus wins, then the later one unless its row
    ends clearly further left (by more than a row's height). A tie goes to
    the later grab, past more of a banner drawing in."""
    if new[0] != old[0]:
        return new[0]
    return new[1] >= old[1] - max(new[2], old[2])


def region_rect(width: int, height: int) -> tuple[int, int, int, int]:
    """The part of a screen of *width* x *height* that is read."""
    w = int(width * REGION_WIDTH_FRACTION)
    h = int(height * REGION_HEIGHT_FRACTION)
    return (width - w) // 2, 0, w, h


# ---- banner.log: what each burst saw ----

@dataclass
class GrabRecord:
    """One read grab, for banner.log: when (seconds after END_TRIAL's own
    time), from which monitor, the frame's format and size ('bgra8
    3840x2160'), the lines read, and what verified it ('score', 'time' or
    None)."""
    at_s: float
    source: str
    frame: str
    lines: list[OcrLine]
    match: str | None = None


def _clock(epoch: float, with_date: bool = False) -> str:
    """Local time to the tenth of a second."""
    when = _dt.datetime.fromtimestamp(epoch)  # noqa: DTZ006  local, like the file names
    text = when.strftime("%Y-%m-%d %H:%M:%S" if with_date else "%H:%M:%S")
    return f"{text}.{when.microsecond // 100000}"


def burst_log_text(target: BannerTarget, acted_epoch: float, seconds: float, outcome: str,
                   grabs: Sequence[GrabRecord], kept: int | None = None) -> str:
    """One burst's block for banner.log: a '=== ' header naming the run,
    when END_TRIAL was written and when the app acted on it, the outcome
    line the status bar showed, then a line per grab with the recognised
    lines that hold a digit under it, the rest only counted. *kept* is the
    index in *grabs* of the grab saved."""
    vet = " vet" if target.is_vet else ""
    late = acted_epoch - target.ended_epoch
    out = [(f"=== {_clock(target.ended_epoch, with_date=True)} {target.name}{vet}:"
            f" score {target.score}, time {target.time_text}"),
           (f"END_TRIAL written at {_clock(target.ended_epoch)}, acted on at {_clock(acted_epoch)}"
            f" ({late:+.1f} s); grabs for {seconds:.0f} s, to {late + seconds:+.1f} s"),
           outcome]
    for i, grab in enumerate(grabs):
        digits = [line.text for line in grab.lines if any(ch.isdigit() for ch in line.text)]
        verdict = f"matched the {grab.match}" if grab.match else "no match"
        if i == kept:
            verdict += ", kept"
        out.append(f"{grab.at_s:+.1f} s {grab.source} {grab.frame}: {len(grab.lines)} lines,"
                   f" {len(digits)} with digits; {verdict}")
        out.extend(f"    {text}" for text in digits)
    return "\n".join(out) + "\n"


def append_burst_log(path: Path, block: str, keep: int = BANNER_LOG_BURSTS) -> bool:
    """Add one burst's *block* to the log at *path*, keeping the newest
    *keep* bursts. False when the file cannot be written: the log never
    stops a capture."""
    path = Path(path)
    try:
        old = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        old = ""
    blocks = [b for b in re.split(r"(?m)^(?==== )", old) if b.strip()]
    blocks.append(block)
    text = "".join(b if b.endswith("\n") else b + "\n" for b in blocks[-keep:])
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


# ---- Windows text recognition through Windows PowerShell ----

_POWERSHELL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                           "System32", "WindowsPowerShell", "v1.0", "powershell.exe")

# Reads image paths from its standard input, one a line, and answers each
# with FILE, LINE... and END records (ERROR in place of the lines when a file
# could not be read); NOENGINE and exit code 2 when Windows has no
# recognition language installed.
OCR_SCRIPT = r"""
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {
    foreach ($lang in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        if ($engine -ne $null) { break }
    }
}
if ($engine -eq $null) { [Console]::Out.WriteLine("NOENGINE"); exit 2 }
[Console]::Out.WriteLine("READY`t" + $engine.RecognizerLanguage.LanguageTag)
while ($null -ne ($path = [Console]::In.ReadLine())) {
    if ($path -eq "") { continue }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    [Console]::Out.WriteLine("FILE`t" + $path)
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        foreach ($line in $result.Lines) {
            $rects = @($line.Words | ForEach-Object { $_.BoundingRect })
            if ($rects.Count -eq 0) { continue }
            $x = ($rects | Measure-Object -Property X -Minimum).Minimum
            $y = ($rects | Measure-Object -Property Y -Minimum).Minimum
            $x2 = ($rects | ForEach-Object { $_.X + $_.Width } | Measure-Object -Maximum).Maximum
            $y2 = ($rects | ForEach-Object { $_.Y + $_.Height } | Measure-Object -Maximum).Maximum
            $text = $line.Text -replace "[`t`r`n]", " "
            [Console]::Out.WriteLine("LINE`t" + $text + "`t" + [int]$x + "`t" + [int]$y + "`t" + [int]($x2 - $x) + "`t" + [int]($y2 - $y))
        }
        $bitmap.Dispose()
        $stream.Dispose()
    } catch {
        $message = $_.Exception.Message -replace "[`t`r`n]", " "
        [Console]::Out.WriteLine("ERROR`t" + $message)
    }
    [Console]::Out.WriteLine("END`t" + $sw.ElapsedMilliseconds)
    [Console]::Out.Flush()
}
"""


def ocr_available() -> bool:
    """Whether this machine can run the recognition: Windows, with Windows
    PowerShell where every Windows 10 and 11 keeps it."""
    return sys.platform == "win32" and os.path.isfile(_POWERSHELL)


def long_path(path: str) -> str:
    """*path* with any 8.3 short name (NEBULA~1) expanded: the WinRT
    StorageFile refuses short names."""
    if sys.platform != "win32":
        return path
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetLongPathNameW(str(path), buffer, len(buffer))
    return buffer.value if 0 < n < len(buffer) else str(path)


def parse_ocr_output(records: Sequence[str]) -> tuple[list[OcrLine], str | None, int | None]:
    """The lines, the error and the milliseconds from the records of one
    FILE...END block."""
    lines: list[OcrLine] = []
    error = None
    elapsed = None
    for record in records:
        parts = record.rstrip("\r\n").split("\t")
        if parts[0] == "LINE" and len(parts) >= 6:
            try:
                lines.append(OcrLine(parts[1], int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])))
            except ValueError:
                continue
        elif parts[0] == "ERROR":
            error = parts[1] if len(parts) > 1 else "unknown error"
        elif parts[0] == "END":
            try:
                elapsed = int(parts[1])
            except (IndexError, ValueError):
                elapsed = None
    return lines, error, elapsed


class OcrError(RuntimeError):
    """The recognition process could not start or has no language."""


class OcrSession:
    """One Windows PowerShell process reading image files on request. Make
    one per burst, read(path) as often as wanted, close() at the end. Use
    from one thread."""

    def __init__(self, powershell: str | None = None):
        self.language: str | None = None
        self.last_elapsed_ms: int | None = None
        exe = powershell or _POWERSHELL
        if sys.platform != "win32" or not os.path.isfile(exe):
            raise OcrError("Windows PowerShell is not available")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # PowerShell's errors go to a file, not a pipe that could fill and
        # stall it, and not nowhere: a process that ends without answering
        # (a Constrained Language Mode or AppLocker policy refusing the
        # WinRT types, a policy refusing the Bypass) is reported with them
        self._stderr_path: str | None = None
        self._proc = None
        try:
            fd, self._stderr_path = tempfile.mkstemp(prefix="esolog-ocr-", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as stderr_file:
                self._proc = subprocess.Popen(
                    [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr_file,
                    text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
        except OSError as exc:
            self.close()
            raise OcrError(f"Windows PowerShell could not start: {exc}") from exc
        assert self._proc.stdin is not None and self._proc.stdout is not None
        # With -Command -, PowerShell runs each statement of its standard
        # input as it arrives. The script's last statement is the read
        # loop, which then takes the paths from the same stream
        self._proc.stdin.write(OCR_SCRIPT + "\n")
        self._proc.stdin.flush()
        ready = self._read_line()
        if ready is None:
            code = self._proc.poll()
            errors = self._stderr_tail()
            self.close()
            raise OcrError(f"Windows PowerShell ended without answering (exit {code})"
                           + (f": {errors}" if errors else ""))
        if ready.startswith("NOENGINE"):
            self.close()
            raise OcrError("Windows has no text recognition language installed")
        if not ready.startswith("READY"):
            self.close()
            raise OcrError(f"unexpected reply from the recognition: {ready[:80]}")
        self.language = ready.split("\t")[1] if "\t" in ready else None

    def _stderr_tail(self, limit: int = 300) -> str:
        """The last part of what the process wrote to its standard error."""
        if not self._stderr_path:
            return ""
        try:
            with open(self._stderr_path, encoding="utf-8", errors="replace") as f:
                text = " ".join(f.read().split())
        except OSError:
            return ""
        return text[-limit:]

    def kill(self) -> None:
        """End the process now (a read that hangs): the pending read then
        returns, and read() raises OcrError."""
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()

    def _read_line(self) -> str | None:
        line = self._proc.stdout.readline()
        return line.rstrip("\r\n") if line else None

    def read(self, path: str) -> list[OcrLine]:
        """The text lines on the image at *path* (any path form; made long
        here). Raises OcrError when the process is gone."""
        if self._proc is None or self._proc.poll() is not None:
            raise OcrError("the recognition process has ended")
        try:
            self._proc.stdin.write(long_path(os.path.abspath(path)) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError) as exc:
            raise OcrError(f"the recognition process is gone: {exc}") from exc
        records: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                raise OcrError("the recognition process ended mid-read")
            records.append(line)
            if line.startswith("END"):
                break
        lines, error, elapsed = parse_ocr_output(records)
        self.last_elapsed_ms = elapsed
        if error and not lines:
            raise OcrError(error)
        return lines

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self._proc = None
        stderr_path = getattr(self, "_stderr_path", None)
        if stderr_path:
            self._stderr_path = None
            try:
                os.remove(stderr_path)
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ---- the display's HDR state and SDR white level ----

def display_sdr_white(device_name: str | None = None) -> tuple[bool, float]:
    """(advanced colour on, SDR white level in nits) for the display whose
    GDI name is *device_name* (\\\\.\\DISPLAY1, as DXGI and DisplayConfig both
    call it), or for the first active display; (False, 80.0) when the API
    is unavailable or the display is not found."""
    if sys.platform != "win32":
        return False, SDR_REFERENCE_NITS
    try:
        return _query_display_config(device_name)
    except (OSError, AttributeError, ValueError):
        return False, SDR_REFERENCE_NITS


def _query_display_config(device_name: str | None) -> tuple[bool, float]:
    import ctypes
    from ctypes import wintypes

    QDC_ONLY_ACTIVE_PATHS = 2
    GET_SOURCE_NAME = 1
    GET_ADVANCED_COLOR_INFO = 9
    GET_SDR_WHITE_LEVEL = 11

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class SourceInfo(ctypes.Structure):
        _fields_ = [("adapterId", LUID), ("id", wintypes.UINT), ("modeInfoIdx", wintypes.UINT),
                    ("statusFlags", wintypes.UINT)]

    class Rational(ctypes.Structure):
        _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]

    class TargetInfo(ctypes.Structure):
        _fields_ = [("adapterId", LUID), ("id", wintypes.UINT), ("modeInfoIdx", wintypes.UINT),
                    ("outputTechnology", wintypes.UINT), ("rotation", wintypes.UINT),
                    ("scaling", wintypes.UINT), ("refreshRate", Rational),
                    ("scanLineOrdering", wintypes.UINT), ("targetAvailable", wintypes.BOOL),
                    ("statusFlags", wintypes.UINT)]

    class PathInfo(ctypes.Structure):
        _fields_ = [("sourceInfo", SourceInfo), ("targetInfo", TargetInfo), ("flags", wintypes.UINT)]

    class ModeInfo(ctypes.Structure):
        _fields_ = [("infoType", wintypes.UINT), ("id", wintypes.UINT), ("adapterId", LUID),
                    ("data", ctypes.c_byte * 48)]

    class Header(ctypes.Structure):
        _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT), ("adapterId", LUID),
                    ("id", wintypes.UINT)]

    class SourceName(ctypes.Structure):
        _fields_ = [("header", Header), ("viewGdiDeviceName", wintypes.WCHAR * 32)]

    class AdvancedColorInfo(ctypes.Structure):
        _fields_ = [("header", Header), ("value", wintypes.UINT), ("colorEncoding", wintypes.UINT),
                    ("bitsPerColorChannel", wintypes.UINT)]

    class SdrWhiteLevel(ctypes.Structure):
        _fields_ = [("header", Header), ("SDRWhiteLevel", wintypes.ULONG)]

    user32 = ctypes.windll.user32
    n_paths, n_modes = wintypes.UINT(), wintypes.UINT()
    if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), ctypes.byref(n_modes)):
        return False, SDR_REFERENCE_NITS
    paths = (PathInfo * max(1, n_paths.value))()
    modes = (ModeInfo * max(1, n_modes.value))()
    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), paths,
                                 ctypes.byref(n_modes), modes, None):
        return False, SDR_REFERENCE_NITS

    def info(struct_type, kind, adapter, ident):
        s = struct_type()
        s.header.type = kind
        s.header.size = ctypes.sizeof(struct_type)
        s.header.adapterId = adapter
        s.header.id = ident
        return s if user32.DisplayConfigGetDeviceInfo(ctypes.byref(s)) == 0 else None

    for i in range(n_paths.value):
        src, tgt = paths[i].sourceInfo, paths[i].targetInfo
        if device_name:
            name = info(SourceName, GET_SOURCE_NAME, src.adapterId, src.id)
            if name is None or name.viewGdiDeviceName != device_name:
                continue
        colour = info(AdvancedColorInfo, GET_ADVANCED_COLOR_INFO, tgt.adapterId, tgt.id)
        white = info(SdrWhiteLevel, GET_SDR_WHITE_LEVEL, tgt.adapterId, tgt.id)
        enabled = bool(colour.value & 2) if colour is not None else False
        nits = white.SDRWhiteLevel / 1000.0 * SDR_REFERENCE_NITS if white is not None else SDR_REFERENCE_NITS
        return enabled, nits
    return False, SDR_REFERENCE_NITS
