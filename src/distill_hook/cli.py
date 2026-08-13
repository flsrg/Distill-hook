from __future__ import annotations

import argparse
import sys

from .engine import distill_output
from .executor import ShellSpec, run_command
from .hook import decode_command, hook_main, install_codex_hook
from .markers import parse_ref
from .store import OmissionStore


def _write_bytes(data: bytes) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        sys.stdout.write(data.decode("utf-8", errors="replace"))
    else:
        stream.write(data)
        stream.flush()


def run_encoded(
    encoded: str,
    *,
    shell_kind: str,
    shell_path_encoded: str,
    login_shell: bool = False,
) -> int:
    command = decode_command(encoded)
    shell = ShellSpec(shell_kind, decode_command(shell_path_encoded), login_shell)
    raw, code = run_command(command, shell=shell)
    try:
        with OmissionStore() as store:
            store.prune()
            result = distill_output(raw, command=command, store=store)
            _write_bytes(result.output)
    except Exception:
        _write_bytes(raw)
    return code


def expand(value: str) -> int:
    ref = parse_ref(value)
    if ref is None:
        print("invalid distill reference", file=sys.stderr)
        return 2
    try:
        with OmissionStore() as store:
            content = store.get(ref)
    except Exception as exc:
        print(f"cannot open distill store: {exc}", file=sys.stderr)
        return 1
    if content is None:
        print(f"distill reference not found: {ref}", file=sys.stderr)
        return 1
    _write_bytes(content)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="distill-hook")
    sub = parser.add_subparsers(dest="command", required=True)

    encoded = sub.add_parser("run-encoded", help=argparse.SUPPRESS)
    encoded.add_argument(
        "--shell-kind",
        choices=("bash", "zsh", "sh", "powershell", "cmd"),
        required=True,
    )
    encoded.add_argument("--shell-path", required=True, help=argparse.SUPPRESS)
    encoded.add_argument("--login-shell", action="store_true", help=argparse.SUPPRESS)
    encoded.add_argument("payload")

    sub.add_parser("codex-hook", help="Run the Codex PreToolUse hook on stdin")

    expand_p = sub.add_parser("expand", help="Restore full output from a distill marker")
    expand_p.add_argument("ref")

    install = sub.add_parser("install-hook", help="Install the Codex PreToolUse hook")
    install.add_argument(
        "--allow-default-mode",
        action="store_true",
        help=(
            "permit rewritten commands in Codex approval modes where PreToolUse "
            "permissionDecision:allow can bypass a prompt"
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run-encoded":
        return run_encoded(
            args.payload,
            shell_kind=args.shell_kind,
            shell_path_encoded=args.shell_path,
            login_shell=args.login_shell,
        )
    if args.command == "codex-hook":
        return hook_main()
    if args.command == "expand":
        return expand(args.ref)
    if args.command == "install-hook":
        try:
            path = install_codex_hook(allow_default=args.allow_default_mode)
        except Exception as exc:
            print(f"failed to install Codex hook: {exc}", file=sys.stderr)
            return 1
        print(f"Installed Codex hook in {path}")
        if not args.allow_default_mode:
            print("Safe mode: automatic rewriting is limited to Codex dontAsk/bypassPermissions modes.")
            print("Re-run with --allow-default-mode only if you accept the approval-bypass tradeoff.")
        print("Restart Codex so it reloads hook configuration.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
