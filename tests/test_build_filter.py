from distill_hook.filters.generic import LintBuildFilter


def test_failure_footer_is_not_duplicated():
    lines = [f"> Task :module{i}:compile UP-TO-DATE" for i in range(80)]
    lines += [
        "> Task :service:compile FAILED",
        "e: Example.kt:3:17 Unresolved reference 'test'.",
        "FAILURE: Build failed with an exception.",
        "* What went wrong:",
        "Compilation error. See log for more details.",
        "* Try:",
        "> Run with --stacktrace option to get the stack trace.",
        "BUILD FAILED in 1s",
        "191 actionable tasks: 7 executed, 184 up-to-date",
        "Configuration cache entry reused.",
    ]

    result = LintBuildFilter().distill("gradle test", "\n".join(lines))

    assert result.text.count("BUILD FAILED in 1s") == 1
    assert result.text.count("> Run with --stacktrace option") == 1
