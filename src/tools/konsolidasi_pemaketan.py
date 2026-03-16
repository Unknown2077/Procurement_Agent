from __future__ import annotations

from typing import Any

from src.data.adapter import DataAdapter


def run_konsolidasi_pemaketan(
    adapter: DataAdapter,
    min_score: float = 0.78,
    limit: int = 12,
) -> tuple[list[dict[str, Any]], list[str], str]:
    candidates = adapter.get_similarity_candidates(
        min_score=min_score,
        limit=limit,
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
    return (
        output,
        ["token_similarity_cross_division", "minimum_similarity_threshold"],
        "Consolidation candidates are selected from cross-division package name similarity.",
    )
