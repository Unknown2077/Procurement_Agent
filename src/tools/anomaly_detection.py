from __future__ import annotations

from typing import Any

from src.data.adapter import DataAdapter


def run_anomaly_detection(
    query: str,
    adapter: DataAdapter,
) -> tuple[list[dict[str, Any]], list[str], str]:
    query_normalized: str = query.lower()
    limit: int = 10
    rules_triggered: list[str] = []
    results: list[dict[str, Any]] = []

    wants_duplicate: bool = "duplicate" in query_normalized
    wants_overlap: bool = "overlap" in query_normalized
    wants_hps: bool = "hps" in query_normalized or "unusual" in query_normalized

    if not (wants_duplicate or wants_overlap or wants_hps):
        wants_duplicate = True
        wants_overlap = True
        wants_hps = True

    if wants_duplicate:
        duplicate_rows = adapter.get_duplicate_titles(limit=limit)
        results.append({"type": "duplicate_title", "items": duplicate_rows})
        rules_triggered.append("duplicate_title_group_by_normalized_name")

    if wants_overlap:
        overlap_rows = adapter.get_overlap_candidates_same_month(limit=limit)
        results.append({"type": "overlap_same_month_same_purpose", "items": overlap_rows})
        rules_triggered.append("overlap_same_month_and_same_justification")

    if wants_hps:
        outlier_rows = adapter.get_hps_outliers(multiplier=1.35, limit=limit)
        results.append({"type": "hps_outlier_over_135pct_avg", "items": outlier_rows})
        rules_triggered.append("hps_above_135pct_category_average")

    reasoning = (
        "Anomalies are computed with deterministic rules for duplicate titles, "
        "same-month justification overlap, and HPS outliers."
    )
    return results, rules_triggered, reasoning
