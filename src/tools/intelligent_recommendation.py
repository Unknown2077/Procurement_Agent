from __future__ import annotations

import re
from typing import Any

from src.data.adapter import DataAdapter, PackageRow


def run_intelligent_recommendation(
    query: str,
    adapter: DataAdapter,
) -> tuple[list[dict[str, Any]], list[str], str]:
    keyword: str = _extract_keyword(query)
    candidates: list[PackageRow] = _search_candidates_with_synonyms(
        adapter=adapter,
        keyword=keyword,
        limit=10,
    )
    if not candidates:
        return (
            [],
            ["no_matching_package_found"],
            "No package matched the search keyword.",
        )

    recommendations: list[dict[str, Any]] = []
    for row in candidates:
        justifikasi_lower: str = row.justifikasi.lower()
        is_urgent: bool = "urgent" in justifikasi_lower or "special" in justifikasi_lower
        if is_urgent and row.anggaran_rkap_rp < 100_000_000:
            recommended_method = "Direct Appointment"
            reason = "Justification indicates urgent/special need with relatively low value."
        else:
            recommended_method = "Tender"
            reason = "Default governance: use tender for transparency and vendor competition."

        recommendations.append(
            {
                "id_paket": row.id_paket,
                "nama_paket": row.nama_paket,
                "existing_method": row.metode_pengadaan,
                "recommended_method": recommended_method,
                "reason": reason,
                "justifikasi": row.justifikasi,
            }
        )

    return (
        recommendations,
        [
            "rule_urgent_keyword_for_direct_appointment",
            "default_method_tender_without_sop_context",
        ],
        "Recommendations are currently rule-based while waiting for official SOP integration.",
    )


def _extract_keyword(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", query.strip().lower())
    if normalized == "":
        raise ValueError("Recommendation query cannot be empty.")
    stopwords: set[str] = {
        "recommend",
        "recommendation",
        "method",
        "procurement",
        "for",
        "please",
        "give",
        "me",
        "package",
        "based",
        "on",
        "the",
        "what",
        "with",
        "and",
        "or",
        "sop",
        "procedure",
        "company",
    }
    tokens: list[str] = [token for token in normalized.split() if token not in stopwords]
    if not tokens:
        raise ValueError("Recommendation keyword could not be detected from query.")
    return " ".join(tokens[-2:])


def _search_candidates_with_synonyms(
    adapter: DataAdapter,
    keyword: str,
    limit: int,
) -> list[PackageRow]:
    variants = _expand_keyword_variants(keyword=keyword)
    unique_rows: dict[str, PackageRow] = {}
    for variant in variants:
        rows = adapter.search_by_name(keyword=variant, limit=limit)
        for row in rows:
            if row.id_paket in unique_rows:
                continue
            unique_rows[row.id_paket] = row
            if len(unique_rows) >= limit:
                return list(unique_rows.values())
    return list(unique_rows.values())


def _expand_keyword_variants(keyword: str) -> list[str]:
    normalized = keyword.strip().lower()
    if normalized == "":
        raise ValueError("Search keyword cannot be empty.")

    synonym_map: dict[str, tuple[str, ...]] = {
        "laptop": ("laptop", "notebook", "komputer portable"),
        "notebook": ("notebook", "laptop", "komputer portable"),
        "komputer portable": ("komputer portable", "laptop", "notebook"),
    }

    variants: list[str] = [normalized]
    for seed, synonyms in synonym_map.items():
        if seed in normalized:
            for synonym in synonyms:
                if synonym not in variants:
                    variants.append(synonym)
    return variants
