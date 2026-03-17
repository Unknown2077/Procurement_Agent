from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RuntimeSkillPack:
    """Skill pack with on-demand loading. Only output_contract is loaded at init."""

    skills_dir: Path
    _output_contract_json: str
    _core_policy: str | None = None

    @property
    def output_contract_json(self) -> str:
        return self._output_contract_json

    @property
    def core_policy(self) -> str:
        if self._core_policy is None:
            skill_file = self.skills_dir / "procurement_agent_skill.md"
            if not skill_file.exists():
                raise FileNotFoundError(f"Skill file missing: {skill_file}")
            self._core_policy = skill_file.read_text(encoding="utf-8")
        return self._core_policy

    @property
    def intent_map_yaml(self) -> str:
        intent_map_file = self.skills_dir / "intent_map.yaml"
        if not intent_map_file.exists():
            raise FileNotFoundError(f"Intent map missing: {intent_map_file}")
        return intent_map_file.read_text(encoding="utf-8")

    @staticmethod
    def load(skills_dir: Path) -> "RuntimeSkillPack":
        skills_dir = Path(skills_dir)
        output_contract_file = skills_dir / "output_contract.json"
        if not output_contract_file.exists():
            raise FileNotFoundError(f"Output contract missing: {output_contract_file}")
        return RuntimeSkillPack(
            skills_dir=skills_dir,
            _output_contract_json=output_contract_file.read_text(encoding="utf-8"),
        )
