from __future__ import annotations

from dataclasses import dataclass

from .budget import estimate_tokens
from .markers import render_marker
from .router import select_filter
from .store import OmissionStore

MIN_SAVED_TOKENS = 40


@dataclass(frozen=True)
class DistillResult:
    output: bytes
    distilled: bool
    filter_name: str | None
    ref: str | None
    raw_tokens: int
    compact_tokens: int


def distill_output(raw: bytes, *, command: str, store: OmissionStore) -> DistillResult:
    text = raw.decode("utf-8", errors="replace")
    raw_tokens = estimate_tokens(text)
    chosen = select_filter(command)
    if chosen is None or len(text.splitlines()) < chosen.min_lines:
        return DistillResult(raw, False, None, None, raw_tokens, raw_tokens)

    try:
        filtered = chosen.distill(command, text)
    except Exception:
        return DistillResult(raw, False, chosen.name, None, raw_tokens, raw_tokens)

    compact_text = filtered.text.rstrip()
    if not compact_text:
        return DistillResult(raw, False, chosen.name, None, raw_tokens, raw_tokens)

    provisional_tokens = estimate_tokens(compact_text) + 30
    if provisional_tokens >= raw_tokens - MIN_SAVED_TOKENS:
        return DistillResult(raw, False, chosen.name, None, raw_tokens, raw_tokens)

    try:
        ref = store.put(raw, command)
    except Exception:
        return DistillResult(raw, False, chosen.name, None, raw_tokens, raw_tokens)

    raw_lines = len(text.splitlines())
    compact_lines = len(compact_text.splitlines())
    omitted_lines = max(0, raw_lines - compact_lines)
    omitted_tokens = max(0, raw_tokens - estimate_tokens(compact_text))
    marker = render_marker(ref, omitted_lines, omitted_tokens)
    final_text = f"{compact_text}\n\n{marker}\n"
    final_tokens = estimate_tokens(final_text)
    if final_tokens >= raw_tokens - MIN_SAVED_TOKENS:
        return DistillResult(raw, False, chosen.name, None, raw_tokens, raw_tokens)

    return DistillResult(
        final_text.encode("utf-8"),
        True,
        chosen.name,
        ref,
        raw_tokens,
        final_tokens,
    )
