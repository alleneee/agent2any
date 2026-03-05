from typing import Annotated

from fastapi import Depends, Request

from ..connections import ClientType
from .prompts import StyleConfig
from .service import DramaService


class DramaServiceManager:
    def __init__(self):
        self._services: dict[str, DramaService] = {}

    def get_or_create(
        self,
        cwd: str,
        client_type: str,
        api_key: str = "",
        model: str = "",
        style: StyleConfig | None = None,
    ) -> DramaService:
        key = f"{cwd}:{client_type}"
        if key not in self._services:
            self._services[key] = DramaService(
                cwd=cwd,
                style=style,
                client_type=ClientType(client_type),
                api_key=api_key,
                model=model,
            )
        return self._services[key]

    async def cleanup(self) -> None:
        self._services.clear()


def get_drama_service_manager(request: Request) -> DramaServiceManager:
    return request.app.state.drama_service_manager


DramaServiceManagerDep = Annotated[DramaServiceManager, Depends(get_drama_service_manager)]
