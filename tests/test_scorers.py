"""Unit tests for the built-in scorers."""

from promptproof.scorers import get_scorer
from promptproof.types import Case, ScorerSpec


def make(name, **config):
    return get_scorer(ScorerSpec(name=name, weight=1.0, config=config))


def case(expected=None):
    return Case(id="x", input="i", expected=expected or {})


def test_json_valid():
    sc = make("json_valid")
    assert sc.score(case(), "{}", {}).passed
    assert not sc.score(case(), "not json", None).passed


def test_json_schema_pass_and_fail():
    sc = make(
        "json_schema",
        required=["category", "needs_human"],
        properties={
            "category": {"type": "string", "enum": ["billing", "bug"]},
            "needs_human": {"type": "boolean"},
        },
    )
    good = sc.score(case(), "", {"category": "billing", "needs_human": True})
    assert good.passed and good.score == 1.0

    bad = sc.score(case(), "", {"category": "nope"})  # missing key + bad enum
    assert not bad.passed and bad.score < 1.0


def test_field_exact_is_case_insensitive():
    sc = make("field_exact", field="category")
    c = case({"category": "Billing"})
    assert sc.score(c, "", {"category": "billing"}).passed
    assert not sc.score(c, "", {"category": "bug"}).passed
    assert not sc.score(c, "", {}).passed  # missing field


def test_field_tolerance():
    sc = make(
        "field_tolerance",
        field="priority",
        tolerance=1,
        range=3,
        mapping={"P0": 0, "P1": 1, "P2": 2, "P3": 3},
    )
    c = case({"priority": "P2"})
    assert sc.score(c, "", {"priority": "P1"}).passed  # within tolerance
    off = sc.score(c, "", {"priority": "P0"})  # off by two
    assert not off.passed and 0.0 <= off.score < 1.0


def test_contains_and_regex():
    contains = make("contains", any=["refund", "charge"])
    assert contains.score(case(), "please refund me", None).passed
    assert not contains.score(case(), "hello world", None).passed

    rx = make("regex", pattern=r"^P[0-3]$", field="priority")
    assert rx.score(case(), "", {"priority": "P0"}).passed
    assert not rx.score(case(), "", {"priority": "high"}).passed


def test_llm_judge_offline():
    sc = make(
        "llm_judge",
        field="summary",
        reference_key="summary",
        provider="mock",
        model="mock-large",
        threshold=0.3,
    )
    c = case({"summary": "the app crashes with a 500 error"})
    good = sc.score(c, "", {"summary": "the app crashes with a 500 error on upload"})
    assert good.passed and good.score > 0.3
    bad = sc.score(c, "", {"summary": "totally unrelated text about pizza"})
    assert bad.score < good.score
