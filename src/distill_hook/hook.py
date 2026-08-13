from __future__ import annotations

import base64
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from .executor import ShellSpec
from .router import normalize_command, select_filter

SHELL_TOOL_NAMES = {"shell_command", "Bash", "PowerShell", "Shell"}
UNSAFE_META_RE = re.compile(r"(?:\$\(|`|\n|\r|&&|\|\||[;|&<>])")
SAFE_PERMISSION_MODES = {"dontAsk", "bypassPermissions"}

SAFE_START_RE = re.compile(
    r"^(?:(?:[^\s=]+=[^\s]+\s+)*)"
    r"(?:"
    r"(?:[^\s/\\]+[/\\])*?(?:pytest|py\.test|jest|vitest|ruff|eslint|mypy|pyright|tsc)\b|"
    r"cargo\s+(?:test|nextest|build|check|clippy)\b|"
    r"go\s+test\b|"
    r"(?:npm|pnpm)\s+(?:test|build|run\s+(?:test|build))\b|"
    r"yarn\s+(?:test|build)\b|"
    r"git\s+(?:status|log|diff)\b|gh\s+pr\s+diff\b|"
    r"(?:make|cmake|gradle|gradlew|mvn)\b|docker\s+(?:build|logs)\b|"
    r"terraform\s+plan\b|kubectl\s+logs\b|journalctl\b|"
    r"(?:rg|grep|find|fd|ls|tree)\b|tail\s+-n\b|cat\s+[^\s]+\.log\b"
    r")",
    re.IGNORECASE,
)

_LOG_COMMAND_RE = re.compile(r"^(?:docker\s+logs|kubectl\s+logs|journalctl|tail\s+-n)\b", re.I)
_FOLLOW_FLAG_RE = re.compile(r"(?:^|\s)(?:-f|-F|--follow(?:=\S+)?)(?=\s|$)", re.I)
_WATCH_FLAG_RE = re.compile(r"(?:^|\s)--watch(?:All)?(?:=\S+)?(?=\s|$)", re.I)


def encode_command(command: str) -> str:
    return base64.urlsafe_b64encode(command.encode("utf-8")).decode("ascii").rstrip("=")


def decode_command(encoded: str) -> str:
    padded = encoded + "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")


def _config_path() -> Path:
    return codex_home() / "distill-hook" / "config.json"


def allow_default_mode() -> bool:
    override = os.environ.get("DISTILL_HOOK_ALLOW_DEFAULT_MODE")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(isinstance(data, dict) and data.get("allow_default_mode") is True)


def _is_long_running_mode(command: str) -> bool:
    if _WATCH_FLAG_RE.search(command):
        return True
    return bool(_LOG_COMMAND_RE.search(command) and _FOLLOW_FLAG_RE.search(command))


def should_rewrite(command: str) -> bool:
    stripped = command.strip()
    if not stripped or "distill-hook run-encoded" in stripped:
        return False
    if UNSAFE_META_RE.search(stripped):
        return False
    normalized = normalize_command(stripped)
    if not SAFE_START_RE.search(normalized):
        return False
    if _is_long_running_mode(normalized):
        return False
    if re.search(r"\bfind\b.*\s-(?:exec|delete|execdir|ok)\b", normalized):
        return False
    return select_filter(normalized) is not None


def _kind_for_path(path: str) -> str | None:
    name = Path(path).stem.lower()
    if name in {"bash", "zsh", "sh", "cmd"}:
        return name
    if name in {"pwsh", "powershell"}:
        return "powershell"
    return None


def _existing(path: str | None) -> str | None:
    if not path:
        return None
    return path if Path(path).is_file() else None


def _resolve_named_shell(
    kind: str,
    preferred: str | None = None,
    *,
    login: bool = False,
) -> ShellSpec | None:
    if preferred and _kind_for_path(preferred) == kind:
        existing = _existing(preferred)
        if existing:
            return ShellSpec(kind, existing, login)

    names: tuple[str, ...]
    fallbacks: tuple[str, ...]
    if kind == "bash":
        names, fallbacks = ("bash",), ("/bin/bash", "/usr/bin/bash")
    elif kind == "zsh":
        names, fallbacks = ("zsh",), ("/bin/zsh",)
    elif kind == "sh":
        names, fallbacks = ("sh",), ("/bin/sh",)
    elif kind == "powershell":
        names = ("pwsh", "powershell")
        fallbacks = (
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "/usr/local/bin/pwsh",
        )
    elif kind == "cmd":
        names = ("cmd.exe", "cmd")
        fallbacks = tuple(filter(None, (os.environ.get("COMSPEC"),)))
    else:
        return None

    for name in names:
        found = shutil.which(name)
        if found:
            return ShellSpec(kind, found, login)
    for path in fallbacks:
        existing = _existing(path)
        if existing:
            return ShellSpec(kind, existing, login)
    return None


def _posix_user_shell() -> str | None:
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_shell or None
    except Exception:
        return None


def _codex_default_shell(*, login: bool = False) -> ShellSpec | None:
    if os.name == "nt":
        return _resolve_named_shell("powershell", login=login) or _resolve_named_shell(
            "cmd", login=login
        )

    preferred = _posix_user_shell()
    preferred_kind = _kind_for_path(preferred) if preferred else None
    if preferred_kind in {"bash", "zsh", "sh"}:
        resolved = _resolve_named_shell(preferred_kind, preferred, login=login)
        if resolved is not None:
            return resolved
    fallback_order = (
        ("zsh", "bash", "sh")
        if sys.platform == "darwin"
        else ("bash", "zsh", "sh")
    )
    for kind in fallback_order:
        resolved = _resolve_named_shell(kind, login=login)
        if resolved is not None:
            return resolved
    return None


def shell_for_tool(tool_name: str, tool_input: dict[str, Any]) -> ShellSpec | None:
    if tool_name == "Bash":
        return _resolve_named_shell("bash")
    if tool_name == "PowerShell":
        return _resolve_named_shell("powershell")
    if tool_name in {"shell_command", "Shell"}:
        return _codex_default_shell(login=tool_input.get("login") is True)
    return None


def rewritten_command(command: str, shell: ShellSpec) -> str:
    encoded = encode_command(command)
    shell_path = encode_command(shell.executable)
    executable = os.environ.get("DISTILL_HOOK_COMMAND", "distill-hook")
    login_arg = " --login-shell" if shell.login else ""
    args = (
        f"run-encoded --shell-kind {shell.kind} --shell-path {shell_path}"
        f"{login_arg} {encoded}"
    )
    if os.name == "nt":
        return f"{executable} {args}"
    return f"{shlex.quote(executable)} {args}"


def handle_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("hook_event_name") != "PreToolUse":
        return None
    tool_name = payload.get("tool_name")
    if tool_name not in SHELL_TOOL_NAMES:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not should_rewrite(command):
        return None
    shell = shell_for_tool(str(tool_name), tool_input)
    if shell is None:
        return None
    permission_mode = payload.get("permission_mode")
    if permission_mode not in SAFE_PERMISSION_MODES and not allow_default_mode():
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "Distill noisy command output before returning it to the model.",
            "updatedInput": {"command": rewritten_command(command, shell)},
        }
    }


def hook_main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        response = handle_payload(payload)
        if response is not None:
            json.dump(response, sys.stdout, separators=(",", ":"))
            sys.stdout.write("\n")
    except Exception:
        return 0
    return 0


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def install_codex_hook(*, allow_default: bool = False) -> Path:
    home = codex_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / "hooks.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Cannot parse existing {path}: {exc}") from exc
    else:
        data = {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object in {path}")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise RuntimeError(f"Expected 'hooks' object in {path}")
    pre = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre, list):
        raise RuntimeError(f"Expected hooks.PreToolUse array in {path}")

    marker = "distill-hook codex-hook"
    installed = False
    for group in pre:
        if isinstance(group, dict):
            handlers = group.get("hooks")
            if isinstance(handlers, list) and any(
                isinstance(h, dict) and marker in str(h.get("command", "")) for h in handlers
            ):
                installed = True
                break

    if not installed:
        pre.append(
            {
                "matcher": "^(?:shell_command|Bash|PowerShell|Shell)$",
                "hooks": [
                    {
                        "type": "command",
                        "command": marker,
                        "timeout": 5,
                        "statusMessage": "Checking output distillation...",
                    }
                ],
            }
        )
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing_allow = False
    if config_path.exists():
        try:
            existing_config = json.loads(config_path.read_text(encoding="utf-8"))
            existing_allow = bool(
                isinstance(existing_config, dict)
                and existing_config.get("allow_default_mode") is True
            )
        except Exception:
            existing_allow = False
    config_path.write_text(
        json.dumps(
            {"allow_default_mode": bool(allow_default or existing_allow)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
