"""
The burst that captures the trial completion banner (issue #167): the GUI
side of banner_capture.

Design: The capture burst. A BannerBurst lives on the UI thread, owned by the
main window, one at a time, started the moment the engine reports END_TRIAL
(on_trial_result), before the fight that carries the result is finalized:
END_COMBAT trails a successful END_TRIAL by up to six seconds on the real logs,
and the banner is on screen for ten. All the work runs on the burst's thread:
it opens a Desktop Duplication reader per monitor (desktop_duplication; a lost
desktop, a mode or HDR switch, is reopened once), and once a second for
fifteen seconds grabs every monitor, converts the frame (frame_to_image), cuts
the top-centre region (banner_capture.region_rect), writes it as a PNG in a
temporary folder, reads it with the Windows recognition (one PowerShell
process for the whole burst) and verifies it against the run's score. The UI
thread only takes part when no monitor can be duplicated (a remote session),
grabbing through Qt's QScreen, which must be used from the UI thread, and
handing the images to the thread. The first verified grab ends the burst: the
band the recognition boxed is cut out of that PNG, padded, and saved under the
run's name in the banner folder. Fifteen seconds with nothing verified end it
with nothing kept, and the reasons the thread noted (no duplication, a lost
monitor) go into the status-bar line. The thread holds frames, images, paths
and text, never a widget, so nothing of Qt's widgets is touched off the UI
thread (the rule of issue #18); the burst deletes itself after it reports.
"""
from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import time
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
        return frame_to_image(frame, self.sdr_white)

    def close(self) -> None:
        if self._dup is not None:
            self._dup.close()
            self._dup = None


class _Worker(QThread):
    """The burst's thread: see the module."""

    verified = Signal(str, object, int, str)  # path, lines, stats line index, how
    rejected = Signal(str)                    # path: nothing of the run on it
    failed = Signal(str)                      # the recognition is unavailable or died
    exhausted = Signal()                      # the fifteen seconds passed, nothing verified
    fallback_needed = Signal()                # no monitor duplicates: grab through Qt on the UI thread

    def __init__(self, target: bc.BannerTarget, temp: Path, parent=None):
        super().__init__(parent)
        self._target = target
        self._temp = temp
        self.notes: list[str] = []
        self.grabs = 0
        self._images: queue.Queue[QImage] = queue.Queue()
        self._stop = threading.Event()
        self._session: bc.OcrSession | None = None

    def submit_image(self, image: QImage) -> None:
        """A screen image grabbed on the UI thread (the Qt fallback)."""
        self._images.put(image)

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
        deadline = time.monotonic() + bc.BURST_SECONDS
        try:
            n = 0
            while not self._stop.is_set():
                started = time.monotonic()
                images = [image for image in (source.grab() for source in sources) if image is not None]
                sources = [source for source in sources if not source.dead]
                if not sources and not fallback_asked:
                    self.notes.append("grabbing through Qt")
                    self.fallback_needed.emit()
                    fallback_asked = True
                while True:
                    try:
                        images.append(self._images.get_nowait())
                    except queue.Empty:
                        break
                for i, image in enumerate(images):
                    if self._stop.is_set() or self._read(n, i, image):
                        return
                n += 1
                self.grabs = n
                if time.monotonic() >= deadline:
                    break
                remaining = started + bc.BURST_INTERVAL_MS / 1000 - time.monotonic()
                if remaining > 0 and self._stop.wait(remaining):
                    return
            if not self._stop.is_set():
                self.exhausted.emit()
        finally:
            for source in sources:
                source.close()
            if self._session is not None:
                self._session.close()
                self._session = None

    def _read(self, n: int, i: int, image: QImage) -> bool:
        """The region of one grab written, read and verified; True when the
        burst is over (verified, or the recognition died)."""
        region = image.copy(*bc.region_rect(image.width(), image.height()))
        path = self._temp / f"grab-{n:02d}-{i}.png"
        if not region.save(str(path), "PNG"):
            return False
        try:
            lines = self._session.read(str(path))
        except bc.OcrError as exc:
            if not self._stop.is_set():
                self.failed.emit(str(exc))
            self._stop.set()
            return True
        found = bc.verify(lines, self._target)
        if found is not None:
            self.verified.emit(str(path), lines, found[0], found[1])
            return True
        self.rejected.emit(str(path))
        return False


class BannerBurst(QObject):
    """See the module. finished carries the saved file (a Path) or None, and
    a line for the status bar. *entry* is the fight the banner belongs to,
    set by the window when the fight is delivered (it comes after the
    result)."""

    finished = Signal(object, str)

    def __init__(self, target: bc.BannerTarget, folder: Path, parent=None):
        super().__init__(parent)
        self.target = target
        self.folder = Path(folder)
        self.entry = None
        self.rejected = 0
        self._temp: Path | None = None
        self._worker: _Worker | None = None
        self._deadline = 0.0
        self._done = False
        self._timer = QTimer(self)  # the Qt fallback's grabs, on the UI thread
        self._timer.setInterval(bc.BURST_INTERVAL_MS)
        self._timer.timeout.connect(self._qt_tick)

    @property
    def notes(self) -> list[str]:
        return list(self._worker.notes) if self._worker is not None else []

    def start(self) -> None:
        self._temp = Path(tempfile.mkdtemp(prefix="esolog-banner-"))
        self._deadline = time.monotonic() + bc.BURST_SECONDS
        worker = _Worker(self.target, self._temp, self)
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
        if self._done or self._worker is None or time.monotonic() >= self._deadline:
            self._timer.stop()
            return
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                self._worker.submit_image(pixmap.toImage())

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
        self.finished.emit(path, message)
        self._end_worker()

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
