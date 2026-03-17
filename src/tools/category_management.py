from __future__ import annotations

import re
from typing import Any


from src.data.adapter import DataAdapter


def run_category_management(
    query: str,
    adapter: DataAdapter,
    entities: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], str]:
    raw_division = entities.get("division", "Divisi SDM")
    if isinstance(raw_division, list) and raw_division:
        division = str(raw_division[0])
    else:
        division = str(raw_division) if raw_division else "Divisi SDM"
    limit: int = _extract_limit(query, default=10)

    rows = adapter.get_top_hps_by_division(division_keyword=division, limit=limit)
    payload = [
        {
            "id_paket": row.id_paket,
            "nama_paket": row.nama_paket,
            "divisi": row.divisi,
            "kategori": row.kategori,
            "anggaran_rkap_rp": row.anggaran_rkap_rp,
            "metode_pengadaan": row.metode_pengadaan,
        }
        for row in rows
    ]
    rules_triggered = [
        "filter_division_contains_keyword",
        "sort_by_anggaran_rkap_desc",
        "limit_applied",
    ]
    reasoning = (
        f"Data is filtered for division '{division}', then sorted by "
        "highest anggaran_rkap_rp."
    )
    return payload, rules_triggered, reasoning


def _extract_limit(query: str, default: int) -> int:
    match = re.search(r"\b(?:top|limit)\s+(\d+)\b", query.lower())
    if not match:
        return default
    return max(1, min(int(match.group(1)), 100))
