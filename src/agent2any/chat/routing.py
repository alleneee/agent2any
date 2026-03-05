import logging
import os
from dataclasses import dataclass

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

from ..config import get_settings
from ..connections import ClientType

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """你是任务路由器。根据任务选择最合适的客户端。

客户端优势：
- claude: 复杂代码架构、代码审查、安全分析、长文档、复杂推理、多步骤规划
- codex: 代码补全、代码转换、简单脚本、API示例、快速代码片段
- gemini: 图像视频理解、通用问答、创意内容、数据可视化、实时查询

只返回JSON：{"client_type":"claude|codex|gemini","task":"任务描述"}"""


@dataclass
class RoutingResult:
    client_type: ClientType
    task: str
    reason: str


class TaskRouter:
    def __init__(self, api_key: str = ""):
        settings = get_settings()
        self._api_key = api_key or settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self._model_name = settings.router_model
        self._agent: ReActAgent | None = None

    def _ensure_agent(self) -> ReActAgent:
        if self._agent is None:
            if not self._api_key:
                raise ValueError("DashScope API key 未配置，请设置 A2A_DASHSCOPE_API_KEY 或 DASHSCOPE_API_KEY")

            model = DashScopeChatModel(
                model_name=self._model_name,
                api_key=self._api_key,
                stream=False,
            )

            self._agent = ReActAgent(
                name="TaskRouter",
                sys_prompt=ROUTER_SYSTEM_PROMPT,
                model=model,
                formatter=DashScopeChatFormatter(),
                memory=InMemoryMemory(),
                max_iters=1,
            )
        return self._agent

    async def route(self, prompt: str) -> RoutingResult:
        agent = self._ensure_agent()
        logger.info(f"路由任务: {prompt[:100]}...")

        msg = Msg("user", prompt, role="user")
        response = await agent(msg)
        raw = response.get_text_content()
        logger.debug(f"路由响应: {raw}")

        return self._parse_response(raw, prompt)

    def _parse_response(self, raw: str, original_prompt: str) -> RoutingResult:
        import json

        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            client_str = data.get("client_type", "claude").lower()
            if client_str not in ("claude", "codex", "gemini"):
                client_str = "claude"

            return RoutingResult(
                client_type=ClientType(client_str),
                task=data.get("task", original_prompt),
                reason="",
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"路由响应解析失败: {e}, raw: {raw}")
            return RoutingResult(
                client_type=ClientType.CLAUDE,
                task=original_prompt,
                reason="",
            )


_router_instance: TaskRouter | None = None


def get_router(api_key: str = "") -> TaskRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = TaskRouter(api_key)
    return _router_instance


async def route_task(prompt: str, api_key: str = "") -> RoutingResult:
    router = get_router(api_key)
    return await router.route(prompt)
