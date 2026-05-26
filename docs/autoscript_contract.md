# Auto Script Function Contract

The app expects a Python module at workspace root:

- `user_auto_script.py`
- function: `run_capture_task(params: dict) -> dict`

## Required input keys (`params`)

- `sample_id: str`
- `magnification: int`
- `exposure_ms: int`
- `frame_count: int`
- `save_dir: str`

## Validation ranges (enforced by app)

- `magnification`: 10 to 2,000,000
- `exposure_ms`: 1 to 120,000
- `frame_count`: 1 to 10,000

## Expected return payload

The function should return a dict containing:

- `status`: e.g. `"success"` or `"failed"`
- `message`: readable result text
- optional extra fields for metadata

## Minimal example

```python
def run_capture_task(params: dict) -> dict:
    # TODO: call microscope capture API here
    print("Capture params:", params)
    return {
        "status": "success",
        "message": "Capture completed",
        "capture_id": "demo-001",
    }
```
