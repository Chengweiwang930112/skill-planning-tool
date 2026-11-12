from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import __version__
from app.api.employees import router as employees_router
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers

OPENAPI_TAGS = [
    {"name": "employees", "description": "Employees and the skills assigned to them."},
    {"name": "infrastructure", "description": "Health probes for the load balancer."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Track employees, their skills and proficiency levels.",
        docs_url="/docs" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    register_error_handlers(app)
    app.include_router(employees_router, prefix=settings.api_v1_prefix)
    app.include_router(health_router)

    return app


app = create_app()
