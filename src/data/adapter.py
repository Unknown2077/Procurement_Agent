from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PackageRow:
    id_paket: str
    nama_paket: str
    kategori: str
    divisi_id: str
    divisi: str
    metode_pengadaan: str
    justifikasi: str
    anggaran_rkap_rp: float
    realisasi_rp: float
    vendor_id: str
    vendor: str
    tgl_usulan: str
    tgl_persetujuan: str
    tgl_kontrak: str
    tgl_selesai: str
    status_pengadaan: str
    status_pembayaran: str
    id_kontrak: str
    flag_duplikat_semantik: str
    catatan_anomali: str


class DataAdapter(Protocol):
    def table_health_check(self) -> None: ...

    def get_top_hps_by_division(self, division_keyword: str, limit: int) -> list[PackageRow]: ...

    def get_duplicate_titles(self, limit: int) -> list[dict[str, object]]: ...

    def get_overlap_candidates_same_month(self, limit: int) -> list[dict[str, object]]: ...

    def get_hps_outliers(self, multiplier: float, limit: int) -> list[dict[str, object]]: ...

    def get_similarity_candidates(self, min_score: float, limit: int) -> list[dict[str, object]]: ...

    def get_similarity_candidates_with_focus(
        self,
        focus_terms: list[str],
        min_score: float,
        limit: int,
    ) -> list[dict[str, object]]: ...

    def search_by_name(self, keyword: str, limit: int) -> list[PackageRow]: ...
