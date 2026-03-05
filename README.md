# Agent2Any

HTTP API bridge for AI Code CLI, 支持 Claude、Codex、Gemini 多种客户端

## 安装

```bash
uv sync
```

## 快速开始

```bash
uv run uvicorn agent2any.main:app --host 0.0.0.0 --port 8080
```

## 配置

通过环境变量配置，前缀 `A2A_`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `A2A_HOST` | `0.0.0.0` | 监听地址 |
| `A2A_PORT` | `8080` | 监听端口 |
| `A2A_LOG_LEVEL` | `INFO` | 日志级别 |
| `A2A_CORS_ORIGINS` | `["*"]` | CORS 允许的源 |
| `A2A_GEMINI_API_KEY` | `""` | Gemini API Key |
| `A2A_DEFAULT_MAX_TURNS` | `10` | 默认最大轮数 |
| `A2A_DEFAULT_CWD` | `.` | 默认工作目录 |
| `A2A_CWD_CLAUDE` | `项目目录/claude` | Claude 默认工作目录 |
| `A2A_CWD_CODEX` | `项目目录/codex` | Codex 默认工作目录 |
| `A2A_CWD_GEMINI` | `项目目录/gemini` | Gemini 默认工作目录 |
| `A2A_DASHSCOPE_API_KEY` | `""` | DashScope API Key (智能路由) |
| `A2A_ROUTER_MODEL` | `qwen-max` | 路由模型名称 |
| `A2A_AUTO_ROUTE` | `false` | 全局启用智能路由 |
| `A2A_FEISHU_ENABLED` | `false` | 启用飞书 Channel |
| `A2A_FEISHU_APP_ID` | `""` | 飞书应用 App ID |
| `A2A_FEISHU_APP_SECRET` | `""` | 飞书应用 App Secret |
| `A2A_FEISHU_VERIFICATION_TOKEN` | `""` | 飞书事件验证 Token |
| `A2A_FEISHU_ENCRYPT_KEY` | `""` | 飞书事件加密 Key |
| `A2A_FEISHU_CONNECTION_MODE` | `websocket` | 连接模式 (`websocket`/`webhook`) |
| `A2A_FEISHU_CLIENT_TYPE` | `claude` | 飞书消息使用的 AI 客户端 |
| `A2A_FEISHU_STREAMING_CARD` | `true` | 启用流式卡片回复 |
| `A2A_FEISHU_CWD` | `.` | 飞书 Agent 工作目录 |
| `A2A_FEISHU_MAX_TURNS` | `10` | 飞书 Agent 最大轮数 |
| `A2A_TRIAGE_ENABLED` | `false` | 启用消息分流 |
| `A2A_TRIAGE_API_KEY` | `""` | 分流模型 API Key (MiniMax) |
| `A2A_TRIAGE_BASE_URL` | `https://api.minimaxi.com/anthropic` | 分流模型 API 地址 |
| `A2A_TRIAGE_MODEL` | `MiniMax-M2.5` | 分流模型名称 |

API Key 通过请求头 `X-API-Key` 传递（替代请求体中的 `api_key` 字段）：

```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-gemini-key" \
  -d '{"prompt": "你好", "cwd": "/tmp/test", "client_type": "gemini"}'
```

## 支持的客户端类型

| 类型 | 协议 | 说明 |
|------|------|------|
| `claude` | claude-agent-sdk | Claude Code CLI 官方 SDK |
| `codex` | MCP (JSON-RPC) | Codex CLI `mcp-server` 模式 |
| `gemini` | ACP | Gemini CLI `--experimental-acp` 模式 |

连接策略：

- **Claude**: 使用 `claude-agent-sdk` 官方 SDK
- **Codex**: 通过 MCP 协议连接 `codex mcp-server`
- **Gemini**: 优先使用 ACP 协议连接 CLI，无 CLI 时回退到 `google-generativeai` API SDK
- **其他 ACP 兼容 CLI** (goose, qwen, kimi, auggie, opencode): 通过 ACP 协议统一接入

## API 端点

### 通用对话

#### 发送消息

```bash
# Claude (默认)
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好"}'

# Codex
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好", "cwd": "/tmp/test", "client_type": "codex"}'

# Gemini
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好", "cwd": "/tmp/test", "client_type": "gemini"}'

# 指定模型
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好", "cwd": "/tmp/test", "client_type": "claude", "model": "claude-sonnet-4-5"}'
```

支持的模型示例：

- **Claude**: `claude-sonnet-4-5`, `claude-opus-4-5` 等
- **Gemini**: `gemini-2.0-flash`, `gemini-1.5-pro` 等
- **Codex**: 由 CLI 配置决定

#### 智能路由

基于 agentscope 实现的智能任务路由，使用 qwen-max 模型自动选择最合适的客户端：

```bash
# 方式1: 不指定 client_type，自动路由
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-dashscope-key" \
  -d '{"prompt": "帮我写一个 Python 爬虫"}'

# 方式2: 显式启用 auto_route
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-dashscope-key" \
  -d '{"prompt": "分析这张图片", "auto_route": true}'
```

路由规则：

| 客户端 | 擅长领域 |
|--------|----------|
| **Claude** | 复杂代码编写、代码审查、长文档处理、复杂推理 |
| **Codex** | 代码补全、代码转换、简单脚本、API 示例 |
| **Gemini** | 多模态任务、通用问答、创意内容、数据分析 |

#### 流式发送

```bash
curl -X POST http://localhost:8080/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "介绍 Python", "cwd": "/tmp/test", "client_type": "claude"}'
```

#### 多轮对话

通过 `session_id` 保持对话上下文：

```bash
# 第一轮对话，获取 session_id
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "我的名字是张三", "cwd": "/tmp/test"}'
# 返回: {"session_id": "abc-123", "content": "...", ...}

# 后续对话，传入相同的 session_id
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "我叫什么名字？", "session_id": "abc-123", "cwd": "/tmp/test"}'
# 返回: {"session_id": "abc-123", "content": "你的名字是张三", ...}
```

#### 会话管理

```bash
# 列出所有会话
curl http://localhost:8080/api/v1/sessions

# 查看指定会话
curl http://localhost:8080/api/v1/sessions/{session_id}

# 删除会话
curl -X DELETE http://localhost:8080/api/v1/sessions/{session_id}
```

### 短剧生成工作流

基于 huobao-drama 项目的工作流设计，支持多种 AI 客户端。

#### 工作流步骤

```text
1. 生成大纲 --> 2. 生成剧本 --> 3. 提取角色
       |              |              |
       v              v              v
4. 提取场景 --> 5. 提取道具 --> 6. 生成分镜
       |
       v
7. 生成帧提示词（首帧/关键帧/尾帧）
```

#### 完整工作流

```bash
curl -X POST http://localhost:8080/api/v1/drama/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "theme": "都市霸总爱上灰姑娘",
    "genre": "甜宠",
    "episode_count": 5,
    "client_type": "claude"
  }'
```

返回 SSE 流，包含每个步骤的进度和结果。

#### 分步调用

##### 1. 生成大纲

```bash
curl -X POST http://localhost:8080/api/v1/drama/outline \
  -H "Content-Type: application/json" \
  -d '{
    "theme": "都市霸总爱上灰姑娘",
    "genre": "甜宠",
    "episode_count": 5,
    "client_type": "claude"
  }'
```

##### 2. 生成剧本

```bash
curl -X POST http://localhost:8080/api/v1/drama/episodes \
  -H "Content-Type: application/json" \
  -d '{"project_id": "xxx", "client_type": "claude"}'
```

##### 3. 提取角色

```bash
curl -X POST http://localhost:8080/api/v1/drama/characters \
  -H "Content-Type: application/json" \
  -d '{"project_id": "xxx", "client_type": "claude"}'
```

##### 4. 提取场景

```bash
curl -X POST http://localhost:8080/api/v1/drama/scenes \
  -H "Content-Type: application/json" \
  -d '{"project_id": "xxx", "client_type": "claude"}'
```

##### 5. 提取道具

```bash
curl -X POST http://localhost:8080/api/v1/drama/props \
  -H "Content-Type: application/json" \
  -d '{"project_id": "xxx", "client_type": "claude"}'
```

##### 6. 生成分镜

```bash
curl -X POST http://localhost:8080/api/v1/drama/storyboard \
  -H "Content-Type: application/json" \
  -d '{"project_id": "xxx", "episode_index": 0, "client_type": "claude"}'
```

##### 7. 生成帧提示词

```bash
curl -X POST http://localhost:8080/api/v1/drama/frame-prompt \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "xxx",
    "episode_index": 0,
    "shot_index": 0,
    "frame_type": "first",
    "client_type": "claude"
  }'
```

frame_type 可选：`first`（首帧）、`key`（关键帧）、`last`（尾帧）

#### 查看项目

```bash
curl http://localhost:8080/api/v1/drama/projects
curl http://localhost:8080/api/v1/drama/projects/{project_id}
```

## 风格配置

```json
{
  "style": {
    "default_style": "现代日系动漫风格",
    "default_image_ratio": "16:9",
    "default_video_ratio": "16:9",
    "language": "zh"
  }
}
```

## 消息分流

启用分流后，Channel 收到的消息会先经过 MiniMax 模型判断：简单问题（知识问答、概念解释、闲聊）由 MiniMax 直接流式回答，复杂编码任务才路由到 CLI。

分流关闭或服务异常时自动回退到 CLI 流程，零影响。

```bash
export A2A_TRIAGE_ENABLED=true
export A2A_TRIAGE_API_KEY=your_minimax_api_key
```

数据流：

```text
用户消息 -> Dispatcher._process()
  -> TriageService.triage(message)
      |-- action="direct" -> MiniMax 流式回答
      |-- action="cli"    -> 原有 CLI 流程
```

## Channel 系统

Channel 系统允许将 AI Agent 接入各种消息平台（飞书、Slack 等），
消息平台用户发消息 -> channel 接收并标准化 -> 复用现有 Agent/Connection 层处理 -> channel 将回复投递回平台。

### 飞书接入

1. 在[飞书开放平台](https://open.feishu.cn/)创建应用，获取 App ID 和 App Secret
2. 启用机器人能力，配置消息接收权限（`im:message`、`im:message.receive_v1`）
3. 配置环境变量并启动：

```bash
export A2A_FEISHU_ENABLED=true
export A2A_FEISHU_APP_ID=your_app_id
export A2A_FEISHU_APP_SECRET=your_app_secret
uv run uvicorn agent2any.main:app --host 0.0.0.0 --port 8080
```

WebSocket 模式（默认）无需配置回调地址，应用启动后自动建立长连接。

Webhook 模式需在飞书开放平台配置回调地址为
`http://your-host:8080/api/v1/channels/feishu/webhook`，并设置：

```bash
export A2A_FEISHU_CONNECTION_MODE=webhook
export A2A_FEISHU_VERIFICATION_TOKEN=your_token
export A2A_FEISHU_ENCRYPT_KEY=your_key
```

### Channel 管理 API

```bash
# 列出所有已注册 channel
curl http://localhost:8080/api/v1/channels
```

### 添加新 Channel

1. 在 `channels/` 下创建新目录（如 `slack/`）
2. 实现 `BaseChannel` 抽象类
3. 在 `main.py` 的 `lifespan` 中注册新 channel

数据流：

```text
消息平台用户发消息
  -> Channel Gateway 接收原始事件
    -> 标准化为 InboundMessage
      -> MessageDispatcher.handle_inbound()
        -> SessionManager.get_or_create()
          -> Agent.send_prompt_stream()
            -> Channel.send_streaming()
平台用户看到流式回复
```

## 项目结构

```text
src/agent2any/
├── main.py             # FastAPI 入口 (lifespan, CORS, exception handlers)
├── config.py           # pydantic-settings 配置管理
├── exceptions.py       # 统一异常体系
├── logging.py          # 日志配置
├── connections/        # AI 客户端连接层
│   ├── base.py         # 抽象基类 + 数据模型
│   ├── claude.py       # Claude (claude-agent-sdk)
│   ├── codex.py        # Codex (MCP JSON-RPC)
│   ├── acp.py          # ACP 协议 (gemini, goose, kimi, ...)
│   ├── gemini.py       # Gemini (google-generativeai API 回退)
│   └── factory.py      # 连接工厂
├── channels/           # Channel 消息平台接入层
│   ├── base.py         # BaseChannel 抽象基类
│   ├── models.py       # InboundMessage, OutboundMessage 统一消息模型
│   ├── registry.py     # ChannelManager 注册表 + 生命周期
│   ├── dispatcher.py   # MessageDispatcher 入站消息桥接
│   ├── router.py       # Channel API 路由 (webhook + 管理)
│   ├── dependencies.py # FastAPI DI
│   └── feishu/         # 飞书实现
│       ├── config.py   # FeishuChannelConfig
│       ├── gateway.py  # WebSocket/Webhook 双模网关
│       ├── outbound.py # 消息发送 + 流式卡片
│       └── channel.py  # FeishuChannel 整合
├── triage/             # 消息分流模块
│   ├── __init__.py     # 导出 TriageService, TriageResult
│   ├── prompts.py      # 分流与回答系统提示词
│   └── service.py      # TriageService 分流判断与流式回答
├── chat/               # 通用对话模块
│   ├── router.py       # API 路由
│   ├── schemas.py      # 请求/响应模型
│   ├── service.py      # Agent + SessionManager
│   ├── routing.py      # 智能路由 (agentscope + qwen-max)
│   └── dependencies.py # FastAPI DI
└── drama/              # 短剧工作流模块
    ├── router.py       # API 路由
    ├── schemas.py      # 请求模型
    ├── service.py      # DramaService
    ├── models.py       # DramaProject, WorkflowStep
    ├── dependencies.py # DramaServiceManager + DI
    └── prompts.py      # 提示词模板
```

## 架构

```text
HTTP Client --> FastAPI (main.py)
                  |
                  +-- chat/router --> Agent --> connections/factory
                  |                                 |
                  +-- drama/router --> DramaService -+
                  |                                  |
                  +-- channels/router (webhook)      |
                  |                                  |
                  +-- ChannelManager                 |
                       |                             |
                       +-- FeishuChannel --> MessageDispatcher
                       |   (WebSocket/Webhook)       |
                       +-- [SlackChannel]       SessionManager --> Agent
                       +-- [更多 Channel]                          |
                                                    +-- connections/claude
                                                    +-- connections/codex
                                                    +-- connections/acp
                                                    +-- connections/gemini
```

## 前置要求

- Python 3.11+
- Claude Code CLI 已安装并完成认证（使用 claude 客户端时）
- Codex CLI 已安装并完成认证（使用 codex 客户端时）
- Gemini CLI 已安装并完成认证（使用 gemini 客户端时）

## 开发

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
```

## 许可证

MIT
