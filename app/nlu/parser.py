"""Rule-based parser from ASR text to capture params."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config.settings import CaptureDefaultSettings
from app.domain.params import CaptureParams


class ParseError(ValueError):
    """Raised when parser cannot produce valid parameters."""


@dataclass
class ParseResult:
    params: CaptureParams
    missing_fields: list[str]
    source_text: str


class IntentParamParser:
    def __init__(self, defaults: CaptureDefaultSettings) -> None:
        self._defaults = defaults

    def parse(self, text: str) -> ParseResult:
        if not text.strip():
            raise ParseError("Empty ASR text.")

        values = {
            "sample_id": self._defaults.sample_id,
            "magnification": self._defaults.magnification,
            "exposure_ms": self._defaults.exposure_ms,
            "frame_count": self._defaults.frame_count,
            "save_dir": str(self._defaults.save_dir),
        }
        missing_fields: list[str] = []

        sample_match = re.search(r"(?:样品|sample)(?:编号|id)?[是为:]?\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if sample_match:
            values["sample_id"] = sample_match.group(1)
        else:
            missing_fields.append("sample_id")

        magnification_match = re.search(r"(?:倍率|magnification)[是为:]?\s*(\d+)", text, re.IGNORECASE)
        if magnification_match:
            values["magnification"] = int(magnification_match.group(1))
        else:
            missing_fields.append("magnification")

        exposure_match = re.search(
            r"(?:曝光|exposure)(?:时间)?[是为:]?\s*(\d+)\s*(ms|毫秒)?",
            text,
            re.IGNORECASE,
        )
        if exposure_match:
            values["exposure_ms"] = int(exposure_match.group(1))
        else:
            missing_fields.append("exposure_ms")

        frame_match = re.search(r"(?:拍|采集|张数|frame_count)[是为:]?\s*(\d+)\s*(?:张|帧)?", text, re.IGNORECASE)
        if frame_match:
            values["frame_count"] = int(frame_match.group(1))
        else:
            missing_fields.append("frame_count")

        dir_match = re.search(r"(?:保存到|save(?:_dir)?)[是为:]?\s*([A-Za-z]:[\\/][^,，。;\n]+|[^\s,，。;]+)", text, re.IGNORECASE)
        if dir_match:
            values["save_dir"] = dir_match.group(1).strip()

        params = CaptureParams.from_dict(values)
        params.validate()
        return ParseResult(params=params, missing_fields=missing_fields, source_text=text)
