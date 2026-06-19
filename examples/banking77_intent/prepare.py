"""Build the banking77 real-data eval example.

Downloads the banking77 benchmark (real banking customer-support messages
labeled with one of 77 intents), samples a test set, and generates:
  - dataset.jsonl        (sampled test cases: message + gold intent)
  - prompts/basic.txt     (zero-shot classifier prompt)
  - prompts/fewshot.txt   (few-shot prompt; examples drawn from TRAIN, no leakage)
  - suite.openai.yaml     (gpt-4o-mini vs gpt-4o, basic vs few-shot)
  - suite.anthropic.yaml  (claude-haiku vs claude-sonnet, basic vs few-shot)

Reproducible (seeded) and stdlib-only. Re-run any time: `python prepare.py`.

Dataset: PolyAI banking77 — https://github.com/PolyAI-LDN/task-specific-datasets
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import urllib.request

import yaml

BASE = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data"
HERE = os.path.dirname(os.path.abspath(__file__))
N = 50
SEED = 7


def fetch(name: str) -> str:
    with urllib.request.urlopen(f"{BASE}/{name}") as r:  # noqa: S310 (trusted URL)
        return r.read().decode("utf-8")


def read_csv(text: str) -> list[tuple[str, str]]:
    rows = csv.DictReader(io.StringIO(text))
    return [(r["text"].strip(), r["category"].strip()) for r in rows if r.get("text") and r.get("category")]


def make_suite(provider: str, small: str, large: str, categories: list[str]) -> dict:
    target = lambda model, prompt: {  # noqa: E731
        "id": f"{model} + {'fewshot' if 'fewshot' in prompt else 'basic'}",
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "params": {"temperature": 0, "max_tokens": 50},
    }
    return {
        "name": f"Banking77 Intent ({provider})",
        "description": (
            "Real banking77 intent classification (77 intents). Compares a basic "
            "vs few-shot prompt across two model tiers, scored on real accuracy."
        ),
        "dataset": "dataset.jsonl",
        "targets": [
            target(small, "prompts/basic.txt"),
            target(small, "prompts/fewshot.txt"),
            target(large, "prompts/basic.txt"),
            target(large, "prompts/fewshot.txt"),
        ],
        "scorers": [
            {
                "name": "json_schema",
                "weight": 1,
                "config": {"required": ["category"], "properties": {"category": {"type": "string", "enum": categories}}},
            },
            # Accuracy is the task — weight it highest.
            {"name": "field_exact", "weight": 3, "config": {"field": "category"}},
        ],
        "thresholds": {"max_score_drop": 0.02, "max_pass_rate_drop": 0.05},
    }


def main() -> None:
    categories = json.loads(fetch("categories.json"))
    test = read_csv(fetch("test.csv"))
    train = read_csv(fetch("train.csv"))

    sample = random.Random(SEED).sample(test, N)

    os.makedirs(os.path.join(HERE, "prompts"), exist_ok=True)
    with open(os.path.join(HERE, "dataset.jsonl"), "w", encoding="utf-8") as f:
        for i, (text, cat) in enumerate(sample, 1):
            f.write(json.dumps({"id": f"b{i:03d}", "input": text, "expected": {"category": cat}}) + "\n")

    label_block = "\n".join(f"- {c}" for c in categories)
    header = (
        "You are a banking customer-support intent classifier.\n"
        'Classify the message into EXACTLY ONE of these intents and return ONLY JSON: {"category": "<intent>"}.\n\n'
        f"Valid intents:\n{label_block}\n\n"
    )

    # Few-shot examples from TRAIN (distinct intents) — never from the test sample.
    seen: set[str] = set()
    examples: list[tuple[str, str]] = []
    for text, cat in train:
        if cat not in seen:
            seen.add(cat)
            examples.append((text, cat))
        if len(examples) >= 3:
            break
    ex_block = "\n".join(f'MESSAGE: {t}\n{{"category": "{c}"}}' for t, c in examples)

    with open(os.path.join(HERE, "prompts", "basic.txt"), "w", encoding="utf-8") as f:
        f.write(header + "MESSAGE: {{input}}\n")
    with open(os.path.join(HERE, "prompts", "fewshot.txt"), "w", encoding="utf-8") as f:
        f.write(header + f"Examples:\n{ex_block}\n\nMESSAGE: {{{{input}}}}\n")

    for fname, provider, small, large in [
        ("suite.openai.yaml", "openai", "gpt-4o-mini", "gpt-4o"),
        ("suite.anthropic.yaml", "anthropic", "claude-haiku-4-5", "claude-sonnet-4-6"),
    ]:
        with open(os.path.join(HERE, fname), "w", encoding="utf-8") as f:
            yaml.safe_dump(make_suite(provider, small, large, categories), f, sort_keys=False, width=4000)

    print(f"✓ wrote {N} test cases, {len(categories)} intents, 2 prompts, 2 suites")
    print(f"  few-shot examples: {[c for _, c in examples]}")


if __name__ == "__main__":
    main()
