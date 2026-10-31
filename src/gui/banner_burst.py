"""
The burst that captures the trial completion banner (issue #167): the GUI
side of banner_capture.

Design: The capture burst. A BannerBurst lives on the UI thread, owned by the
main window, one at a time. On start it opens a Desktop Duplication reader for
every monitor (desktop_duplication; Qt's screen grab when duplication is
refused), starts the recognition thread and a one-second timer. Each tick
grabs every monitor, cuts the top-centre region (banner_capture.region_rect),
writes it as a PNG in a temporary folder and hands the path to the thread,
which reads it with the Windows recognition (one PowerShell process for the
whole burst) and verifies it against the run's score. The first verified grab
stops the burst: the band the recognition boxed is cut out of that PNG, padded,
and saved under the run's name in the banner folder. When the fifteen seconds
pass with nothing verified, the burst waits for the grabs still in the thread's
queue, then reports that nothing was kept. The thread holds paths and text
only, never a Qt object, so nothing of Qt's is touched off the UI thread
(the rule of issue #18); the burst deletes itself after it reports.
"""
from __future__ import annotations

import queue
import shutil
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage

import banner_capture as bc

__all__ = ["BannerBurst", "frame_to_image"]


def frame_to_image(frame, sdr_white_nits: float = bc.SDR_REFERENCE_NITS) -> QImage:
    """A desktop_duplication.Frame as an 8-bit sRGB QImage. An FP16 frame
    (an HDR desktop, linear scRGB with 1.0 at 80 nits) is divided by the
    display's SDR white level over 80 nits, so what Windows shows as SDR
    white is white, then converted from linear to sRGB by Qt (see the
    design note in banner_capture). Here, on the GUI side, because the
    engine's modules never import Qt."""
    from PySide6.QtGui import QColor, QColorSpace, QPainter

    import desktop_duplication as dd
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


class _Recognizer(QThread):
    """Reads the grabs in the order they come and reports the first that
    shows the run's score."""

    verified = Signal(str, object, int, str)  # path, lines, stats line index, how
    rejected = Signal(str)                    # path: nothing of the run on it
    failed = Signal(str)                      # the recognition is unavailable or died

    def __init__(self, target: bc.BannerTarget, parent=None):
        super().__init__(parent)
        self._target = target
        self._queue: queue.Queue[str | None] = queue.Queue()

    def submit(self, path: str) -> None:
        self._queue.put(path)

    def stop(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        try:
            session = bc.OcrSession()
        except bc.OcrError as exc:
            self.failed.emit(str(exc))
            return
        with session:
            while True:
                path = self._queue.get()
                if path is None:
                    return
                try:
                    lines = session.read(path)
                except bc.OcrError as exc:
                    self.failed.emit(str(exc))
                    return
                found = bc.verify(lines, self._target)
                if found is not None:
                    self.verified.emit(path, lines, found[0], found[1])
                    return
                self.rejected.emit(path)


class _Source:
    """One monitor to grab: a duplicator, or a Qt screen when duplication
    is refused."""

    def __init__(self, duplicator=None, screen=None, sdr_white_nits: float = bc.SDR_REFERENCE_NITS,
                 name: str = ""):
        self._dup = duplicator
        self._screen = screen
        self._sdr_white = sdr_white_nits
        self.name = name

    def grab(self) -> QImage | None:
        if self._dup is not None:
            import desktop_duplication as dd
            try:
                frame = self._dup.grab(deadline_s=0.5)
            except dd.DuplicationError:
                return None
            if frame is None:
                return None
            return frame_to_image(frame, self._sdr_white)
        if self._screen is not None:
            pixmap = self._screen.grabWindow(0)
            return pixmap.toImage() if not pixmap.isNull() else None
        return None

    def close(self) -> None:
        if self._dup is not None:
            self._dup.close()
            self._dup = None
        self._screen = None


def _open_sources(notes: list[str]) -> list[_Source]:
    """A source per monitor: duplication where it works, Qt's grab for the
    rest (or for every screen when the duplication API is missing)."""
    sources: list[_Source] = []
    try:
        import desktop_duplication as dd
        outputs = dd.list_outputs()
    except (OSError, AttributeError, RuntimeError) as exc:  # the DXGI entry points missing, or the call failing
        notes.append(f"desktop duplication unavailable ({exc})")
        outputs = []
    for info in outputs:
        try:
            dup = dd.DesktopDuplicator(info)
        except dd.DuplicationError as exc:
            notes.append(f"{info.device_name}: {exc}")
            continue
        _hdr, nits = bc.display_sdr_white(info.device_name)
        sources.append(_Source(duplicator=dup, sdr_white_nits=nits, name=info.device_name))
    if not sources:
        for screen in QGuiApplication.screens():
            sources.append(_Source(screen=screen, name=screen.name()))
        if sources:
            notes.append("grabbing through Qt")
    return sources


class BannerBurst(QObject):
    """See the module. finished carries the saved file (a Path) or None, and
    a line for the status bar."""

    finished = Signal(object, str)

    def __init__(self, target: bc.BannerTarget, folder: Path, parent=None):
        super().__init__(parent)
        self.target = target
        self.folder = Path(folder)
        self.notes: list[str] = []
        self.grabs = 0
        self._sources: list[_Source] = []
        self._temp: Path | None = None
        self._worker: _Recognizer | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(bc.BURST_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._deadline = 0.0
        self._pending = 0
        self._closing = False
        self._done = False

    def start(self) -> None:
        self._temp = Path(tempfile.mkdtemp(prefix="esolog-banner-"))
        self._sources = _open_sources(self.notes)
        if not self._sources:
            self._finish(None, "Score banner: no screen to grab")
            return
        self._worker = _Recognizer(self.target, self)
        self._worker.verified.connect(self._on_verified)
        self._worker.rejected.connect(self._on_rejected)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._deadline = time.monotonic() + bc.BURST_SECONDS
        self._timer.start()
        self._tick()

    def cancel(self) -> None:
        """Stop now (the window is closing); no report."""
        self._done = True
        self._timer.stop()
        self._stop_worker(wait=True)
        self._cleanup()

    @Slot()
    def _tick(self) -> None:
        if self._done or self._closing:
            return
        n = self.grabs
        self.grabs += 1
        for i, source in enumerate(self._sources):
            image = source.grab()
            if image is None:
                continue
            region = image.copy(*bc.region_rect(image.width(), image.height()))
            path = self._temp / f"grab-{n:02d}-{i}.png"
            if region.save(str(path), "PNG") and self._worker is not None:
                self._pending += 1
                self._worker.submit(str(path))
        if time.monotonic() >= self._deadline:
            self._timer.stop()
            self._closing = True
            if self._pending == 0:
                self._finish(None, "Score banner: nothing was captured")
            # else the last rejections, or a verification, end it

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
        self._pending -= 1
        if self._closing and self._pending <= 0 and not self._done:
            self._finish(None, "Score banner: the score was not seen on screen; nothing kept")

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._finish(None, f"Score banner: {message}")

    def _finish(self, path: Path | None, message: str) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._stop_worker(wait=False)
        for source in self._sources:
            source.close()
        self._sources = []
        self.finished.emit(path, message)

    def _stop_worker(self, wait: bool) -> None:
        worker = self._worker
        if worker is None:
            return
        worker.stop()
        if wait:
            worker.wait(10000)
            self._worker = None
            return
        # Let the thread end, then drop the temporary grabs and this object
        worker.finished.connect(self._on_worker_finished)
        if worker.isFinished():
            self._on_worker_finished()

    @Slot()
    def _on_worker_finished(self) -> None:
        self._worker = None
        self._cleanup()
        self.deleteLater()

    def _cleanup(self) -> None:
        if self._temp is not None:
            shutil.rmtree(self._temp, ignore_errors=True)
            self._temp = None
