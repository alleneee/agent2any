import asyncio
import os
from typing import Any, AsyncIterator

from .base import (
    BaseConnection,
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
)


class GeminiConnection(BaseConnection):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self._client = None
        self._model = None
        self._chat = None

    @property
    def client_type(self) -> ClientType:
        return ClientType.GEMINI

    def _ensure_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("请安装 google-generativeai: pip install google-generativeai")

            api_key = self.config.api_key or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                raise ValueError("Gemini API Key 未配置，请设置 GEMINI_API_KEY 环境变量或提供 api_key")

            genai.configure(api_key=api_key)
            self._client = genai

            model_name = self.config.model or "gemini-2.0-flash"
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }

            system_instruction = self.config.system_prompt if self.config.system_prompt else None

            self._model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                system_instruction=system_instruction,
            )

            self._chat = self._model.start_chat(history=[])

    async def send_prompt(self, prompt: str) -> str:
        self._ensure_client()
        response = await asyncio.to_thread(self._chat.send_message, prompt)
        return response.text

    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        self._ensure_client()
        response = await asyncio.to_thread(self._chat.send_message, prompt, stream=True)

        for chunk in response:
            if chunk.text:
                yield MessageChunk(text=chunk.text, chunk_type="text")

        yield {"type": "result", "stop_reason": "end_turn"}

    async def stop(self) -> None:
        self._chat = None
        self._model = None
        self._client = None
