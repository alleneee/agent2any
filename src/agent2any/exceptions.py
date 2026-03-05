import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class Agent2AnyError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SessionNotFoundError(Agent2AnyError):
    def __init__(self, session_id: str):
        super().__init__(f"会话不存在: {session_id}", status_code=404)


class ProjectNotFoundError(Agent2AnyError):
    def __init__(self, project_id: str):
        super().__init__(f"项目不存在: {project_id}", status_code=404)


class ConnectionError(Agent2AnyError):
    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class AIParseError(Agent2AnyError):
    def __init__(self, step: str, detail: str):
        super().__init__(f"解析{step}失败: {detail}", status_code=422)


async def agent2any_exception_handler(request: Request, exc: Agent2AnyError) -> JSONResponse:
    logger.warning("业务异常: %s (status=%d)", exc.message, exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常")
    return JSONResponse(status_code=500, content={"error": "内部服务器错误"})
