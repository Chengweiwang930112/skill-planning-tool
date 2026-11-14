from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.api.employees import router as employees_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.skills import router as skills_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.frontend import SinglePageApp
from app.core.limits import reject_oversized_requests

OPENAPI_TAGS = [
    {"name": "employees", "description": "Employees and the skills assigned to them."},
    {"name": "skills", "description": "The catalogue of skills employees can be assigned."},
    {"name": "imports", "description": "Upload employees as CSV and review past imports."},
    {"name": "infrastructure", "description": "Health probes for the load balancer."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # libpq has no connect timeout of its own: an unreachable database (say, a wrong
    # security group) would hold every request, and its worker thread, for minutes.
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

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
    app.state.sessionmaker = sessionmaker(engine, expire_on_commit=False)
    register_error_handlers(app)
    app.middleware("http")(reject_oversized_requests)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.include_router(employees_router, prefix=settings.api_v1_prefix)
    app.include_router(skills_router, prefix=settings.api_v1_prefix)
    app.include_router(imports_router, prefix=settings.api_v1_prefix)
    app.include_router(health_router)
    # Mounted last, so that it only receives what no route matched.
    if settings.static_dir:
        app.mount("/", SinglePageApp(directory=settings.static_dir), name="frontend")

    return app


app = create_app()
