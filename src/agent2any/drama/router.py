import json
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from ..connections import ClientType
from ..exceptions import ProjectNotFoundError
from .dependencies import DramaServiceManager, DramaServiceManagerDep
from .prompts import StyleConfig
from .schemas import (
    EpisodeRequest,
    OutlineRequest,
    ProjectRequest,
    ScriptRequest,
    StoryboardRequest,
)
from .service import DramaService

router = APIRouter()


def _create_service(
    manager: DramaServiceManager,
    request,
    api_key: str = "",
    style: StyleConfig | None = None,
) -> DramaService:
    return manager.get_or_create(
        cwd=request.cwd,
        client_type=request.client_type,
        api_key=api_key,
        model=request.model,
        style=style,
    )


def _create_outline_service(
    manager: DramaServiceManager,
    request: OutlineRequest,
    api_key: str = "",
) -> DramaService:
    style = StyleConfig(**request.style) if request.style else None
    service = DramaService(
        cwd=request.cwd,
        style=style,
        client_type=ClientType(request.client_type),
        api_key=api_key,
        model=request.model,
    )
    manager._services[f"{request.cwd}:{request.client_type}"] = service
    return service


@router.post("/drama/outline")
async def generate_outline(
    request: OutlineRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_outline_service(manager, request, x_api_key)
    return await service.generate_outline(
        theme=request.theme,
        genre=request.genre,
        episode_count=request.episode_count,
    )


@router.post("/drama/outline/stream")
async def generate_outline_stream(
    request: OutlineRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> StreamingResponse:
    service = _create_outline_service(manager, request, x_api_key)

    async def generate():
        async for chunk in service.generate_outline_stream(
            theme=request.theme,
            genre=request.genre,
            episode_count=request.episode_count,
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/drama/episodes")
async def generate_episodes(
    request: ProjectRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.generate_episode_scripts(request.project_id)


@router.post("/drama/characters")
async def extract_characters(
    request: ScriptRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.extract_characters(
        project_id=request.project_id,
        script_content=request.script_content,
    )


@router.post("/drama/scenes")
async def extract_scenes(
    request: ScriptRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.extract_scenes(
        project_id=request.project_id,
        script_content=request.script_content,
    )


@router.post("/drama/props")
async def extract_props(
    request: ScriptRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.extract_props(
        project_id=request.project_id,
        script_content=request.script_content,
    )


@router.post("/drama/storyboard")
async def generate_storyboard(
    request: EpisodeRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.generate_storyboard(
        project_id=request.project_id,
        episode_index=request.episode_index,
    )


@router.post("/drama/frame-prompt")
async def generate_frame_prompt(
    request: StoryboardRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> dict[str, Any]:
    service = _create_service(manager, request, x_api_key)
    return await service.generate_frame_prompt(
        project_id=request.project_id,
        episode_index=request.episode_index,
        shot_index=request.shot_index,
        frame_type=request.frame_type,
    )


@router.post("/drama/workflow")
async def run_workflow(
    request: OutlineRequest,
    manager: DramaServiceManagerDep,
    x_api_key: str = Header(""),
) -> StreamingResponse:
    service = _create_outline_service(manager, request, x_api_key)

    async def generate():
        async for step in service.run_full_workflow(
            theme=request.theme,
            genre=request.genre,
            episode_count=request.episode_count,
        ):
            yield f"data: {json.dumps({
                'step': step.name,
                'status': step.status,
                'progress': step.progress,
                'message': step.message,
                'result': step.result,
            }, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/drama/projects")
async def list_projects(
    manager: DramaServiceManagerDep,
    cwd: str = ".",
) -> list[dict]:
    service = manager.get_or_create(cwd, "claude")
    return service.list_projects()


@router.get("/drama/projects/{project_id}")
async def get_project(
    project_id: str,
    manager: DramaServiceManagerDep,
    cwd: str = ".",
) -> dict[str, Any]:
    service = manager.get_or_create(cwd, "claude")
    project = service.get_project(project_id)
    if not project:
        raise ProjectNotFoundError(project_id)
    return {
        "id": project.id,
        "title": project.title,
        "theme": project.theme,
        "genre": project.genre,
        "outline": project.outline,
        "episodes": project.episodes,
        "characters": project.characters,
        "scenes": project.scenes,
        "props": project.props,
        "storyboards": project.storyboards,
    }
