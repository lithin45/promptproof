"""Importing this package registers all built-in scorers."""

from .base import Scorer, get_scorer, register_scorer  # noqa: F401

from . import structure  # noqa: F401,E402
from . import fields  # noqa: F401,E402
from . import text  # noqa: F401,E402
from . import judge  # noqa: F401,E402

__all__ = ["Scorer", "get_scorer", "register_scorer"]
