"""
File: brisart_ai/io/input_cleaner.py

Purpose
-------
Normalize pasted shell-like or quoted user input before retrieval.

Public operations: normalize_shellish_input (text) - Trim whitespace and unwrap one pair
of matching surrounding quotes.

Internal helpers include _strip_quotes.

Communication / relationships
-----------------------------
Conversation and session memory use this shared normalizer.

Direct importing modules include brisart_ai/core/conversation.py,
brisart_ai/core/session_memory.py, brisart_ai/io/tests/test_input_cleaner.py.

Settings / parameters
---------------------
Takes a string, not an argv list.

Call signatures: normalize_shellish_input(text).

Edge cases
----------
Recognized wrappers are removed without executing the line.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
This is not a general-purpose shell parser or sanitizer.

The normalizer is not an escaping or security boundary. It must not be used to construct executable shell commands from user input.

Examples
--------
normalize_shellish_input('"permit fee"')

For a concrete entry point, inspect `normalize_shellish_input`; invoke it through the existing
application entry point or its documented caller. The example above is illustrative of this
file's present interface; do not treat it as an instruction to create additional state or call
private functions directly.
"""

from __future__ import annotations


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def normalize_shellish_input(text: str) -> str:
    """Trim whitespace and unwrap one pair of matching surrounding quotes."""
    raw = text.strip()
    if not raw:
        return raw
    return _strip_quotes(raw)


__all__ = ["normalize_shellish_input"]
