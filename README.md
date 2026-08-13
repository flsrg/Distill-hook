# Distill Hook

A small, standalone command-output distiller for Codex. It uses a Codex `PreToolUse` hook to wrap selected noisy shell commands **before execution**, captures the command's stdout/stderr locally, returns a compact deterministic view to the model, and stores the original output for explicit recovery.

This project is an independent implementation focused only on command-output distillation. It does not require Repowise indexing, MCP, graph/PageRank data, a dashboard, or a server.

## How it works

```text
Codex proposes: sh ./gradlew test
        │
        ▼
PreToolUse hook
        │ updatedInput.command
        ▼
/absolute/path/to/distill-hook run-encoded <opaque-command>
        │
        ├─ runs the original command through the original shell dialect
        ├─ captures stdout + stderr in one stream
        ├─ selects a deterministic structural filter
        ├─ stores the full raw bytes in SQLite when compaction is useful
        └─ prints only the compact view + recovery marker
        │
        ▼
Codex receives the compact text as the normal shell tool result
```

The wrapped command's exit code is preserved. If classification, filtering, storage, or distillation fails, the original captured output is returned instead.

# Install and connect to Codex Desktop

The recommended end-user installation uses **pipx**. You do not need to clone this repository, create a virtual environment, or activate a venv manually.

The current ChatGPT desktop app includes **Codex** as a separate view. OpenAI's desktop guidance is available here: <https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex>.

## 1. Install pipx

### macOS

If you use Homebrew:

```bash
brew install pipx
pipx ensurepath
exec zsh
```

You only need to install pipx once.

## 2. Install Distill Hook from GitHub

```bash
pipx install git+https://github.com/flsrg/Distill-hook.git
```

Verify that the CLI is available:

```bash
distill-hook --help
which distill-hook
```

`which distill-hook` should return an absolute path, for example:

```text
/Users/you/.local/bin/distill-hook
```

If the command is not found after installing with pipx, run:

```bash
pipx ensurepath
exec zsh
```

and try again.

## 3. Register the hook with Codex

Run:

```bash
distill-hook install-hook
```

The installer:

- creates or updates `${CODEX_HOME:-~/.codex}/hooks.json`;
- preserves unrelated existing hooks;
- registers a `PreToolUse` handler for supported shell tools;
- resolves the installed `distill-hook` executable to an **absolute path** so the desktop app does not depend on your interactive shell's `PATH`;
- stores the resolved executable in `~/.codex/distill-hook/config.json` so rewritten commands reuse the same absolute path.

Verify the generated files:

```bash
cat ~/.codex/hooks.json
cat ~/.codex/distill-hook/config.json
```

The hook command in `hooks.json` should contain an absolute executable path, conceptually:

```json
{
  "type": "command",
  "command": "/Users/you/.local/bin/distill-hook codex-hook",
  "timeout": 5,
  "statusMessage": "Checking output distillation..."
}
```

The config should also contain the resolved executable:

```json
{
  "allow_default_mode": false,
  "executable": "/Users/you/.local/bin/distill-hook"
}
```

## 4. Restart the desktop app

Fully quit the ChatGPT desktop app and reopen it so Codex reloads hook configuration.

On desktop:

1. Open ChatGPT and sign in.
2. Select **Codex** from the top-left menu.
3. Open a local folder or Git repository.
4. Start a local Codex task normally.

## 5. Choose the permission behavior

### Safe mode — default

A normal installation uses:

```bash
distill-hook install-hook
```

In safe mode, Distill Hook rewrites commands only when the incoming Codex permission mode is already `dontAsk` or `bypassPermissions`.

This is intentionally conservative because Codex currently requires a `PreToolUse` hook that returns `updatedInput` to also return an `allow` permission decision.

### Normal/default Codex approval mode — explicit opt-in

If the hook is installed correctly but does not trigger in your normal Codex session, and you explicitly accept the approval-flow tradeoff, reinstall the hook with:

```bash
distill-hook install-hook --allow-default-mode
```

Then verify:

```bash
cat ~/.codex/distill-hook/config.json
```

You should see:

```json
{
  "allow_default_mode": true,
  "executable": "/absolute/path/to/distill-hook"
}
```

Use this option deliberately: when Distill Hook mutates a tool input, it returns an `allow` decision for that rewritten command.

# Verify that distillation is working

A successful end-to-end run has three visible signs.

## 1. Codex runs the absolute wrapper

For example, an Android/Gradle command may appear as:

```text
Ran /Users/you/.local/bin/distill-hook run-encoded --shell-kind bash --shell-path ...
```

This proves the `PreToolUse` hook fired and rewrote the original command through the installed Distill Hook executable.

## 2. Noisy output is compacted

A large Gradle result may contain a structural omission placeholder such as:

```text
> Task :app:preBuild UP-TO-DATE
> Task :data:preBuild UP-TO-DATE
... 120 build lines omitted ...
> Task :app:test

BUILD SUCCESSFUL in 37s
108 actionable tasks: 108 executed
```

Failure output keeps relevant error neighborhoods and the final build/test summary instead of blindly truncating the tail.

## 3. A recovery marker appears

A distilled result ends with a marker similar to:

```text
[distill#36c4a0716336c4e0: 131 lines omitted (~1315 tokens); restore: distill-hook expand 36c4a0716336c4e0]
```

That marker confirms that compaction was useful and that the original raw output was stored for recovery.

## Recommended Android/Gradle smoke test

In a Gradle project, ask Codex to run the complete JVM test suite. A useful explicit test is:

```bash
sh ./gradlew test --rerun-tasks
```

Simple shell-launched Gradle forms such as `sh ./gradlew ...` and `bash ./gradlew ...` are supported. Shell-program forms such as `sh -c ...` or `bash -lc ...`, command chains, pipelines, and redirects remain intentionally excluded.

If the run is large enough to benefit from compaction, you should see the absolute `distill-hook run-encoded` wrapper plus a `[distill#...]` recovery marker.

# Restore omitted output

Use the reference from the marker:

```bash
distill-hook expand 36c4a0716336c4e0
```

The omission database defaults to:

```text
~/.codex/distill-hook/omissions.db
```

Stored entries are kept for seven days and the compressed store is capped at roughly 50 MiB. Set `DISTILL_HOOK_STORE` to override the database path.

# Update or reinstall

To replace an existing pipx installation with the latest `main` branch:

```bash
pipx install --force git+https://github.com/flsrg/Distill-hook.git
```

Then run the installer again so the executable path and config are refreshed:

```bash
distill-hook install-hook
```

If you previously enabled default-mode rewriting and want to keep it enabled, use:

```bash
distill-hook install-hook --allow-default-mode
```

Finally, fully quit and reopen the ChatGPT desktop app.

# Troubleshooting

## `distill-hook: command not found`

Run:

```bash
pipx ensurepath
exec zsh
which distill-hook
```

If `which distill-hook` still returns nothing, inspect:

```bash
pipx list
```

and reinstall the package.

## Hook is installed but Codex does not show `run-encoded`

Check:

```bash
cat ~/.codex/hooks.json
cat ~/.codex/distill-hook/config.json
```

Common reasons:

- Codex is running in normal/default permission mode while `allow_default_mode` is `false`;
- the desktop app was not restarted after hook installation;
- the proposed command is unsupported;
- the command contains a chain, pipeline, redirect, command substitution, multiline shell program, or another intentionally excluded shell shape.

## `run-encoded` appears but there is no `[distill#...]` marker

This can be normal. Distill Hook returns raw output when:

- the output is too small;
- the selected filter cannot reduce it meaningfully;
- compaction would not save enough tokens;
- filtering or storage fails and the engine falls open to the original output.

## Verify the stored executable path

The executable in these two files should agree:

```bash
which distill-hook
cat ~/.codex/hooks.json
cat ~/.codex/distill-hook/config.json
```

If they do not, rerun:

```bash
distill-hook install-hook
```

and restart the desktop app.

# Supported command families

- **tests:** pytest, Jest, Vitest, Cargo/nextest, Go test, npm/pnpm/yarn test
- **Git:** status, log, diff, `gh pr diff`
- **lint/build:** Ruff, ESLint, mypy, pyright, tsc, Cargo build/check/clippy, npm/pnpm/yarn build, make/CMake, Gradle/Gradle Wrapper, Maven, Docker build, Terraform plan
- **search/listing:** rg, grep, safe find/fd, ls/tree
- **logs:** docker logs, kubectl logs, journalctl, common `.log`/tail reads

The hook intentionally ignores unknown commands, command chains, pipelines, redirects, shell substitutions, multiline programs, long-running follow/watch modes, and mutating `find` actions. This keeps command mutation narrow and fail-open.

# Safety model

- **Pre-execution interception:** raw noisy output does not need to enter model context first.
- **Fail open:** unsupported commands and internal failures leave the original tool call/output intact.
- **Conservative rewrite grammar:** only single, recognized command families are wrapped; compound shell programs are passed through.
- **Approval-aware default:** normal/default approval mode is not rewritten unless the user explicitly opts in.
- **Reversible:** raw bytes are stored before a recovery marker is emitted.
- **Net-positive only:** compaction is returned only when it saves a meaningful amount.
- **Exit code preserved:** the wrapper exits with the original command's code.
- **No LLM in the distiller:** filters are deterministic parsers/heuristics.

# Development / contributing

The pipx flow above is for normal users. For repository development, use a local virtual environment instead:

```bash
git clone https://github.com/flsrg/Distill-hook.git
cd Distill-hook
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q
```

Do not use the development venv as the normal Codex Desktop installation path; the pipx installation is simpler and gives the hook a stable user-level executable.