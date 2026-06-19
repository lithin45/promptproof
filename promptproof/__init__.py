"""PromptProof — catch LLM prompt & model regressions before they ship.

A small, dependency-light harness that runs an evaluation *suite* (a dataset +
one or more model/prompt *targets* + a set of *scorers*), stores every run, and
compares a candidate run against a baseline to detect regressions — with a CLI,
a CI gate (non-zero exit on regression), and an exportable feed for the
dashboard.

The whole thing runs offline with zero API keys via the built-in MockProvider;
drop in real keys (ANTHROPIC_API_KEY / OPENAI_API_KEY) to evaluate live models.
"""

__version__ = "0.1.0"
