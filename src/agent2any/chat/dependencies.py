from typing import Annotated

from fastapi import Depends, Request

from .service import SessionManager


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
