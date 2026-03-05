from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Callable, Coroutine

from .models import InboundMessage, OutboundMessage

MessageHandler = Callable[[InboundMessage], Coroutine[Any, Any, None]]


class BaseChannel(ABC):
    def __init__(self):
        self._message_handler: MessageHandler | None = None

    @property
    @abstractmethod
    def channel_id(self) -> str:
        ...

    @property
    @abstractmethod
    def platform(self) -> str:
        ...

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        ...

    @abstractmethod
    async def send_streaming(
        self,
        conversation_id: str,
        reply_to_message_id: str,
        chunks: AsyncIterator[str],
    ) -> None:
        ...

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._message_handler = handler

    async def _dispatch_inbound(self, message: InboundMessage) -> None:
        if self._message_handler is not None:
            await self._message_handler(message)
