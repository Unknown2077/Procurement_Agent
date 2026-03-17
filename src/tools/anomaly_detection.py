from __future__ import annotations

from typing import Any

from src.data.adapter import DataAdapter

ANOMALY_TYPE_DUPLICATE = "duplicate"
ANOMALY_TYPE_OVERLAP = "overlap"
ANOMALY_TYPE_HPS = "hps"
VALID_ANOMALY_TYPES: frozenset[str] = frozenset(
    {ANOMALY_TYPE_DUPLICATE, ANOMALY_TYPE_OVERLAP, ANOMALY_TYPE_HPS}
)


def _parse_anomaly_types(entities: dict[str, Any]) -> list[str]:
    raw = entities.get("anomaly_types")
    if raw is None:
        raise ValueError(
            "Anomaly detection requires anomaly_types in entities. "
            "Specify which checks to run: duplicate, overlap, hps."
        )
    if isinstance(raw, list):
        types = [str(t).strip().lower() for t in raw if t is not None and str(t).strip()]
    else:
        types = [t.strip().lower() for t in str(raw).split(",") if t.strip()]
    filtered = [t for t in types if t in VALID_ANOMALY_TYPES]
    if not filtered:
        raise ValueError(
            f"anomaly_types must include at least one of: {sorted(VALID_ANOMALY_TYPES)}. "
            f"Got: {raw}"
        )
    return filtered


def run_anomaly_detection(
    adapter: DataAdapter,
    entities: dict[str, Any],
    limit: int = 10,
) -> tuple[list[dict[str, Any]], list[str], str]:
    anomaly_types: list[str] = _parse_anomaly_types(entities)
    rules_triggered: list[str] = []
    results: list[dict[str, Any]] = []

    if ANOMALY_TYPE_DUPLICATE in anomaly_types:
        duplicate_rows = adapter.get_duplicate_titles(limit=limit)
        results.append({"type": "duplicate_title_within_divisi_id", "items": duplicate_rows})
        rules_triggered.append("duplicate_title_group_by_normalized_name_and_divisi_id")

    if ANOMALY_TYPE_OVERLAP in anomaly_types:
        overlap_rows = adapter.get_overlap_candidates_same_month(limit=limit)
        results.append({"type": "overlap_same_month_same_purpose", "items": overlap_rows})
        rules_triggered.append("overlap_same_month_and_same_justification")

    if ANOMALY_TYPE_HPS in anomaly_types:
        outlier_rows = adapter.get_hps_outliers(multiplier=1.35, limit=limit)
        results.append({"type": "hps_outlier_over_135pct_avg", "items": outlier_rows})
        rules_triggered.append("hps_above_135pct_category_average")

    reasoning = (
        "Anomalies are computed from LLM-extracted anomaly_types: "
        "duplicate (within same divisi_id), overlap (same month + purpose), HPS outliers."
    )
    return results, rules_triggered, reasoning
