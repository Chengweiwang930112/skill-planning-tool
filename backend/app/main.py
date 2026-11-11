from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:

    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Track employees, their skills and proficiency levels.",
        docs_url="/docs" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.include_router(health_router)

    return app


app = create_app()
