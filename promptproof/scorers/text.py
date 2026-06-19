"""Text scorers that work on the raw output or a specific parsed field."""

from __future__ import annotations

import re

from .base import Scorer, register_scorer


def _text(output: str, parsed, field) -> str:
    if field:
        if isinstance(parsed, dict) and field in parsed:
            return str(parsed[field])
        return ""
    return output


@register_scorer("contains")
class Contains(Scorer):
    """config: { any: [...], all: [...], field: <opt>, case_sensitive: <bool> }"""

    def score(self, case, output, parsed):
        field = self.config.get("field")
        cs = self.config.get("case_sensitive", False)
        text = _text(output, parsed, field)
        text = text if cs else text.lower()

        def norm(x: str) -> str:
            return x if cs else x.lower()

        any_ = self.config.get("any", [])
        all_ = self.config.get("all", [])
        ok = True
        problems: list[str] = []
        if any_:
            hit = any(norm(s) in text for s in any_)
            ok = ok and hit
            if not hit:
                problems.append(f"none of {any_}")
        if all_:
            missing = [s for s in all_ if norm(s) not in text]
            ok = ok and not missing
            if missing:
                problems.append(f"missing {missing}")
        return self._result(1.0 if ok else 0.0, ok, "; ".join(problems) or "ok")


@register_scorer("regex")
class Regex(Scorer):
    """config: { pattern: <regex>, field: <opt> }"""

    def score(self, case, output, parsed):
        field = self.config.get("field")
        text = _text(output, parsed, field)
        pattern = self.config["pattern"]
        ok = bool(re.search(pattern, text))
        return self._result(1.0 if ok else 0.0, ok, f"/{pattern}/ {'matched' if ok else 'no match'}")
