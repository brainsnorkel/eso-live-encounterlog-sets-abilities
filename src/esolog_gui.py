#!/usr/bin/env python3
"""ESO Log Tail GUI entry point."""

import os
import sys

# Flat engine imports (esolog_tail, app_config, ...) resolve against src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _enable_crash_log():
    """Crash/exception capture for windowed builds.

    PyInstaller's console=False mode sets sys.stderr to None, and an
    unhandled Python exception then escalates through the default excepthook
    into a fatal CRT abort (observed as 0xc0000409 in ucrtbase.dll). Route
    everything to a crash.log instead: unhandled exceptions become logged
    non-fatal events, and genuine native faults dump their stacks too.
    """
    import datetime
    import faulthandler
    import threading
    import traceback
    try:
        from app_config import default_config_path
        crash_path = default_config_path().parent / "crash.log"
        crash_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(crash_path, "a", buffering=1, encoding="utf-8")
        handle.write(f"\n--- session {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        faulthandler.enable(file=handle, all_threads=True)

        def _log_exception(exc_type, exc, tb):
            try:
                handle.write(f"[{datetime.datetime.now():%H:%M:%S}] "
                             f"Unhandled exception:\n")
                traceback.print_exception(exc_type, exc, tb, file=handle)
            except Exception:
                pass  # logging must never raise

        sys.excepthook = _log_exception
        threading.excepthook = lambda args: _log_exception(
            args.exc_type, args.exc_value, args.exc_traceback)

        # Give writeless streams a destination so stray prints can't break
        if sys.stderr is None:
            sys.stderr = handle
        if sys.stdout is None:
            sys.stdout = handle
        return handle  # keep alive for the process lifetime
    except Exception:
        faulthandler.enable()
        return None


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app_config import AppConfig
    from gui.main_window import MainWindow

    crash_log = _enable_crash_log()  # noqa: F841 (must outlive the app)

    app = QApplication(sys.argv)
    app.setApplicationName("ESO Log Tail")
    app.setOrganizationName("esolog-tail")

    # Window icon: bundled next to the app when frozen, repo root in dev
    from pathlib import Path
    from PySide6.QtGui import QIcon
    base = Path(getattr(sys, "_MEIPASS",
                        Path(__file__).resolve().parent.parent))
    icon_path = base / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = AppConfig()
    window = MainWindow(config)
    window.show()
    exit_code = app.exec()
    # Deterministic destruction order: the window (and the worker thread it
    # joined in closeEvent) must go before the QApplication. Leaving both to
    # frame teardown destroys them in unspecified order, which is a known
    # native-crash-at-exit pattern in Qt bindings.
    del window
    del app
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
