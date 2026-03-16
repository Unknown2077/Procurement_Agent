from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class NIMClient:
    api_key: str
    model: str
    temperature: float
    timeout_seconds: int
    max_retries: int

    def summarize(self, prompt: str) -> str:
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as exc:
            raise RuntimeError(
                "langchain-nvidia-ai-endpoints is not installed. Run `uv sync`."
            ) from exc

        llm = ChatNVIDIA(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            model_kwargs={
                "timeout": self.timeout_seconds,
                "max_retries": self.max_retries,
            },
        )
        response = llm.invoke(prompt)
        content = getattr(response, "content", None)
        if not isinstance(content, str) or content.strip() == "":
            raise RuntimeError("NIM API returned empty content.")
        return content.strip()

    def summarize_json(self, prompt: str, required_keys: tuple[str, ...]) -> dict[str, Any]:
        raw_output: str = self.summarize(prompt)
        parsed_output: dict[str, Any] = _parse_json_object(raw_output)
        missing_keys: list[str] = [
            key for key in required_keys if key not in parsed_output
        ]
        if missing_keys:
            raise RuntimeError(
                "NIM JSON response is missing required keys: "
                + ", ".join(missing_keys)
            )
        return parsed_output

    def healthcheck(self) -> None:
        prompt = "Reply exactly with: NIM_HEALTH_OK"
        result: str = self.summarize(prompt)
        if "NIM_HEALTH_OK" not in result:
            raise RuntimeError(
                f"NIM healthcheck failed. Unexpected response: {result}"
            )


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    stripped: str = raw_text.strip()
    candidates: tuple[str, ...] = (stripped, _strip_code_fence(stripped))
    for candidate in candidates:
        if candidate == "":
            continue
        try:
            parsed: Any = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(
        "NIM response is not a valid JSON object. "
        "Ensure the model returns raw JSON without extra text."
    )


def _strip_code_fence(text: str) -> str:
    if text.startswith("```") and text.endswith("```"):
        lines: list[str] = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text
