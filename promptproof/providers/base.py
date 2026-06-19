"""Provider abstraction + a tiny registry.

A Provider turns (model, prompt, params) into an LLMResponse carrying the text
plus the bookkeeping an eval harness cares about: tokens, cost, latency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    model: str


class Provider:
    def complete(self, model: str, prompt: str, params: dict) -> LLMResponse:  # noqa: D401
        raise NotImplementedError


def cost_usd(tokens_in: int, tokens_out: int, price_in: float, price_out: float) -> float:
    """price_* are USD per 1M tokens."""
    return tokens_in / 1_000_000 * price_in + tokens_out / 1_000_000 * price_out


def with_retry(do_request, max_retries: int = 4, retry_on=(429, 500, 502, 503, 529)):
    """Call do_request() (-> a requests.Response), retrying transient API errors
    (rate limits, overload) with exponential backoff. Raises on final failure.

    Production LLM APIs return 429/529 under load; an eval harness that crashes on
    those produces misleading scores, so we retry instead.
    """
    delay = 1.0
    resp = None
    for attempt in range(max_retries):
        resp = do_request()
        if resp.status_code in retry_on and attempt < max_retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


_REGISTRY: dict[str, type[Provider]] = {}


def register_provider(name: str):
    def deco(cls: type[Provider]) -> type[Provider]:
        _REGISTRY[name] = cls
        return cls

    return deco


def get_provider(name: str) -> Provider:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown provider {name!r}. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()
