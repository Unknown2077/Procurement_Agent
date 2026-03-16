from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class FormattedResponse:
    payload: dict[str, Any]


class OutputContractValidator:
    def __init__(self, contract_json_text: str) -> None:
        try:
            schema: dict[str, Any] = json.loads(contract_json_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid output contract JSON format.") from exc
        self._validator = Draft202012Validator(schema)

    def validate(self, payload: dict[str, Any]) -> None:
        errors = sorted(self._validator.iter_errors(payload), key=lambda err: err.path)
        if errors:
            message = "; ".join(error.message for error in errors)
            raise ValueError(f"Output contract validation failed: {message}")


def format_response(
    intent: str,
    query: str,
    data: list[dict[str, Any]],
    reasoning: str,
    rules_triggered: list[str],
    skill_used: bool,
    skill_reason: str,
    confidence_score: float,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "query": query,
        "reasoning": reasoning,
        "rules_triggered": rules_triggered,
        "skill_used": skill_used,
        "skill_reason": skill_reason,
        "confidence_score": confidence_score,
        "result_count": len(data),
        "result": data,
    }
