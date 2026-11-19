import json
import logging
import sys

from app.core.logs import JsonFormatter, request_id


def record(**extra: object) -> logging.LogRecord:
    entry = logging.makeLogRecord({"name": "app.test", "levelname": "INFO", "msg": "%s rows"})
    entry.args = (3,)
    entry.__dict__.update(extra)
    return entry


def test_writes_one_json_object_with_the_extra_fields_and_the_request_id() -> None:
    # Given
    token = request_id.set("abc123")

    # When
    try:
        line = JsonFormatter().format(record(import_id=7, file="employees.csv"))
    finally:
        request_id.reset(token)

    # Then
    entry = json.loads(line)
    assert "\n" not in line
    assert entry["message"] == "3 rows"
    assert (entry["level"], entry["logger"], entry["request_id"]) == ("INFO", "app.test", "abc123")
    assert (entry["import_id"], entry["file"]) == (7, "employees.csv")
    assert entry["time"].endswith("+00:00")


def test_logs_an_exception_with_its_traceback_and_no_request_id_outside_requests() -> None:
    # Given
    try:
        raise RuntimeError("database gone")
    except RuntimeError:
        failed = record(exc_info=sys.exc_info())

    # When
    entry = json.loads(JsonFormatter().format(failed))

    # Then
    assert "RuntimeError: database gone" in entry["exception"]
    assert "request_id" not in entry
