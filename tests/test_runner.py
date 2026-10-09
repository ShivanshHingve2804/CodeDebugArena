"""Tests for CodeDebugArena's CLI runner."""

from types import SimpleNamespace

import runner


def _challenge(root, name, *files):
    directory = root / name
    directory.mkdir()
    for filename in files:
        (directory / filename).write_text("# fixture\n", encoding="utf-8")
    return directory


def test_numeric_challenge_selection_is_exact(tmp_path):
    first = _challenge(tmp_path, "01_binary_search", "buggy.py")
    tenth = _challenge(tmp_path, "10_file_leak", "buggy.py")
    eleventh = _challenge(tmp_path, "11_merge_sort", "buggy.py")

    selected = runner._select_challenges([first, tenth, eleventh], "1")

    assert selected == [first]


def test_name_selection_is_case_insensitive(tmp_path):
    first = _challenge(tmp_path, "01_binary_search", "buggy.py")
    second = _challenge(tmp_path, "02_mutable_default", "buggy.py")

    assert runner._select_challenges([first, second], "BINARY") == [first]


def test_pytest_failure_requires_test_failure_not_collection_error():
    assert runner._has_pytest_failure("FAILED test_case.py::test_bug\n1 failed in 0.01s")
    assert not runner._has_pytest_failure(
        "ERROR collecting test_case.py\nModuleNotFoundError: No module named 'buggy'"
    )


def test_expected_timeout_is_limited_to_slow_buggy_challenge(tmp_path):
    slow = tmp_path / "09_recursive_fibonacci_blowup"
    ordinary = tmp_path / "01_binary_search_off_by_one"

    assert runner._timeout_for(slow, "buggy") == runner.EXPECTED_BUGGY_TIMEOUT_SECONDS
    assert runner._timeout_for(slow, "fixed") == runner.DEFAULT_TEST_TIMEOUT_SECONDS
    assert runner._timeout_for(ordinary, "buggy") == runner.DEFAULT_TEST_TIMEOUT_SECONDS


def test_missing_challenge_files_fail_test_command(tmp_path, monkeypatch):
    _challenge(tmp_path, "01_incomplete", "fixed.py")
    monkeypatch.setattr(runner, "CHALLENGES_DIR", tmp_path)

    result = runner.cmd_test(
        SimpleNamespace(target="fixed", challenge=None, verbose=False)
    )

    assert result != 0


def test_buggy_target_that_passes_is_not_a_success(tmp_path, monkeypatch):
    challenge = _challenge(
        tmp_path,
        "01_broken_benchmark",
        "buggy.py",
        "fixed.py",
        "test_challenge.py",
    )
    monkeypatch.setattr(runner, "CHALLENGES_DIR", tmp_path)
    monkeypatch.setattr(
        runner,
        "_run_challenge_tests",
        lambda challenge, target: (0, False, "3 passed in 0.01s"),
    )

    result = runner.cmd_test(
        SimpleNamespace(target="buggy", challenge=None, verbose=False)
    )

    assert challenge.exists()
    assert result != 0


def test_buggy_collection_error_is_not_counted_as_expected_failure(tmp_path, monkeypatch):
    _challenge(
        tmp_path,
        "01_collection_error",
        "buggy.py",
        "fixed.py",
        "test_challenge.py",
    )
    monkeypatch.setattr(runner, "CHALLENGES_DIR", tmp_path)
    monkeypatch.setattr(
        runner,
        "_run_challenge_tests",
        lambda challenge, target: (
            2,
            False,
            "ERROR collecting test_challenge.py\\n"
            "ModuleNotFoundError: No module named 'buggy'",
        ),
    )

    result = runner.cmd_test(
        SimpleNamespace(target="buggy", challenge=None, verbose=False)
    )

    assert result != 0
