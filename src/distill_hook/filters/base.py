from __future__ import annotations

import re
from dataclasses import dataclass

ERROR_RE = re.compile(
    r"(?:\berror\b|\berrors\b|\bfailed\b|\bfailure\b|\bfatal\b|\bpanic(?:ked)?\b|"
    r"\bexception\b|\btraceback\b|\bassert(?:ion)?\b|\bdenied\b|\brefused\b|"
    r"\bunreachable\b|\berror\[[A-Z0-9]+\]|--- FAIL:|\bFAIL\b|^[✗×❌])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FilterResult:
    text: str
    kept_lines: int


class OutputFilter:
    name = "base"
    min_lines = 20

    def matches_command(self, command: str) -> bool:
        raise NotImplementedError

    def distill(self, command: str, output: str) -> FilterResult:
        raise NotImplementedError


def is_error_line(line: str) -> bool:
    return bool(ERROR_RE.search(line))


def head_tail_with_errors(lines: list[str], *, head: int, tail: int) -> list[str]:
    if len(lines) <= head + tail:
        return lines
    keep = set(range(min(head, len(lines))))
    keep.update(range(max(0, len(lines) - tail), len(lines)))
    keep.update(i for i, line in enumerate(lines) if is_error_line(line))
    result: list[str] = []
    previous: int | None = None
    for i in sorted(keep):
        if previous is not None and i > previous + 1:
            result.append(f"... {i - previous - 1} lines omitted ...")
        result.append(lines[i])
        previous = i
    return result
