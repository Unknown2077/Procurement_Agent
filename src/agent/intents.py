from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any

from src.llm.nim_client import NIMClient


class IntentType(StrEnum):
    CATEGORY_MANAGEMENT = "category_management"
    ANOMALY_DETECTION = "anomaly_detection"
    INTELLIGENT_RECOMMENDATION = "intelligent_recommendation"
    KONSOLIDASI_PEMAKETAN = "konsolidasi_pemaketan"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    intent: IntentType
    confidence: float
    entities: dict[str, str]
    complexity_score: float


def parse_intent(query: str, nim_client: NIMClient) -> IntentResult:
    normalized_query: str = query.strip()
    if normalized_query == "":
        raise ValueError("Query cannot be empty.")

    prompt = (
        "Classify procurement query intent and extract entities.\n"
        "Return STRICT JSON only with keys: intent, confidence, entities, complexity_score.\n"
        "intent must be one of: category_management, anomaly_detection, "
        "intelligent_recommendation, konsolidasi_pemaketan, unknown.\n"
        "confidence and complexity_score must be between 0.0 and 1.0.\n"
        f"Query: {normalized_query}"
    )
    payload = nim_client.summarize_json(
        prompt=prompt,
        required_keys=("intent", "confidence", "entities", "complexity_score"),
    )
    intent_value = str(payload["intent"]).strip().lower()
    try:
        intent = IntentType(intent_value)
    except ValueError as exc:
        raise RuntimeError(
            f"NIM returned unsupported intent '{intent_value}'."
        ) from exc

    confidence = _coerce_unit_interval(payload["confidence"], field_name="confidence")
    complexity_score = _coerce_unit_interval(
        payload["complexity_score"],
        field_name="complexity_score",
    )
    entities_raw = payload["entities"]
    entities_raw = _normalize_entities(entities_raw)
    entities: dict[str, str] = {}
    for key, value in entities_raw.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text == "" or value_text == "":
            continue
        entities[key_text] = value_text

    return IntentResult(
        intent=intent,
        confidence=confidence,
        entities=entities,
        complexity_score=complexity_score,
    )


def _coerce_unit_interval(raw_value: object, field_name: str) -> float:
    try:
        parsed_value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"NIM response field '{field_name}' must be numeric."
        ) from exc
    if not 0.0 <= parsed_value <= 1.0:
        raise RuntimeError(
            f"NIM response field '{field_name}' must be between 0.0 and 1.0."
        )
    return parsed_value


def _normalize_entities(raw_entities: object) -> dict[str, Any]:
    if raw_entities is None:
        return {}
    if isinstance(raw_entities, dict):
        return raw_entities
    if isinstance(raw_entities, list):
        if len(raw_entities) == 0:
            return {}
        return _map_entities_from_list(raw_entities)
    if isinstance(raw_entities, str):
        raw_text = raw_entities.strip()
        if raw_text == "":
            return {}
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "NIM response field 'entities' must be a JSON object. "
                "Got non-JSON string."
            ) from exc
        if parsed is None:
            return {}
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and len(parsed) == 0:
            return {}
        if isinstance(parsed, list):
            return _map_entities_from_list(parsed)
    raise RuntimeError(
        "NIM response field 'entities' must be a JSON object, null, or empty array."
    )


def _map_entities_from_list(raw_entities: list[object]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        candidate_key = _first_non_empty(
            item.get("key"),
            item.get("name"),
            item.get("entity"),
            item.get("field"),
            item.get("type"),
        )
        candidate_value = _first_non_empty(
            item.get("value"),
            item.get("text"),
            item.get("content"),
            item.get("normalized"),
        )
        if candidate_key is None:
            if len(item) == 1:
                first_key, first_value = next(iter(item.items()))
                candidate_key = _first_non_empty(first_key)
                candidate_value = _first_non_empty(first_value)
            else:
                continue
        if candidate_value is None:
            continue
        mapped[candidate_key] = candidate_value
    return mapped


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text != "":
            return text
    return None
