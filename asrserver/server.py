"""Offline LAN ASR service with Whisper/Vosk engines."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import wave
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from vosk import KaldiRecognizer, Model

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "vosk-model-small-cn-0.22"
MODEL_PATH = Path(os.getenv("ASR_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
ASR_ENGINE = os.getenv("ASR_ENGINE", "whisper").strip().lower()

WHISPER_MODEL = os.getenv("ASR_WHISPER_MODEL", "small").strip()
WHISPER_DEVICE = os.getenv("ASR_WHISPER_DEVICE", "cpu").strip()
WHISPER_COMPUTE_TYPE = os.getenv("ASR_WHISPER_COMPUTE_TYPE", "int8").strip()
WHISPER_LANGUAGE = os.getenv("ASR_WHISPER_LANGUAGE", "zh").strip()
WHISPER_ALLOW_CPU_FALLBACK = os.getenv("ASR_WHISPER_ALLOW_CPU_FALLBACK", "true").lower() in (
    "1",
    "true",
    "yes",
)

app = FastAPI(title="Offline ASR Server", version="1.0.0")
logger = logging.getLogger("asrserver")

_model: Model | None = None
_model_error: str | None = None
_whisper_model: Any | None = None
_whisper_model_error: str | None = None
_whisper_runtime_device: str = WHISPER_DEVICE
_whisper_runtime_compute_type: str = WHISPER_COMPUTE_TYPE


def _load_model_once() -> Model:
    global _model, _model_error
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        _model_error = f"Vosk model path not found: {MODEL_PATH}"
        raise RuntimeError(_model_error)
    try:
        _model = Model(str(MODEL_PATH))
        _model_error = None
        return _model
    except Exception as exc:  # pragma: no cover - depends on external model files.
        _model_error = f"Failed to load model from {MODEL_PATH}: {exc}"
        raise RuntimeError(_model_error) from exc


def _load_whisper_once() -> Any:
    global _whisper_model, _whisper_model_error
    global _whisper_runtime_device, _whisper_runtime_compute_type
    if _whisper_model is not None:
        return _whisper_model

    model_source: str | Path = WHISPER_MODEL
    if WHISPER_MODEL.startswith(".") or WHISPER_MODEL.startswith("/") or ":" in WHISPER_MODEL:
        model_source = Path(WHISPER_MODEL)
        if not model_source.exists():
            _whisper_model_error = f"Whisper model path not found: {model_source}"
            raise RuntimeError(_whisper_model_error)

    try:
        from faster_whisper import WhisperModel  # Local import for graceful dependency errors.
    except Exception as exc:
        _whisper_model_error = (
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        )
        raise RuntimeError(_whisper_model_error) from exc

    try:
        _whisper_runtime_device = WHISPER_DEVICE
        _whisper_runtime_compute_type = WHISPER_COMPUTE_TYPE
        _whisper_model = WhisperModel(
            str(model_source),
            device=_whisper_runtime_device,
            compute_type=_whisper_runtime_compute_type,
        )
        _whisper_model_error = None
        return _whisper_model
    except Exception as exc:  # pragma: no cover - runtime dependency/model specific.
        if WHISPER_DEVICE.startswith("cuda") and WHISPER_ALLOW_CPU_FALLBACK:
            try:
                _whisper_runtime_device = "cpu"
                _whisper_runtime_compute_type = "int8"
                _whisper_model = WhisperModel(
                    str(model_source),
                    device=_whisper_runtime_device,
                    compute_type=_whisper_runtime_compute_type,
                )
                _whisper_model_error = (
                    f"CUDA init failed ({exc}); auto-fallback to CPU int8 is active."
                )
                return _whisper_model
            except Exception as fallback_exc:
                _whisper_model_error = (
                    f"Failed to load Whisper with CUDA ({exc}) and CPU fallback ({fallback_exc})."
                )
                raise RuntimeError(_whisper_model_error) from fallback_exc

        _whisper_model_error = f"Failed to load Whisper model '{model_source}': {exc}"
        raise RuntimeError(_whisper_model_error) from exc


def _decode_wav_to_text_vosk(wav_path: Path) -> str:
    model = _load_model_once()
    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        samp_width = wav_file.getsampwidth()

        if channels != 1:
            raise HTTPException(status_code=400, detail="Audio must be mono wav (1 channel).")
        if sample_rate != 16000:
            raise HTTPException(status_code=400, detail="Audio sample rate must be 16000Hz.")
        if samp_width != 2:
            raise HTTPException(status_code=400, detail="Audio must be 16-bit PCM wav.")

        recognizer = KaldiRecognizer(model, sample_rate)
        segments: list[str] = []
        last_partial = ""

        while True:
            data = wav_file.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                part = json.loads(recognizer.Result()).get("text", "").strip()
                if part:
                    segments.append(part)
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                if partial:
                    last_partial = partial

        final_part = json.loads(recognizer.FinalResult()).get("text", "").strip()
        if final_part:
            segments.append(final_part)

    merged = " ".join(segments).strip()
    if not merged and last_partial:
        return last_partial
    return merged


def _decode_wav_to_text_whisper(wav_path: Path) -> str:
    global _whisper_model, _whisper_runtime_device, _whisper_runtime_compute_type
    model = _load_whisper_once()
    try:
        segments, _info = model.transcribe(
            str(wav_path),
            language=WHISPER_LANGUAGE or None,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
    except Exception as exc:  # pragma: no cover - runtime dependency/model specific.
        message = str(exc).lower()
        should_retry_cpu = (
            WHISPER_ALLOW_CPU_FALLBACK
            and _whisper_runtime_device.startswith("cuda")
            and any(token in message for token in ("cublas", "cudnn", "cuda"))
        )
        if should_retry_cpu:
            # Runtime CUDA linking issues can appear only on first inference.
            # Reloading with CPU keeps service alive instead of returning 503.
            try:
                from faster_whisper import WhisperModel

                model_source: str | Path = WHISPER_MODEL
                if WHISPER_MODEL.startswith(".") or WHISPER_MODEL.startswith("/") or ":" in WHISPER_MODEL:
                    model_source = Path(WHISPER_MODEL)

                _whisper_model = WhisperModel(
                    str(model_source),
                    device="cpu",
                    compute_type="int8",
                )
                _whisper_runtime_device = "cpu"
                _whisper_runtime_compute_type = "int8"
                model = _whisper_model
                segments, _info = model.transcribe(
                    str(wav_path),
                    language=WHISPER_LANGUAGE or None,
                    vad_filter=True,
                    beam_size=5,
                    condition_on_previous_text=False,
                )
            except Exception as retry_exc:
                raise RuntimeError(
                    f"Whisper transcription failed after CPU fallback: {retry_exc}"
                ) from retry_exc
        else:
            raise RuntimeError(f"Whisper transcription failed: {exc}") from exc

    text = "".join(segment.text for segment in segments).strip()
    return text


@app.on_event("startup")
def warmup_engine() -> None:
    """Warm up model at startup to avoid first-request timeouts."""
    try:
        if ASR_ENGINE == "whisper":
            _load_whisper_once()
            logger.info(
                "Whisper warmup completed. device=%s compute_type=%s model=%s",
                _whisper_runtime_device,
                _whisper_runtime_compute_type,
                WHISPER_MODEL,
            )
        elif ASR_ENGINE == "vosk":
            _load_model_once()
            logger.info("Vosk warmup completed. model_path=%s", MODEL_PATH)
    except Exception as exc:  # pragma: no cover - startup resiliency
        logger.exception("ASR warmup failed, requests may be slower/fail initially: %s", exc)


@app.get("/health")
def health() -> dict:
    if ASR_ENGINE == "vosk":
        try:
            _load_model_once()
            return {
                "ok": True,
                "engine": "vosk",
                "model_path": str(MODEL_PATH),
            }
        except RuntimeError:
            return {
                "ok": False,
                "engine": "vosk",
                "model_path": str(MODEL_PATH),
                "error": _model_error or "Unknown model load error",
            }

    if ASR_ENGINE == "whisper":
        try:
            _load_whisper_once()
            return {
                "ok": True,
                "engine": "whisper",
                "whisper_model": WHISPER_MODEL,
                "device": _whisper_runtime_device,
                "compute_type": _whisper_runtime_compute_type,
                "language": WHISPER_LANGUAGE,
                "fallback_enabled": WHISPER_ALLOW_CPU_FALLBACK,
            }
        except RuntimeError:
            return {
                "ok": False,
                "engine": "whisper",
                "whisper_model": WHISPER_MODEL,
                "error": _whisper_model_error or "Unknown whisper load error",
            }

    return {
        "ok": False,
        "engine": ASR_ENGINE,
        "error": "Unsupported ASR_ENGINE, use whisper or vosk.",
    }


@app.post("/recognize")
async def recognize(audio: UploadFile = File(...)) -> dict:
    suffix = Path(audio.filename or "input.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(await audio.read())

    try:
        if ASR_ENGINE == "vosk":
            text = _decode_wav_to_text_vosk(tmp_path)
        elif ASR_ENGINE == "whisper":
            text = _decode_wav_to_text_whisper(tmp_path)
        else:
            raise RuntimeError(f"Unsupported ASR_ENGINE: {ASR_ENGINE}")
        return {"text": text}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except wave.Error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid wav format: {exc}") from exc
    except Exception as exc:  # pragma: no cover - runtime guard.
        raise HTTPException(status_code=500, detail=f"Unexpected ASR error: {exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
