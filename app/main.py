"""Application entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from app.asr.client import AsrClient
from app.audio.recorder import AudioRecorder
from app.capture.executor import CaptureExecutor
from app.config.settings import load_settings
from app.nlu.hybrid_parser import HybridParamParser
from app.ui.main_window import MainWindow


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def main() -> int:
    settings = load_settings()
    settings.audio.output_dir.mkdir(parents=True, exist_ok=True)
    settings.capture_defaults.save_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(settings.app.log_file)

    app = QApplication(sys.argv)
    window = MainWindow(
        recorder=AudioRecorder(settings.audio),
        asr_client=AsrClient(settings.asr),
        parser=HybridParamParser(settings.capture_defaults, settings.llm_nlu),
        executor=CaptureExecutor(),
    )
    window.setWindowTitle(settings.app.title)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
