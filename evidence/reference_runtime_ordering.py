"""Minimal public reconstruction of the vulnerable admission ordering.

This file preserves only the mechanism needed by the experiment. It contains
no application-specific runtime, credentials, prompts, memory, or tool code.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def sequential_admission(
    assistant_response: dict[str, Any],
    history: list[dict[str, Any]],
    dispatch: Callable[[str, dict[str, Any]], None],
) -> None:
    """Admit the response, then parse and dispatch each call sequentially."""
    history.append(assistant_response)
    for tool_call in assistant_response.get("tool_calls", []):
        function = tool_call["function"]
        arguments = json.loads(function["arguments"])
        dispatch(function["name"], arguments)
