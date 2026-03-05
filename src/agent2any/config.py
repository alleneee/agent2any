from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = {"env_prefix": "A2A_", "env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]
    gemini_api_key: str = ""
    default_max_turns: int = 10
    default_cwd: str = str(Path.home())
    cwd_claude: str = str(Path.home())
    cwd_codex: str = str(Path.home())
    cwd_gemini: str = str(Path.home())
    auto_route: bool = False

    feishu_enabled: bool = False
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_connection_mode: Literal["websocket", "webhook"] = "websocket"
    feishu_client_type: str = "claude"
    feishu_streaming_card: bool = True
    feishu_cwd: str = "."
    feishu_max_turns: int = 10

    triage_enabled: bool = False
    triage_api_key: str = ""
    triage_base_url: str = "https://api.minimaxi.com/anthropic"
    triage_model: str = "MiniMax-M2.5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
