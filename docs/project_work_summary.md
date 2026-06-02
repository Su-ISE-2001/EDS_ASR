# 语音驱动 EDS 采集项目工作总结

## 项目链接与演示

- 主项目仓库（ASR + Web + 执行链路）：[Su-ISE-2001/EDS_ASR](https://github.com/Su-ISE-2001/EDS_ASR.git)
- 4090 云端 NLU 仓库：[Su-ISE-2001/NLU](https://github.com/Su-ISE-2001/NLU.git)
- 演示视频（预留，后续替换）：[Demo Video Placeholder](https://example.com/demo-video)

## 1. 项目目标

本项目围绕电镜场景，建设“语音输入 -> 参数理解 -> 自动采集执行”的可用链路，优先满足近期核心需求：

- 近场语音交互可用（录音、识别、参数确认、执行）。
- 在无公网条件下支持局域网 ASR 服务部署。
- 将识别文本转为结构化参数并传入 Python 采集函数。
- 为后续远场无线麦、多轮对话、LLM 深度理解预留扩展能力。

## 2. 当前系统架构

- **前端层**
  - 桌面端（PyQt，历史实现）
  - Web 端（当前主用，便于迁移部署）
- **语音层**
  - 本地录音（设备可选、实时电平显示）
  - ASR 服务（局域网 HTTP，支持本机先跑通再迁移）
- **语义层**
  - 规则解析 + LLM 解析（`llm_first` / `rule_first`）
  - 云端返回 `slots`，本地归一化为 `tcp_phase_analysis` 参数
- **执行层**
  - 将参数传入 `user_auto_script.py`
  - 当前已支持直接调用 `tcp_phase_analysis(...)`

## 3. 已完成功能清单

### 3.1 录音与设备能力

- 录音开始/结束流程稳定。
- 支持输入设备枚举与切换。
- 支持录音时全程电平显示。
- 修复了常见 `DirectSound` 打开失败问题，增加采样率回退策略与可读错误提示。

### 3.2 ASR 能力

- 已完成 ASR 客户端与服务端联调（HTTP 接口）。
- 支持 ASR 文本后处理：
  - 去口头词
  - 术语归一化
  - 中文数字归一化
  - 繁体转简体（避免繁简混出影响后续解析）

### 3.3 NLU 与参数提取

- 完成 ASR 文本到结构化参数的全流程接入。
- 已接入云端 NLU 服务。
- `task_type` 已对齐为 `tcp_phase_analysis`。
- 新增管线接口：`/api/pipeline/asr_to_llm_json`（ASR -> NLU -> JSON）。
- 前端可展示原始 NLU JSON，便于调试 `slots` 抽取。

### 3.4 TCP 参数执行链路

- 前端参数区已统一为 `tcp_phase_analysis` 的 8 个参数：
  - `mag_n`
  - `interval_m`
  - `move_cnt_w`
  - `move_cnt_h`
  - `res_w`
  - `res_h`
  - `dwell`
  - `frames_n`
- 一键 ASR->LLM 后可自动回填上述参数。
- 新增执行接口：`/api/execute_tcp`，可直接调用本地 `tcp_phase_analysis(...)`。
- 新增 `user_auto_script.py` 模板，支持快速替换为真实仪器 API。

### 3.5 文档与可迁移性

- 已重写 `README.md`，避免写死本机绝对路径。
- 配置集中在 `app/config/settings.yaml`，服务地址可按环境替换。
- ASR/NLU 服务支持独立迁移部署。

## 4. 关键问题与处理结果

- **ASR 返回空文本**
  - 增强服务端与客户端容错与提示，定位更直接。
- **GPU/CUDA 依赖问题**
  - 提供 CPU fallback，保证业务可先跑通。
- **LLM 返回空 `slots`**
  - 调整云端输入输出契约与本地解析兼容策略，增加回退逻辑。
- **Web 启动模块路径问题**
  - 优化入口脚本，支持从不同工作目录启动。
- **Windows Git 仓库安全校验与远端地址错误**
  - 给出安全目录处理与远端修正方案，恢复推送流程。

## 5. 当前可运行业务闭环

1. 在 Web 页面录音并完成 ASR。
2. 将识别文本发送到云端 NLU。
3. 云端返回 `slots`，本地归一化并补默认值。
4. 前端展示并允许确认 8 个 TCP 参数。
5. 调用 `/api/execute_tcp`，进入本地 `tcp_phase_analysis(...)` 执行。

## 6. 待办与下一阶段建议

- 接入真实仪器 SDK，替换 `user_auto_script.py` 中的 stub 实现。
- 增加执行前参数合法性与单位一致性校验（业务级规则）。
- 增加端到端回归测试（ASR/NLU/执行全链路）。
- 增加运维能力（健康检查、日志聚合、错误告警）。
- 评估远场无线麦与按键/PTT 事件联动方案（长期需求）。

## 7. 交付结论

当前版本已经完成可演示、可联调、可迁移的 MVP 闭环。  
在不改主架构的前提下，可继续平滑迭代至“远场 + 多轮 + 更强语义理解”的长期目标。
