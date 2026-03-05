import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..connections import (
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
    create_connection,
)
from ..exceptions import SessionNotFoundError


@dataclass
class Agent:
    client_type: ClientType | str = ClientType.CLAUDE
    cwd: str = "."
    system_prompt: str = ""
    max_turns: int = 10
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _connection: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.client_type, str):
            self.client_type = ClientType(self.client_type.lower())

    def _get_connection(self):
        if self._connection is None:
            config = ConnectionConfig(
                cwd=self.cwd,
                system_prompt=self.system_prompt,
                max_turns=self.max_turns,
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
            )
            self._connection = create_connection(self.client_type, config)
        return self._connection

    async def send_prompt(self, prompt: str) -> str:
        conn = self._get_connection()
        return await conn.send_prompt(prompt)

    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        conn = self._get_connection()
        async for chunk in conn.send_prompt_stream(prompt):
            yield chunk

    async def stop(self) -> None:
        if self._connection is not None:
            await self._connection.stop()
            self._connection = None


@dataclass
class ClaudeAgent(Agent):
    client_type: ClientType | str = field(default=ClientType.CLAUDE)
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] = field(default_factory=list)


@dataclass
class CodexAgent(Agent):
    client_type: ClientType | str = field(default=ClientType.CODEX)


@dataclass
class GeminiAgent(Agent):
    client_type: ClientType | str = field(default=ClientType.GEMINI)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Agent] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str, factory) -> Agent:
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = factory()
            return self._sessions[session_id]

    def get(self, session_id: str) -> Agent:
        agent = self._sessions.get(session_id)
        if agent is None:
            raise SessionNotFoundError(session_id)
        return agent

    async def delete(self, session_id: str) -> None:
        agent = self._sessions.pop(session_id, None)
        if agent is None:
            raise SessionNotFoundError(session_id)
        await agent.stop()

    def list_all(self) -> dict[str, Agent]:
        return dict(self._sessions)

    async def cleanup(self) -> None:
        for agent in self._sessions.values():
            await agent.stop()
        self._sessions.clear()
