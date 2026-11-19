"""The skills script with the API it calls replaced by a mock."""

import io
import json
import urllib.error
from email.message import Message
from unittest.mock import MagicMock

import pytest

from scripts import add_skills


def http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("url", code, "", Message(), io.BytesIO(body))


def test_posts_each_name_and_counts_the_ones_the_catalogue_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    urlopen = MagicMock(side_effect=[MagicMock(), http_error(409)])
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    # When
    result = add_skills.add_skills("http://backend/", ["Go", "Rust"])

    # Then
    assert result == (1, 1)
    requests = [call.args[0] for call in urlopen.call_args_list]
    assert [r.full_url for r in requests] == ["http://backend/api/v1/skills"] * 2
    assert [json.loads(r.data) for r in requests] == [{"name": "Go"}, {"name": "Rust"}]
    assert {r.get_method() for r in requests} == {"POST"}


def test_stops_at_any_other_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    error = http_error(422, b'{"detail":"too long"}')
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(side_effect=error))

    # When / Then
    with pytest.raises(SystemExit, match=r"^Go: 422 .*too long"):
        add_skills.add_skills("http://backend", ["Go"])


def test_says_when_the_backend_cannot_be_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    error = urllib.error.URLError("connection refused")
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(side_effect=error))

    # When / Then
    with pytest.raises(SystemExit, match=r"^Cannot reach the backend at http://backend: conn"):
        add_skills.add_skills("http://backend", ["Go"])
