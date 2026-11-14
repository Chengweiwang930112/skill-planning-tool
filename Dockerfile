# One image with the API and the frontend it serves: a single process to run and scale.

# Frontend: install exactly the locked packages and build for production.
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# Backend: resolve dependencies exactly as locked, without development tools.
FROM python:3.12-slim-bookworm AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Runtime: the virtual environment, the code and the built frontend; no Node.js.
FROM python:3.12-slim-bookworm
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=backend /app/.venv .venv
COPY backend/alembic.ini ./
COPY backend/migrations migrations
COPY backend/app app
COPY --from=frontend /frontend/dist/frontend/browser static
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENVIRONMENT=production \
    APP_STATIC_DIR=/app/static
USER app
EXPOSE 8000
# One process per container: scale by running more containers (ECS tasks), not workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
