from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversationType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    RICH_TEXT = "rich_text"


class Sender(BaseModel):
    id: str
    name: str = ""
    platform: str = ""


class InboundMessage(BaseModel):
    channel_id: str
    message_id: str
    conversation_id: str
    conversation_type: ConversationType
    sender: Sender
    content: str
    message_type: MessageType = MessageType.TEXT
    mentioned: bool = False
    raw_event: dict[str, Any] = Field(default_factory=dict)


class OutboundMessage(BaseModel):
    channel_id: str
    conversation_id: str
    reply_to_message_id: str = ""
    content: str
