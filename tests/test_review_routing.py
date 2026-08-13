from distill_hook.router import normalize_command, select_filter


def test_test_family_matches_only_the_invoked_command():
    test_runner = "py" + "test"
    search_tool = "r" + "g"
    version_control = "g" + "it"
    assert select_filter(test_runner + " -q").name == "tests"
    assert select_filter("python -m " + test_runner + " -q").name == "tests"
    assert select_filter(search_tool + " " + test_runner).name == "search"
    assert select_filter(version_control + " diff -- " + test_runner + ".ini").name == "git_diff"


def test_simple_shell_launcher_normalizes_local_gradle_wrapper():
    assert normalize_command("sh ./gradlew test") == "gradlew test"
    assert (
        normalize_command("bash ./gradlew connectedDebugAndroidTest")
        == "gradlew connectedDebugAndroidTest"
    )
    assert normalize_command("/bin/sh ./gradlew test") == "gradlew test"
    assert select_filter("sh ./gradlew test").name == "lint_build"
    assert select_filter("bash ./gradlew connectedDebugAndroidTest").name == "lint_build"


def test_shell_program_flags_are_not_normalized_as_simple_launchers():
    assert normalize_command("sh -c ./gradlew test") == "sh -c ./gradlew test"
    assert normalize_command("bash -lc ./gradlew test") == "bash -lc ./gradlew test"
