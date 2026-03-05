import asyncio
import json
import os
import re
import shutil
import subprocess
import uuid
from typing import Any, AsyncIterator

from .base import (
    BaseConnection,
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
)


class CodexConnection(BaseConnection):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.process: asyncio.subprocess.Process | None = None
        self.conversation_id: str | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None

    @property
    def client_type(self) -> ClientType:
        return ClientType.CODEX

    def _detect_mcp_command(self, cli_path: str) -> list[str]:
        try:
            result = subprocess.run(
                [cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout.strip())
            if match:
                major, minor, _ = map(int, match.groups())
                if major > 0 or (major == 0 and minor >= 40):
                    return ["mcp-server"]
                else:
                    return ["mcp", "serve"]
        except Exception:
            pass
        return ["mcp-server"]

    async def _start_process(self) -> None:
        cli_path = shutil.which("codex")
        if not cli_path:
            raise FileNotFoundError("Codex CLI 未安装或不在 PATH 中")

        mcp_args = self._detect_mcp_command(cli_path)

        env = os.environ.copy()
        env["CODEX_NO_INTERACTIVE"] = "1"
        env["CODEX_AUTO_CONTINUE"] = "1"

        self.process = await asyncio.create_subprocess_exec(
            cli_path,
            *mcp_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
            env=env,
        )

        self._read_task = asyncio.create_task(self._read_loop())
        await asyncio.sleep(3)
        await self._initialize()

    async def _initialize(self) -> None:
        try:
            await self._request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agent2any", "version": "0.1.0"},
                },
                timeout=15,
            )
        except Exception:
            try:
                await self._request("tools/list", {}, timeout=10)
            except Exception as e:
                raise RuntimeError(f"Codex MCP 初始化失败: {e}")

    async def _read_loop(self) -> None:
        if not self.process or not self.process.stdout:
            return

        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8").strip()
                if not decoded:
                    continue
                if decoded.startswith("{") and decoded.endswith("}"):
                    try:
                        msg = json.loads(decoded)
                        self._handle_message(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break

    def _handle_message(self, msg: dict) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            request_id = msg["id"]
            if request_id in self._pending:
                future = self._pending.pop(request_id)
                if not future.done():
                    if "error" in msg:
                        future.set_exception(
                            RuntimeError(msg["error"].get("message", "Unknown error"))
                        )
                    else:
                        future.set_result(msg.get("result"))

    async def _request(
        self, method: str, params: dict | None = None, timeout: float = 200
    ) -> Any:
        if not self.process or not self.process.stdin:
            await self._start_process()

        self._request_id += 1
        request_id = self._request_id

        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params:
            request["params"] = params

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future

        line = json.dumps(request) + "\n"
        self.process.stdin.write(line.encode("utf-8"))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise

    async def send_prompt(self, prompt: str) -> str:
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

        result = await self._request(
            "tools/call",
            {
                "name": "codex",
                "arguments": {
                    "prompt": prompt,
                    "cwd": self.config.cwd,
                    "sandbox": "workspace-write",
                },
                "config": {"conversationId": self.conversation_id},
            },
            timeout=600,
        )

        if isinstance(result, dict):
            if "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                    return "\n".join(texts)
                return str(content)
            return json.dumps(result)
        return str(result) if result else ""

    async def send_prompt_stream(
        self, prompt: str
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict[str, Any]]:
        result = await self.send_prompt(prompt)
        yield MessageChunk(text=result, chunk_type="text")
        yield {"type": "result", "stop_reason": "end_turn"}

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

        self._pending.clear()
