import shutil

from .acp import ACP_BACKENDS, AcpConnection
from .base import BaseConnection, ClientType, ConnectionConfig
from .claude import ClaudeConnection
from .codex import CodexConnection
from .gemini import GeminiConnection

ACP_ONLY_BACKENDS = {
    k for k in ACP_BACKENDS if k not in ("claude", "codex")
}


def create_connection(
    client_type: ClientType | str,
    config: ConnectionConfig | None = None,
    **kwargs,
) -> BaseConnection:
    if isinstance(client_type, str):
        client_type = ClientType(client_type.lower())

    if config is None:
        config = ConnectionConfig(**kwargs)

    backend = client_type.value

    if client_type == ClientType.CLAUDE:
        return ClaudeConnection(config)

    if client_type == ClientType.CODEX:
        return CodexConnection(config)

    if client_type == ClientType.GEMINI:
        if shutil.which("gemini"):
            return AcpConnection(config, backend="gemini")
        return GeminiConnection(config)

    if backend in ACP_ONLY_BACKENDS:
        return AcpConnection(config, backend=backend)

    raise ValueError(f"不支持的客户端类型: {client_type}")
