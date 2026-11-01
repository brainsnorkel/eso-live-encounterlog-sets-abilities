"""
The burst that captures the trial completion banner (issue #167): the GUI
side of banner_capture.

Design: The capture burst. A BannerBurst lives on the UI thread, owned by the
main window, one at a time, started the moment the engine reports END_TRIAL
(on_trial_result), before the fight that carries the result is finalized:
END_COMBAT trails a successful END_TRIAL by up to six seconds on the real logs,
and the banner is on screen for ten. All the work runs on the burst's thread:
it opens a Desktop Duplication reader per monitor (desktop_duplication; a lost
desktop, a mode or HDR switch, is reopened once), and once a second until
END_TRIAL's own time plus 45 s (banner_capture.burst_seconds) grabs every
monitor, converts the frame (frame_to_image), cuts the top-centre region
(banner_capture.region_rect), writes it as a PNG in a temporary folder, reads
it with the Windows recognition (one PowerShell process for the whole burst)
and verifies it against the run's score. The UI thread only takes part when no
monitor can be duplicated (a remote session), grabbing through Qt's QScreen,
which must be used from the UI thread, and handing the images to the thread.
The first verified grab is followed by banner_capture.FOLLOW_UP_GRABS more of
the same monitor, a second apart, for a banner still drawing in; the most
complete verified one (banner_capture.more_complete) is then cut out of its
PNG, symmetric about the screen's centre line, and saved under the run's name
in the banner folder. A burst that runs out with nothing verified ends with
nothing kept, and the reasons the thread noted (no duplication, a lost
monitor) go into the status-bar line. Every outcome, a cancelled burst's too,
is written to banner.log with a line per grab (banner_capture.burst_log_text).
The thread holds frames, images, paths and text, never a widget, so nothing of
Qt's widgets is touched off the UI thread (the rule of issue #18); the burst
deletes itself after it reports.
"""
from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QColorSpace, QGuiApplication, QImage, QPainter

import banner_capture as bc
import desktop_duplication as dd

__all__ = ["BannerBurst", "frame_to_image"]

# How long one monitor's grab waits for a presented frame: the game presents
# sixty times a second; a static second monitor times out
GRAB_DEADLINE_S = 0.1


def frame_to_image(frame, sdr_white_nits: float = bc.SDR_REFERENCE_NITS) -> QImage:
    """A desktop_duplication.Frame as an 8-bit sRGB QImage. An FP16 frame
    (an HDR desktop, linear scRGB with 1.0 at 80 nits) is divided by the
    display's SDR white level over 80 nits, so what Windows shows as SDR
    white is white, then converted from linear to sRGB by Qt (see the
    design note in banner_capture). Here, on the GUI side, because the
    engine's modules never import Qt."""
    fmt = frame.format
    if fmt == dd.FORMAT_B8G8R8A8_UNORM:
        image = QImage(frame.data, frame.width, frame.height, frame.stride, QImage.Format.Format_ARGB32).copy()
        return image.convertToFormat(QImage.Format.Format_RGB32)
    if fmt == dd.FORMAT_R8G8B8A8_UNORM:
        image = QImage(frame.data, frame.width, frame.height, frame.stride, QImage.Format.Format_RGBA8888).copy()
        return image.convertToFormat(QImage.Format.Format_RGB32)
    if fmt == dd.FORMAT_R10G10B10A2_UNORM:
        image = QImage(frame.data, frame.width, frame.height, frame.stride,
                       QImage.Format.Format_A2BGR30_Premultiplied).copy()
        return image.convertToFormat(QImage.Format.Format_RGB32)
    if fmt == dd.FORMAT_R16G16B16A16_FLOAT:
        image = QImage(frame.data, frame.width, frame.height, frame.stride, QImage.Format.Format_RGBA16FPx4).copy()
        scale = bc.SDR_REFERENCE_NITS / float(sdr_white_nits or bc.SDR_REFERENCE_NITS)
        if 0 < scale < 1:
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            painter.fillRect(image.rect(), QColor.fromRgbF(scale, scale, scale, 1.0))
            painter.end()
        image.setColorSpace(QColorSpace(QColorSpace.Primaries.SRgb, QColorSpace.TransferFunction.Linear))
        srgb = image.convertedToColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        return srgb.convertToFormat(QImage.Format.Format_RGB32)
    raise ValueError(f"unhandled desktop format {fmt}")


class _Source:
    """One monitor read through Desktop Duplication on the burst's thread.
    A lost desktop (DXGI_ERROR_ACCESS_LOST: a mode or HDR switch, another
    app taking the output) is reopened once; a monitor that cannot be
    opened again is dead and noted."""

    def __init__(self, info: dd.OutputInfo, notes: list[str]):
        self.info = info
        self.name = info.device_name
        self._notes = notes
        self._dup: dd.DesktopDuplicator | None = None
        self.sdr_white = bc.SDR_REFERENCE_NITS
        self.dead = False
        self.last_format = ""  # the last frame's, for banner.log
        self._open()

    def _open(self) -> None:
        try:
            self._dup = dd.DesktopDuplicator(self.info)
        except dd.DuplicationError as exc:
            self._notes.append(f"{self.name}: {exc}")
            self._dup = None
            self.dead = True
            return
        # Read with the desktop: an HDR switch changes the white level too
        _hdr, self.sdr_white = bc.display_sdr_white(self.name)

    def grab(self) -> QImage | None:
        if self.dead or self._dup is None:
            return None
        try:
            frame = self._dup.grab(deadline_s=GRAB_DEADLINE_S)
        except dd.DuplicationError:
            self.close()
            self._open()
            if self.dead:
                return None
            try:
                frame = self._dup.grab(deadline_s=GRAB_DEADLINE_S)
            except dd.DuplicationError as exc:
                self._notes.append(f"{self.name}: {exc}")
                self.close()
                self.dead = True
                return None
        if frame is None:
            return None
        self.last_format = frame.format_name
        return frame_to_image(frame, self.sdr_white)

    def close(self) -> None:
        if self._dup is not None:
            self._dup.close()
            self._dup = None


@dataclass
class _Candidate:
    """A verified grab: how complete (banner_capture.completeness), its
    region's PNG, the lines read, the stats line and how it verified, the
    monitor it came from and its record in _Worker.records."""
    rank: tuple[bool, int, int]
    path: str
    lines: list
    index: int
    how: str
    source: str
    record: int


class _Worker(QThread):
    """The burst's thread: see the module."""

    verified = Signal(str, object, int, str)  # the grab kept: path, lines, stats line index, how
    rejected = Signal(str)                    # path: nothing of the run on it
    failed = Signal(str)                      # the recognition is unavailable or died
    exhausted = Signal()                      # the time ran out, nothing verified
    fallback_needed = Signal()                # no monitor duplicates: grab through Qt on the UI thread

    def __init__(self, target: bc.BannerTarget, temp: Path, seconds: float, parent=None):
        super().__init__(parent)
        self._target = target
        self._temp = temp
        self._seconds = seconds
        self.notes: list[str] = []
        self.records: list[bc.GrabRecord] = []  # every grab read, for banner.log
        self.kept: int | None = None            # the record of the grab kept
        self.grabs = 0
        self._images: queue.Queue[tuple[str, QImage]] = queue.Queue()
        self._stop = threading.Event()
        self._session: bc.OcrSession | None = None

    def submit_image(self, source: str, image: QImage) -> None:
        """A screen image grabbed on the UI thread (the Qt fallback)."""
        self._images.put((source, image))

    def stop(self) -> None:
        self._stop.set()

    def kill(self) -> None:
        """For a recognition read that hangs: end its process, so run()
        returns; then wait() the thread again."""
        self._stop.set()
        session = self._session
        if session is not None:
            session.kill()

    def run(self) -> None:
        try:
            self._session = bc.OcrSession()
        except bc.OcrError as exc:
            self.failed.emit(str(exc))
            return
        sources: list[_Source] = []
        try:
            outputs = dd.list_outputs()
        except (OSError, AttributeError, RuntimeError) as exc:  # the DXGI entry points missing, or failing
            self.notes.append(f"desktop duplication unavailable ({exc})")
            outputs = []
        for info in outputs:
            source = _Source(info, self.notes)
            if not source.dead:
                sources.append(source)
        fallback_asked = False
        if not sources:
            self.notes.append("grabbing through Qt")
            self.fallback_needed.emit()
            fallback_asked = True
        deadline = time.monotonic() + self._seconds
        best: _Candidate | None = None
        follow_ups = 0
        try:
            n = 0
            while not self._stop.is_set():
                started = time.monotonic()
                at_s = time.time() - self._target.ended_epoch
                images = []
                for source in sources:
                    image = source.grab()
                    if image is not None:
                        images.append((source.name, f"{source.last_format} {image.width()}x{image.height()}", image))
                sources = [source for source in sources if not source.dead]
                if not sources and not fallback_asked:
                    self.notes.append("grabbing through Qt")
                    self.fallback_needed.emit()
                    fallback_asked = True
                while True:
                    try:
                        name, image = self._images.get_nowait()
                    except queue.Empty:
                        break
                    images.append((name, f"qt {image.width()}x{image.height()}", image))
                if best is not None:
                    # The follow-ups: the monitor the banner is on
                    images = [item for item in images if item[0] == best.source]
                for i, (name, frame, image) in enumerate(images):
                    if self._stop.is_set():
                        return
                    over, found = self._read(n, i, at_s, name, frame, image)
                    if over:
                        return
                    if found is not None and (best is None or bc.more_complete(found.rank, best.rank)):
                        best = found
                n += 1
                self.grabs = n
                if best is not None:
                    if follow_ups >= bc.FOLLOW_UP_GRABS:
                        break
                    follow_ups += 1
                elif time.monotonic() >= deadline:
                    break
                remaining = started + bc.BURST_INTERVAL_MS / 1000 - time.monotonic()
                if remaining > 0 and self._stop.wait(remaining):
                    return
            if self._stop.is_set():
                return
            if best is not None:
                self.kept = best.record
                self.verified.emit(best.path, best.lines, best.index, best.how)
            else:
                self.exhausted.emit()
        finally:
            for source in sources:
                source.close()
            if self._session is not None:
                self._session.close()
                self._session = None

    def _read(self, n: int, i: int, at_s: float, source: str, frame: str,
              image: QImage) -> tuple[bool, _Candidate | None]:
        """The region of one grab written, read, verified and recorded:
        (whether the burst is over, the recognition having died; the grab
        when it verified)."""
        region = image.copy(*bc.region_rect(image.width(), image.height()))
        path = self._temp / f"grab-{n:02d}-{i}.png"
        if not region.save(str(path), "PNG"):
            return False, None
        try:
            lines = self._session.read(str(path))
        except bc.OcrError as exc:
            if not self._stop.is_set():
                self.failed.emit(str(exc))
            self._stop.set()
            return True, None
        found = bc.verify(lines, self._target)
        self.records.append(bc.GrabRecord(at_s, source, frame, lines, found[1] if found else None))
        if found is None:
            self.rejected.emit(str(path))
            return False, None
        return False, _Candidate(bc.completeness(lines, found[0], self._target), str(path), lines,
                                 found[0], found[1], source, len(self.records) - 1)


class BannerBurst(QObject):
    """See the module. finished carries the saved file (a Path) or None, and
    a line for the status bar. *entry* is the fight the banner belongs to,
    set by the window when the fight is delivered (it comes after the
    result). *log_path* is banner.log's, None for no log."""

    finished = Signal(object, str)

    def __init__(self, target: bc.BannerTarget, folder: Path, parent=None, log_path: Path | None = None):
        super().__init__(parent)
        self.target = target
        self.folder = Path(folder)
        self.entry = None
        self.rejected = 0
        self._log_path = Path(log_path) if log_path is not None else None
        self._logged = False
        self._temp: Path | None = None
        self._worker: _Worker | None = None
        self._acted = 0.0
        self._seconds = float(bc.BURST_MIN_SECONDS)
        self._done = False
        self._timer = QTimer(self)  # the Qt fallback's grabs, on the UI thread
        self._timer.setInterval(bc.BURST_INTERVAL_MS)
        self._timer.timeout.connect(self._qt_tick)

    @property
    def notes(self) -> list[str]:
        return list(self._worker.notes) if self._worker is not None else []

    def start(self) -> None:
        self._temp = Path(tempfile.mkdtemp(prefix="esolog-banner-"))
        self._acted = time.time()
        self._seconds = bc.burst_seconds(self.target.ended_epoch, self._acted)
        worker = _Worker(self.target, self._temp, self._seconds, self)
        worker.verified.connect(self._on_verified)
        worker.rejected.connect(self._on_rejected)
        worker.failed.connect(self._on_failed)
        worker.exhausted.connect(self._on_exhausted)
        worker.fallback_needed.connect(self._start_qt_fallback)
        self._worker = worker
        worker.start()

    def cancel(self) -> None:
        """Stop now (the window is closing); no report. A recognition read
        that hangs is ended by killing its process, so the thread is never
        destroyed running."""
        self._done = True
        self._timer.stop()
        worker = self._worker
        if worker is not None:
            worker.stop()
            if not worker.wait(3000):
                worker.kill()
                worker.wait(10000)
            self._write_log("Score banner: cancelled, the window closed")
            self._worker = None
        self._cleanup()

    @Slot()
    def _start_qt_fallback(self) -> None:
        if self._done:
            return
        self._timer.start()
        self._qt_tick()

    @Slot()
    def _qt_tick(self) -> None:
        # Until the thread reports: it keeps the burst's time and its
        # follow-up grabs
        if self._done or self._worker is None:
            self._timer.stop()
            return
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                self._worker.submit_image(f"Qt {screen.name()}", pixmap.toImage())

    @Slot(str, object, int, str)
    def _on_verified(self, path: str, lines, index: int, how: str) -> None:
        if self._done:
            return
        image = QImage(path)
        if image.isNull():
            self._finish(None, "Score banner: the verified grab could not be read back")
            return
        rect = bc.crop_rect(lines, index, image.width(), image.height())
        banner = image.copy(*rect)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._finish(None, f"Score banner: cannot make {self.folder} ({exc})")
            return
        out = self.folder / self.target.file_name
        if not banner.save(str(out), "PNG"):
            self._finish(None, f"Score banner: could not write {out.name}")
            return
        self._finish(out, f"Score banner saved: {out.name}")

    @Slot(str)
    def _on_rejected(self, path: str) -> None:
        self.rejected += 1

    @Slot()
    def _on_exhausted(self) -> None:
        self._finish(None, f"Score banner: the score was not seen on screen in {self.rejected} grabs; nothing kept")

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._finish(None, f"Score banner: {message}")

    def _finish(self, path: Path | None, message: str) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        notes = self.notes
        if path is None and notes:
            message = f"{message} ({'; '.join(notes)})"
        self._write_log(message, saved=path is not None)
        self.finished.emit(path, message)
        self._end_worker()

    def _write_log(self, outcome: str, saved: bool = False) -> None:
        """This burst's block in banner.log, once. The thread has stopped
        adding records: it reports, or is stopped, after its last read."""
        if self._log_path is None or self._logged:
            return
        self._logged = True
        worker = self._worker
        records = list(worker.records) if worker is not None else []
        kept = worker.kept if worker is not None and saved else None
        block = bc.burst_log_text(self.target, self._acted, self._seconds, outcome, records, kept)
        bc.append_burst_log(self._log_path, block)

    def _end_worker(self) -> None:
        """Let the thread end, then drop the temporary grabs and this
        object. The finished signal is connected before the running check,
        so a thread ending in between is not missed."""
        worker = self._worker
        if worker is None:
            self._on_worker_finished()
            return
        worker.stop()
        worker.finished.connect(self._on_worker_finished)
        if worker.isFinished():
            self._on_worker_finished()

    @Slot()
    def _on_worker_finished(self) -> None:
        if self._temp is None and self._worker is None:
            return  # already done
        self._worker = None
        self._cleanup()
        self.deleteLater()

    def _cleanup(self) -> None:
        if self._temp is not None:
            shutil.rmtree(self._temp, ignore_errors=True)
            self._temp = None
