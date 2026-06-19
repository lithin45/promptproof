"""Field-level scorers: compare a value in the parsed JSON to a gold value."""

from __future__ import annotations

from .base import Scorer, register_scorer


def _gold(case, config, field):
    return case.expected.get(config.get("expected_key", field))


def _norm(v) -> str:
    return str(v).strip().lower()


def _map(v, mapping):
    if mapping is not None:
        return mapping.get(str(v))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@register_scorer("field_exact")
class FieldExact(Scorer):
    """Exact (case-insensitive) match of parsed[field] vs the gold value.

    config: { field: <key>, expected_key: <optional gold key in case.expected> }
    """

    def score(self, case, output, parsed):
        field = self.config["field"]
        if not isinstance(parsed, dict) or field not in parsed:
            return self._result(0.0, False, f"'{field}' missing from output")
        gold = _gold(case, self.config, field)
        if gold is None:
            return self._result(0.0, False, f"no gold value for '{field}'")
        ok = _norm(parsed[field]) == _norm(gold)
        return self._result(1.0 if ok else 0.0, ok, f"got {parsed[field]!r}, expected {gold!r}")


@register_scorer("field_tolerance")
class FieldTolerance(Scorer):
    """Graded numeric match within a tolerance (e.g. priority within one level).

    config: { field, tolerance: <int>, mapping: {label: number}, range: <int> }
    """

    def score(self, case, output, parsed):
        field = self.config["field"]
        tol = self.config.get("tolerance", 0)
        mapping = self.config.get("mapping")
        if not isinstance(parsed, dict) or field not in parsed:
            return self._result(0.0, False, f"'{field}' missing from output")
        gold = _gold(case, self.config, field)
        pv, gv = _map(parsed[field], mapping), _map(gold, mapping)
        if pv is None or gv is None:
            return self._result(0.0, False, f"can't map values ({parsed[field]!r} vs {gold!r})")
        diff = abs(pv - gv)
        rng = self.config.get("range", 3) or 1
        score = max(0.0, 1.0 - diff / rng)
        return self._result(score, diff <= tol, f"|{pv}-{gv}|={diff:g} (tol {tol})")
