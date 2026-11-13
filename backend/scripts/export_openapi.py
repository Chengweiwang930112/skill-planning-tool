"""Print the OpenAPI schema, for generating the frontend's API types."""

import json

from app.core.config import Settings
from app.main import create_app

if __name__ == "__main__":
    app = create_app(Settings(environment="local"))
    print(json.dumps(app.openapi(), indent=2))
