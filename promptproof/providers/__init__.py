"""Importing this package registers all built-in providers."""

from .base import LLMResponse, Provider, cost_usd, get_provider, register_provider  # noqa: F401

# Side-effect imports register each provider in the registry.
from . import mock  # noqa: F401,E402
from . import anthropic  # noqa: F401,E402
from . import openai  # noqa: F401,E402

__all__ = ["LLMResponse", "Provider", "cost_usd", "get_provider", "register_provider"]
