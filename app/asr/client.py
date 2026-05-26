"""LAN ASR HTTP client."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config.settings import AsrSettings
from app.asr.postprocessor import postprocess_text


class AsrError(RuntimeError):
    """Raised when ASR service call fails."""


class AsrClient:
    def __init__(self, settings: AsrSettings) -> None:
        self._settings = settings

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise AsrError(f"Audio file not found: {audio_path}")

        if self._settings.backend == "lan_http":
            text = self._transcribe_via_http(audio_path)
        else:
            raise AsrError(f"Unsupported ASR backend: {self._settings.backend}")

        if not text:
            raise AsrError("ASR returned empty transcript.")

        final_text = str(text).strip()
        if self._settings.postprocess_enabled:
            final_text = postprocess_text(final_text)
        return final_text

    def _transcribe_via_http(self, audio_path: Path) -> str:
        parsed = urlparse(self._settings.endpoint)
        if parsed.hostname == "0.0.0.0":
            raise AsrError(
                "Invalid ASR endpoint host 0.0.0.0. "
                "Use 127.0.0.1 for local service or actual server LAN IP."
            )

        try:
            with audio_path.open("rb") as handle:
                response = requests.post(
                    self._settings.endpoint,
                    files={"audio": (audio_path.name, handle, "audio/wav")},
                    timeout=self._settings.timeout_seconds,
                    verify=self._settings.verify_ssl,
                )
            if response.status_code >= 400:
                detail = response.text.strip()
                raise AsrError(
                    f"ASR service HTTP {response.status_code}. "
                    f"Endpoint={self._settings.endpoint}. Response={detail}"
                )
        except requests.RequestException as exc:
            raise AsrError(f"Failed to call ASR service: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AsrError("ASR service response is not valid JSON.") from exc

        text = payload.get("text") or payload.get("result") or payload.get("transcript")
        if not text:
            raise AsrError(
                "ASR returned empty text. Please verify selected microphone/input level "
                "and speak longer/clearer. "
                f"Response keys: {list(payload.keys())}"
            )
        return str(text)
