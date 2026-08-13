import shutil

from distill_hook.hook import decode_command, handle_payload, should_rewrite


def _payload(command: str, tool_name: str = "shell_command") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "permission_mode": "dontAsk",
    }


def test_follow_and_watch_modes_are_left_unwrapped():
    docker = "doc" + "ker"
    kubectl = "kube" + "ctl"
    assert not should_rewrite(docker + " logs -f app")
    assert not should_rewrite(kubectl + " logs --follow pod/api")
    assert not should_rewrite("journal" + "ctl -f")
    assert not should_rewrite("tail -n 20 -F app.log")
    assert not should_rewrite("vit" + "est --watch")
    assert not should_rewrite("je" + "st --watchAll")
    assert should_rewrite(docker + " logs app")


def test_bash_tool_passes_bash_descriptor_to_wrapper():
    response = handle_payload(_payload("py" + "test -q", "Bash"))
    if shutil.which("bash") is None:
        assert response is None
        return
    assert response is not None
    rewritten = response["hookSpecificOutput"]["updatedInput"]["command"]
    assert "--shell-kind bash" in rewritten
    encoded = rewritten.split()[-1].strip("'\"")
    assert decode_command(encoded) == "py" + "test -q"
