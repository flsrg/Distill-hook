from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Cheap conservative token estimate used only for savings decisions."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)
