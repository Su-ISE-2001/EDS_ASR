"""Web API + minimal frontend for capture workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.asr.client import AsrClient, AsrError
from app.audio.recorder import AudioRecorder, RecorderError
from app.capture.executor import CaptureExecutor
from app.config.settings import Settings, load_settings
from app.domain.params import CaptureParams, ParamValidationError
from app.nlu.hybrid_parser import HybridParamParser
from app.nlu.parser import ParseError, ParseResult

TCP_PARAM_KEYS = [
    "mag_n",
    "interval_m",
    "move_cnt_w",
    "move_cnt_h",
    "res_w",
    "res_h",
    "dwell",
    "frames_n",
]

TCP_DEFAULTS = {
    "mag_n": 1500.0,
    "interval_m": 0.00009,
    "move_cnt_w": 2,
    "move_cnt_h": 3,
    "res_w": 768,
    "res_h": 512,
    "dwell": 0.00002,
    "frames_n": 23,
}


@dataclass
class RuntimeState:
    latest_audio_path: Path | None = None


class DeviceSetRequest(BaseModel):
    device_index: int | None = None


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)


class ExecuteRequest(BaseModel):
    sample_id: str
    magnification: int
    exposure_ms: int
    frame_count: int
    save_dir: str


class LlmPipelineRequest(BaseModel):
    text: str | None = None


class TcpExecuteRequest(BaseModel):
    mag_n: float
    interval_m: float
    move_cnt_w: int
    move_cnt_h: int
    res_w: int
    res_h: int
    dwell: float
    frames_n: int


def _build_services() -> tuple[Settings, RuntimeState, AudioRecorder, AsrClient, HybridParamParser, CaptureExecutor]:
    settings = load_settings()
    settings.audio.output_dir.mkdir(parents=True, exist_ok=True)
    settings.capture_defaults.save_dir.mkdir(parents=True, exist_ok=True)
    state = RuntimeState()
    recorder = AudioRecorder(settings.audio)
    asr_client = AsrClient(settings.asr)
    parser = HybridParamParser(settings.capture_defaults, settings.llm_nlu)
    executor = CaptureExecutor()
    return settings, state, recorder, asr_client, parser, executor


settings, state, recorder, asr_client, parser, executor = _build_services()
app = FastAPI(title="Capture Web Service", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_path = Path(__file__).resolve().parents[1] / "web" / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "capture_web", "asr_endpoint": settings.asr.endpoint}


@app.get("/api/devices")
def list_devices() -> dict:
    devices = [{"index": index, "name": name} for index, name in recorder.list_input_devices()]
    return {
        "selected_label": recorder.get_selected_input_device_label(),
        "devices": devices,
    }


@app.post("/api/device")
def set_device(req: DeviceSetRequest) -> dict:
    try:
        recorder.set_input_device(req.device_index)
    except RecorderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "selected_label": recorder.get_selected_input_device_label()}


@app.post("/api/record/start")
def record_start() -> dict:
    try:
        recorder.start()
    except RecorderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "state": "recording"}


@app.post("/api/record/stop")
def record_stop() -> dict:
    try:
        result = recorder.stop()
    except RecorderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state.latest_audio_path = result.path
    return {
        "ok": True,
        "audio_path": str(result.path),
        "duration_seconds": result.duration_seconds,
    }


@app.get("/api/record/status")
def record_status() -> dict:
    latest, peak = recorder.get_level_snapshot()
    if latest > 1.0:
        latest = latest / 32768.0
    if peak > 1.0:
        peak = peak / 32768.0
    return {
        "is_recording": recorder.is_recording,
        "latest_level": max(0.0, min(1.0, latest)),
        "peak_level": max(0.0, min(1.0, peak)),
    }


@app.post("/api/transcribe/latest")
def transcribe_latest() -> dict:
    if state.latest_audio_path is None:
        raise HTTPException(status_code=400, detail="No recorded audio available.")
    try:
        text = asr_client.transcribe(state.latest_audio_path)
    except AsrError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "text": text, "audio_path": str(state.latest_audio_path)}


def _parse_text(text: str) -> ParseResult:
    try:
        return parser.parse(text)
    except (ParseError, ParamValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _call_llm_nlu_raw(text: str) -> dict:
    if not settings.llm_nlu.enabled:
        raise HTTPException(status_code=400, detail="llm_nlu.enabled is false.")
    try:
        response = requests.post(
            settings.llm_nlu.endpoint,
            json={
                "task_type": settings.llm_nlu.task_type,
                "text": text,
                "defaults": TCP_DEFAULTS,
            },
            timeout=settings.llm_nlu.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"LLM NLU request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"LLM NLU non-JSON response: {response.text}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"LLM NLU HTTP {response.status_code}: {payload}")
    return payload


def _normalize_tcp_params(nlu_payload: dict) -> tuple[dict, list[str]]:
    slots = nlu_payload.get("slots") if isinstance(nlu_payload, dict) else {}
    slots = slots if isinstance(slots, dict) else {}
    alias_map = {
        "magnification": "mag_n",
        "frame_count": "frames_n",
        "frames": "frames_n",
    }

    merged = dict(TCP_DEFAULTS)
    provided_keys: set[str] = set()
    for raw_key, value in slots.items():
        key = alias_map.get(str(raw_key), str(raw_key))
        if key not in merged:
            continue
        try:
            if key in {"move_cnt_w", "move_cnt_h", "res_w", "res_h", "frames_n"}:
                merged[key] = int(value)
            else:
                merged[key] = float(value)
            provided_keys.add(key)
        except (TypeError, ValueError):
            continue

    missing = [k for k in TCP_PARAM_KEYS if k not in provided_keys]
    return merged, missing


@app.post("/api/parse")
def parse_text(req: ParseRequest) -> dict:
    parsed = _parse_text(req.text)
    return {
        "ok": True,
        "params": asdict(parsed.params),
        "missing_fields": parsed.missing_fields,
        "source_text": parsed.source_text,
    }


@app.post("/api/pipeline/asr_to_llm_json")
def asr_to_llm_json(req: LlmPipelineRequest) -> dict:
    text = (req.text or "").strip()
    audio_path = None
    if not text:
        if state.latest_audio_path is None:
            raise HTTPException(status_code=400, detail="No text provided and no recorded audio available.")
        audio_path = str(state.latest_audio_path)
        try:
            text = asr_client.transcribe(state.latest_audio_path)
        except AsrError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    llm_payload = _call_llm_nlu_raw(text)
    tcp_params, missing_fields = _normalize_tcp_params(llm_payload)
    return {
        "ok": True,
        "audio_path": audio_path,
        "text": text,
        "task_type": settings.llm_nlu.task_type,
        "nlu": llm_payload,
        "tcp_params": tcp_params,
        "missing_fields": missing_fields,
    }


def _validate_tcp_params(params: dict) -> None:
    def _must_positive_int(name: str) -> None:
        value = int(params[name])
        if value <= 0:
            raise HTTPException(status_code=400, detail=f"{name} must be > 0.")

    def _must_positive_float(name: str) -> None:
        value = float(params[name])
        if value <= 0:
            raise HTTPException(status_code=400, detail=f"{name} must be > 0.")

    _must_positive_float("mag_n")
    _must_positive_float("interval_m")
    _must_positive_int("move_cnt_w")
    _must_positive_int("move_cnt_h")
    _must_positive_int("res_w")
    _must_positive_int("res_h")
    _must_positive_float("dwell")
    _must_positive_int("frames_n")


@app.post("/api/execute_tcp")
def execute_tcp(req: TcpExecuteRequest) -> dict:
    params = req.model_dump()
    _validate_tcp_params(params)
    result = executor.execute_tcp_phase_analysis(params)
    return {
        "ok": result.success,
        "success": result.success,
        "message": result.message,
        "task_id": result.task_id,
        "payload": result.payload,
    }


@app.post("/api/execute")
def execute(req: ExecuteRequest) -> dict:
    params = CaptureParams.from_dict(req.model_dump())
    try:
        params.validate()
    except ParamValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = executor.execute(params)
    return {
        "ok": result.success,
        "success": result.success,
        "message": result.message,
        "task_id": result.task_id,
        "payload": result.payload,
    }
