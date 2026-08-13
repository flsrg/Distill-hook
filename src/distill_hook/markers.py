from __future__ import annotations

import re

REF_RE = re.compile(r"\b([0-9a-f]{16})\b")


def render_marker(ref: str, omitted_lines: int, omitted_tokens: int) -> str:
    return (
        f"[distill#{ref}: {omitted_lines} lines omitted "
        f"(~{omitted_tokens} tokens); restore: distill-hook expand {ref}]"
    )


def parse_ref(value: str) -> str | None:
    value = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{16}", value):
        return value
    match = REF_RE.search(value)
    return match.group(1) if match else None
