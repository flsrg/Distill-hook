from __future__ import annotations

import re

from .filters import FILTERS
from .filters.base import OutputFilter

WRAPPER_PREFIX_RE = re.compile(
    r"^(?:(?:env\s+)?(?:uv\s+run|uvx|npx|pnpm\s+exec|poetry\s+run|python\s+-m)\s+)+",
    re.IGNORECASE,
)
SIMPLE_SHELL_PREFIX_RE = re.compile(
    r"^(?:(?:/usr/bin/|/bin/)?(?:sh|bash))\s+(?![\s-])",
    re.IGNORECASE,
)
LOCAL_EXEC_PREFIX_RE = re.compile(r"^\.[/\\](?=[^/\\\s]+(?:\s|$))")


def normalize_command(command: str) -> str:
    text = command.strip()
    text = re.sub(r"^(?:[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+)+", "", text)
    previous = None
    while text != previous:
        previous = text
        text = WRAPPER_PREFIX_RE.sub("", text)
        text = SIMPLE_SHELL_PREFIX_RE.sub("", text)
        text = LOCAL_EXEC_PREFIX_RE.sub("", text)
    return text


def select_filter(command: str) -> OutputFilter | None:
    normalized = normalize_command(command)
    for output_filter in FILTERS:
        if output_filter.matches_command(normalized):
            return output_filter
    return None
