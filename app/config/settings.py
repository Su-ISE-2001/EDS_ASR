"""Runtime settings loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AppSettings:
    title: str
    log_file: Path


@dataclass(frozen=True)
class AudioSettings:
    sample_rate: int
    channels: int
    dtype: str
    output_dir: Path
    input_device: str


@dataclass(frozen=True)
class AsrSettings:
    backend: str
    endpoint: str
    timeout_seconds: int
    verify_ssl: bool
    postprocess_enabled: bool


@dataclass(frozen=True)
class LlmNluSettings:
    enabled: bool
    endpoint: str
    timeout_seconds: int
    task_type: str
    parse_mode: str


@dataclass(frozen=True)
class CaptureDefaultSettings:
    sample_id: str
    magnification: int
    interval: float
    move_cnt_w: int
    move_cnt_h: int
    dwell: float
    frame_count: int
    save_dir: Path


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    audio: AudioSettings
    asr: AsrSettings
    llm_nlu: LlmNluSettings
    capture_defaults: CaptureDefaultSettings


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def load_settings(settings_path: Path | None = None) -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    final_path = settings_path or (project_root / "app" / "config" / "settings.yaml")
    content: dict[str, Any] = yaml.safe_load(final_path.read_text(encoding="utf-8"))

    app_section = content["app"]
    audio_section = content["audio"]
    asr_section = content["asr"]
    llm_nlu_section = content.get("llm_nlu", {})
    capture_section = content["capture_defaults"]

    return Settings(
        app=AppSettings(
            title=app_section["title"],
            log_file=_resolve_path(project_root, app_section["log_file"]),
        ),
        audio=AudioSettings(
            sample_rate=int(audio_section["sample_rate"]),
            channels=int(audio_section["channels"]),
            dtype=audio_section["dtype"],
            output_dir=_resolve_path(project_root, audio_section["output_dir"]),
            input_device=str(audio_section.get("input_device", "")).strip(),
        ),
        asr=AsrSettings(
            backend=asr_section.get("backend", "lan_http"),
            endpoint=asr_section["endpoint"],
            timeout_seconds=int(asr_section["timeout_seconds"]),
            verify_ssl=bool(asr_section["verify_ssl"]),
            postprocess_enabled=bool(asr_section.get("postprocess_enabled", True)),
        ),
        llm_nlu=LlmNluSettings(
            enabled=bool(llm_nlu_section.get("enabled", False)),
            endpoint=str(llm_nlu_section.get("endpoint", "http://127.0.0.1:9100/nlu/parse")).strip(),
            timeout_seconds=int(llm_nlu_section.get("timeout_seconds", 20)),
            task_type=str(llm_nlu_section.get("task_type", "capture_params")).strip(),
            parse_mode=str(llm_nlu_section.get("parse_mode", "llm_first")).strip().lower(),
        ),
        capture_defaults=CaptureDefaultSettings(
            sample_id=capture_section["sample_id"],
            magnification=int(capture_section["magnification"]),
            interval=float(capture_section["interval_um"])/1000000,
            move_cnt_w=int(capture_section["move_cnt_w"]),
            move_cnt_h=int(capture_section["move_cnt_h"]),
            dwell=float(capture_section["dwell_ms"])/1000,
            frame_count=int(capture_section["frame_count"]),
            save_dir=_resolve_path(project_root, capture_section["save_dir"]),
        ),
    )
