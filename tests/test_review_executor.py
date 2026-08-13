import shutil

import pytest

from distill_hook.executor import ShellSpec, run_command, shell_argv


def test_shell_argv_uses_requested_dialect():
    assert shell_argv("printf x", ShellSpec("bash", "/bin/bash")) == ["/bin/bash", "-c", "printf x"]
    assert shell_argv("Write-Output $env:NAME", ShellSpec("powershell", "pwsh")) == [
        "pwsh",
        "-NoProfile",
        "-Command",
        "Write-Output $env:NAME",
    ]
    assert shell_argv("echo %NAME%", ShellSpec("cmd", "cmd.exe")) == [
        "cmd.exe",
        "/c",
        "echo %NAME%",
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash unavailable")
def test_executor_uses_bash_semantics_when_requested():
    output, code = run_command(
        "printf '%s\\n' {one,two}",
        shell=ShellSpec("bash", shutil.which("bash") or "/bin/bash"),
    )
    assert code == 0
    assert output.decode().splitlines() == ["one", "two"]
