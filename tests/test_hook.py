import json
from pathlib import Path

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


def test_default_permission_mode_is_not_auto_approved(monkeypatch):
    p = payload("pytest -q")
    p["permission_mode"] = "default"
    monkeypatch.delenv("DISTILL_HOOK_ALLOW_DEFAULT_MODE", raising=False)
    monkeypatch.setenv("CODEX_HOME", "/definitely/missing/distill-hook-test")
    assert handle_payload(p) is None

    monkeypatch.setenv("DISTILL_HOOK_ALLOW_DEFAULT_MODE", "1")
    assert handle_payload(p) is not None


def test_installer_preserves_existing_hooks(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
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
    (tmp_path / "hooks.json").write_text(json.dumps(existing), encoding="utf-8")
    path = install_codex_hook()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["hooks"]["PreToolUse"]) == 2
    install_codex_hook()
    data2 = json.loads(path.read_text(encoding="utf-8"))
    assert len(data2["hooks"]["PreToolUse"]) == 2

    install_codex_hook(allow_default=True)
    config = json.loads((tmp_path / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config["allow_default_mode"] is True
    install_codex_hook()
    config2 = json.loads((tmp_path / "distill-hook" / "config.json").read_text(encoding="utf-8"))
    assert config2["allow_default_mode"] is True
