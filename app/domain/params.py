"""Capture parameter model and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


class ParamValidationError(ValueError):
    """Raised when capture parameters are invalid."""


@dataclass
class CaptureParams:
    sample_id: str
    magnification: int
    exposure_ms: int
    frame_count: int
    save_dir: str

    def validate(self) -> None:
        if not self.sample_id.strip():
            raise ParamValidationError("sample_id cannot be empty.")
        if not (10 <= self.magnification <= 2_000_000):
            raise ParamValidationError("magnification must be in [10, 2000000].")
        if not (1 <= self.exposure_ms <= 120_000):
            raise ParamValidationError("exposure_ms must be in [1, 120000].")
        if not (1 <= self.frame_count <= 10_000):
            raise ParamValidationError("frame_count must be in [1, 10000].")
        if not self.save_dir.strip():
            raise ParamValidationError("save_dir cannot be empty.")

    def to_payload(self) -> dict:
        payload = asdict(self)
        payload["save_dir"] = str(Path(payload["save_dir"]))
        return payload

    @classmethod
    def from_dict(cls, source: dict) -> "CaptureParams":
        return cls(
            sample_id=str(source["sample_id"]),
            magnification=int(source["magnification"]),
            exposure_ms=int(source["exposure_ms"]),
            frame_count=int(source["frame_count"]),
            save_dir=str(source["save_dir"]),
        )
