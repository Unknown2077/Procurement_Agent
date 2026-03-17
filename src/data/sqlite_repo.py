from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from rapidfuzz import fuzz

from src.data.adapter import DataAdapter, PackageRow


FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|ATTACH|DETACH|PRAGMA)\b",
    flags=re.IGNORECASE,
)


class SQLiteRepository(DataAdapter):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        if not db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")

    def table_health_check(self) -> None:
        expected_tables: set[str] = {
            "dokumen_pengadaan",
            "master_vendor",
            "master_divisi",
            "mapping_3_database",
        }
        with self._connect() as connection:
            rows = self._execute_readonly(
                connection,
                "SELECT name FROM sqlite_master WHERE type='table';",
                (),
            )
            existing_tables: set[str] = {row["name"] for row in rows}

        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise ValueError(
                f"Missing required tables in DB: {', '.join(sorted(missing_tables))}"
            )

    def get_top_hps_by_division(self, division_keyword: str, limit: int) -> list[PackageRow]:
        safe_limit: int = max(1, min(limit, 100))
        pattern: str = f"%{division_keyword}%"
        sql = """
            SELECT *
            FROM dokumen_pengadaan
            WHERE lower(divisi) LIKE lower(?)
            ORDER BY anggaran_rkap_rp DESC
            LIMIT ?;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, (pattern, safe_limit))
        return [self._to_package_row(row) for row in rows]

    def get_duplicate_titles(self, limit: int) -> list[dict[str, object]]:
        safe_limit: int = max(1, min(limit, 100))
        sql = """
            SELECT
              lower(trim(nama_paket)) AS normalized_name,
              divisi_id,
              divisi,
              COUNT(*) AS total,
              GROUP_CONCAT(id_paket) AS paket_ids
            FROM dokumen_pengadaan
            WHERE divisi_id IS NOT NULL AND trim(divisi_id) <> ''
            GROUP BY lower(trim(nama_paket)), divisi_id
            HAVING COUNT(*) > 1
            ORDER BY total DESC, normalized_name ASC
            LIMIT ?;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, (safe_limit,))
        return [dict(row) for row in rows]

    def get_overlap_candidates_same_month(self, limit: int) -> list[dict[str, object]]:
        safe_limit: int = max(1, min(limit, 100))
        sql = """
            SELECT
              substr(tgl_usulan, 1, 7) AS month_bucket,
              lower(trim(justifikasi)) AS normalized_purpose,
              COUNT(*) AS total,
              GROUP_CONCAT(id_paket) AS paket_ids,
              GROUP_CONCAT(nama_paket) AS paket_names
            FROM dokumen_pengadaan
            WHERE tgl_usulan IS NOT NULL
              AND trim(tgl_usulan) <> ''
              AND justifikasi IS NOT NULL
              AND trim(justifikasi) <> ''
            GROUP BY month_bucket, normalized_purpose
            HAVING COUNT(*) > 1
            ORDER BY total DESC
            LIMIT ?;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, (safe_limit,))
        return [dict(row) for row in rows]

    def get_hps_outliers(self, multiplier: float, limit: int) -> list[dict[str, object]]:
        safe_limit: int = max(1, min(limit, 100))
        if multiplier <= 1.0:
            raise ValueError("Multiplier must be > 1.0 for outlier detection.")
        sql = """
            WITH category_avg AS (
              SELECT kategori, AVG(anggaran_rkap_rp) AS avg_hps
              FROM dokumen_pengadaan
              GROUP BY kategori
            )
            SELECT
              d.id_paket,
              d.nama_paket,
              d.kategori,
              d.divisi,
              d.anggaran_rkap_rp,
              c.avg_hps,
              ROUND(d.anggaran_rkap_rp / c.avg_hps, 4) AS ratio_to_avg
            FROM dokumen_pengadaan d
            JOIN category_avg c ON d.kategori = c.kategori
            WHERE d.anggaran_rkap_rp > (? * c.avg_hps)
            ORDER BY ratio_to_avg DESC
            LIMIT ?;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, (multiplier, safe_limit))
        return [dict(row) for row in rows]

    def get_similarity_candidates(self, min_score: float, limit: int) -> list[dict[str, object]]:
        if not (0.0 <= min_score <= 1.0):
            raise ValueError("min_score must be between 0.0 and 1.0.")
        safe_limit: int = max(1, min(limit, 200))
        sql = """
            SELECT id_paket, nama_paket, divisi, kategori, anggaran_rkap_rp
            FROM dokumen_pengadaan
            ORDER BY nama_paket ASC;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, ())

        candidates: list[dict[str, object]] = []
        for left_idx in range(len(rows)):
            left_row = rows[left_idx]
            for right_idx in range(left_idx + 1, len(rows)):
                right_row = rows[right_idx]
                if left_row["id_paket"] == right_row["id_paket"]:
                    continue
                if left_row["divisi"] == right_row["divisi"]:
                    continue
                score = fuzz.token_sort_ratio(
                    left_row["nama_paket"],
                    right_row["nama_paket"],
                ) / 100.0
                if score < min_score:
                    continue
                candidates.append(
                    {
                        "left_id_paket": left_row["id_paket"],
                        "left_nama_paket": left_row["nama_paket"],
                        "left_divisi": left_row["divisi"],
                        "right_id_paket": right_row["id_paket"],
                        "right_nama_paket": right_row["nama_paket"],
                        "right_divisi": right_row["divisi"],
                        "similarity_score": round(score, 4),
                    }
                )
                if len(candidates) >= safe_limit:
                    return candidates
        return candidates

    def get_similarity_candidates_with_focus(
        self,
        focus_terms: list[str],
        min_score: float,
        limit: int,
    ) -> list[dict[str, object]]:
        if not (0.0 <= min_score <= 1.0):
            raise ValueError("min_score must be between 0.0 and 1.0.")
        safe_limit: int = max(1, min(limit, 200))
        if not focus_terms:
            return self.get_similarity_candidates(min_score=min_score, limit=safe_limit)

        patterns = tuple(
            f"%{str(term).strip().lower()}%" for term in focus_terms if term and str(term).strip()
        )
        if not patterns:
            return self.get_similarity_candidates(min_score=min_score, limit=safe_limit)

        sql = f"""
            SELECT id_paket, nama_paket, divisi, divisi_id, kategori, anggaran_rkap_rp
            FROM dokumen_pengadaan
            WHERE {" OR ".join("lower(nama_paket) LIKE ?" for _ in patterns)}
            ORDER BY nama_paket ASC;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, patterns)

        candidates: list[dict[str, object]] = []
        for left_idx in range(len(rows)):
            left_row = rows[left_idx]
            for right_idx in range(left_idx + 1, len(rows)):
                right_row = rows[right_idx]
                if left_row["id_paket"] == right_row["id_paket"]:
                    continue
                if left_row["divisi"] == right_row["divisi"]:
                    continue
                score = fuzz.token_sort_ratio(
                    left_row["nama_paket"],
                    right_row["nama_paket"],
                ) / 100.0
                if score < min_score:
                    continue
                candidates.append(
                    {
                        "left_id_paket": left_row["id_paket"],
                        "left_nama_paket": left_row["nama_paket"],
                        "left_divisi": left_row["divisi"],
                        "right_id_paket": right_row["id_paket"],
                        "right_nama_paket": right_row["nama_paket"],
                        "right_divisi": right_row["divisi"],
                        "similarity_score": round(score, 4),
                    }
                )
                if len(candidates) >= safe_limit:
                    return candidates
        return candidates

    def search_by_name(self, keyword: str, limit: int) -> list[PackageRow]:
        safe_limit: int = max(1, min(limit, 100))
        pattern: str = f"%{keyword}%"
        sql = """
            SELECT *
            FROM dokumen_pengadaan
            WHERE lower(nama_paket) LIKE lower(?)
            ORDER BY anggaran_rkap_rp DESC
            LIMIT ?;
        """
        with self._connect() as connection:
            rows = self._execute_readonly(connection, sql, (pattern, safe_limit))
        return [self._to_package_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection: sqlite3.Connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _execute_readonly(
        self,
        connection: sqlite3.Connection,
        sql: str,
        params: tuple[object, ...],
    ) -> list[sqlite3.Row]:
        if FORBIDDEN_SQL_PATTERN.search(sql):
            raise ValueError("Blocked non-readonly SQL statement.")
        cursor = connection.execute(sql, params)
        return cursor.fetchall()

    @staticmethod
    def _to_package_row(row: sqlite3.Row) -> PackageRow:
        return PackageRow(
            id_paket=str(row["id_paket"] or ""),
            nama_paket=str(row["nama_paket"] or ""),
            kategori=str(row["kategori"] or ""),
            divisi_id=str(row["divisi_id"] or ""),
            divisi=str(row["divisi"] or ""),
            metode_pengadaan=str(row["metode_pengadaan"] or ""),
            justifikasi=str(row["justifikasi"] or ""),
            anggaran_rkap_rp=float(row["anggaran_rkap_rp"] or 0.0),
            realisasi_rp=float(row["realisasi_rp"] or 0.0),
            vendor_id=str(row["vendor_id"] or ""),
            vendor=str(row["vendor"] or ""),
            tgl_usulan=str(row["tgl_usulan"] or ""),
            tgl_persetujuan=str(row["tgl_persetujuan"] or ""),
            tgl_kontrak=str(row["tgl_kontrak"] or ""),
            tgl_selesai=str(row["tgl_selesai"] or ""),
            status_pengadaan=str(row["status_pengadaan"] or ""),
            status_pembayaran=str(row["status_pembayaran"] or ""),
            id_kontrak=str(row["id_kontrak"] or ""),
            flag_duplikat_semantik=str(row["flag_duplikat_semantik"] or ""),
            catatan_anomali=str(row["catatan_anomali"] or ""),
        )
