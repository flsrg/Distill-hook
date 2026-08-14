from __future__ import annotations

import re

from .base import FilterResult, OutputFilter, head_tail_with_errors, is_error_line


class LintBuildFilter(OutputFilter):
    name = "lint_build"
    min_lines = 35
    COMMAND_RE = re.compile(
        r"\b(?:ruff|eslint|mypy|pyright|tsc|cargo\s+(?:build|check|clippy)|"
        r"npm\s+run\s+build|pnpm\s+(?:build|run\s+build)|yarn\s+build|make|cmake|"
        r"gradle|gradlew|mvn|docker\s+build|terraform\s+plan)\b",
        re.IGNORECASE,
    )

    def matches_command(self, command: str) -> bool:
        return bool(self.COMMAND_RE.search(command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        error_indices = [i for i, line in enumerate(lines) if is_error_line(line)]
        if error_indices:
            keep: set[int] = set()
            for i in error_indices:
                keep.update(range(max(0, i - 3), min(len(lines), i + 6)))
            keep.update(range(max(0, len(lines) - 8), len(lines)))
            compact: list[str] = []
            prev = None
            for i in sorted(keep):
                if prev is not None and i > prev + 1:
                    compact.append(f"... {i - prev - 1} build lines omitted ...")
                compact.append(lines[i])
                prev = i
        else:
            compact = head_tail_with_errors(lines, head=14, tail=18)
        return FilterResult("\n".join(compact), len(compact))


class SearchOutputFilter(OutputFilter):
    name = "search"
    min_lines = 60
    COMMAND_RE = re.compile(r"(?:^|\s)(?:rg|grep|find|fd)(?:\s|$)")

    def matches_command(self, command: str) -> bool:
        if re.search(r"\bfind\b.*\s-(?:exec|delete|execdir|ok)\b", command):
            return False
        return bool(self.COMMAND_RE.search(command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        grouped: dict[str, list[str]] = {}
        for line in lines:
            key = line.split(":", 1)[0] if ":" in line else "(other)"
            grouped.setdefault(key, []).append(line)
        ranked = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
        out = [f"search results: {len(lines)} lines across {len(grouped)} groups"]
        for key, matches in ranked[:20]:
            out.append(f"\n## {key} ({len(matches)} matches)")
            out.extend(matches[:6])
            if len(matches) > 6:
                out.append(f"... {len(matches) - 6} more matches in {key} ...")
        return FilterResult("\n".join(out), len(out))


class FileListingFilter(OutputFilter):
    name = "listing"
    min_lines = 80

    def matches_command(self, command: str) -> bool:
        return bool(re.search(r"(?:^|[;&|]\s*)(?:ls|tree)(?:\s|$)", command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        compact = lines[:50]
        if len(lines) > 70:
            compact.append(f"... {len(lines) - 70} listing lines omitted ...")
            compact.extend(lines[-20:])
        return FilterResult("\n".join(compact), len(compact))


class LogOutputFilter(OutputFilter):
    name = "logs"
    min_lines = 80

    def matches_command(self, command: str) -> bool:
        return bool(
            re.search(
                r"\b(?:docker\s+logs|kubectl\s+logs|journalctl|tail\s+-n|cat\s+[^;&|]*\.log)\b",
                command,
                re.IGNORECASE,
            )
        )

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        compact = head_tail_with_errors(lines, head=12, tail=40)
        return FilterResult("\n".join(compact), len(compact))
