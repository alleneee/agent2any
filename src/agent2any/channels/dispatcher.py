import asyncio
import logging
import time

from ..chat.service import Agent, ClaudeAgent, CodexAgent, GeminiAgent, SessionManager
from ..config import get_settings
from ..connections import ClientType, MessageChunk, ToolCallInfo
from .base import BaseChannel
from .models import InboundMessage
from .registry import ChannelManager

logger = logging.getLogger(__name__)

TTL_SECONDS = 60


class MessageDispatcher:
    def __init__(self, session_manager: SessionManager, channel_manager: ChannelManager):
        self._session_manager = session_manager
        self._channel_manager = channel_manager
        self._seen: dict[str, float] = {}

    def _is_duplicate(self, message_id: str) -> bool:
        now = time.monotonic()
        expired = [k for k, v in self._seen.items() if now - v > TTL_SECONDS]
        for k in expired:
            del self._seen[k]
        if message_id in self._seen:
            return True
        self._seen[message_id] = now
        return False

    async def handle_inbound(self, message: InboundMessage) -> None:
        if self._is_duplicate(message.message_id):
            logger.debug("重复消息，跳过: %s", message.message_id)
            return

        channel = self._channel_manager.get(message.channel_id)
        if channel is None:
            logger.warning("未知 channel: %s", message.channel_id)
            return

        asyncio.create_task(self._process(channel, message))

    async def _process(self, channel: BaseChannel, message: InboundMessage) -> None:
        settings = get_settings()

        logger.info("_process 收到消息: channel=%s, msg_id=%s, content=%s",
                    message.channel_id, message.message_id, message.content[:100])

        if settings.triage_enabled and settings.triage_api_key:
            try:
                from ..triage import TriageService

                triage_svc = TriageService()
                action, chunks = await triage_svc.handle(message.content)
                if action == "direct" and chunks is not None:
                    await channel.send_streaming(
                        conversation_id=message.conversation_id,
                        reply_to_message_id=message.message_id,
                        chunks=chunks,
                    )
                    return
            except Exception:
                logger.warning("分流服务异常，回退到CLI", exc_info=True)

        session_id = f"{message.channel_id}:{message.conversation_id}"

        def _factory() -> Agent:
            ct = ClientType.CLAUDE
            cwd = settings.default_cwd
            max_turns = settings.default_max_turns

            if hasattr(channel, "_config"):
                cfg = channel._config
                if hasattr(cfg, "cwd") and cfg.cwd and cfg.cwd != ".":
                    cwd = cfg.cwd
                if hasattr(cfg, "max_turns") and cfg.max_turns:
                    max_turns = cfg.max_turns
                if hasattr(cfg, "client_type") and cfg.client_type:
                    try:
                        ct = ClientType(cfg.client_type)
                    except ValueError:
                        pass

            if ct == ClientType.CLAUDE:
                return ClaudeAgent(cwd=cwd, max_turns=max_turns, session_id=session_id)
            elif ct == ClientType.CODEX:
                return CodexAgent(cwd=cwd, max_turns=max_turns, session_id=session_id)
            else:
                return GeminiAgent(cwd=cwd, max_turns=max_turns, session_id=session_id)

        try:
            agent = await self._session_manager.get_or_create(session_id, _factory)
            await self._process_streaming(channel, agent, message)
        except Exception:
            logger.exception("处理消息失败: %s", message.message_id)

    async def _process_streaming(
        self, channel: BaseChannel, agent: Agent, message: InboundMessage
    ) -> None:
        async def _chunks():
            async for event in agent.send_prompt_stream(message.content):
                if isinstance(event, MessageChunk):
                    yield event.text
                elif isinstance(event, ToolCallInfo):
                    if event.output:
                        yield f"\n[工具 {event.tool_name}]: {event.output}\n"
                elif isinstance(event, dict):
                    text = event.get("text", "")
                    if text:
                        yield text

        try:
            await channel.send_streaming(
                conversation_id=message.conversation_id,
                reply_to_message_id=message.message_id,
                chunks=_chunks(),
            )
        except Exception:
            logger.warning("流式发送失败，回退到非流式", exc_info=True)
            try:
                content = await agent.send_prompt(message.content)
                from .models import OutboundMessage

                await channel.send(
                    OutboundMessage(
                        channel_id=message.channel_id,
                        conversation_id=message.conversation_id,
                        reply_to_message_id=message.message_id,
                        content=content,
                    )
                )
            except Exception:
                logger.exception("非流式发送也失败: %s", message.message_id)
