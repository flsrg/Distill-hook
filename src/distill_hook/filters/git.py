from __future__ import annotations

import re

from .base import FilterResult, OutputFilter, head_tail_with_errors


class GitStatusFilter(OutputFilter):
    name = "git_status"
    min_lines = 30

    def matches_command(self, command: str) -> bool:
        return bool(re.search(r"\bgit\s+status\b", command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        compact = head_tail_with_errors(lines, head=16, tail=16)
        return FilterResult("\n".join(compact), len(compact))


class GitLogFilter(OutputFilter):
    name = "git_log"
    min_lines = 24

    def matches_command(self, command: str) -> bool:
        return bool(re.search(r"\bgit\s+log\b", command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        commits: list[str] = []
        current_sha = ""
        current_subject = ""
        for line in lines:
            m = re.match(r"^commit\s+([0-9a-f]{7,40})", line, re.I)
            if m:
                if current_sha:
                    commits.append(f"{current_sha[:10]} {current_subject}".rstrip())
                current_sha, current_subject = m.group(1), ""
                continue
            if current_sha and line.startswith("    ") and line.strip() and not current_subject:
                current_subject = line.strip()
        if current_sha:
            commits.append(f"{current_sha[:10]} {current_subject}".rstrip())
        if not commits:
            nonempty = [line for line in lines if line.strip()]
            commits = nonempty[:30]
        compact = [f"git log: showing {min(len(commits), 30)} entries"] + commits[:30]
        return FilterResult("\n".join(compact), len(compact))


class GitDiffFilter(OutputFilter):
    name = "git_diff"
    min_lines = 50

    def matches_command(self, command: str) -> bool:
        return bool(re.search(r"(?:\bgit\s+diff\b|\bgh\s+pr\s+diff\b)", command))

    def distill(self, command: str, output: str) -> FilterResult:
        lines = output.splitlines()
        files: list[tuple[str, list[str], int, int]] = []
        current_name = "(preamble)"
        current: list[str] = []
        added = deleted = 0
        for line in lines:
            if line.startswith("diff --git "):
                if current:
                    files.append((current_name, current, added, deleted))
                parts = line.split()
                current_name = parts[-1][2:] if parts else "unknown"
                current = [line]
                added = deleted = 0
                continue
            current.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                deleted += 1
        if current:
            files.append((current_name, current, added, deleted))
        ranked = sorted(files, key=lambda item: item[2] + item[3], reverse=True)
        out = [f"git diff: {len(files)} file section(s)"]
        for name, block, plus, minus in ranked[:5]:
            out.append(f"\n### {name} (+{plus}/-{minus})")
            out.extend(head_tail_with_errors(block, head=24, tail=24))
        if len(ranked) > 5:
            out.append("\nOther changed files:")
            out.extend(f"- {n} (+{a}/-{d})" for n, _b, a, d in ranked[5:25])
        return FilterResult("\n".join(out), len(out))
