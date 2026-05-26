"""Cloud NLU service skeleton for ASR text -> structured params."""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    task_type: str = Field(default="capture_params")
    text: str
    defaults: dict[str, Any]


class ParseResponse(BaseModel):
    intent: str
    params: dict[str, Any]
    missing_fields: list[str]
    confidence: float
    reason: str


app = FastAPI(title="NLU Service", version="0.1.0")


def _extract_with_rules(text: str, defaults: dict[str, Any]) -> tuple[dict[str, Any], list[str], float]:
    params = {
        "sample_id": defaults.get("sample_id", "default_sample"),
        "magnification": int(defaults.get("magnification", 5000)),
        "exposure_ms": int(defaults.get("exposure_ms", 100)),
        "frame_count": int(defaults.get("frame_count", 1)),
        "save_dir": str(defaults.get("save_dir", "data/output")),
    }
    missing_fields: list[str] = []
    score = 1.0

    sample_match = re.search(r"(?:样品|sample)(?:编号|id)?[是为:]?\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if sample_match:
        params["sample_id"] = sample_match.group(1)
    else:
        missing_fields.append("sample_id")
        score -= 0.2

    mag_match = re.search(r"(?:倍率|magnification)[是为:]?\s*(\d+)", text, re.IGNORECASE)
    if mag_match:
        params["magnification"] = int(mag_match.group(1))
    else:
        missing_fields.append("magnification")
        score -= 0.2

    exposure_match = re.search(r"(?:曝光|exposure)(?:时间)?[是为:]?\s*(\d+)\s*(ms|毫秒)?", text, re.IGNORECASE)
    if exposure_match:
        params["exposure_ms"] = int(exposure_match.group(1))
    else:
        missing_fields.append("exposure_ms")
        score -= 0.2

    frame_match = re.search(r"(?:拍|采集|张数|frame_count)[是为:]?\s*(\d+)\s*(?:张|帧)?", text, re.IGNORECASE)
    if frame_match:
        params["frame_count"] = int(frame_match.group(1))
    else:
        missing_fields.append("frame_count")
        score -= 0.2

    dir_match = re.search(r"(?:保存到|save(?:_dir)?)[是为:]?\s*([A-Za-z]:[\\/][^,，。;\n]+|[^\s,，。;]+)", text, re.IGNORECASE)
    if dir_match:
        params["save_dir"] = dir_match.group(1).strip()
    else:
        score -= 0.1

    return params, missing_fields, max(0.0, score)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "nlu_service", "mode": "skeleton"}


@app.post("/nlu/parse", response_model=ParseResponse)
def parse_payload(request: ParseRequest) -> ParseResponse:
    # TODO: replace with model inference call on 4090 machine.
    params, missing_fields, confidence = _extract_with_rules(request.text, request.defaults)
    return ParseResponse(
        intent=request.task_type,
        params=params,
        missing_fields=missing_fields,
        confidence=confidence,
        reason="rule_skeleton_parser",
    )
