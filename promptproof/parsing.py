"""Best-effort JSON extraction from model output.

LLMs love to wrap JSON in prose and ```code fences```. This pulls the first
valid JSON value out of a noisy string so structured scorers have something to
grade. Returns None if nothing parses.
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str | None) -> Any:
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = (fenced.group(1) if fenced else text).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fall back to the first balanced {...} object.
    start = candidate.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(candidate[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None
