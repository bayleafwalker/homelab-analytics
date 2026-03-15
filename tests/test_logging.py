from __future__ import annotations

import json
import logging

from packages.shared.logging import JsonLogFormatter


def test_json_log_formatter_emits_structured_fields_and_context() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="homelab_analytics.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="request handled",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "info"
    assert payload["logger"] == "homelab_analytics.api"
    assert payload["message"] == "request handled"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert "timestamp" in payload
