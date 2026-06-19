"""Tiny shared helpers."""

from __future__ import annotations

import re


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "suite"
