from typing import Literal

from pydantic import BaseModel


class FeishuChannelConfig(BaseModel):
    app_id: str
    app_secret: str
    encrypt_key: str = ""
    verification_token: str = ""
    connection_mode: Literal["websocket", "webhook"] = "websocket"
    client_type: str = "claude"
    streaming_card: bool = True
    cwd: str = "."
    max_turns: int = 10
