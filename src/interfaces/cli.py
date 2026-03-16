from __future__ import annotations

import json
from typing import Any


def render_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
