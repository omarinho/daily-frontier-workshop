"""Small, pure text helpers shared across the pipeline (no I/O, no state)."""

from __future__ import annotations

import re

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Normalize a topic title into a dedup-comparable slug.

    ``"MCP (Model Context Protocol) Servers"`` -> ``"mcp-model-context-protocol-servers"``.
    """
    return _SLUG_PATTERN.sub("-", title.lower()).strip("-")
