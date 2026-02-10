"""Entry point for rekordbox-creative."""

import logging
import sys
import traceback
from pathlib import Path


def main():
    """Launch the application."""
    # Set up file logging to capture crashes
    log_path = Path(__file__).resolve().parent.parent.parent / "rekordbox_creative.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_path), mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logger = logging.getLogger("rekordbox_creative")
    logger.info("Starting Rekordbox Creative...")
    logger.info("Log file: %s", log_path)

    try:
        from PyQt6.QtWidgets import QApplication

        from rekordbox_creative.ui.app import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("Rekordbox Creative")
        app.setStyle("Fusion")

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception:
        logger.critical("Fatal error:\n%s", traceback.format_exc())
        # Also write to a crash file in case logging failed
        crash_path = Path(__file__).resolve().parent.parent.parent / "crash.log"
        crash_path.write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
