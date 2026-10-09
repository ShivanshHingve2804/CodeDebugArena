"""CodeDebugArena - CLI runner for debugging challenges.

Commands:
  python runner.py list
  python runner.py test --target fixed
  python runner.py test --target buggy
  python runner.py validate
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

CHALLENGES_DIR = Path(__file__).parent / "challenges"

# Bound every child test run so one pathological challenge cannot hang the
# entire benchmark. Challenge 09 intentionally has exponential-time Fibonacci.
DEFAULT_TEST_TIMEOUT_SECONDS = 15
EXPECTED_BUGGY_TIMEOUT_SECONDS = 3
EXPECTED_BUGGY_TIMEOUT_CHALLENGES = {"09_recursive_fibonacci_blowup"}

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_challenges() -> list:
    """Discover all challenge directories sorted by their numeric prefix."""
    if not CHALLENGES_DIR.exists():
        return []
    dirs = [
        directory
        for directory in CHALLENGES_DIR.iterdir()
        if directory.is_dir() and not directory.name.startswith("_")
    ]

    def sort_key(directory: Path) -> Tuple[int, str]:
        match = re.match(r"^(\d+)_", directory.name)
        return (int(match.group(1)) if match else sys.maxsize, directory.name)

    return sorted(dirs, key=sort_key)


def _select_challenges(challenges: list, selector: Optional[str]) -> list:
    """Select by exact challenge number or case-insensitive name substring."""
    if selector is None:
        return challenges

    query = selector.strip().lower()
    if not query:
        return []

    if query.isdigit():
        number = int(query)
        matches = []
        for challenge in challenges:
            match = re.match(r"^(\d+)_", challenge.name)
            if match and int(match.group(1)) == number:
                matches.append(challenge)
        return matches

    return [challenge for challenge in challenges if query in challenge.name.lower()]


def _timeout_for(challenge: Path, target: str) -> int:
    """Return the test timeout, shortened for the intentionally slow buggy case."""
    if (
        target == "buggy"
        and challenge.name in EXPECTED_BUGGY_TIMEOUT_CHALLENGES
    ):
        return EXPECTED_BUGGY_TIMEOUT_SECONDS
    return DEFAULT_TEST_TIMEOUT_SECONDS


def _decode_output(value) -> str:
    """Normalize subprocess output, including bytes returned on timeout."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_challenge_tests(
    challenge: Path,
    target: str,
) -> Tuple[Optional[int], bool, str]:
    """Run one challenge's tests.

    Returns (return_code, timed_out, combined_output). A timed-out process has
    return_code=None; callers must decide whether that timeout was expected.
    """
    test_file = challenge / "test_challenge.py"
    env = os.environ.copy()
    env["CHALLENGE_TARGET"] = target

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-q",
        "--tb=short",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(challenge),
            env=env,
            timeout=_timeout_for(challenge, target),
        )
    except subprocess.TimeoutExpired as exc:
        output = _decode_output(exc.stdout) + "\n" + _decode_output(exc.stderr)
        return None, True, output

    return result.returncode, False, result.stdout + "\n" + result.stderr


def _has_pytest_failure(output: str) -> bool:
    """Distinguish an actual failing test from collection/import errors."""
    if "ERROR collecting" in output or "ImportError while importing" in output:
        return False
    if "ModuleNotFoundError" in output or "SyntaxError:" in output:
        return False
    return bool(re.search(r"\b\d+\s+failed\b", output))


def _print_failure_detail(output: str, verbose: bool) -> None:
    if verbose and output.strip():
        for line in output.strip().splitlines()[-12:]:
            print(f"     {DIM}{line}{RESET}")


def cmd_list(args) -> int:
    """List all available challenges."""
    challenges = get_challenges()
    if not challenges:
        print(f"{RED}No challenges found at {CHALLENGES_DIR}.{RESET}")
        return 1

    print(f"\n{BOLD}CodeDebugArena - {len(challenges)} Challenges{RESET}\n")
    print(f"  {'#':<5} {'Challenge':<45} {'Status':<20}")
    print(f"  {'-'*5} {'-'*45} {'-'*20}")

    for challenge in challenges:
        name = challenge.name
        has_buggy = (challenge / "buggy.py").is_file()
        has_fixed = (challenge / "fixed.py").is_file()
        has_test = (challenge / "test_challenge.py").is_file()

        if has_buggy and has_fixed and has_test:
            status = f"{GREEN}OK complete{RESET}"
        else:
            missing = []
            if not has_buggy:
                missing.append("buggy.py")
            if not has_fixed:
                missing.append("fixed.py")
            if not has_test:
                missing.append("test_challenge.py")
            status = f"{YELLOW}MISSING missing: {', '.join(missing)}{RESET}"

        match = re.match(r"^(\d+)_", name)
        number = match.group(1) if match else "?"
        display_name = name[match.end():] if match else name
        print(f"  {number:<5} {display_name:<45} {status}")

    print()
    return 0


def cmd_test(args) -> int:
    """Run one or more challenge suites against buggy or fixed implementations."""
    challenges = _select_challenges(get_challenges(), args.challenge)
    target = args.target

    if not challenges:
        selector = f" matching '{args.challenge}'" if args.challenge else ""
        print(f"{RED}No challenges found{selector}.{RESET}")
        return 2

    print(f"\n{BOLD}Running tests against {target.upper()} versions{RESET}\n")

    total_pass = 0
    total_fail = 0
    total_error = 0
    tested = 0

    for challenge in challenges:
        test_file = challenge / "test_challenge.py"
        target_file = challenge / f"{target}.py"

        if not test_file.is_file() or not target_file.is_file():
            missing = []
            if not test_file.is_file():
                missing.append("test_challenge.py")
            if not target_file.is_file():
                missing.append(f"{target}.py")
            print(f"  {YELLOW}SKIP  {challenge.name}: missing {', '.join(missing)}{RESET}")
            total_error += 1
            continue

        tested += 1
        return_code, timed_out, output = _run_challenge_tests(challenge, target)

        if timed_out:
            timeout = _timeout_for(challenge, target)
            if (
                target == "buggy"
                and challenge.name in EXPECTED_BUGGY_TIMEOUT_CHALLENGES
            ):
                print(
                    f"  {GREEN}OK {challenge.name}: expected buggy timeout "
                    f"({timeout}s){RESET}"
                )
                total_fail += 1
            else:
                print(
                    f"  {RED}FAIL {challenge.name}: test process timed out "
                    f"after {timeout}s{RESET}"
                )
                total_error += 1
        elif return_code == 0:
            print(f"  {GREEN}OK {challenge.name}: ALL TESTS PASSED{RESET}")
            total_pass += 1
        else:
            print(f"  {RED}FAIL {challenge.name}: TESTS FAILED{RESET}")
            _print_failure_detail(output, args.verbose)
            total_fail += 1

    print(
        f"\n{BOLD}Results:{RESET} "
        f"{GREEN}{total_pass} passed{RESET}, "
        f"{RED}{total_fail} failed{RESET}, "
        f"{YELLOW}{total_error} errors/skipped{RESET}"
    )

    if target == "buggy":
        print(f"  {DIM}(Expected: every buggy implementation should fail its tests){RESET}")
        # A benchmark run is considered healthy only if every selected buggy
        # version is caught and no challenge had to be skipped.
        return 0 if total_fail == tested and total_error == 0 and tested > 0 else 1

    return 1 if total_fail or total_error else 0


def cmd_validate(args) -> int:
    """Verify that buggy versions fail for test reasons and fixed versions pass."""
    challenges = get_challenges()
    if not challenges:
        print(f"{RED}No challenges found at {CHALLENGES_DIR}.{RESET}")
        return 2

    print(f"\n{BOLD}Validating all challenges...{RESET}\n")

    valid = 0
    invalid = 0

    for challenge in challenges:
        test_file = challenge / "test_challenge.py"
        buggy_file = challenge / "buggy.py"
        fixed_file = challenge / "fixed.py"

        if not all(file.is_file() for file in (test_file, buggy_file, fixed_file)):
            print(f"  {YELLOW}SKIP  {challenge.name}: incomplete challenge{RESET}")
            invalid += 1
            continue

        buggy_code, buggy_timed_out, buggy_output = _run_challenge_tests(
            challenge, "buggy"
        )
        fixed_code, fixed_timed_out, fixed_output = _run_challenge_tests(
            challenge, "fixed"
        )

        expected_slow_timeout = (
            buggy_timed_out
            and challenge.name in EXPECTED_BUGGY_TIMEOUT_CHALLENGES
        )
        buggy_fails_for_test = (
            not buggy_timed_out
            and buggy_code != 0
            and _has_pytest_failure(buggy_output)
        )
        buggy_failure_detected = expected_slow_timeout or buggy_fails_for_test
        fixed_passes = fixed_code == 0 and not fixed_timed_out

        if buggy_failure_detected and fixed_passes:
            timeout_note = " (expected performance timeout)" if expected_slow_timeout else ""
            print(
                f"  {GREEN}OK {challenge.name}: valid "
                f"(buggy fails OK{timeout_note}, fixed passes OK){RESET}"
            )
            valid += 1
            continue

        issues = []
        if buggy_timed_out and not expected_slow_timeout:
            issues.append("buggy tests timed out unexpectedly")
        elif not buggy_failure_detected:
            if buggy_code == 0 and not buggy_timed_out:
                issues.append("buggy implementation passed all tests")
            else:
                issues.append("buggy run errored without a confirmed test failure")

        if fixed_timed_out:
            issues.append("fixed tests timed out")
        elif not fixed_passes:
            issues.append("fixed implementation failed its tests")

        print(f"  {RED}FAIL {challenge.name}: INVALID - {'; '.join(issues)}{RESET}")
        if not buggy_failure_detected:
            _print_failure_detail(buggy_output, getattr(args, "verbose", False))
        if not fixed_passes:
            _print_failure_detail(fixed_output, getattr(args, "verbose", False))
        invalid += 1

    print(
        f"\n{BOLD}Validation:{RESET} "
        f"{GREEN}{valid} valid{RESET}, "
        f"{RED}{invalid} invalid{RESET} out of {len(challenges)} challenges"
    )
    return 1 if invalid else 0


def main() -> None:
    """Parse CLI arguments and execute the requested command."""
    parser = argparse.ArgumentParser(
        prog="python runner.py",
        description="CodeDebugArena - Run and validate debugging challenges",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("list", help="List all available challenges")

    test_parser = subparsers.add_parser("test", help="Run challenge tests")
    test_parser.add_argument(
        "--target",
        choices=["buggy", "fixed"],
        default="fixed",
        help="Which version to test (default: fixed)",
    )
    test_parser.add_argument(
        "--challenge",
        "-c",
        help="Challenge number (exact) or name substring",
    )
    test_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show test output on failure",
    )

    subparsers.add_parser(
        "validate",
        help="Verify that buggy versions fail and fixed versions pass",
    )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    if args.command == "list":
        sys.exit(cmd_list(args))
    if args.command == "test":
        sys.exit(cmd_test(args))
    if args.command == "validate":
        sys.exit(cmd_validate(args))


if __name__ == "__main__":
    main()
