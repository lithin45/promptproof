"""Structural scorers: is it JSON, and does it match the expected shape?"""

from __future__ import annotations

from .base import Scorer, register_scorer


def _check_type(val, t) -> bool:
    if t is None:
        return True
    return {
        "string": isinstance(val, str),
        "boolean": isinstance(val, bool),
        "number": isinstance(val, (int, float)) and not isinstance(val, bool),
        "integer": isinstance(val, int) and not isinstance(val, bool),
        "array": isinstance(val, list),
        "object": isinstance(val, dict),
    }.get(t, True)


@register_scorer("json_valid")
class JsonValid(Scorer):
    def score(self, case, output, parsed):
        ok = isinstance(parsed, (dict, list))
        return self._result(1.0 if ok else 0.0, ok,
                            "valid JSON" if ok else "output is not parseable JSON")


@register_scorer("json_schema")
class JsonSchema(Scorer):
    """Minimal schema check (no jsonschema dependency).

    config:
      required:   [list of keys that must be present]
      properties: { key: { type: string|boolean|number|integer|array|object,
                           enum: [...] } }
    Score is the fraction of individual checks that pass; `passed` requires all.
    """

    def score(self, case, output, parsed):
        if not isinstance(parsed, dict):
            return self._result(0.0, False, "no JSON object to validate")

        required = self.config.get("required", [])
        props = self.config.get("properties", {})
        checks: list[bool] = []
        problems: list[str] = []

        for key in required:
            present = key in parsed
            checks.append(present)
            if not present:
                problems.append(f"missing '{key}'")

        for key, spec in props.items():
            if key not in parsed:
                continue  # presence handled by `required`
            val = parsed[key]
            type_ok = _check_type(val, spec.get("type"))
            checks.append(type_ok)
            if not type_ok:
                problems.append(f"'{key}' wrong type")
            if "enum" in spec:
                enum_ok = val in spec["enum"]
                checks.append(enum_ok)
                if not enum_ok:
                    problems.append(f"'{key}'={val!r} not in enum")

        total = len(checks) or 1
        passed_n = sum(1 for c in checks if c)
        score = passed_n / total
        return self._result(score, score >= 1.0, "; ".join(problems) or "schema ok")
