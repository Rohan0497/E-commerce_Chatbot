"""Tool specifications and registry utilities for the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Protocol


class ToolFn(Protocol):
    """Callable signature every tool implementation must follow."""

    def __call__(self, args: Dict) -> Dict:
        ...


@dataclass(slots=True)
class ToolSpec:
    """Metadata wrapper used by the agent to invoke tools in a uniform way."""

    name: str
    fn: ToolFn
