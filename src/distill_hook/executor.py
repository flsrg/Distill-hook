from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class ShellSpec:
    kind: str
    executable: str
    login: bool = False


def shell_argv(command: str, shell: ShellSpec) -> list[str]:
    """Build argv for the same shell dialect that Codex used for the tool call."""
    if shell.kind in {"bash", "zsh", "sh"}:
        return [shell.executable, "-lc" if shell.login else "-c", command]
    if shell.kind == "powershell":
        args = [shell.executable]
        if not shell.login:
            args.append("-NoProfile")
        args.extend(["-Command", command])
        return args
    if shell.kind == "cmd":
        return [shell.executable, "/c", command]
    raise ValueError(f"unsupported shell kind: {shell.kind}")


def run_command(command: str, *, shell: ShellSpec | None = None) -> tuple[bytes, int]:
    """Run with the invoking shell and merge stdout/stderr in emission order.

    Output is spooled to a temporary file while the command runs, avoiding the
    previous ever-growing in-memory chunk list for noisy finite commands.
    """
    if shell is None:
        shell = ShellSpec("cmd", "cmd.exe") if os.name == "nt" else ShellSpec("sh", "/bin/sh")

    with tempfile.TemporaryFile() as capture:
        proc = subprocess.Popen(
            shell_argv(command, shell),
            shell=False,
            stdout=capture,
            stderr=subprocess.STDOUT,
        )
        exit_code = proc.wait()
        capture.seek(0)
        return capture.read(), exit_code
