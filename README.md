# Voice Capture + ASR + NLU + TCP Phase Analysis

本项目实现了从语音到参数、再到仪器函数调用的完整链路，支持桌面端和 Web 端。  
文档中的配置全部使用相对路径或可替换占位符，方便迁移到新机器/新服务器。

## 功能概览

- **录音采集**：选择输入设备，开始/停止录音，实时电平显示。
- **ASR 转写**：调用局域网/本机 ASR 服务，将音频转文字。
- **文本后处理**：去口头词、术语归一化、中文数字归一化、繁体转简体。
- **云端/本地 NLU**：将转写文本解析为 `tcp_phase_analysis` 参数。
- **参数执行**：将 8 个参数传给 `user_auto_script.py` 中的 `tcp_phase_analysis(...)`。

## 目录结构（关键部分）

- `app/`：主应用代码（Web API、录音、ASR 客户端、执行器）
- `web/`：前端页面
- `asrserver/`：可独立迁移部署的 ASR 服务
- `nlu_service/`：可独立迁移部署的 NLU 服务（可选）
- `user_auto_script.py`：你对接真实仪器 API 的文件

## 环境准备

在项目根目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 启动方式

### 1) Web 服务（推荐）

在项目根目录：

```bash
python -m app.web_main
```

访问：

- `http://127.0.0.1:8080`

### 2) 桌面 GUI（保留）

```bash
python -m app.main
```

## Web 端使用流程

1. 选择输入设备
2. 开始录音 / 结束录音
3. 点击“一键 ASR -> LLM JSON”
4. 页面自动填充 `tcp_phase_analysis` 的 8 个参数
5. 点击“执行 TCP 相位分析”

## 配置说明（可迁移）

配置文件：`app/config/settings.yaml`

建议使用下列模板（按你的环境替换占位符）：

```yaml
audio:
  sample_rate: 16000
  channels: 1
  dtype: int16
  output_dir: data/audio
  input_device: ""

asr:
  backend: lan_http
  endpoint: http://<ASR_HOST>:<ASR_PORT>/recognize
  timeout_seconds: 120
  verify_ssl: false
  postprocess_enabled: true

llm_nlu:
  enabled: true
  endpoint: http://<NLU_HOST>:<NLU_PORT>/nlu/parse
  timeout_seconds: 30
  task_type: tcp_phase_analysis
  parse_mode: llm_first
```

说明：

- `output_dir`、`save_dir` 推荐使用相对路径（例如 `data/audio`），避免机器绑定。
- 不要在代码中写死 IP，统一在 `settings.yaml` 改。
- `audio.input_device`：
  - `""`：系统默认输入
  - `"3"`：按设备索引
  - `"USB"`：按设备名包含匹配

## ASR / NLU 接口约定

### ASR 接口

- 请求：`multipart/form-data`，字段名 `audio`
- 响应 JSON 至少包含以下之一：
  - `text`
  - `result`
  - `transcript`

### NLU 接口

- 请求字段：
  - `task_type`（建议 `tcp_phase_analysis`）
  - `text`
  - `defaults`
- 响应字段：
  - `slots`（包含参数抽取结果）

## tcp_phase_analysis 参数约定

系统执行时传入以下参数：

- `mag_n: float`
- `interval_m: float`
- `move_cnt_w: int`
- `move_cnt_h: int`
- `res_w: int`
- `res_h: int`
- `dwell: float`
- `frames_n: int`

若某些参数未识别到，前端会按默认值补齐并提示 `missing_fields`。

## 对接真实仪器函数

编辑 `user_auto_script.py`，实现：

- `tcp_phase_analysis(...)`

你可以直接在该函数中调用实际 SDK/API。  
当前仓库自带的是可运行 stub，用于联调链路。

## 迁移建议

迁移到新机器时，优先迁移以下目录/文件：

- `app/`
- `web/`
- `asrserver/`（若 ASR 独立部署）
- `nlu_service/`（若 NLU 独立部署）
- `requirements.txt`
- `user_auto_script.py`（你的真实硬件对接逻辑）

迁移后只需要改 `app/config/settings.yaml` 中的主机地址和端口，无需改代码路径。
