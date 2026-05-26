"""Adapter around user-provided auto script."""

from __future__ import annotations

import importlib
import logging
from typing import Any


logger = logging.getLogger(__name__)


class AutoScriptAdapter:
    """Loads user auto-script callables if available."""

    def __init__(self) -> None:
        self._run_capture_task, self._tcp_phase_analysis = self._load_callables()

    def _load_callables(self):
        try:
            module = importlib.import_module("user_auto_script")
            run_fn = getattr(module, "run_capture_task", self._fallback_run_capture_task)
            tcp_fn = getattr(module, "tcp_phase_analysis", None)
            if tcp_fn is None:
                logger.warning(
                    "user_auto_script.tcp_phase_analysis not found; TCP execute endpoint will use fallback."
                )
                tcp_fn = self._fallback_tcp_phase_analysis
            return run_fn, tcp_fn
        except Exception:
            logger.warning(
                "user_auto_script not found; fallback mock executor is used."
            )
            return self._fallback_run_capture_task, self._fallback_tcp_phase_analysis

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._run_capture_task(params)

    def run_tcp_phase_analysis(self, params: dict[str, Any]) -> dict[str, Any]:
        result = self._tcp_phase_analysis(
            mag_n=float(params["mag_n"]),
            interval_m=float(params["interval_m"]),
            move_cnt_w=int(params["move_cnt_w"]),
            move_cnt_h=int(params["move_cnt_h"]),
            res_w=int(params["res_w"]),
            res_h=int(params["res_h"]),
            dwell=float(params["dwell"]),
            frames_n=int(params["frames_n"]),
        )
        if isinstance(result, dict):
            payload = dict(result)
        else:
            payload = {"result": result}
        payload.setdefault("status", "success")
        payload.setdefault("message", "tcp_phase_analysis executed.")
        payload["params"] = {
            "mag_n": float(params["mag_n"]),
            "interval_m": float(params["interval_m"]),
            "move_cnt_w": int(params["move_cnt_w"]),
            "move_cnt_h": int(params["move_cnt_h"]),
            "res_w": int(params["res_w"]),
            "res_h": int(params["res_h"]),
            "dwell": float(params["dwell"]),
            "frames_n": int(params["frames_n"]),
        }
        return payload

    @staticmethod
    def _fallback_run_capture_task(params: dict[str, Any]) -> dict[str, Any]:
        logger.info("Fallback capture execution with params=%s", params)
        return {
            "status": "mock_success",
            "message": "Fallback executor ran. Add user_auto_script.py to use real hardware.",
            "params": params,
        }

    @staticmethod
    def _fallback_tcp_phase_analysis(
        mag_n: float,
        interval_m: float,
        move_cnt_w: int,
        move_cnt_h: int,
        res_w: int,
        res_h: int,
        dwell: float,
        frames_n: int,
    ) -> dict[str, Any]:
        params = {
            "mag_n": mag_n,
            "interval_m": interval_m,
            "move_cnt_w": move_cnt_w,
            "move_cnt_h": move_cnt_h,
            "res_w": res_w,
            "res_h": res_h,
            "dwell": dwell,
            "frames_n": frames_n,
        }
        logger.info("Fallback tcp_phase_analysis execution with params=%s", params)
        return {
            "status": "mock_success",
            "message": "Fallback tcp_phase_analysis ran. Add user_auto_script.py for real hardware.",
            "params": params,
        }
