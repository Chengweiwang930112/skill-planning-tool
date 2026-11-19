import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("app")
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# What every LogRecord has; anything else was passed in `extra` and is logged as a field.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
# A caller's request id is kept only if it cannot break a log line or a header.
_VALID_ID = re.compile(r"[\w.-]{1,64}")
_PROBES = {"/healthz", "/readyz"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, as CloudWatch Logs reads them from the container."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if current := request_id.get():
            entry["request_id"] = current
        entry |= {key: value for key, value in vars(record).items() if key not in _STANDARD}
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """The application's own logs, to stdout; uvicorn keeps its own for the server."""
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


async def log_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Gives every request an id, from the caller's X-Request-ID or a new one, which its
    log lines and its response carry, and logs one line per request."""
    given = request.headers.get("x-request-id", "")
    current = given if _VALID_ID.fullmatch(given) else uuid.uuid4().hex
    request.state.request_id = current
    token = request_id.set(current)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = current
        return response
    finally:
        if request.url.path not in _PROBES or status >= 400:
            logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        request_id.reset(token)
