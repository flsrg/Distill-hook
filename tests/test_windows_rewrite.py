import subprocess

from distill_hook.executor import ShellSpec
from distill_hook.hook import rewritten_command


def test_windows_powershell_uses_call_operator_for_quoted_executable(monkeypatch):
    executable = r"C:\Program Files\Distill Hook\distill-hook.exe"
    monkeypatch.setenv("DISTILL_HOOK_COMMAND", executable)
    monkeypatch.setattr("distill_hook.hook.os.name", "nt")

    rewritten = rewritten_command(
        "pytest -q",
        ShellSpec("powershell", r"C:\Program Files\PowerShell\7\pwsh.exe"),
    )

    quoted = subprocess.list2cmdline([executable])
    assert quoted.startswith('"')
    assert rewritten.startswith(
        f"& {quoted} run-encoded --shell-kind powershell "
    )


def test_windows_cmd_keeps_native_invocation_syntax(monkeypatch):
    executable = r"C:\Program Files\Distill Hook\distill-hook.exe"
    monkeypatch.setenv("DISTILL_HOOK_COMMAND", executable)
    monkeypatch.setattr("distill_hook.hook.os.name", "nt")

    rewritten = rewritten_command(
        "pytest -q",
        ShellSpec("cmd", r"C:\Windows\System32\cmd.exe"),
    )

    quoted = subprocess.list2cmdline([executable])
    assert rewritten.startswith(f"{quoted} run-encoded --shell-kind cmd ")
    assert not rewritten.startswith("& ")
