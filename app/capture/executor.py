"""Capture task execution orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.capture.auto_script_adapter import AutoScriptAdapter
from app.domain.params import CaptureParams


logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    message: str
    task_id: str
    payload: dict


class CaptureExecutor:
    def __init__(self, adapter: AutoScriptAdapter | None = None) -> None:
        self._adapter = adapter or AutoScriptAdapter()

    def execute(self, params: CaptureParams) -> ExecutionResult:
        params.validate()
        payload = params.to_payload()
        task_id = datetime.now().strftime("task_%Y%m%d_%H%M%S")

        logger.info("Starting capture task_id=%s payload=%s", task_id, payload)
        try:
            result_payload = self._adapter.run(payload)
            status = str(result_payload.get("status", "unknown")).lower()
            success = "success" in status
            message = str(result_payload.get("message", "No message"))
            logger.info("Finished capture task_id=%s success=%s", task_id, success)
            return ExecutionResult(
                success=success,
                message=message,
                task_id=task_id,
                payload=result_payload,
            )
        except Exception as exc:
            logger.exception("Capture execution failed for task_id=%s", task_id)
            return ExecutionResult(
                success=False,
                message=f"Capture execution failed: {exc}",
                task_id=task_id,
                payload={},
            )

    def execute_tcp_phase_analysis(self, params: dict) -> ExecutionResult:
        task_id = datetime.now().strftime("task_%Y%m%d_%H%M%S")
        logger.info("Starting tcp_phase_analysis task_id=%s payload=%s", task_id, params)
        try:
            result_payload = self._adapter.run_tcp_phase_analysis(params)
            status = str(result_payload.get("status", "unknown")).lower()
            success = "success" in status
            message = str(result_payload.get("message", "No message"))
            logger.info("Finished tcp_phase_analysis task_id=%s success=%s", task_id, success)
            return ExecutionResult(
                success=success,
                message=message,
                task_id=task_id,
                payload=result_payload,
            )
        except Exception as exc:
            logger.exception("tcp_phase_analysis execution failed for task_id=%s", task_id)
            return ExecutionResult(
                success=False,
                message=f"tcp_phase_analysis execution failed: {exc}",
                task_id=task_id,
                payload={},
            )
