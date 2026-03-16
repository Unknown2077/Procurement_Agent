from __future__ import annotations

from dataclasses import dataclass

from src.agent.intents import IntentResult, IntentType
from src.llm.nim_client import NIMClient


@dataclass(frozen=True)
class SkillDecision:
    use_core_policy: bool
    use_feature_playbook: bool
    reason: str
    confidence_score: float


def decide_skill_usage(
    query: str,
    intent_result: IntentResult,
    nim_client: NIMClient,
) -> SkillDecision:
    prompt = (
        "Decide whether procurement response should use feature playbook.\n"
        "Return STRICT JSON only with keys: use_core_policy, use_feature_playbook, "
        "reason, confidence_score.\n"
        "use_core_policy and use_feature_playbook must be booleans.\n"
        "confidence_score must be between 0.0 and 1.0.\n"
        f"Query: {query}\n"
        f"Intent: {intent_result.intent.value}\n"
        f"Intent confidence: {intent_result.confidence}\n"
        f"Complexity score: {intent_result.complexity_score}\n"
        f"Entities: {intent_result.entities}"
    )
    payload = nim_client.summarize_json(
        prompt=prompt,
        required_keys=(
            "use_core_policy",
            "use_feature_playbook",
            "reason",
            "confidence_score",
        ),
    )
    use_core_policy = _coerce_bool(payload["use_core_policy"], "use_core_policy")
    use_feature_playbook = _coerce_bool(
        payload["use_feature_playbook"],
        "use_feature_playbook",
    )
    reason = str(payload["reason"]).strip()
    if reason == "":
        raise RuntimeError("NIM response field 'reason' must be a non-empty string.")
    confidence_score = _coerce_unit_interval(
        payload["confidence_score"],
        "confidence_score",
    )
    return SkillDecision(
        use_core_policy=use_core_policy,
        use_feature_playbook=use_feature_playbook,
        reason=reason,
        confidence_score=confidence_score,
    )


def _coerce_bool(raw_value: object, field_name: str) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    raise RuntimeError(f"NIM response field '{field_name}' must be a boolean.")


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
