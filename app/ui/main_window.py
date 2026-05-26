"""Main PyQt window for offline voice capture workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.asr.client import AsrClient, AsrError
from app.audio.recorder import AudioRecorder, RecorderError
from app.capture.executor import CaptureExecutor
from app.domain.params import CaptureParams, ParamValidationError
from app.nlu.parser import ParseError


class ParserProtocol(Protocol):
    def parse(self, text: str): ...


class ModeSelectionDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Select Interaction Mode")
        self.selected_mode = "voice"

        layout = QVBoxLayout(self)
        label = QLabel("Choose operation mode:")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["voice", "keyboard"])

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(label)
        layout.addWidget(self.mode_combo)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.selected_mode = self.mode_combo.currentText()
        super().accept()


class ParamConfirmDialog(QDialog):
    def __init__(self, params: CaptureParams, missing_fields: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Capture Params")
        self._edits: dict[str, QLineEdit] = {}
        self._missing_fields = missing_fields

        layout = QVBoxLayout(self)
        form = QFormLayout()
        fields = {
            "sample_id": params.sample_id,
            "magnification": str(params.magnification),
            "exposure_ms": str(params.exposure_ms),
            "frame_count": str(params.frame_count),
            "save_dir": params.save_dir,
        }
        for key, value in fields.items():
            edit = QLineEdit(value)
            if key in missing_fields:
                edit.setPlaceholderText("missing from speech, please confirm")
            self._edits[key] = edit
            form.addRow(key, edit)

        warning_label = QLabel(
            "Fields from defaults: " + (", ".join(missing_fields) if missing_fields else "None")
        )
        warning_label.setStyleSheet("color: #8a6d3b;")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(warning_label)
        layout.addWidget(buttons)

    def get_params(self) -> CaptureParams:
        return CaptureParams(
            sample_id=self._edits["sample_id"].text().strip(),
            magnification=int(self._edits["magnification"].text().strip()),
            exposure_ms=int(self._edits["exposure_ms"].text().strip()),
            frame_count=int(self._edits["frame_count"].text().strip()),
            save_dir=self._edits["save_dir"].text().strip(),
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        recorder: AudioRecorder,
        asr_client: AsrClient,
        parser: ParserProtocol,
        executor: CaptureExecutor,
    ) -> None:
        super().__init__()
        self._recorder = recorder
        self._asr_client = asr_client
        self._parser = parser
        self._executor = executor
        self._mode = "voice"
        self._latest_audio: Path | None = None

        self.setWindowTitle("Offline Voice Capture MVP")
        self.resize(900, 600)
        self._build_ui()
        self._init_mode_from_popup()
        self._refresh_controls()

    def _build_ui(self) -> None:
        central = QWidget(self)
        grid = QGridLayout(central)

        self.mode_label = QLabel("Mode: voice")
        self.device_label = QLabel("Input device:")
        self.device_combo = QComboBox()
        self.start_btn = QPushButton("Start Recording")
        self.stop_btn = QPushButton("Stop Recording")
        self.parse_btn = QPushButton("Parse And Execute")
        self.keyboard_btn = QPushButton("Parse Keyboard Input")

        self.asr_text = QPlainTextEdit()
        self.asr_text.setPlaceholderText("ASR text or keyboard command appears here...")

        self.status_label = QLabel("Ready")
        self.hotkey_label = QLabel("Hotkeys: F8 start/stop recording, F9 parse+execute")
        self.audio_level_label = QLabel("Mic level: idle")
        self.audio_level_bar = QProgressBar()
        self.audio_level_bar.setRange(0, 100)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.setFormat("%p%")

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.mode_label)
        top_bar.addWidget(self.device_label)
        top_bar.addWidget(self.device_combo)
        top_bar.addStretch()
        top_bar.addWidget(self.start_btn)
        top_bar.addWidget(self.stop_btn)
        top_bar.addWidget(self.parse_btn)
        top_bar.addWidget(self.keyboard_btn)

        grid.addLayout(top_bar, 0, 0)
        grid.addWidget(QLabel("Command Text"), 1, 0)
        grid.addWidget(self.asr_text, 2, 0)
        grid.addWidget(self.status_label, 3, 0)
        grid.addWidget(self.audio_level_label, 4, 0)
        grid.addWidget(self.audio_level_bar, 5, 0)
        grid.addWidget(self.hotkey_label, 6, 0)

        self.start_btn.clicked.connect(self._start_recording)
        self.stop_btn.clicked.connect(self._stop_recording)
        self.parse_btn.clicked.connect(self._parse_and_execute_voice)
        self.keyboard_btn.clicked.connect(self._parse_and_execute_keyboard)
        self.device_combo.currentIndexChanged.connect(self._on_input_device_changed)

        self.record_toggle_shortcut = QShortcut(QKeySequence("F8"), self)
        self.record_toggle_shortcut.activated.connect(self._toggle_recording_with_key)
        self.parse_shortcut = QShortcut(QKeySequence("F9"), self)
        self.parse_shortcut.activated.connect(self._run_mode_action_with_key)

        self._populate_input_devices()
        self.meter_timer = QTimer(self)
        self.meter_timer.setInterval(80)
        self.meter_timer.timeout.connect(self._refresh_audio_meter)
        self.meter_timer.start()
        self.setCentralWidget(central)

    def _init_mode_from_popup(self) -> None:
        dialog = ModeSelectionDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._mode = dialog.selected_mode
        self.mode_label.setText(f"Mode: {self._mode}")

    def _refresh_controls(self) -> None:
        voice_mode = self._mode == "voice"
        self.start_btn.setEnabled(voice_mode and not self._recorder.is_recording)
        self.stop_btn.setEnabled(voice_mode and self._recorder.is_recording)
        self.parse_btn.setEnabled(voice_mode)
        self.keyboard_btn.setEnabled(not voice_mode)
        self.device_combo.setEnabled(voice_mode and not self._recorder.is_recording)

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
            self.status_label.setText("Recording...")
            self._refresh_controls()
        except RecorderError as exc:
            QMessageBox.critical(self, "Recorder Error", str(exc))

    def _stop_recording(self) -> None:
        try:
            result = self._recorder.stop()
            self._latest_audio = result.path
            self.status_label.setText(f"Saved: {result.path} ({result.duration_seconds:.2f}s)")
            self._refresh_controls()
        except RecorderError as exc:
            QMessageBox.critical(self, "Recorder Error", str(exc))
        finally:
            self._refresh_controls()

    def _toggle_recording_with_key(self) -> None:
        if self._mode != "voice":
            self.status_label.setText("Keyboard mode: use F9 to parse typed text.")
            return
        if self._recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _run_mode_action_with_key(self) -> None:
        if self._mode == "voice":
            self._parse_and_execute_voice()
        else:
            self._parse_and_execute_keyboard()

    def _refresh_audio_meter(self) -> None:
        latest, peak = self._recorder.get_level_snapshot()
        if latest > 1.0:
            latest = latest / 32768.0
        if peak > 1.0:
            peak = peak / 32768.0

        latest = max(0.0, min(1.0, latest))
        peak = max(0.0, min(1.0, peak))
        self.audio_level_bar.setValue(int(latest * 100))

        if self._recorder.is_recording:
            self.audio_level_label.setText(
                f"Mic level: live {int(latest * 100)}% (peak {int(peak * 100)}%)"
            )
        else:
            self.audio_level_label.setText("Mic level: idle")

    def _populate_input_devices(self) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("System default input", None)
        for index, name in self._recorder.list_input_devices():
            self.device_combo.addItem(f"{index}: {name}", index)

        selected_label = self._recorder.get_selected_input_device_label()
        target_index = 0
        for row in range(self.device_combo.count()):
            if self.device_combo.itemText(row) == selected_label:
                target_index = row
                break
        self.device_combo.setCurrentIndex(target_index)
        self.device_combo.blockSignals(False)
        self.status_label.setText(f"Ready ({selected_label})")

    def _on_input_device_changed(self, row: int) -> None:
        selected = self.device_combo.itemData(row)
        try:
            self._recorder.set_input_device(selected)
            self.status_label.setText(f"Input device switched: {self._recorder.get_selected_input_device_label()}")
        except RecorderError as exc:
            QMessageBox.critical(self, "Input Device Error", str(exc))
            self._populate_input_devices()

    def _parse_and_execute_voice(self) -> None:
        if not self._latest_audio:
            QMessageBox.warning(self, "No Audio", "Please record audio first.")
            return
        self.status_label.setText("Transcribing...")
        try:
            text = self._asr_client.transcribe(self._latest_audio)
        except AsrError as exc:
            QMessageBox.critical(self, "ASR Error", str(exc))
            self.status_label.setText("ASR failed")
            return
        self.asr_text.setPlainText(text)
        self._parse_and_execute_text(text)

    def _parse_and_execute_keyboard(self) -> None:
        text = self.asr_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Required", "Please type command text first.")
            return
        self._parse_and_execute_text(text)

    def _parse_and_execute_text(self, text: str) -> None:
        try:
            parse_result = self._parser.parse(text)
        except (ParseError, ParamValidationError, ValueError) as exc:
            QMessageBox.critical(self, "Parse Error", str(exc))
            self.status_label.setText("Parse failed")
            return

        dialog = ParamConfirmDialog(parse_result.params, parse_result.missing_fields, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.status_label.setText("Execution cancelled")
            return

        try:
            confirmed = dialog.get_params()
            confirmed.validate()
        except (ParamValidationError, ValueError) as exc:
            QMessageBox.critical(self, "Validation Error", str(exc))
            self.status_label.setText("Validation failed")
            return

        result = self._executor.execute(confirmed)
        if result.success:
            QMessageBox.information(self, "Capture Result", f"{result.message}\nTask: {result.task_id}")
            self.status_label.setText(f"Done: {result.task_id}")
        else:
            QMessageBox.critical(self, "Capture Result", f"{result.message}\nTask: {result.task_id}")
            self.status_label.setText(f"Failed: {result.task_id}")
