import logging
from collections.abc import AsyncIterator
from typing import Literal

import anthropic

from ..config import get_settings
from .prompts import TRIAGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

CLI_SIGNAL = '{"action":"cli"'


class TriageService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.triage_api_key,
            base_url=settings.triage_base_url,
            timeout=30.0,
        )
        self._model = settings.triage_model

    async def handle(
        self, message: str
    ) -> tuple[Literal["direct", "cli"], AsyncIterator[str] | None]:
        logger.info("开始分流: %s", message[:100])
        manager = self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=TRIAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        stream = await manager.__aenter__()

        buffer = ""
        is_cli = False

        async for text in stream.text_stream:
            buffer += text
            if len(buffer.lstrip()) >= len(CLI_SIGNAL):
                if buffer.lstrip().startswith(CLI_SIGNAL):
                    is_cli = True
                break

        if is_cli:
            await manager.__aexit__(None, None, None)
            logger.info("分流结果: cli")
            return ("cli", None)

        logger.info("分流结果: direct")

        async def _stream_remaining() -> AsyncIterator[str]:
            try:
                yield buffer
                async for remaining in stream.text_stream:
                    yield remaining
            finally:
                await manager.__aexit__(None, None, None)

        return ("direct", _stream_remaining())
