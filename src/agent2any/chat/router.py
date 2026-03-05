import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..connections import ClientType, MessageChunk, ToolCallInfo
from ..triage import TriageService
from .dependencies import SessionManagerDep
from .schemas import ChatRequest, ChatResponse, SessionInfo
from .service import Agent, ClaudeAgent, CodexAgent, GeminiAgent

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_default_cwd(client_type: ClientType) -> str:
    settings = get_settings()
    cwd_map = {
        ClientType.CLAUDE: settings.cwd_claude,
        ClientType.CODEX: settings.cwd_codex,
        ClientType.GEMINI: settings.cwd_gemini,
    }
    return cwd_map.get(client_type, settings.default_cwd)


def _create_agent(
    client_type: ClientType,
    cwd: str,
    instructions: str,
    allowed_tools: list[str],
    max_turns: int,
    model: str,
    session_id: str,
    api_key: str = "",
) -> Agent:
    if cwd == ".":
        cwd = _get_default_cwd(client_type)

    if client_type == ClientType.CLAUDE:
        return ClaudeAgent(
            cwd=cwd,
            system_prompt=instructions,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            model=model,
            session_id=session_id,
        )
    elif client_type == ClientType.CODEX:
        return CodexAgent(
            cwd=cwd,
            system_prompt=instructions,
            max_turns=max_turns,
            api_key=api_key,
            model=model,
            session_id=session_id,
        )
    else:
        return GeminiAgent(
            cwd=cwd,
            system_prompt=instructions,
            max_turns=max_turns,
            api_key=api_key,
            model=model,
            session_id=session_id,
        )


async def _maybe_route(request: ChatRequest, api_key: str = "") -> tuple[ClientType, str]:
    settings = get_settings()
    need_route = request.auto_route or request.client_type is None or settings.auto_route

    if need_route and settings.triage_enabled and settings.triage_api_key:
        try:
            triage = TriageService()
            result = await triage.handle(request.prompt)
            if result.action == "cli" and result.client_type:
                ct = ClientType(result.client_type)
                logger.info("路由结果: %s, task: %s...", ct.value, result.task[:50])
                return ct, result.task
            logger.info("路由结果: direct，回退到默认客户端")
            return ClientType.CLAUDE, request.prompt
        except Exception as e:
            logger.warning("路由失败，使用默认客户端: %s", e)
            return ClientType.CLAUDE, request.prompt

    if request.client_type:
        return ClientType(request.client_type), request.prompt
    return ClientType.CLAUDE, request.prompt


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    manager: SessionManagerDep,
    x_api_key: str = Header(""),
) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    client_type, task = await _maybe_route(request, x_api_key)

    agent = await manager.get_or_create(
        session_id,
        lambda: _create_agent(
            client_type=client_type,
            cwd=request.cwd,
            instructions=request.instructions,
            allowed_tools=request.allowed_tools,
            max_turns=request.max_turns,
            model=request.model,
            session_id=session_id,
            api_key=x_api_key,
        ),
    )
    content = await agent.send_prompt(task)
    return ChatResponse(
        session_id=session_id,
        content=content,
        client_type=str(agent.client_type.value),
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    manager: SessionManagerDep,
    x_api_key: str = Header(""),
) -> StreamingResponse:
    session_id = request.session_id or str(uuid.uuid4())
    client_type, task = await _maybe_route(request, x_api_key)

    agent = await manager.get_or_create(
        session_id,
        lambda: _create_agent(
            client_type=client_type,
            cwd=request.cwd,
            instructions=request.instructions,
            allowed_tools=request.allowed_tools,
            max_turns=request.max_turns,
            model=request.model,
            session_id=session_id,
            api_key=x_api_key,
        ),
    )

    async def generate():
        yield f"data: {json.dumps({'type': 'session', 'data': {'session_id': session_id, 'client_type': str(agent.client_type.value)}})}\n\n"

        async for event in agent.send_prompt_stream(task):
            chunk: dict[str, Any]
            if isinstance(event, MessageChunk):
                chunk = {"type": "text", "data": {"text": event.text}}
            elif isinstance(event, ToolCallInfo):
                chunk = {
                    "type": "tool_call",
                    "data": {
                        "tool_name": event.tool_name,
                        "tool_id": event.tool_id,
                        "input": event.input_data,
                        "output": event.output,
                        "is_error": event.is_error,
                    },
                }
            elif isinstance(event, dict):
                chunk = {"type": event.get("type", "event"), "data": event}
            else:
                continue

            yield f"data: {json.dumps(chunk)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(manager: SessionManagerDep) -> list[SessionInfo]:
    return [
        SessionInfo(
            session_id=sid,
            cwd=agent.cwd,
            client_type=str(agent.client_type.value),
        )
        for sid, agent in manager.list_all().items()
    ]


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str, manager: SessionManagerDep) -> SessionInfo:
    agent = manager.get(session_id)
    return SessionInfo(
        session_id=session_id,
        cwd=agent.cwd,
        client_type=str(agent.client_type.value),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, manager: SessionManagerDep) -> dict[str, str]:
    await manager.delete(session_id)
    return {"status": "ok", "session_id": session_id}
