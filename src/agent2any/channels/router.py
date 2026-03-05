import logging

from fastapi import APIRouter, Request, Response

from .dependencies import ChannelManagerDep
from .feishu.gateway import FeishuGateway

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/channels")
async def list_channels(manager: ChannelManagerDep):
    result = []
    for cid, ch in manager.list_all().items():
        result.append({
            "channel_id": cid,
            "platform": ch.platform,
        })
    return result


@router.post("/channels/{channel_id}/webhook")
async def webhook_event(
    channel_id: str,
    request: Request,
    manager: ChannelManagerDep,
):
    channel = manager.get(channel_id)
    if channel is None:
        return Response(status_code=404, content=f"Channel not found: {channel_id}")

    body = await request.body()
    headers = dict(request.headers)

    if hasattr(channel, "_gateway") and isinstance(channel._gateway, FeishuGateway):
        resp_body = channel._gateway.handle_webhook_event(body, headers)
        return Response(content=resp_body, media_type="application/json")

    return Response(status_code=400, content="Webhook not supported for this channel")
