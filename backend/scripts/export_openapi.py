"""Print the OpenAPI schema, for generating the frontend's API types."""

import json
import sys

from app.core.config import Settings
from app.main import create_app

if __name__ == "__main__":
    schema = create_app(Settings(environment="local")).openapi()
    # Bytes, so that Windows does not turn the newlines into CRLF.
    sys.stdout.buffer.write(json.dumps(schema, indent=2).encode() + b"\n")
