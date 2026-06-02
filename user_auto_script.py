"""User hardware integration entry points.

Replace the stub implementation with your real microscope API calls.
"""

from __future__ import annotations


def tcp_phase_analysis(
    mag_n: float = 1500.0,
    interval_m: float = 0.00009,
    move_cnt_w: int = 2,
    move_cnt_h: int = 3,
    res_w: int = 768,
    res_h: int = 512,
    dwell: float = 0.00002,
    frames_n: int = 23,
):
    from apero_autoscript import tcp_phase_map
    # Example:
    # from your_sdk import microscope
    # return microscope.tcp_phase_analysis(...)
    print(
        "[user_auto_script] tcp_phase_analysis called:",
        {
            "mag_n": mag_n,
            "interval_m": interval_m,
            "move_cnt_w": move_cnt_w,
            "move_cnt_h": move_cnt_h,
            "res_w": res_w,
            "res_h": res_h,
            "dwell": dwell,
            "frames_n": frames_n,
        },
    )
    return tcp_phase_map.tcp_phase_analysis(
        pos_i_=-1,
        mag_n_=mag_n,
        interval_m_=interval_m,
        move_cnt_w_=move_cnt_w,
        move_cnt_h_=move_cnt_h,
        res_w_=res_w,
        res_h_=res_h,
        dwell_s_=dwell,
        frames_n_=frames_n,
        show_statis=True,
        microscope_=None,
    )


def run_capture_task(params: dict) -> dict:
    """Compatibility wrapper for legacy execute endpoint."""
    return tcp_phase_analysis(
        mag_n=float(params.get("mag_n", params.get("magnification", 1500.0))),
        interval_m=float(params.get("interval_m", 0.00009)),
        move_cnt_w=int(params.get("move_cnt_w", 2)),
        move_cnt_h=int(params.get("move_cnt_h", 3)),
        res_w=int(params.get("res_w", 768)),
        res_h=int(params.get("res_h", 512)),
        dwell=float(params.get("dwell", 0.00002)),
        frames_n=int(params.get("frames_n", params.get("frame_count", 23))),
    )
