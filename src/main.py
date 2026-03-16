from __future__ import annotations

import argparse
from pathlib import Path

from src.agent.orchestrator import AgentOrchestrator
from src.agent.response_formatter import OutputContractValidator
from src.config.runtime import RuntimeSkillPack
from src.config.settings import AppSettings
from src.data.sqlite_repo import SQLiteRepository
from src.interfaces.cli import render_json
from src.llm.nim_client import NIMClient
from src.observability.trace_logger import TraceLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Procurement CLI Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser("query", help="Run one procurement query")
    query_parser.add_argument("text", type=str, help="Natural language query")

    subparsers.add_parser(
        "preflight",
        help="Validate env, DB, skill pack, and NIM health before running agent",
    )
    return parser.parse_args()


def build_orchestrator(settings: AppSettings) -> AgentOrchestrator:
    adapter = SQLiteRepository(settings.sqlite_path)
    skills_dir = Path("src/skills")
    skill_pack = RuntimeSkillPack.load(skills_dir=skills_dir)
    validator = OutputContractValidator(contract_json_text=skill_pack.output_contract_json)
    trace_logger = TraceLogger(output_path=settings.trace_log_path)

    if not settings.nim_enabled:
        raise RuntimeError(
            "NIM_ENABLED must be true for agent-driven routing."
        )
    nim_client = NIMClient(
        api_key=settings.nvidia_api_key,
        model=settings.nim_model,
        temperature=settings.model_temperature,
        timeout_seconds=settings.nim_timeout_seconds,
        max_retries=settings.nim_max_retries,
    )

    return AgentOrchestrator(
        adapter=adapter,
        contract_validator=validator,
        skill_pack=skill_pack,
        trace_logger=trace_logger,
        nim_client=nim_client,
    )


def run_preflight(settings: AppSettings) -> None:
    print("[preflight] Loading runtime skill pack...")
    skill_pack = RuntimeSkillPack.load(skills_dir=Path("src/skills"))
    OutputContractValidator(contract_json_text=skill_pack.output_contract_json)
    print("[preflight] Output contract is valid.")

    print("[preflight] Checking database...")
    repo = SQLiteRepository(settings.sqlite_path)
    repo.table_health_check()
    print("[preflight] Database tables are healthy.")

    if not settings.nim_enabled:
        raise RuntimeError(
            "NIM_ENABLED must be true for agent-driven routing preflight."
        )

    print("[preflight] Checking NVIDIA NIM connectivity...")
    nim_client = NIMClient(
        api_key=settings.nvidia_api_key,
        model=settings.nim_model,
        temperature=settings.model_temperature,
        timeout_seconds=settings.nim_timeout_seconds,
        max_retries=settings.nim_max_retries,
    )
    nim_client.healthcheck()
    print("[preflight] NIM health check passed.")

    print("[preflight] OK")


def main() -> None:
    args = parse_args()
    settings = AppSettings.from_env()

    if args.command == "preflight":
        run_preflight(settings)
        return

    if args.command == "query":
        orchestrator = build_orchestrator(settings)
        payload = orchestrator.handle_query(args.text)
        render_json(payload)
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
