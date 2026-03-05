import logging

from .base import BaseChannel, MessageHandler

logger = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        cid = channel.channel_id
        if cid in self._channels:
            raise ValueError(f"Channel 已注册: {cid}")
        self._channels[cid] = channel
        logger.info("注册 channel: %s (platform=%s)", cid, channel.platform)

    def get(self, channel_id: str) -> BaseChannel | None:
        return self._channels.get(channel_id)

    def list_all(self) -> dict[str, BaseChannel]:
        return dict(self._channels)

    async def start_all(self, message_handler: MessageHandler) -> None:
        for channel in self._channels.values():
            channel.set_message_handler(message_handler)
            await channel.start()
            logger.info("启动 channel: %s", channel.channel_id)

    async def stop_all(self) -> None:
        for channel in self._channels.values():
            try:
                await channel.stop()
                logger.info("停止 channel: %s", channel.channel_id)
            except Exception:
                logger.exception("停止 channel 失败: %s", channel.channel_id)
