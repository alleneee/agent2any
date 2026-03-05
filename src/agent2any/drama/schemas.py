from typing import Literal

from pydantic import BaseModel, Field


class DramaBaseRequest(BaseModel):
    cwd: str = Field(".", description="工作目录")
    client_type: Literal["claude", "codex", "gemini"] = Field("claude", description="客户端类型")
    model: str = Field("", description="模型名称")


class OutlineRequest(DramaBaseRequest):
    theme: str = Field(..., description="主题")
    genre: str = Field("", description="类型偏好")
    episode_count: int = Field(5, description="剧集数量", ge=1, le=20)
    style: dict = Field(default_factory=dict, description="风格配置")


class ProjectRequest(DramaBaseRequest):
    project_id: str = Field(..., description="项目ID")


class EpisodeRequest(ProjectRequest):
    episode_index: int = Field(0, description="剧集索引", ge=0)


class StoryboardRequest(EpisodeRequest):
    shot_index: int = Field(0, description="镜头索引", ge=0)
    frame_type: str = Field("first", description="帧类型: first/key/last")


class ScriptRequest(ProjectRequest):
    script_content: str = Field("", description="剧本内容（可选）")
