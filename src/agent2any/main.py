import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .channels import ChannelManager, MessageDispatcher
from .channels.feishu import FeishuChannel, FeishuChannelConfig
from .channels.router import router as channel_router
from .chat import SessionManager, router
from .config import get_settings
from .drama import DramaServiceManager, router as drama_router
from .exceptions import Agent2AnyError, agent2any_exception_handler, unhandled_exception_handler
from .logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    session_manager = SessionManager()
    app.state.session_manager = session_manager
    app.state.drama_service_manager = DramaServiceManager()

    channel_manager = ChannelManager()
    app.state.channel_manager = channel_manager

    if settings.feishu_enabled:
        feishu_config = FeishuChannelConfig(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            encrypt_key=settings.feishu_encrypt_key,
            verification_token=settings.feishu_verification_token,
            connection_mode=settings.feishu_connection_mode,
            client_type=settings.feishu_client_type,
            streaming_card=settings.feishu_streaming_card,
            cwd=settings.feishu_cwd,
            max_turns=settings.feishu_max_turns,
        )
        feishu_channel = FeishuChannel(feishu_config)
        channel_manager.register(feishu_channel)

        dispatcher = MessageDispatcher(session_manager, channel_manager)
        await channel_manager.start_all(dispatcher.handle_inbound)
        logger.info("飞书 channel 已启动")

    yield

    await channel_manager.stop_all()
    await app.state.session_manager.cleanup()
    await app.state.drama_service_manager.cleanup()


app = FastAPI(
    title="Agent2Any",
    description="HTTP API bridge for AI Code CLI",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Agent2AnyError, agent2any_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(router, prefix="/api/v1", tags=["chat"])
app.include_router(drama_router, prefix="/api/v1", tags=["drama"])
app.include_router(channel_router, prefix="/api/v1", tags=["channels"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


def main():
    import uvicorn

    s = get_settings()
    uvicorn.run("agent2any.main:app", host=s.host, port=s.port, reload=True)


if __name__ == "__main__":
    main()
