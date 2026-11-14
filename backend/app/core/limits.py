from fastapi import Request, status
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.core.errors import problem

# Above the import's 10 MB, so that oversized CSV files still get its specific error.
MAX_REQUEST_BYTES = 12 * 1024 * 1024


async def reject_oversized_requests(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Refuses a request by its declared size before its body is read."""
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        return problem(status.HTTP_413_CONTENT_TOO_LARGE, "The request is larger than 12 MB")
    return await call_next(request)
