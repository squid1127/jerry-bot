"""Function call models for Gemini plugin."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FunctionCall:
    """Class for a function call."""

    name: str
    arguments: dict[str, Any]
