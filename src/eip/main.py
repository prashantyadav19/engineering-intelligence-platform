from fastapi import FastAPI

from eip import __version__
from eip.api.routes import health
from eip.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.include_router(health.router)
    return app


app = create_app()