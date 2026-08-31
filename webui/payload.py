"""Typed accessors for untrusted JSON request bodies.

Request payloads arrive as ``dict[str, Any]`` from the network. These helpers
narrow one field to a known shape, returning the empty value instead of raising,
so callers never have to re-check what a key actually contained.
"""

from __future__ import annotations

from typing import Any


def dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``payload[key]`` when it is a JSON object, otherwise ``{}``."""
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def str_field(payload: dict[str, Any], key: str, default: str = "") -> str:
    """Return ``payload[key]`` as a stripped string, falling back to ``default``."""
    value = payload.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default
