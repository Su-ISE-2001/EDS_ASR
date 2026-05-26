# nlu_service (Cloud semantic parser)

This service converts ASR text into structured capture parameters.

## Start

```powershell
cd nlu_service
.\start.ps1
```

Service endpoints:

- `GET /health`
- `POST /nlu/parse`

## Request example

```json
{
  "task_type": "capture_params",
  "text": "样品A1 倍率5000 曝光200ms 拍5张 保存到D:\\capture",
  "defaults": {
    "sample_id": "default_sample",
    "magnification": 5000,
    "exposure_ms": 100,
    "frame_count": 1,
    "save_dir": "data/output"
  }
}
```

## Response example

```json
{
  "intent": "capture_params",
  "params": {
    "sample_id": "A1",
    "magnification": 5000,
    "exposure_ms": 200,
    "frame_count": 5,
    "save_dir": "D:\\capture"
  },
  "missing_fields": [],
  "confidence": 0.9,
  "reason": "rule_skeleton_parser"
}
```

## Notes

- This is a skeleton parser for local/cloud integration testing.
- Replace `_extract_with_rules()` in `app.py` with actual model inference on 4090 server.
