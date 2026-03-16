from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppSettings:
    nvidia_api_key: str
    nim_model: str
    model_temperature: float
    nim_timeout_seconds: int
    nim_max_retries: int
    nim_enabled: bool
    agent_driven_mode: bool
    db_backend: str
    sqlite_path: Path
    trace_log_path: Path

    @staticmethod
    def from_env() -> "AppSettings":
        load_dotenv()

        nvidia_api_key: str = _required_env("NVIDIA_API_KEY")
        nim_model: str = _required_env("NIM_MODEL")
        model_temperature: float = _float_env("MODEL_TEMPERATURE", default=0.2)
        nim_timeout_seconds: int = _int_env("NIM_TIMEOUT_SECONDS", default=30)
        nim_max_retries: int = _int_env("NIM_MAX_RETRIES", default=2)
        nim_enabled: bool = _bool_env("NIM_ENABLED", default=True)
        agent_driven_mode: bool = _bool_env("AGENT_DRIVEN_MODE", default=True)
        db_backend: str = _required_env("DB_BACKEND").lower().strip()
        sqlite_path: Path = Path(_required_env("SQLITE_PATH"))
        trace_log_path: Path = Path(
            os.getenv("TRACE_LOG_PATH", "logs/agent_trace.jsonl").strip()
        )

        if not (0.0 <= model_temperature <= 2.0):
            raise ValueError(
                "MODEL_TEMPERATURE must be between 0.0 and 2.0."
            )
        if nim_timeout_seconds <= 0:
            raise ValueError("NIM_TIMEOUT_SECONDS must be greater than 0.")
        if nim_max_retries < 0:
            raise ValueError("NIM_MAX_RETRIES must be >= 0.")
        if agent_driven_mode and not nim_enabled:
            raise ValueError(
                "NIM_ENABLED must be true when AGENT_DRIVEN_MODE is enabled."
            )
        if db_backend not in {"sqlite"}:
            raise ValueError(
                f"Unsupported DB_BACKEND='{db_backend}'. Supported: sqlite."
            )
        if db_backend == "sqlite" and not sqlite_path.exists():
            raise FileNotFoundError(
                f"SQLITE_PATH not found: {sqlite_path}. Generate DB first."
            )

        return AppSettings(
            nvidia_api_key=nvidia_api_key,
            nim_model=nim_model,
            model_temperature=model_temperature,
            nim_timeout_seconds=nim_timeout_seconds,
            nim_max_retries=nim_max_retries,
            nim_enabled=nim_enabled,
            agent_driven_mode=agent_driven_mode,
            db_backend=db_backend,
            sqlite_path=sqlite_path,
            trace_log_path=trace_log_path,
        )


def _required_env(name: str) -> str:
    value: str | None = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _float_env(name: str, default: float) -> float:
    raw: str | None = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a float. Got: {raw}") from exc


def _int_env(name: str, default: int) -> int:
    raw: str | None = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer. Got: {raw}") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw: str | None = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized: str = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{name} must be boolean-like. Got: {raw}")
