"""A deterministic, offline LLM simulator.

The point of the MockProvider is that the *entire* harness — tests, the example
suite, the dashboard demo — runs with **zero API keys**. But a dumb stub that
returns a constant string would make every target score identically, so the
eval comparison would be meaningless.

Instead, this mock behaves like a tiny, prompt-driven model for the example
"support-ticket triage" task:

* It reads the **requested JSON keys** straight out of the prompt — so a prompt
  that asks for ``type`` instead of ``category`` (a realistic refactor mistake)
  produces output that fails the schema scorer. That is how the regression demo
  works end-to-end with no network.
* It classifies the ticket with keyword heuristics, and applies a **refined**
  rule set when the prompt contains few-shot ``Examples:`` or the model is the
  "large" tier — so better prompts / bigger models genuinely score higher.
* It reports realistic per-model **cost and latency**, so the cost-vs-quality
  view is real.

Everything is deterministic (hash-seeded), so runs are reproducible.
"""

from __future__ import annotations

import hashlib
import json
import re

from .base import LLMResponse, Provider, cost_usd, register_provider

# Per-model economics + behavior. Prices are USD per 1M tokens (roughly modeled
# on real small/large tiers). Two *independent* quality axes keep the demo
# leaderboard interesting:
#   - prompt few-shot examples  -> better CATEGORY accuracy (refined keywords)
#   - bigger model (summary_words) -> better SUMMARY (higher judge score)
# So "small+fewshot" can out-score "large+basic": prompt quality > model size.
MOCK_MODELS = {
    "mock-small": {"price_in": 0.15, "price_out": 0.60, "base_latency": 240.0, "summary_words": 9},
    "mock-large": {"price_in": 3.00, "price_out": 15.00, "base_latency": 820.0, "summary_words": 18},
}
_DEFAULT_MODEL = {"price_in": 0.50, "price_out": 1.50, "base_latency": 400.0, "summary_words": 12}

# Base keyword sets (what the "small" model / terse prompt knows).
CATEGORY_KEYWORDS = {
    "billing": ["refund", "charge", "charged", "invoice", "payment", "billed",
                "subscription", "price", "pricing", "money", "overcharge"],
    "bug": ["error", "crash", "crashed", "broken", "bug", "exception", "500",
            "stack trace", "fails", "failing", "doesn't work", "won't load"],
    "feature_request": ["feature", "add support", "would love", "please add",
                        "wish", "suggestion", "request", "it'd be great"],
    "account": ["login", "log in", "password", "sign in", "signin", "locked out",
                "account", "2fa", "verification", "reset"],
}
# Extra keywords the "large" model / few-shot prompt also recognizes — these fix
# the confusing cases, which is exactly why refined targets score higher.
REFINED_EXTRA = {
    "billing": ["double charged", "charged twice", "billing", "receipt", "plan", "renewed"],
    "bug": ["error code", "blank screen", "not loading", "spinning", "timeout", "glitch"],
    "feature_request": ["could you add", "any plans to", "missing the ability",
                        "no option to", "be able to", "support for"],
    "account": ["mfa", "sso", "email change", "deactivate", "can't get into"],
}

P0 = ["outage", "down", "data loss", "critical", "security breach",
      "everything is broken", "production down", "can't access at all"]
P1 = ["urgent", "asap", "immediately", "blocked", "can't work", "deadline", "losing customers"]
P3 = ["whenever", "no rush", "low priority", "minor", "nice to have", "someday", "not urgent"]

NEG = ["angry", "frustrated", "terrible", "worst", "unacceptable", "ridiculous",
       "furious", "disappointed", "!!!", "cancel", "awful", "annoyed"]
POS = ["thanks", "thank you", "great", "love", "awesome", "appreciate", "fantastic", "amazing"]

_DEFAULT_KEYS = ["category", "priority", "sentiment", "needs_human", "summary"]
_STOP = {"the", "a", "an", "is", "it", "to", "of", "and", "for", "my", "i", "in", "on", "this", "that"}


def _stable_int(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", s.lower()) if w not in _STOP}


def _hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def _classify(ticket: str, refined: bool) -> str:
    t = ticket.lower()
    scores: dict[str, int] = {}
    for cat, base in CATEGORY_KEYWORDS.items():
        kws = base + (REFINED_EXTRA[cat] if refined else [])
        scores[cat] = _hits(t, kws)
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "other"


def _priority(ticket: str) -> str:
    t = ticket.lower()
    if _hits(t, P0):
        return "P0"
    if _hits(t, P1):
        return "P1"
    if _hits(t, P3):
        return "P3"
    return "P2"


def _sentiment(ticket: str) -> str:
    t = ticket.lower()
    if _hits(t, NEG):
        return "negative"
    if _hits(t, POS):
        return "positive"
    return "neutral"


def _requested_keys(prompt: str) -> list[str]:
    m = re.search(r"keys?:\s*([a-zA-Z0-9_,\s]+)", prompt)
    if not m:
        return list(_DEFAULT_KEYS)
    raw = m.group(1)
    keys = [k.strip().lower() for k in raw.split(",")]
    keys = [k for k in keys if re.fullmatch(r"[a-z0-9_]+", k)]
    return keys or list(_DEFAULT_KEYS)


def _extract_ticket(prompt: str) -> str:
    # Use the LAST "TICKET:" so few-shot example tickets aren't picked up.
    idx = prompt.rfind("TICKET:")
    if idx == -1:
        return prompt.strip()
    return prompt[idx + len("TICKET:") :].strip()


@register_provider("mock")
class MockProvider(Provider):
    def complete(self, model: str, prompt: str, params: dict) -> LLMResponse:  # noqa: D401
        cfg = MOCK_MODELS.get(model, _DEFAULT_MODEL)

        if "[[JUDGE]]" in prompt:
            text = self._judge(prompt)
        else:
            text = self._triage(model, prompt, cfg)

        tokens_in = max(1, len(prompt) // 4)
        tokens_out = max(1, len(text) // 4)
        latency = cfg["base_latency"] + (_stable_int(prompt) % 200)
        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(tokens_in, tokens_out, cfg["price_in"], cfg["price_out"]),
            latency_ms=round(latency, 1),
            model=model,
        )

    # ---- task: support-ticket triage ------------------------------------- #
    def _triage(self, model: str, prompt: str, cfg: dict) -> str:
        few_shot = bool(re.search(r"examples?:", prompt, re.I))
        ticket = _extract_ticket(prompt)
        keys = _requested_keys(prompt)

        category = _classify(ticket, refined=few_shot)
        priority = _priority(ticket)
        sentiment = _sentiment(ticket)
        needs_human = category in ("billing", "account") or priority in ("P0", "P1")
        summary = " ".join(ticket.split()[: cfg["summary_words"]])

        values = {
            "category": category,
            "type": category,  # alias used by the regressed prompt
            "priority": priority,
            "sentiment": sentiment,
            "needs_human": needs_human,
            "escalate": needs_human,
            "summary": summary,
        }
        obj = {k: values.get(k, "") for k in keys}
        # Wrap in prose + a code fence on purpose — the JSON extractor must cope.
        return "Here is the structured result:\n```json\n" + json.dumps(obj, indent=2) + "\n```"

    # ---- judge: score a summary against a reference ----------------------- #
    def _judge(self, prompt: str) -> str:
        ref = re.search(r"REFERENCE:\s*(.*?)\s*CANDIDATE:", prompt, re.S)
        cand = re.search(r"CANDIDATE:\s*(.*)", prompt, re.S)
        ref_w = _words(ref.group(1)) if ref else set()
        cand_w = _words(cand.group(1)) if cand else set()
        union = ref_w | cand_w
        jac = (len(ref_w & cand_w) / len(union)) if union else 0.0
        score = round(min(1.0, 0.25 + 1.1 * jac), 2)
        obj = {"score": score, "reason": f"lexical overlap {jac:.2f} with the reference summary"}
        return "```json\n" + json.dumps(obj) + "\n```"
