"""OpenAI-compatible provider (used when OPENAI_API_KEY is set).

Works with any OpenAI-compatible Chat Completions endpoint via OPENAI_BASE_URL.
`requests` is imported lazily (see promptproof[live]).
"""

from __future__ import annotations

import os
import time

from .base import LLMResponse, Provider, cost_usd, register_provider, with_retry

# USD per 1M tokens (input, output).
PRICES = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
}


@register_provider("openai")
class OpenAIProvider(Provider):
    def complete(self, model: str, prompt: str, params: dict) -> LLMResponse:  # noqa: D401
        try:
            import requests
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The openai provider needs requests: pip install 'promptproof[live]'"
            ) from e

        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        url = (os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
               + "/chat/completions")
        body = {
            "model": model,
            "temperature": params.get("temperature", 0.0),
            "messages": [{"role": "user", "content": prompt}],
        }
        if "max_tokens" in params:
            body["max_tokens"] = params["max_tokens"]

        t0 = time.perf_counter()
        resp = with_retry(
            lambda: requests.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
                timeout=params.get("timeout", 60),
            )
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tin = usage.get("prompt_tokens", max(1, len(prompt) // 4))
        tout = usage.get("completion_tokens", max(1, len(text) // 4))
        pin, pout = PRICES.get(model, (0.0, 0.0))
        return LLMResponse(text, tin, tout, cost_usd(tin, tout, pin, pout), round(latency_ms, 1), model)
