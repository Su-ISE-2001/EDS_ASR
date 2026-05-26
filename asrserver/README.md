# asrserver (Offline LAN ASR)

This folder is a standalone ASR service.
You can run it locally first, then copy this folder to a server machine later.

## 1) Choose engine (Whisper recommended)

- Default engine is Whisper (`ASR_ENGINE=whisper`).
- Optional fallback engine is Vosk (`ASR_ENGINE=vosk`).

### Whisper mode (default)

- By default, service uses `ASR_WHISPER_MODEL=small` and auto-downloads model on first run.
- If you need fully offline model loading, set:
  - `ASR_WHISPER_MODEL=/absolute/path/to/local-whisper-model`

### Vosk mode (optional)

Download Vosk Chinese model and extract to:

- `asrserver/models/vosk-model-small-cn-0.22`

Or set:

- `ASR_MODEL_PATH=/absolute/path/to/vosk-model`

## 2) Start service (Windows PowerShell)

```powershell
cd asrserver
.\start.ps1
```

GPU test (Whisper on CUDA):

```powershell
cd asrserver
.\start_gpu.ps1
```

Service listens on:

- `http://0.0.0.0:9000`

## 3) API

- Health check: `GET /health`
- Recognition: `POST /recognize` with multipart field `audio`
  - Vosk mode expects wav mono/16k/16-bit
  - Whisper mode supports common audio formats (wav recommended)

Successful response:

```json
{"text": "recognized content"}
```

## 4) Connect app client

Set `app/config/settings.yaml`:

```yaml
asr:
  backend: lan_http
  endpoint: http://127.0.0.1:9000/recognize
  timeout_seconds: 30
  verify_ssl: false
  postprocess_enabled: true
```

For another machine in LAN, replace `127.0.0.1` with ASR server IP.

## 5) Engine environment variables

- `ASR_ENGINE`: `whisper` (default) or `vosk`
- `ASR_WHISPER_MODEL`: default `small`
- `ASR_WHISPER_DEVICE`: default `cpu`
- `ASR_WHISPER_COMPUTE_TYPE`: default `int8`
- `ASR_WHISPER_LANGUAGE`: default `zh`
- `ASR_WHISPER_ALLOW_CPU_FALLBACK`: default `true` (if CUDA init fails, auto use CPU)
- `ASR_MODEL_PATH`: Vosk model path (used when `ASR_ENGINE=vosk`)
