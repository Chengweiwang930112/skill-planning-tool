"""Add skills to the catalogue through the API, one name per line of a file:

    uv run python -m scripts.add_skills ../samples/skills.txt [--url http://127.0.0.1:8000]

Names the catalogue already has are skipped, so it can run again. Through the API
rather than the database, so that it works against any running instance and the API's
validation and duplicate check apply.
"""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def read_names(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return [name for line in lines if (name := line.strip()) and not name.startswith("#")]


def add_skills(url: str, names: list[str]) -> tuple[int, int]:
    created = existing = 0
    for name in names:
        request = urllib.request.Request(
            f"{url.rstrip('/')}/api/v1/skills",
            data=json.dumps({"name": name}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=10).close()
            created += 1
        except urllib.error.HTTPError as error:
            if error.code != 409:
                raise SystemExit(f"{name}: {error.code} {error.read().decode()}") from None
            existing += 1
        except urllib.error.URLError as error:
            raise SystemExit(f"Cannot reach the backend at {url}: {error.reason}") from None
    return created, existing


def main() -> None:
    parser = argparse.ArgumentParser(description="Add skills to the catalogue.")
    parser.add_argument("file", type=Path, help="one skill name per line; # starts a comment")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="the running backend")
    args = parser.parse_args()
    created, existing = add_skills(args.url, read_names(args.file))
    print(f"Added {created} skills; {existing} were already in the catalogue.")


if __name__ == "__main__":
    main()
