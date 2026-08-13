from __future__ import annotations

import re

from .base import FilterResult, OutputFilter, head_tail_with_errors, is_error_line


class TestOutputFilter(OutputFilter):
    name = "tests"
    min_lines = 24
    COMMAND_RE = re.compile(
        r"(?:^|[;&|]\s*|\b)(?:pytest|py\.test|jest|vitest|cargo\s+(?:test|nextest)|"
        r"go\s+test|npm\s+(?:test|run\s+test)|pnpm\s+(?:test|run\s+test)|yarn\s+test)\b",
        re.IGNORECASE,
    )

    def matches_command(self, command: str) -> bool:
        return bool(self.COMMAND_RE.search(command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        keep: set[int] = set()
        important = re.compile(
            r"(?:=+\s*(?:FAILURES|ERRORS|short test summary info|test session starts)|"
            r"^FAILED\b|^ERROR\b|^E\s+|^F\s+|^--- FAIL:|^failures:|^test result:|"
            r"\bpassed\b.*\bfailed\b|\btests?\s+(?:passed|failed)\b)",
            re.IGNORECASE,
        )
        for i, line in enumerate(lines):
            if important.search(line) or is_error_line(line):
                for j in range(max(0, i - 2), min(len(lines), i + 5)):
                    keep.add(j)
        if len(keep) < 8:
            compact = head_tail_with_errors(lines, head=12, tail=18)
        else:
            compact = []
            previous = None
            for i in sorted(keep):
                if previous is not None and i > previous + 1:
                    compact.append(f"... {i - previous - 1} test lines omitted ...")
                compact.append(lines[i])
                previous = i
        return FilterResult("\n".join(compact), len(compact))
