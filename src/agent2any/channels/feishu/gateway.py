import asyncio
import json
import logging
import threading
from collections.abc import Callable, Coroutine
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from ..models import ConversationType, InboundMessage, MessageType, Sender
from .config import FeishuChannelConfig

logger = logging.getLogger(__name__)

InboundCallback = Callable[[InboundMessage], Coroutine[Any, Any, None]]


class FeishuGateway:
    def __init__(self, channel_id: str, config: FeishuChannelConfig):
        self._channel_id = channel_id
        self._config = config
        self._callback: InboundCallback | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None

        self._lark_client = lark.Client.builder().app_id(
            config.app_id
        ).app_secret(
            config.app_secret
        ).log_level(
            lark.LogLevel.WARNING
        ).build()

        self._event_handler = (
            lark.EventDispatcherHandler.builder(
                config.encrypt_key, config.verification_token
            )
            .register_p2_im_message_receive_v1(self._on_message_receive)
            .build()
        )

    @property
    def lark_client(self) -> lark.Client:
        return self._lark_client

    @property
    def event_handler(self) -> lark.EventDispatcherHandler:
        return self._event_handler

    def set_callback(self, callback: InboundCallback) -> None:
        self._callback = callback

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._config.connection_mode == "websocket":
            self._start_websocket()
        logger.info("飞书网关已启动 (mode=%s)", self._config.connection_mode)

    async def stop(self) -> None:
        logger.info("飞书网关已停止")

    def _start_websocket(self) -> None:
        def _run():
            import lark_oapi.ws.client as ws_module

            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)
            ws_module.loop = thread_loop

            ws_client = lark.ws.Client(
                self._config.app_id,
                self._config.app_secret,
                event_handler=self._event_handler,
                log_level=lark.LogLevel.WARNING,
            )
            ws_client.start()

        self._ws_thread = threading.Thread(target=_run, daemon=True, name="feishu-ws")
        self._ws_thread.start()
        logger.info("飞书 WebSocket 守护线程已启动")

    def handle_webhook_event(self, request_body: bytes, headers: dict[str, str]) -> str:
        from lark_oapi.adapter.starlette import parse_req as starlette_parse_req

        req = starlette_parse_req(request_body, headers)
        resp = lark.EventDispatcherHandler.do_handle(self._event_handler, req)
        return resp.body

    def _on_message_receive(self, data: P2ImMessageReceiveV1) -> None:
        try:
            event = data.event
            message = event.message
            sender = event.sender

            content_str = message.content or "{}"
            content_data = json.loads(content_str)
            text = content_data.get("text", "")

            chat_type = message.chat_type
            conv_type = (
                ConversationType.PRIVATE if chat_type == "p2p" else ConversationType.GROUP
            )

            mentioned = False
            if message.mentions:
                mention_keys = []
                for m in message.mentions:
                    mention_keys.append(m.key)
                    if m.id and m.id.user_id:
                        pass
                mentioned = True
                for mk in mention_keys:
                    text = text.replace(mk, "").strip()

            if not text:
                return

            sender_id = ""
            sender_name = ""
            if sender and sender.sender_id:
                sender_id = sender.sender_id.open_id or ""
            if sender:
                sender_name = sender.sender_type or ""

            inbound = InboundMessage(
                channel_id=self._channel_id,
                message_id=message.message_id,
                conversation_id=message.chat_id,
                conversation_type=conv_type,
                sender=Sender(id=sender_id, name=sender_name, platform="feishu"),
                content=text,
                message_type=MessageType.TEXT,
                mentioned=mentioned,
                raw_event=data.raw if hasattr(data, "raw") else {},
            )

            if self._callback and self._loop:
                asyncio.run_coroutine_threadsafe(self._callback(inbound), self._loop)

        except Exception:
            logger.exception("处理飞书消息事件失败")
