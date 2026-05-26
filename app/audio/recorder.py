"""Audio recording service for WAV capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock

import numpy as np
import sounddevice as sd
import soundfile as sf

from app.config.settings import AudioSettings


class RecorderError(RuntimeError):
    """Raised when recording state transitions are invalid."""


@dataclass
class RecordingResult:
    path: Path
    duration_seconds: float


class AudioRecorder:
    def __init__(self, settings: AudioSettings) -> None:
        self._settings = settings
        self._stream: sd.InputStream | None = None
        self._frames: list[np.ndarray] = []
        self._is_recording = False
        self._active_sample_rate = int(settings.sample_rate)
        self._level_lock = Lock()
        self._latest_level = 0.0
        self._peak_level = 0.0
        try:
            self._selected_input_device: int | None = self._resolve_input_device(settings.input_device)
        except RecorderError:
            # Fall back to system default if configured device is unavailable.
            self._selected_input_device = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self) -> None:
        if self._is_recording:
            raise RecorderError("Recording is already in progress.")

        self._frames = []
        with self._level_lock:
            self._latest_level = 0.0
            self._peak_level = 0.0
        self._settings.output_dir.mkdir(parents=True, exist_ok=True)

        def _callback(indata: np.ndarray, _frames: int, _time, status) -> None:
            if status:
                print(f"[AudioRecorder] callback status: {status}")
            self._frames.append(indata.copy())
            normalized = indata.astype(np.float32)
            rms = float(np.sqrt(np.mean(np.square(normalized))))
            with self._level_lock:
                self._latest_level = rms
                if rms > self._peak_level:
                    self._peak_level = rms

        candidate_rates = [int(self._settings.sample_rate), 48000, 44100, 16000]
        try:
            device_info = sd.query_devices(device=self._selected_input_device, kind="input")
            default_rate = int(float(device_info.get("default_samplerate", 0)))
            if default_rate > 0:
                candidate_rates.append(default_rate)
        except Exception:
            pass
        candidate_rates = list(dict.fromkeys(candidate_rates))

        errors: list[str] = []
        for rate in candidate_rates:
            try:
                self._stream = sd.InputStream(
                    samplerate=rate,
                    channels=self._settings.channels,
                    dtype=self._settings.dtype,
                    device=self._selected_input_device,
                    callback=_callback,
                )
                self._stream.start()
                self._active_sample_rate = rate
                break
            except (sd.PortAudioError, ValueError) as exc:
                errors.append(f"{rate}Hz: {exc}")
                self._stream = None

        if self._stream is None:
            device_label = self.get_selected_input_device_label()
            detail = " | ".join(errors[-2:]) if errors else "unknown PortAudio error"
            raise RecorderError(
                "无法打开录音设备。请检查设备是否被占用、系统隐私麦克风权限、或切换输入设备。"
                f" 当前设备: {device_label}. 最近错误: {detail}"
            )
        self._is_recording = True

    def stop(self) -> RecordingResult:
        if not self._is_recording:
            raise RecorderError("Recording has not started.")

        assert self._stream is not None
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._is_recording = False

        if not self._frames:
            raise RecorderError("No audio data captured. Please re-record.")

        waveform = np.concatenate(self._frames, axis=0)
        output_path = self._build_output_path()
        sf.write(
            file=output_path,
            data=waveform,
            samplerate=self._active_sample_rate,
            subtype="PCM_16",
        )
        duration = float(waveform.shape[0]) / float(self._active_sample_rate)
        with self._level_lock:
            self._latest_level = 0.0
        return RecordingResult(path=output_path, duration_seconds=duration)

    def _build_output_path(self) -> Path:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._settings.output_dir / f"record_{now}.wav"

    def get_level_snapshot(self) -> tuple[float, float]:
        with self._level_lock:
            return self._latest_level, self._peak_level

    def list_input_devices(self) -> list[tuple[int, str]]:
        devices = sd.query_devices()
        result: list[tuple[int, str]] = []
        for index, item in enumerate(devices):
            if int(item.get("max_input_channels", 0)) > 0:
                name = str(item.get("name", f"input-{index}"))
                result.append((index, name))
        return result

    def set_input_device(self, device_index: int | None) -> None:
        if self._is_recording:
            raise RecorderError("Cannot switch input device while recording.")
        if device_index is None:
            self._selected_input_device = None
            return
        inputs = {idx for idx, _ in self.list_input_devices()}
        if device_index not in inputs:
            raise RecorderError(f"Input device index {device_index} is invalid.")
        self._selected_input_device = device_index

    def get_selected_input_device_label(self) -> str:
        if self._selected_input_device is None:
            return "System default input"
        for index, name in self.list_input_devices():
            if index == self._selected_input_device:
                return f"{index}: {name}"
        return f"{self._selected_input_device}: unknown (device list changed)"

    def _resolve_input_device(self, configured_device: str) -> int | None:
        if not configured_device:
            return None

        devices = self.list_input_devices()
        if configured_device.isdigit():
            wanted = int(configured_device)
            for index, _name in devices:
                if index == wanted:
                    return wanted
            raise RecorderError(f"Configured input_device index not found: {configured_device}")

        needle = configured_device.lower()
        for index, name in devices:
            if needle in name.lower():
                return index
        raise RecorderError(f"Configured input_device not found by name: {configured_device}")
