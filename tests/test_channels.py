"""
Channel 系统单元测试
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent2any.channels.base import BaseChannel
from agent2any.channels.dispatcher import MessageDispatcher
from agent2any.channels.models import (
    ConversationType,
    InboundMessage,
    MessageType,
    OutboundMessage,
    Sender,
)
from agent2any.channels.registry import ChannelManager
from agent2any.channels.router import router as channel_router


class FakeChannel(BaseChannel):
    def __init__(self, cid: str = "fake"):
        super().__init__()
        self._cid = cid
        self.started = False
        self.stopped = False
        self.sent_messages: list[OutboundMessage] = []
        self.streaming_calls: list[dict] = []

    @property
    def channel_id(self) -> str:
        return self._cid

    @property
    def platform(self) -> str:
        return "fake"

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, message: OutboundMessage) -> None:
        self.sent_messages.append(message)

    async def send_streaming(
        self,
        conversation_id: str,
        reply_to_message_id: str,
        chunks: AsyncIterator[str],
    ) -> None:
        text = ""
        async for chunk in chunks:
            text += chunk
        self.streaming_calls.append({
            "conversation_id": conversation_id,
            "reply_to": reply_to_message_id,
            "text": text,
        })


def _make_inbound(channel_id: str = "fake", msg_id: str = "msg-1") -> InboundMessage:
    return InboundMessage(
        channel_id=channel_id,
        message_id=msg_id,
        conversation_id="chat-123",
        conversation_type=ConversationType.PRIVATE,
        sender=Sender(id="user-1", name="Test", platform="fake"),
        content="hello",
        message_type=MessageType.TEXT,
    )


@pytest.fixture
def client():
    @asynccontextmanager
    async def _lifespan(a: FastAPI):
        a.state.channel_manager = ChannelManager()
        yield

    test_app = FastAPI(lifespan=_lifespan)
    test_app.include_router(channel_router, prefix="/api/v1")
    with TestClient(test_app) as c:
        yield c


class TestChannelManager:
    def test_register_and_get(self):
        mgr = ChannelManager()
        ch = FakeChannel("test-1")
        mgr.register(ch)
        assert mgr.get("test-1") is ch

    def test_register_duplicate_raises(self):
        mgr = ChannelManager()
        ch = FakeChannel("dup")
        mgr.register(ch)
        with pytest.raises(ValueError, match="已注册"):
            mgr.register(FakeChannel("dup"))

    def test_get_unknown_returns_none(self):
        mgr = ChannelManager()
        assert mgr.get("nope") is None

    def test_list_all(self):
        mgr = ChannelManager()
        mgr.register(FakeChannel("a"))
        mgr.register(FakeChannel("b"))
        assert set(mgr.list_all().keys()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_start_and_stop_all(self):
        mgr = ChannelManager()
        ch = FakeChannel("x")
        mgr.register(ch)
        handler = AsyncMock()
        await mgr.start_all(handler)
        assert ch.started
        assert ch._message_handler is handler
        await mgr.stop_all()
        assert ch.stopped


class TestMessageDispatcher:
    @pytest.mark.asyncio
    async def test_dedup(self):
        from agent2any.chat.service import SessionManager

        sm = SessionManager()
        cm = ChannelManager()
        ch = FakeChannel("fake")
        cm.register(ch)

        dispatcher = MessageDispatcher(sm, cm)

        assert not dispatcher._is_duplicate("dup-1")
        assert dispatcher._is_duplicate("dup-1")

    @pytest.mark.asyncio
    async def test_unknown_channel_skipped(self):
        from agent2any.chat.service import SessionManager

        sm = SessionManager()
        cm = ChannelManager()
        dispatcher = MessageDispatcher(sm, cm)

        await dispatcher.handle_inbound(_make_inbound(channel_id="unknown"))


class TestModels:
    def test_inbound_message_creation(self):
        msg = _make_inbound()
        assert msg.channel_id == "fake"
        assert msg.content == "hello"
        assert msg.conversation_type == ConversationType.PRIVATE

    def test_outbound_message_creation(self):
        msg = OutboundMessage(
            channel_id="fake",
            conversation_id="chat-1",
            content="hi",
        )
        assert msg.reply_to_message_id == ""

    def test_conversation_type_enum(self):
        assert ConversationType.PRIVATE.value == "private"
        assert ConversationType.GROUP.value == "group"


class TestChannelAPI:
    def test_list_channels(self, client):
        response = client.get("/api/v1/channels")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_webhook_unknown_channel(self, client):
        response = client.post(
            "/api/v1/channels/nonexistent/webhook",
            content=b"{}",
        )
        assert response.status_code == 404
