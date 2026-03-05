from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class ClientType(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"


@dataclass
class MessageChunk:
    text: str
    chunk_type: str = "text"


@dataclass
class ToolCallInfo:
    tool_name: str
    tool_id: str
    input_data: dict = field(default_factory=dict)
    output: str | None = None
    is_error: bool = False


@dataclass
class ConnectionConfig:
    cwd: str = "."
    system_prompt: str = ""
    max_turns: int = 10
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class BaseConnection(ABC):
    def __init__(self, config: ConnectionConfig):
        self.config = config

    @abstractmethod
    async def send_prompt(self, prompt: str) -> str:
        pass

    @abstractmethod
    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @property
    @abstractmethod
    def client_type(self) -> ClientType:
        pass
