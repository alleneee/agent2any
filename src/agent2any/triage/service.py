import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anthropic

from ..config import get_settings
from .prompts import TOOL_NAME_TO_CLIENT, TRIAGE_SYSTEM_PROMPT, TRIAGE_TOOLS

logger = logging.getLogger(__name__)


@dataclass
class TriageResult:
    action: str  # "direct" | "cli"
    client_type: str  # "claude" | "codex" | "gemini"
    task: str
    stream: AsyncIterator[str] | None = None


class TriageService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.triage_api_key,
            base_url=settings.triage_base_url,
            timeout=30.0,
        )
        self._model = settings.triage_model

    async def handle(self, message: str) -> TriageResult:
        logger.info("开始分流: %s", message[:100])

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=TRIAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            tools=TRIAGE_TOOLS,
        )

        for block in response.content:
            if block.type == "tool_use":
                client_type = TOOL_NAME_TO_CLIENT.get(block.name, "claude")
                input_data = block.input if isinstance(block.input, dict) else {}
                task = input_data.get("task", message)
                logger.info("分流结果: cli -> %s", client_type)
                return TriageResult(
                    action="cli",
                    client_type=client_type,
                    task=task,
                )

        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        full_text = "".join(text_parts)
        logger.info("分流结果: direct")

        async def _stream_text() -> AsyncIterator[str]:
            yield full_text

        return TriageResult(
            action="direct",
            client_type="",
            task=message,
            stream=_stream_text(),
        )

