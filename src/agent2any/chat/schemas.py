from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="用户提示")
    session_id: str | None = Field(None, description="会话 ID")
    cwd: str = Field(".", description="工作目录")
    instructions: str = Field("", description="任务指令/上下文")
    allowed_tools: list[str] = Field(default_factory=list, description="允许的工具列表")
    max_turns: int = Field(10, description="最大轮数")
    client_type: Literal["claude", "codex", "gemini"] | None = Field(None, description="客户端类型，为空时自动路由")
    model: str = Field("", description="模型名称")
    auto_route: bool = Field(False, description="强制启用智能路由")


class ChatResponse(BaseModel):
    session_id: str
    content: str
    client_type: str
    cost_usd: float | None = None


class SessionInfo(BaseModel):
    session_id: str
    cwd: str
    client_type: str
