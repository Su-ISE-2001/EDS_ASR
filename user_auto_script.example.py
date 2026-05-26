"""Rename this file to `user_auto_script.py` and implement hardware call."""


def run_capture_task(params: dict) -> dict:
    print("[example] execute capture with:", params)
    return {
        "status": "success",
        "message": "Example auto script executed.",
        "params": params,
    }
