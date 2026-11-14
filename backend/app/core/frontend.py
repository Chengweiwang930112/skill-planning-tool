import re

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Angular puts a content hash into the names of the files it builds.
HASHED_FILE = re.compile(r"-[A-Za-z0-9_-]{8}\.(?:js|css|woff2?)$")


class SinglePageApp(StaticFiles):
    """Serves the built frontend. Paths that are not files are the app's own routes and
    get index.html, except under /api/, where a missing route must stay a 404."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # The URL path, not `path`: that one is a file system path with OS separators.
        if scope["path"].startswith("/api/"):
            raise HTTPException(404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            path = "index.html"
            response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if HASHED_FILE.search(path) else "no-cache"
        )
        return response
