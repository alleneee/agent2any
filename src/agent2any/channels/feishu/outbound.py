import json
import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 4000

STREAMING_CARD_TEMPLATE = {
    "type": "template",
    "data": {
        "template_id": "",
        "template_variable": {"content": ""},
    },
}


class FeishuOutbound:
    def __init__(self, client: lark.Client):
        self._client = client

    async def send_text(
        self, chat_id: str, text: str, reply_to: str = ""
    ) -> str | None:
        if reply_to:
            return await self._reply_message(reply_to, text)

        chunks = [text[i : i + MAX_TEXT_LENGTH] for i in range(0, len(text), MAX_TEXT_LENGTH)]
        last_msg_id = None
        for chunk in chunks:
            body = CreateMessageRequestBody.builder().receive_id(
                chat_id
            ).msg_type(
                "text"
            ).content(
                json.dumps({"text": chunk})
            ).build()

            request = CreateMessageRequest.builder().receive_id_type(
                "chat_id"
            ).request_body(
                body
            ).build()

            response = await self._client.im.v1.message.acreate(request)
            if response.success():
                last_msg_id = response.data.message_id
            else:
                logger.error("发送消息失败: code=%s, msg=%s", response.code, response.msg)

        return last_msg_id

    async def _reply_message(self, message_id: str, text: str) -> str | None:
        body = ReplyMessageRequestBody.builder().msg_type(
            "text"
        ).content(
            json.dumps({"text": text})
        ).build()

        request = ReplyMessageRequest.builder().message_id(
            message_id
        ).request_body(
            body
        ).build()

        response = await self._client.im.v1.message.areply(request)
        if response.success():
            return response.data.message_id
        logger.error("回复消息失败: code=%s, msg=%s", response.code, response.msg)
        return None

    async def create_streaming_card(self, chat_id: str, reply_to: str = "") -> str | None:
        card_content = json.dumps({
            "config": {"wide_screen_mode": True},
            "elements": [
                {"tag": "markdown", "content": "..."}
            ],
        })

        if reply_to:
            body = ReplyMessageRequestBody.builder().msg_type(
                "interactive"
            ).content(
                card_content
            ).build()
            request = ReplyMessageRequest.builder().message_id(
                reply_to
            ).request_body(
                body
            ).build()
            response = await self._client.im.v1.message.areply(request)
        else:
            body = CreateMessageRequestBody.builder().receive_id(
                chat_id
            ).msg_type(
                "interactive"
            ).content(
                card_content
            ).build()
            request = CreateMessageRequest.builder().receive_id_type(
                "chat_id"
            ).request_body(
                body
            ).build()
            response = await self._client.im.v1.message.acreate(request)

        if response.success():
            return response.data.message_id
        logger.error("创建流式卡片失败: code=%s, msg=%s", response.code, response.msg)
        return None

    async def update_streaming_card(
        self, message_id: str, text: str, done: bool = False
    ) -> bool:
        suffix = "" if done else "\n\n..."
        card_content = json.dumps({
            "config": {"wide_screen_mode": True},
            "elements": [
                {"tag": "markdown", "content": text + suffix}
            ],
        })

        body = PatchMessageRequestBody.builder().content(card_content).build()
        request = PatchMessageRequest.builder().message_id(
            message_id
        ).request_body(
            body
        ).build()

        response = await self._client.im.v1.message.apatch(request)
        if not response.success():
            logger.error("更新卡片失败: code=%s, msg=%s", response.code, response.msg)
            return False
        return True
