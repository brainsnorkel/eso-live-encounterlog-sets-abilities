#!/usr/bin/env python3
"""ESO Log Tail GUI entry point."""

import os
import sys

# Flat engine imports (esolog_tail, app_config, ...) resolve against src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app_config import AppConfig
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ESO Log Tail")
    app.setOrganizationName("esolog-tail")

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
