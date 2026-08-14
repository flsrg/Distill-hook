import json
import shlex
from pathlib import Path

import pytest

from distill_hook.executor import ShellSpec
from distill_hook.hook import decode_command, handle_payload, install_codex_hook


def payload(command: str):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "shell_command",
        "tool_input": {"command": command},
        "permission_mode": "dontAsk",
        "cwd": "/tmp/project",
    }


def test_rewrites_supported_noisy_command():
    response = handle_payload(payload("pytest -q"))
    assert response is not None
    rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]
    assert "distill-hook" in rewritten
    encoded = rewritten.split()[-1].strip("'\"")
    assert decode_command(encoded) == "pytest -q"


def test_does_not_rewrite_unknown_or_unsafe_shell_shape():
    assert handle_payload(payload("echo hello")) is None
    assert handle_payload(payload("pytest $(cat args.txt)")) is None
    assert handle_payload(payload("rm -rf /tmp/x; pytest -q")) is None
    assert handle_payload(payload("pytest -q | tee results.txt")) is None


def test_rewrites_noisy_tail_after_read_only_sed_prelude(monkeypatch):
    monkeypatch.setattr(
        "distill_hook.hook.shell_for_tool",
        lambda _tool_name, _tool_input: ShellSpec("bash", "/bin/bash"),
    )
    command = "sed -n '1,240p' /tmp/SKILL.md && sh ./gradlew test"

    response = handle_payload(payload(command))
    assert response is not None
    rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]

    assert rewritten.startswith("sed -n '1,240p' /tmp/SKILL.md && ")
    encoded = rewritten.split()[-1].strip("'\"")
    assert decode_command(encoded) == "sh ./gradlew test"


@pytest.mark.parametrize(
    "command",
    [
        "echo hello && sh ./gradlew test",
        "sed -n '1e whoami' /tmp/SKILL.md && sh ./gradlew test",
        "sed -n '1,240p' /tmp/SKILL.md && echo hello",
        "sed -n '1,240p' /tmp/SKILL.md && sh ./gradlew test && echo hello",
    ],
)
def test_does_not_rewrite_unsafe_compounds(command, monkeypatch):
    monkeypatch.setattr(
        "distill_hook.hook.shell_for_tool",
        lambda _tool_name, _tool_input: ShellSpec("bash", "/bin/bash"),
    )

    assert handle_payload(payload(command)) is None


@pytest.mark.parametrize(
    "command",
    [
        "sed -n '1,240p' \"$(printf /tmp/SKILL.md)\" && sh ./gradlew test",
        "sed -n '1,240p' \"`printf /tmp/SKILL.md`\" && sh ./gradlew test",
    ],
)
def test_does_not_rewrite_sed_prelude_with_shell_substitution(command, monkeypatch):
    monkeypatch.setattr(
        "distill_hook.hook.shell_for_tool",
        lambda _tool_name, _tool_input: ShellSpec("bash", "/bin/bash"),
    )

    assert handle_payload(payload(command)) is None


def test_preserves_quoted_sed_prelude(monkeypatch):
    monkeypatch.setattr(
        "distill_hook.hook.shell_for_tool",
        lambda _tool_name, _tool_input: ShellSpec("sh", "/bin/sh"),
    )
    prelude = "sed -n '1,240p' '/tmp/path with spaces/SKILL.md'"

    response = handle_payload(payload(f"{prelude} && sh ./gradlew test"))
    assert response is not None
    rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]

    assert rewritten.startswith(f"{prelude} && ")


def test_default_permission_mode_is_not_auto_approved(monkeypatch):
    p = payload("pytest -q")
    p["permission_mode"] = "default"
    monkeypatch.delenv("DISTILL_HOOK_ALLOW_DEFAULT_MODE", raising=False)
    monkeypatch.setenv("CODEX_HOME", "/definitely/missing/distill-hook-test")
    assert handle_payload(p) is None

    monkeypatch.setenv("DISTILL_HOOK_ALLOW_DEFAULT_MODE", "1")
    assert handle_payload(p) is not None


def test_rewrite_uses_installed_absolute_executable(tmp_path: Path, monkeypatch):
    home = tmp_path / "codex-home"
    executable = tmp_path / "pipx apps" / "distill-hook"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.delenv("DISTILL_HOOK_COMMAND", raising=False)

    install_codex_hook(executable=str(executable))
    monkeypatch.setattr(
        "distill_hook.hook.shell_for_tool",
        lambda _tool_name, _tool_input: ShellSpec("sh", "/bin/sh"),
    )

    response = handle_payload(payload("pytest -q"))
    assert response is not None
    rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]
    expected = shlex.quote(str(executable.absolute()))
    assert rewritten.startswith(f"{expected} run-encoded ")

    config = json.loads((home / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config["executable"] == str(executable.absolute())


def test_installer_preserves_existing_hooks_and_uses_absolute_path(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    home = tmp_path / "codex-home"
    home.mkdir()
    executable = tmp_path / "pipx apps" / "distill-hook"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    existing = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "^apply_patch$",
                    "hooks": [{"type": "command", "command": "other-hook"}],
                }
            ]
        }
    }
    (home / "hooks.json").write_text(json.dumps(existing), encoding="utf-8")

    path = install_codex_hook(executable=str(executable))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["hooks"]["PreToolUse"]) == 2
    installed_command = data["hooks"]["PreToolUse"][1]["hooks"][0]["command"]
    assert installed_command == f"{shlex.quote(str(executable.absolute()))} codex-hook"

    install_codex_hook(executable=str(executable))
    data2 = json.loads(path.read_text(encoding="utf-8"))
    assert len(data2["hooks"]["PreToolUse"]) == 2

    install_codex_hook(allow_default=True, executable=str(executable))
    config = json.loads((home / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config["allow_default_mode"] is True
    assert config["executable"] == str(executable.absolute())
    install_codex_hook(executable=str(executable))
    config2 = json.loads((home / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config2["allow_default_mode"] is True
    assert config2["executable"] == str(executable.absolute())


def test_installer_migrates_legacy_path_dependent_hook(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    home = tmp_path / "codex-home"
    home.mkdir()
    executable = tmp_path / "bin" / "distill-hook"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    legacy = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "^(?:shell_command|Bash|PowerShell|Shell)$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "distill-hook codex-hook",
                            "timeout": 5,
                        }
                    ],
                }
            ]
        }
    }
    (home / "hooks.json").write_text(json.dumps(legacy), encoding="utf-8")

    path = install_codex_hook(executable=str(executable))
    data = json.loads(path.read_text(encoding="utf-8"))
    handlers = data["hooks"]["PreToolUse"]
    assert len(handlers) == 1
    assert handlers[0]["hooks"][0]["command"] == f"{shlex.quote(str(executable.absolute()))} codex-hook"


def test_installer_resolves_distill_hook_from_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    executable = tmp_path / "pipx" / "distill-hook"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("distill_hook.hook.shutil.which", lambda name: str(executable) if name == "distill-hook" else None)
    monkeypatch.setattr("distill_hook.hook.sys.argv", ["python"])

    path = install_codex_hook()
    data = json.loads(path.read_text(encoding="utf-8"))
    command = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert command == f"{shlex.quote(str(executable.absolute()))} codex-hook"


def test_installer_custom_override_is_idempotent(tmp_path: Path, monkeypatch):
    home = tmp_path / "codex-home"
    executable = tmp_path / "custom apps" / "custom-distiller"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("DISTILL_HOOK_COMMAND", str(executable))
    monkeypatch.setattr("distill_hook.hook.sys.argv", ["python"])

    path = install_codex_hook()
    install_codex_hook()

    data = json.loads(path.read_text(encoding="utf-8"))
    handlers = data["hooks"]["PreToolUse"]
    assert len(handlers) == 1
    expected = f"{shlex.quote(str(executable.absolute()))} codex-hook"
    assert handlers[0]["hooks"][0]["command"] == expected

    config = json.loads((home / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config["executable"] == str(executable.absolute())


def test_installer_fails_clearly_when_executable_is_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.delenv("DISTILL_HOOK_COMMAND", raising=False)
    monkeypatch.setattr("distill_hook.hook.shutil.which", lambda _name: None)
    monkeypatch.setattr("distill_hook.hook.sys.argv", ["python"])

    with pytest.raises(RuntimeError, match="Cannot locate the distill-hook executable"):
        install_codex_hook()
