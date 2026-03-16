from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSkillPack:
    core_policy: str
    intent_map_yaml: str
    output_contract_json: str

    @staticmethod
    def load(skills_dir: Path) -> "RuntimeSkillPack":
        skill_file: Path = skills_dir / "procurement_agent_skill.md"
        intent_map_file: Path = skills_dir / "intent_map.yaml"
        output_contract_file: Path = skills_dir / "output_contract.json"

        for file_path in (skill_file, intent_map_file, output_contract_file):
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Runtime skill file missing: {file_path}"
                )

        return RuntimeSkillPack(
            core_policy=skill_file.read_text(encoding="utf-8"),
            intent_map_yaml=intent_map_file.read_text(encoding="utf-8"),
            output_contract_json=output_contract_file.read_text(encoding="utf-8"),
        )
