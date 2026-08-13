import sys

from distill_hook.executor import run_command
from distill_hook.hook import decode_command, encode_command


def test_command_encoding_round_trip():
    command = "printf 'hello world' && echo done"
    assert decode_command(encode_command(command)) == command


def test_executor_merges_stderr_into_output():
    code = "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"
    command = f'"{sys.executable}" -c "{code}"'
    output, exit_code = run_command(command)
    text = output.decode()
    assert "out" in text
    assert "err" in text
    assert exit_code == 7
