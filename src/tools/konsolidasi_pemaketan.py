from __future__ import annotations

from typing import Any

from src.data.adapter import DataAdapter


def _parse_focus_terms(entities: dict[str, Any]) -> list[str]:
    raw = entities.get("focus_terms")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if t is not None and str(t).strip()]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def run_konsolidasi_pemaketan(
    adapter: DataAdapter,
    entities: dict[str, Any],
    min_score: float = 0.78,
    limit: int = 12,
) -> tuple[list[dict[str, Any]], list[str], str]:
    focus_terms: list[str] = _parse_focus_terms(entities)
    if focus_terms:
        candidates = adapter.get_similarity_candidates_with_focus(
            focus_terms=focus_terms,
            min_score=min_score,
            limit=limit,
        )
        rules_triggered = [
            "token_similarity_cross_division",
            "minimum_similarity_threshold",
            "focus_terms_filter_from_llm",
        ]
        reasoning = (
            "Consolidation candidates are filtered by LLM-extracted focus_terms, "
            "then selected from cross-division package name similarity."
        )
    else:
        candidates = adapter.get_similarity_candidates(min_score=min_score, limit=limit)
        rules_triggered = ["token_similarity_cross_division", "minimum_similarity_threshold"]
        reasoning = (
            "Consolidation candidates are selected from cross-division package name similarity."
        )

    output: list[dict[str, Any]] = []
    for candidate in candidates:
        output.append(
            {
                "left_id_paket": candidate["left_id_paket"],
                "left_nama_paket": candidate["left_nama_paket"],
                "left_divisi": candidate["left_divisi"],
                "right_id_paket": candidate["right_id_paket"],
                "right_nama_paket": candidate["right_nama_paket"],
                "right_divisi": candidate["right_divisi"],
                "similarity_score": candidate["similarity_score"],
                "recommendation": "Consider cross-division consolidation for efficiency.",
            }
        )
    return output, rules_triggered, reasoning
