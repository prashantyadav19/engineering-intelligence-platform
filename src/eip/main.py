from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eip import __version__
from eip.api.routes import health
from eip.core.config import get_settings
from eip.core.redis import redis_client
from eip.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.include_router(health.router)
    return app


app = create_app()