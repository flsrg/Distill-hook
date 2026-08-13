from distill_hook.router import select_filter


def test_test_family_matches_only_the_invoked_command():
    test_runner = "py" + "test"
    search_tool = "r" + "g"
    version_control = "g" + "it"
    assert select_filter(test_runner + " -q").name == "tests"
    assert select_filter("python -m " + test_runner + " -q").name == "tests"
    assert select_filter(search_tool + " " + test_runner).name == "search"
    assert select_filter(version_control + " diff -- " + test_runner + ".ini").name == "git_diff"
