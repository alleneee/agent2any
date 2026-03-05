import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .base import (
    BaseConnection,
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
)

JSONRPC_VERSION = "2.0"

ACP_BACKENDS: dict[str, dict[str, Any]] = {
    "claude": {
        "command": "npx",
        "args": ["@zed-industries/claude-code-acp"],
        "detect_cmd": "claude",
    },
    "codex": {
        "command": "codex",
        "args": ["--experimental-acp"],
        "detect_cmd": "codex",
    },
    "gemini": {
        "command": "gemini",
        "args": ["--experimental-acp"],
        "detect_cmd": "gemini",
    },
    "goose": {
        "command": "goose",
        "args": ["acp"],
        "detect_cmd": "goose",
    },
    "qwen": {
        "command": "npx",
        "args": ["@qwen-code/qwen-code", "--experimental-acp"],
        "detect_cmd": "npx",
    },
    "kimi": {
        "command": "kimi",
        "args": ["--acp"],
        "detect_cmd": "kimi",
    },
    "opencode": {
        "command": "opencode",
        "args": ["acp"],
        "detect_cmd": "opencode",
    },
    "auggie": {
        "command": "auggie",
        "args": ["--acp"],
        "detect_cmd": "auggie",
    },
}


@dataclass
class AcpSessionUpdate:
    update_type: str
    content: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    tool_status: str = ""
    raw: dict = field(default_factory=dict)


class AcpConnection(BaseConnection):
    def __init__(self, config: ConnectionConfig, backend: str = "claude"):
        super().__init__(config)
        self.backend = backend
        self.process: asyncio.subprocess.Process | None = None
        self.session_id: str | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self._updates: asyncio.Queue[AcpSessionUpdate] = asyncio.Queue()
        self._initialized = False

    @property
    def client_type(self) -> ClientType:
        return ClientType(self.backend)

    async def _start(self) -> None:
        backend_config = ACP_BACKENDS.get(self.backend)
        if not backend_config:
            raise ValueError(f"不支持的 ACP 后端: {self.backend}")

        detect_cmd = backend_config["detect_cmd"]
        if not shutil.which(detect_cmd):
            raise FileNotFoundError(
                f"{self.backend} CLI 未安装或不在 PATH 中 (需要: {detect_cmd})"
            )

        command = backend_config["command"]
        args = list(backend_config["args"])

        env = os.environ.copy()
        env.pop("NODE_OPTIONS", None)
        env.pop("NODE_INSPECT", None)
        env.pop("NODE_DEBUG", None)

        cmd_path = shutil.which(command) or command

        self.process = await asyncio.create_subprocess_exec(
            cmd_path,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
            env=env,
        )

        self._read_task = asyncio.create_task(self._read_loop())

        await asyncio.sleep(2)

        await self._initialize()

    async def _initialize(self) -> None:
        result = await self._request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {
                        "readTextFile": True,
                        "writeTextFile": True,
                    },
                },
            },
            timeout=60,
        )
        self._initialized = True
        return result

    async def _new_session(self) -> str:
        result = await self._request(
            "session/new",
            {"cwd": self.config.cwd, "mcpServers": []},
            timeout=60,
        )
        if isinstance(result, dict) and "sessionId" in result:
            self.session_id = result["sessionId"]
        return self.session_id or ""

    async def _read_loop(self) -> None:
        if not self.process or not self.process.stdout:
            return

        buffer = ""
        while True:
            try:
                data = await self.process.stdout.read(8192)
                if not data:
                    break

                buffer += data.decode("utf-8")
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self._handle_message(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break

    def _handle_message(self, msg: dict) -> None:
        if "method" in msg:
            self._handle_incoming(msg)
        elif "id" in msg and ("result" in msg or "error" in msg):
            request_id = msg["id"]
            if request_id in self._pending:
                future = self._pending.pop(request_id)
                if not future.done():
                    if "error" in msg:
                        error_msg = msg["error"].get("message", "Unknown ACP error")
                        future.set_exception(RuntimeError(error_msg))
                    else:
                        result = msg.get("result")
                        if isinstance(result, dict) and result.get("stopReason") == "end_turn":
                            self._updates.put_nowait(
                                AcpSessionUpdate(update_type="end_turn")
                            )
                        future.set_result(result)

    def _handle_incoming(self, msg: dict) -> None:
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "session/update":
            update = params.get("update", {})
            update_type = update.get("sessionUpdate", "")

            if update_type == "agent_message_chunk":
                content = update.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else ""
                if text:
                    self._updates.put_nowait(
                        AcpSessionUpdate(update_type="text", content=text, raw=update)
                    )

            elif update_type == "agent_thought_chunk":
                content = update.get("content", {})
                text = content.get("text", "") if isinstance(content, dict) else ""
                if text:
                    self._updates.put_nowait(
                        AcpSessionUpdate(
                            update_type="thought", content=text, raw=update
                        )
                    )

            elif update_type == "tool_call":
                self._updates.put_nowait(
                    AcpSessionUpdate(
                        update_type="tool_call",
                        tool_call_id=update.get("toolCallId", ""),
                        tool_name=update.get("toolName", ""),
                        tool_status=update.get("status", ""),
                        content=json.dumps(update.get("content", {}), ensure_ascii=False),
                        raw=update,
                    )
                )

            elif update_type == "tool_call_update":
                self._updates.put_nowait(
                    AcpSessionUpdate(
                        update_type="tool_call_update",
                        tool_call_id=update.get("toolCallId", ""),
                        tool_status=update.get("status", ""),
                        content=json.dumps(update.get("content", {}), ensure_ascii=False),
                        raw=update,
                    )
                )

        elif method == "request_permission":
            request_id = msg.get("id")
            if request_id is not None:
                response = {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": request_id,
                    "result": {
                        "outcome": {"outcome": "selected", "optionId": "allow_once"}
                    },
                }
                self._send_raw(response)

        elif method == "fs/read_text_file":
            request_id = msg.get("id")
            file_path = params.get("path", "")
            if request_id is not None:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    response = {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": request_id,
                        "result": {"content": content},
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": request_id,
                        "error": {"code": -32603, "message": str(e)},
                    }
                self._send_raw(response)

        elif method == "fs/write_text_file":
            request_id = msg.get("id")
            file_path = params.get("path", "")
            content = params.get("content", "")
            if request_id is not None:
                try:
                    import pathlib
                    pathlib.Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    response = {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": request_id,
                        "result": None,
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": JSONRPC_VERSION,
                        "id": request_id,
                        "error": {"code": -32603, "message": str(e)},
                    }
                self._send_raw(response)

    def _send_raw(self, msg: dict) -> None:
        if self.process and self.process.stdin:
            line = json.dumps(msg) + "\n"
            self.process.stdin.write(line.encode("utf-8"))

    async def _request(
        self, method: str, params: dict | None = None, timeout: float = 300
    ) -> Any:
        if not self.process or not self.process.stdin:
            await self._start()

        self._request_id += 1
        request_id = self._request_id

        msg = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "method": method}
        if params:
            msg["params"] = params

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future

        self._send_raw(msg)
        try:
            await self.process.stdin.drain()
        except Exception:
            pass

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"ACP 请求超时: {method} ({timeout}s)")

    async def _ensure_session(self) -> None:
        if not self._initialized:
            await self._start()
        if not self.session_id:
            await self._new_session()

    async def send_prompt(self, prompt: str) -> str:
        await self._ensure_session()

        prompt_future = asyncio.ensure_future(
            self._request(
                "session/prompt",
                {
                    "sessionId": self.session_id,
                    "prompt": [{"type": "text", "text": prompt}],
                },
                timeout=600,
            )
        )

        result_parts: list[str] = []

        while not prompt_future.done():
            try:
                update = await asyncio.wait_for(self._updates.get(), timeout=1)
                if update.update_type == "text":
                    result_parts.append(update.content)
                elif update.update_type == "end_turn":
                    break
            except asyncio.TimeoutError:
                continue

        try:
            await prompt_future
        except Exception:
            pass

        while not self._updates.empty():
            try:
                update = self._updates.get_nowait()
                if update.update_type == "text":
                    result_parts.append(update.content)
            except asyncio.QueueEmpty:
                break

        return "".join(result_parts)

    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        await self._ensure_session()

        prompt_future = asyncio.ensure_future(
            self._request(
                "session/prompt",
                {
                    "sessionId": self.session_id,
                    "prompt": [{"type": "text", "text": prompt}],
                },
                timeout=600,
            )
        )

        while not prompt_future.done():
            try:
                update = await asyncio.wait_for(self._updates.get(), timeout=1)

                if update.update_type == "text":
                    yield MessageChunk(text=update.content, chunk_type="text")
                elif update.update_type == "thought":
                    yield MessageChunk(text=update.content, chunk_type="thought")
                elif update.update_type == "tool_call":
                    yield ToolCallInfo(
                        tool_name=update.tool_name,
                        tool_id=update.tool_call_id,
                        input_data=update.raw.get("content", {}),
                    )
                elif update.update_type == "tool_call_update":
                    yield ToolCallInfo(
                        tool_name="tool_result",
                        tool_id=update.tool_call_id,
                        output=update.content,
                        is_error=update.tool_status == "failed",
                    )
                elif update.update_type == "end_turn":
                    break
            except asyncio.TimeoutError:
                continue

        try:
            result = await prompt_future
            stop_reason = None
            if isinstance(result, dict):
                stop_reason = result.get("stopReason")
            yield {"type": "result", "stop_reason": stop_reason or "end_turn"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}

        while not self._updates.empty():
            try:
                update = self._updates.get_nowait()
                if update.update_type == "text":
                    yield MessageChunk(text=update.content, chunk_type="text")
            except asyncio.QueueEmpty:
                break

    async def stop(self) -> None:
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            self.process = None

        for future in self._pending.values():
            if not future.done():
                future.set_exception(RuntimeError("ACP connection closed"))
        self._pending.clear()
        self.session_id = None
        self._initialized = False
