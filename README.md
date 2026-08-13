# Distill Hook

A small, standalone command-output distiller for Codex. It uses a Codex `PreToolUse` hook to wrap selected noisy shell commands **before execution**, captures the command's stdout/stderr locally, returns a compact deterministic view to the model, and stores the original output for explicit recovery.

This project is an independent implementation focused only on command-output distillation. It does not require Repowise indexing, MCP, graph/PageRank data, a dashboard, or a server.

## How it works

```text
Codex proposes: pytest -q
        │
        ▼
PreToolUse hook
        │ updatedInput.command
        ▼
distill-hook run-encoded <opaque-command>
        │
        ├─ runs the original command through the platform shell
        ├─ captures stdout + stderr in one stream
        ├─ selects a deterministic structural filter
        ├─ stores the full raw bytes in SQLite when compaction is useful
        └─ prints only the compact view + recovery marker
        │
        ▼
Codex receives the compact text as the normal shell tool result
```

The wrapped command's exit code is preserved. If classification, filtering, storage, or distillation fails, the original captured output is returned instead.

## Install

```bash
python -m pip install -e .
distill-hook install-hook
```

The installer adds a `PreToolUse` command hook to `${CODEX_HOME:-~/.codex}/hooks.json` while preserving existing hooks. Restart Codex after installation so it reloads hook configuration.

Current Codex requires `permissionDecision: "allow"` when a `PreToolUse` hook returns `updatedInput`. Because that can affect approval behavior, **safe mode is the default**: automatic rewriting runs only when the incoming Codex `permission_mode` is already `dontAsk` or `bypassPermissions`. To explicitly accept automatic rewriting in the normal/default approval mode, install with:

```bash
distill-hook install-hook --allow-default-mode
```

That opt-in is stored in `~/.codex/distill-hook/config.json`. Depending on the Codex build/channel, hooks may still be feature-gated; use a current Codex build with hooks enabled.

## Supported command families (v0.1)

- tests: pytest, Jest, Vitest, Cargo/nextest, Go test, npm/pnpm/yarn test
- Git: status, log, diff, `gh pr diff`
- lint/build: Ruff, ESLint, mypy, pyright, tsc, Cargo build/check/clippy, npm/pnpm/yarn build, make/CMake, Gradle, Maven, Docker build, Terraform plan
- search/listing: rg, grep, safe find/fd, ls/tree
- logs: docker logs, kubectl logs, journalctl, common `.log`/tail reads

The hook intentionally ignores unknown commands, command chains, pipelines, redirects, shell substitutions, multiline programs, and mutating `find` actions. This keeps command mutation narrow and fail-open.

## Restore omitted output

A compacted result ends with a marker such as:

```text
[distill#5c91b2724e2a2c89: 150 lines omitted (~2400 tokens); restore: distill-hook expand 5c91b2724e2a2c89]
```

Recover the original captured bytes with:

```bash
distill-hook expand 5c91b2724e2a2c89
```

The omission database defaults to `~/.codex/distill-hook/omissions.db`, keeps recent entries for seven days, and is capped to roughly 50 MiB of compressed content. Set `DISTILL_HOOK_STORE` to override the path.

## Safety model

- **Pre-execution interception:** raw noisy output does not need to enter the model context first.
- **Fail open:** unsupported commands and internal failures leave the original tool call/output intact.
- **Conservative rewrite grammar:** only single, recognized command families are wrapped; compound shell programs are passed through.
- **Approval-aware default:** normal approval mode is not rewritten unless the user explicitly opts in.
- **Reversible:** raw bytes are stored before a recovery marker is emitted.
- **Net-positive only:** compaction is returned only when it saves a meaningful amount.
- **Exit code preserved:** the wrapper exits with the original command's code.
- **No LLM in the distiller:** filters are deterministic parsers/heuristics.

## Development

```bash
python -m pytest -q
```
