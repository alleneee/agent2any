import json
import logging
from typing import AsyncIterator

from ..connections import (
    ClientType,
    ConnectionConfig,
    MessageChunk,
    ToolCallInfo,
    create_connection,
)
from ..exceptions import AIParseError, ProjectNotFoundError
from .models import DramaProject, WorkflowStep, safe_parse_json
from .prompts import PromptTemplates, StyleConfig

logger = logging.getLogger(__name__)


def _get_project_or_raise(projects: dict[str, DramaProject], project_id: str) -> DramaProject:
    project = projects.get(project_id)
    if not project:
        raise ProjectNotFoundError(project_id)
    return project


class DramaService:
    def __init__(
        self,
        cwd: str = ".",
        style: StyleConfig | None = None,
        max_turns: int = 5,
        client_type: ClientType | str = ClientType.CLAUDE,
        api_key: str = "",
        model: str = "",
    ):
        self.cwd = cwd
        self.style = style or StyleConfig()
        self.prompts = PromptTemplates(self.style)
        self.max_turns = max_turns
        self.projects: dict[str, DramaProject] = {}
        self.client_type = ClientType(client_type) if isinstance(client_type, str) else client_type
        self.api_key = api_key
        self.model = model

    def _create_connection(self, system_prompt: str = ""):
        default_prompt = "你是专业的短剧创作AI助手。所有输出必须是纯JSON格式，不要包含markdown代码块或额外说明。"
        config = ConnectionConfig(
            cwd=self.cwd,
            system_prompt=system_prompt or default_prompt,
            max_turns=self.max_turns,
            api_key=self.api_key,
            model=self.model,
        )
        return create_connection(self.client_type, config)

    async def _call_ai(self, prompt: str, system_prompt: str = "") -> str:
        conn = self._create_connection(system_prompt)
        try:
            return await conn.send_prompt(prompt)
        finally:
            await conn.stop()

    async def _call_ai_stream(
        self, prompt: str, system_prompt: str = ""
    ) -> AsyncIterator[MessageChunk | ToolCallInfo | dict]:
        conn = self._create_connection(system_prompt)
        try:
            async for chunk in conn.send_prompt_stream(prompt):
                yield chunk
        finally:
            await conn.stop()

    async def generate_outline(
        self, theme: str, genre: str = "", episode_count: int = 5
    ) -> dict:
        logger.info("生成大纲: theme=%s, genre=%s, episodes=%d", theme, genre, episode_count)
        system_prompt = self.prompts.get_outline_prompt()
        user_prompt = self.prompts.format_outline_request(theme, genre, episode_count)

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            outline = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("大纲", str(e))

        project = DramaProject(
            theme=theme,
            genre=genre,
            title=outline.get("title", ""),
            outline=outline,
        )
        self.projects[project.id] = project
        return {"project_id": project.id, "outline": outline}

    async def generate_outline_stream(
        self, theme: str, genre: str = "", episode_count: int = 5
    ) -> AsyncIterator[dict]:
        logger.info("流式生成大纲: theme=%s, genre=%s, episodes=%d", theme, genre, episode_count)
        system_prompt = self.prompts.get_outline_prompt()
        user_prompt = self.prompts.format_outline_request(theme, genre, episode_count)

        full_text = []
        async for chunk in self._call_ai_stream(user_prompt, system_prompt):
            if isinstance(chunk, MessageChunk):
                full_text.append(chunk.text)
                yield {"type": "text", "content": chunk.text}
            elif isinstance(chunk, dict) and chunk.get("type") == "result":
                yield {"type": "progress", "status": "parsing"}

        text = "".join(full_text)
        try:
            outline = safe_parse_json(text)
        except json.JSONDecodeError as e:
            yield {"type": "error", "message": f"解析大纲失败: {e}"}
            return

        project = DramaProject(
            theme=theme,
            genre=genre,
            title=outline.get("title", ""),
            outline=outline,
        )
        self.projects[project.id] = project
        yield {"type": "result", "project_id": project.id, "outline": outline}

    async def generate_episode_scripts(self, project_id: str) -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("生成剧本: project_id=%s", project_id)

        system_prompt = self.prompts.get_episode_script_prompt()

        outline_text = json.dumps(project.outline, ensure_ascii=False, indent=2)
        char_text = ""
        if project.characters:
            char_text = "\n角色设定：\n" + json.dumps(project.characters, ensure_ascii=False, indent=2)

        episode_count = len(project.outline.get("episodes", []))
        user_prompt = f"""剧本大纲：
{outline_text}
{char_text}

请基于以上大纲创作 {episode_count} 集的详细剧本。

**重要要求：**
- 必须生成完整的 {episode_count} 集
- 每集约3-5分钟（150-300秒）
- 返回的JSON中episodes数组必须包含 {episode_count} 个元素"""

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            data = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("剧本", str(e))

        episodes = data.get("episodes", data) if isinstance(data, dict) else data
        project.episodes = episodes
        return {"project_id": project_id, "episodes": episodes}

    async def extract_characters(self, project_id: str, script_content: str = "") -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("提取角色: project_id=%s", project_id)

        if not script_content:
            if project.episodes:
                script_content = "\n\n".join(
                    ep.get("script_content", ep.get("summary", "")) for ep in project.episodes
                )
            elif project.outline:
                script_content = json.dumps(project.outline, ensure_ascii=False)

        system_prompt = self.prompts.get_character_extraction_prompt()
        user_prompt = self.prompts.format_character_request(script_content)

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            characters = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("角色", str(e))

        for i, char in enumerate(characters):
            char["id"] = i + 1
        project.characters = characters
        return {"project_id": project_id, "characters": characters}

    async def extract_scenes(self, project_id: str, script_content: str = "") -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("提取场景: project_id=%s", project_id)

        if not script_content:
            if project.episodes:
                script_content = "\n\n".join(
                    ep.get("script_content", ep.get("summary", "")) for ep in project.episodes
                )

        system_prompt = self.prompts.get_scene_extraction_prompt()
        user_prompt = f"【剧本内容】\n{script_content}\n\n请提取所有场景背景。"

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            scenes = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("场景", str(e))

        for i, scene in enumerate(scenes):
            scene["id"] = i + 1
        project.scenes = scenes
        return {"project_id": project_id, "scenes": scenes}

    async def extract_props(self, project_id: str, script_content: str = "") -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("提取道具: project_id=%s", project_id)

        if not script_content:
            if project.episodes:
                script_content = "\n\n".join(
                    ep.get("script_content", ep.get("summary", "")) for ep in project.episodes
                )

        system_prompt = self.prompts.get_prop_extraction_prompt()
        user_prompt = f"【剧本内容】\n{script_content}"

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            props = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("道具", str(e))

        for i, prop in enumerate(props):
            prop["id"] = i + 1
        project.props = props
        return {"project_id": project_id, "props": props}

    async def generate_storyboard(self, project_id: str, episode_index: int = 0) -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("生成分镜: project_id=%s, episode=%d", project_id, episode_index)

        if episode_index >= len(project.episodes):
            raise AIParseError("分镜", f"剧集索引超出范围: {episode_index}")

        episode = project.episodes[episode_index]
        script_content = episode.get("script_content", episode.get("summary", ""))

        system_prompt = self.prompts.get_storyboard_prompt()
        user_prompt = self.prompts.format_storyboard_request(
            script_content, project.characters, project.scenes
        )

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            data = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("分镜", str(e))

        storyboards = data.get("storyboards", data) if isinstance(data, dict) else data
        project.storyboards[episode_index] = storyboards

        total_duration = sum(sb.get("duration", 0) for sb in storyboards)
        return {
            "project_id": project_id,
            "episode_index": episode_index,
            "storyboards": storyboards,
            "total_count": len(storyboards),
            "total_duration": total_duration,
        }

    async def generate_frame_prompt(
        self, project_id: str, episode_index: int, shot_index: int, frame_type: str = "first"
    ) -> dict:
        project = _get_project_or_raise(self.projects, project_id)
        logger.info("生成帧提示词: project_id=%s, ep=%d, shot=%d, type=%s", project_id, episode_index, shot_index, frame_type)

        storyboards = project.storyboards.get(episode_index, [])
        if shot_index >= len(storyboards):
            raise AIParseError("帧提示词", f"镜头索引超出范围: {shot_index}")

        storyboard = storyboards[shot_index]

        prompt_map = {
            "first": self.prompts.get_first_frame_prompt,
            "key": self.prompts.get_key_frame_prompt,
            "last": self.prompts.get_last_frame_prompt,
        }
        system_prompt = prompt_map.get(frame_type, self.prompts.get_first_frame_prompt)()
        user_prompt = self.prompts.format_frame_request(storyboard, frame_type)

        result = await self._call_ai(user_prompt, system_prompt)

        try:
            frame_data = safe_parse_json(result)
        except json.JSONDecodeError as e:
            raise AIParseError("帧提示词", str(e))

        return {
            "project_id": project_id,
            "episode_index": episode_index,
            "shot_index": shot_index,
            "frame_type": frame_type,
            "frame_prompt": frame_data,
        }

    async def run_full_workflow(
        self, theme: str, genre: str = "", episode_count: int = 5
    ) -> AsyncIterator[WorkflowStep]:
        logger.info("运行完整工作流: theme=%s, genre=%s, episodes=%d", theme, genre, episode_count)
        steps = [
            "生成大纲",
            "生成剧本",
            "提取角色",
            "提取场景",
            "提取道具",
            "生成分镜",
        ]

        project_id = None

        yield WorkflowStep(name=steps[0], status="running", progress=0, message="正在生成剧本大纲...")
        try:
            result = await self.generate_outline(theme, genre, episode_count)
        except Exception as e:
            yield WorkflowStep(name=steps[0], status="failed", message=str(e))
            return
        project_id = result["project_id"]
        yield WorkflowStep(name=steps[0], status="completed", progress=100, result=result["outline"])

        yield WorkflowStep(name=steps[1], status="running", progress=0, message="正在生成分集剧本...")
        try:
            result = await self.generate_episode_scripts(project_id)
        except Exception as e:
            yield WorkflowStep(name=steps[1], status="failed", message=str(e))
            return
        yield WorkflowStep(name=steps[1], status="completed", progress=100, result=result["episodes"])

        yield WorkflowStep(name=steps[2], status="running", progress=0, message="正在提取角色...")
        try:
            result = await self.extract_characters(project_id)
        except Exception as e:
            yield WorkflowStep(name=steps[2], status="failed", message=str(e))
            return
        yield WorkflowStep(name=steps[2], status="completed", progress=100, result=result["characters"])

        yield WorkflowStep(name=steps[3], status="running", progress=0, message="正在提取场景...")
        try:
            result = await self.extract_scenes(project_id)
        except Exception as e:
            yield WorkflowStep(name=steps[3], status="failed", message=str(e))
            return
        yield WorkflowStep(name=steps[3], status="completed", progress=100, result=result["scenes"])

        yield WorkflowStep(name=steps[4], status="running", progress=0, message="正在提取道具...")
        try:
            result = await self.extract_props(project_id)
        except Exception as e:
            yield WorkflowStep(name=steps[4], status="failed", message=str(e))
            return
        yield WorkflowStep(name=steps[4], status="completed", progress=100, result=result["props"])

        yield WorkflowStep(name=steps[5], status="running", progress=0, message="正在生成分镜头...")
        project = self.projects[project_id]
        all_storyboards = {}
        for i in range(len(project.episodes)):
            yield WorkflowStep(
                name=steps[5],
                status="running",
                progress=int((i / len(project.episodes)) * 100),
                message=f"正在生成第 {i + 1} 集分镜...",
            )
            try:
                result = await self.generate_storyboard(project_id, i)
                all_storyboards[i] = result["storyboards"]
            except Exception:
                logger.warning("生成第 %d 集分镜失败，跳过", i + 1, exc_info=True)

        yield WorkflowStep(name=steps[5], status="completed", progress=100, result=all_storyboards)

        yield WorkflowStep(
            name="完成",
            status="completed",
            progress=100,
            message="短剧生成完成",
            result={
                "project_id": project_id,
                "project": {
                    "title": project.title,
                    "theme": project.theme,
                    "genre": project.genre,
                    "outline": project.outline,
                    "episodes": project.episodes,
                    "characters": project.characters,
                    "scenes": project.scenes,
                    "props": project.props,
                    "storyboards": project.storyboards,
                },
            },
        )

    def get_project(self, project_id: str) -> DramaProject | None:
        return self.projects.get(project_id)

    def list_projects(self) -> list[dict]:
        return [
            {
                "id": p.id,
                "title": p.title,
                "theme": p.theme,
                "genre": p.genre,
                "episode_count": len(p.episodes),
                "character_count": len(p.characters),
            }
            for p in self.projects.values()
        ]
