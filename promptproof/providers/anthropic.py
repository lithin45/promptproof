"""Anthropic provider (used when ANTHROPIC_API_KEY is set).

`requests` is imported lazily so the package installs and runs with zero extra
dependencies; you only need `pip install promptproof[live]` to hit a real API.
"""

from __future__ import annotations

import os
import time

from .base import LLMResponse, Provider, cost_usd, register_provider, with_retry

# USD per 1M tokens (input, output). Extend as needed.
PRICES = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


@register_provider("anthropic")
class AnthropicProvider(Provider):
    def complete(self, model: str, prompt: str, params: dict) -> LLMResponse:  # noqa: D401
        try:
            import requests
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The anthropic provider needs requests: pip install 'promptproof[live]'"
            ) from e

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        url = (os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
               + "/v1/messages")
        body = {
            "model": model,
            "max_tokens": params.get("max_tokens", 1024),
            "temperature": params.get("temperature", 0.0),
            "messages": [{"role": "user", "content": prompt}],
        }
        t0 = time.perf_counter()
        resp = with_retry(
            lambda: requests.post(
                url,
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=params.get("timeout", 60),
            )
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        data = resp.json()

        text = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        tin = usage.get("input_tokens", max(1, len(prompt) // 4))
        tout = usage.get("output_tokens", max(1, len(text) // 4))
        pin, pout = PRICES.get(model, (0.0, 0.0))
        return LLMResponse(text, tin, tout, cost_usd(tin, tout, pin, pout), round(latency_ms, 1), model)
