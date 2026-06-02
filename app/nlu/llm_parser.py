"""Client parser that calls remote/local LLM NLU service."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from app.config.settings import CaptureDefaultSettings, LlmNluSettings
from app.domain.params import CaptureParams
from app.nlu.parser import ParseError, ParseResult


@dataclass
class LlmParsePayload:
    task_type: str
    text: str
    defaults: dict


class LlmParamParser:
    def __init__(self, settings: LlmNluSettings, defaults: CaptureDefaultSettings) -> None:
        self._settings = settings
        self._defaults = defaults

    def parse(self, text: str) -> ParseResult:
        payload = LlmParsePayload(
            task_type=self._settings.task_type,
            text=text,
            defaults={
                "sample_id": self._defaults.sample_id,
                "magnification": self._defaults.magnification,
                "interval": self._defaults.interval,
                "move_cnt_w": self._defaults.move_cnt_w,
                "move_cnt_h": self._defaults.move_cnt_h,
                "dwell": self._defaults.dwell,
                "frame_count": self._defaults.frame_count,
                "save_dir": str(self._defaults.save_dir),
            },
        )
        try:
            response = requests.post(
                self._settings.endpoint,
                json={
                    "task_type": payload.task_type,
                    "text": payload.text,
                    "defaults": payload.defaults,
                },
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ParseError(f"LLM NLU request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ParseError("LLM NLU returned non-JSON response.") from exc

        # Support both schemas:
        # 1) {"params": {...}, "missing_fields": [...]}
        # 2) {"intent": "...", "slots": {...}, "needs_confirmation": true}
        params_data = data.get("params")
        if not isinstance(params_data, dict):
            slots_data = data.get("slots")
            if isinstance(slots_data, dict):
                params_data = self._slots_to_params(slots_data)
            else:
                params_data = {}

        merged = {
            "sample_id": params_data.get("sample_id", self._defaults.sample_id),
            "magnification": params_data.get("magnification", self._defaults.magnification),
            "interval": params_data.get("interval", self._defaults.interval),
            "move_cnt_w": params_data.get("move_cnt_w", self._defaults.move_cnt_w),
            "move_cnt_h": params_data.get("move_cnt_h", self._defaults.move_cnt_h),
            "dwell": params_data.get("dwell", self._defaults.dwell),
            "frame_count": params_data.get("frame_count", self._defaults.frame_count),
            "save_dir": params_data.get("save_dir", str(self._defaults.save_dir)),
        }
        required = ["sample_id", "magnification", "exposure_ms", "frame_count", "save_dir"]
        missing_fields = data.get("missing_fields")
        if missing_fields is None:
            missing_fields = [key for key in required if key not in params_data]
        if not isinstance(missing_fields, list):
            missing_fields = []

        params = CaptureParams.from_dict(merged)
        params.validate()
        return ParseResult(params=params, missing_fields=missing_fields, source_text=text)

    @staticmethod
    def _slots_to_params(slots: dict) -> dict:
        key_map = {
            "sample_id": "sample_id",
            "sample": "sample_id",
            "样品": "sample_id",
            "magnification": "magnification",
            "mag_n": "magnification",
            "interval": "interval",
            "interval_m": "interval",
            "move_cnt_w": "move_cnt_w",
            "move_cnt_h": "move_cnt_h",
            "dwell": "dwell",
            "倍率": "magnification",
            "exposure_ms": "exposure_ms",
            "曝光": "exposure_ms",
            "frame_count": "frame_count",
            "frames_n": "frame_count",
            "帧数": "frame_count",
            "save_dir": "save_dir",
            "保存路径": "save_dir",
        }
        out: dict = {}
        for k, v in slots.items():
            target = key_map.get(str(k).strip().lower(), key_map.get(str(k).strip()))
            if target:
                out[target] = v
        return out
