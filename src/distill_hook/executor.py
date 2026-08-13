from __future__ import annotations

import subprocess


def run_command(command: str) -> tuple[bytes, int]:
    """Run through the platform shell, preserving stdout/stderr order in one pipe."""
    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None
    chunks: list[bytes] = []
    while True:
        chunk = proc.stdout.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks), proc.wait()
