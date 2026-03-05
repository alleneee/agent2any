from typing import Any, AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from .base import (
    BaseConnection,
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
)


class ClaudeConnection(BaseConnection):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.allowed_tools: list[str] = []
        self.permission_mode: str = "acceptEdits"
        self._client: ClaudeSDKClient | None = None

    @property
    def client_type(self) -> ClientType:
        return ClientType.CLAUDE

    def _build_options(self) -> ClaudeAgentOptions:
        opts = ClaudeAgentOptions(
            cwd=self.config.cwd,
            max_turns=self.config.max_turns,
            permission_mode=self.permission_mode,
        )
        if self.config.system_prompt:
            opts.system_prompt = self.config.system_prompt
        if self.config.model:
            opts.model = self.config.model
        if self.allowed_tools:
            opts.allowed_tools = self.allowed_tools
        return opts

    async def _ensure_client(self) -> ClaudeSDKClient:
        if self._client is None:
            options = self._build_options()
            self._client = ClaudeSDKClient(options=options)
            await self._client.__aenter__()
        return self._client

    async def send_prompt(self, prompt: str) -> str:
        client = await self._ensure_client()
        await client.query(prompt)
        result_parts: list[str] = []

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_parts.append(block.text)

        return "".join(result_parts)

    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        client = await self._ensure_client()
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield MessageChunk(text=block.text, chunk_type="text")
                    elif isinstance(block, ToolUseBlock):
                        yield ToolCallInfo(
                            tool_name=block.name,
                            tool_id=block.id,
                            input_data=block.input if isinstance(block.input, dict) else {},
                        )
                    elif isinstance(block, ToolResultBlock):
                        content = block.content
                        if isinstance(content, str):
                            output_text = content
                        elif isinstance(content, list):
                            output_text = "\n".join(
                                item.text if hasattr(item, "text") else str(item) for item in content
                            )
                        else:
                            output_text = str(content) if content else ""

                        yield ToolCallInfo(
                            tool_name="tool_result",
                            tool_id=block.tool_use_id,
                            output=output_text,
                            is_error=block.is_error if hasattr(block, "is_error") else False,
                        )

            elif isinstance(message, ResultMessage):
                yield {
                    "type": "result",
                    "stop_reason": message.stop_reason if hasattr(message, "stop_reason") else None,
                    "total_cost_usd": message.total_cost_usd if hasattr(message, "total_cost_usd") else None,
                }

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
