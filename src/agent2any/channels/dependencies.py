from typing import Annotated

from fastapi import Depends, Request

from .registry import ChannelManager


def get_channel_manager(request: Request) -> ChannelManager:
    return request.app.state.channel_manager


ChannelManagerDep = Annotated[ChannelManager, Depends(get_channel_manager)]
