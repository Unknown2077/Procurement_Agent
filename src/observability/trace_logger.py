from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SENSITIVE_KEYS: set[str] = {"nvidia_api_key", "api_key", "token", "authorization"}


class TraceLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, payload: dict[str, Any]) -> None:
        safe_payload = _redact(payload)
        safe_payload["timestamp_utc"] = datetime.now(UTC).isoformat()
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_payload, ensure_ascii=True) + "\n")


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = "***REDACTED***"
            continue
        if isinstance(value, dict):
            redacted[key] = _redact(value)
            continue
        redacted[key] = value
    return redacted
