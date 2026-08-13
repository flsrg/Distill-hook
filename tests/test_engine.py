from pathlib import Path

from distill_hook.engine import distill_output
from distill_hook.store import OmissionStore


def test_test_output_distills_and_round_trips(tmp_path: Path):
    lines = ["================ test session starts ================"]
    lines += [f"test_{i}.py::test_ok PASSED" for i in range(160)]
    lines += [
        "================ FAILURES ================",
        "________________ test_login ________________",
        "E   AssertionError: expected 200, got 401",
        "================ short test summary info ================",
        "FAILED tests/test_auth.py::test_login - AssertionError",
        "1 failed, 160 passed in 2.00s",
    ]
    raw = ("\n".join(lines) + "\n").encode()
    with OmissionStore(tmp_path / "store.db") as store:
        result = distill_output(raw, command="pytest -q", store=store)
        assert result.distilled
        assert b"AssertionError" in result.output
        assert b"distill#" in result.output
        assert result.ref is not None
        assert store.get(result.ref) == raw


def test_shell_launched_gradle_output_distills_and_round_trips(tmp_path: Path):
    lines = ["Calculating task graph for tasks: test"]
    lines += [f"> Task :module{i}:compileDebugKotlin UP-TO-DATE" for i in range(120)]
    lines += [
        "> Task :service:test",
        "BUILD SUCCESSFUL in 42s",
        "108 actionable tasks: 7 executed, 101 up-to-date",
    ]
    raw = ("\n".join(lines) + "\n").encode()

    with OmissionStore(tmp_path / "gradle-store.db") as store:
        result = distill_output(raw, command="sh ./gradlew test", store=store)
        assert result.distilled
        assert b"BUILD SUCCESSFUL" in result.output
        assert b"distill#" in result.output
        assert result.ref is not None
        assert store.get(result.ref) == raw


def test_unknown_command_falls_back_raw(tmp_path: Path):
    raw = ("hello\n" * 100).encode()
    with OmissionStore(tmp_path / "store.db") as store:
        result = distill_output(raw, command="printf hello", store=store)
    assert result.output == raw
    assert not result.distilled
