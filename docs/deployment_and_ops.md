# Deployment and Operations Notes

## 1) Offline network topology

- Microscope control PC runs this app (`python -m app.main`)
- LAN ASR server runs in intranet with no internet dependency
- Control PC sends WAV files to ASR endpoint over intranet

## 2) First-time setup

1. Install Python 3.10+ on control PC
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `app/config/settings.yaml`
4. Add `user_auto_script.py` implementing `run_capture_task`

## 3) ASR API contract

- Endpoint: `POST /recognize`
- Content type: multipart form-data
- File field: `audio` (wav)
- Return JSON with one field:
  - `text`, or
  - `result`, or
  - `transcript`

## 4) Typical runtime flow

1. Launch app and choose mode (`voice` or `keyboard`)
2. Voice mode: click start/stop recording
3. App calls ASR and fills recognized text
4. App parses text to capture params
5. User confirms/edits params
6. App executes `run_capture_task(params)`

## 5) Troubleshooting

- `ASR Error`: verify ASR endpoint, timeout, and LAN connectivity
- `Recorder Error`: verify microphone is connected and selected as system input
- `Validation Error`: adjust parameter ranges in command or dialog
- `Fallback executor ran`: create `user_auto_script.py` in workspace root
