import logging
import time
from collections.abc import AsyncIterator

from ..base import BaseChannel
from ..models import OutboundMessage
from .config import FeishuChannelConfig
from .gateway import FeishuGateway
from .outbound import FeishuOutbound

logger = logging.getLogger(__name__)

THROTTLE_INTERVAL = 0.5


class FeishuChannel(BaseChannel):
    def __init__(self, config: FeishuChannelConfig, channel_id: str = "feishu"):
        super().__init__()
        self._config = config
        self._id = channel_id
        self._gateway = FeishuGateway(channel_id, config)
        self._outbound = FeishuOutbound(self._gateway.lark_client)

    @property
    def channel_id(self) -> str:
        return self._id

    @property
    def platform(self) -> str:
        return "feishu"

    async def start(self) -> None:
        self._gateway.set_callback(self._dispatch_inbound)
        await self._gateway.start()
        logger.info("飞书 channel [%s] 已启动", self._id)

    async def stop(self) -> None:
        await self._gateway.stop()
        logger.info("飞书 channel [%s] 已停止", self._id)

    async def send(self, message: OutboundMessage) -> None:
        await self._outbound.send_text(
            chat_id=message.conversation_id,
            text=message.content,
            reply_to=message.reply_to_message_id,
        )

    async def send_streaming(
        self,
        conversation_id: str,
        reply_to_message_id: str,
        chunks: AsyncIterator[str],
    ) -> None:
        if not self._config.streaming_card:
            full_text = ""
            async for chunk in chunks:
                full_text += chunk
            await self._outbound.send_text(
                chat_id=conversation_id,
                text=full_text,
                reply_to=reply_to_message_id,
            )
            return

        card_msg_id = await self._outbound.create_streaming_card(
            chat_id=conversation_id,
            reply_to=reply_to_message_id,
        )
        if not card_msg_id:
            full_text = ""
            async for chunk in chunks:
                full_text += chunk
            await self._outbound.send_text(
                chat_id=conversation_id,
                text=full_text,
                reply_to=reply_to_message_id,
            )
            return

        accumulated = ""
        last_update = 0.0

        async for chunk in chunks:
            accumulated += chunk
            now = time.monotonic()
            if now - last_update >= THROTTLE_INTERVAL:
                await self._outbound.update_streaming_card(card_msg_id, accumulated)
                last_update = now

        await self._outbound.update_streaming_card(card_msg_id, accumulated, done=True)
