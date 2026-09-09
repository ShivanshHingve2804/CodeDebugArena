"""CodeDebugArena — CLI runner for debugging challenges.

Provides commands to list, test, and validate debugging challenges.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


CHALLENGES_DIR = Path(__file__).parent / "challenges"

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_challenges() -> list:
    """Discover all challenge directories sorted by number."""
    if not CHALLENGES_DIR.exists():
        return []
    dirs = [d for d in sorted(CHALLENGES_DIR.iterdir()) if d.is_dir() and not d.name.startswith("_")]
    return dirs


def cmd_list(args):
    """List all available challenges."""
    challenges = get_challenges()
    if not challenges:
        print(f"{RED}No challenges found.{RESET}")
        return

    print(f"\n{BOLD}🐛 CodeDebugArena — {len(challenges)} Challenges{RESET}\n")
    print(f"  {'#':<5} {'Challenge':<45} {'Files':<10}")
    print(f"  {'─'*5} {'─'*45} {'─'*10}")

    for ch_dir in challenges:
        name = ch_dir.name
        files = list(ch_dir.glob("*.py"))
        has_buggy = (ch_dir / "buggy.py").exists()
        has_fixed = (ch_dir / "fixed.py").exists()
        has_test = (ch_dir / "test_challenge.py").exists()

        status = ""
        if has_buggy and has_fixed and has_test:
            status = f"{GREEN}✓ complete{RESET}"
        else:
            missing = []
            if not has_buggy:
                missing.append("buggy")
            if not has_fixed:
                missing.append("fixed")
            if not has_test:
                missing.append("test")
            status = f"{YELLOW}✗ missing: {', '.join(missing)}{RESET}"

        num = name.split("_")[0] if "_" in name else "?"
        display_name = "_".join(name.split("_")[1:]) if "_" in name else name
        print(f"  {num:<5} {display_name:<45} {status}")

    print()


def cmd_test(args):
    """Run tests for challenges against buggy or fixed versions."""
    challenges = get_challenges()
    target = args.target  # "buggy" or "fixed"

    if args.challenge:
        challenges = [c for c in challenges if c.name.startswith(f"{args.challenge:>02}") or args.challenge in c.name]
        if not challenges:
            print(f"{RED}Challenge '{args.challenge}' not found.{RESET}")
            return 1

    print(f"\n{BOLD}🧪 Running tests against {target.upper()} versions{RESET}\n")

    total_pass = 0
    total_fail = 0
    total_error = 0

    for ch_dir in challenges:
        test_file = ch_dir / "test_challenge.py"
        target_file = ch_dir / f"{target}.py"

        if not test_file.exists():
            print(f"  {YELLOW}⏭  {ch_dir.name}: no test file{RESET}")
            total_error += 1
            continue

        if not target_file.exists():
            print(f"  {YELLOW}⏭  {ch_dir.name}: no {target}.py{RESET}")
            total_error += 1
            continue

        # Run pytest on the test file with the target module
        env = os.environ.copy()
        env["CHALLENGE_TARGET"] = target

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            cwd=str(ch_dir),
            env=env,
        )

        if result.returncode == 0:
            print(f"  {GREEN}✅ {ch_dir.name}: ALL TESTS PASSED{RESET}")
            total_pass += 1
        else:
            print(f"  {RED}❌ {ch_dir.name}: TESTS FAILED{RESET}")
            if args.verbose:
                for line in result.stdout.strip().split("\n")[-5:]:
                    print(f"     {DIM}{line}{RESET}")
            total_fail += 1

    print(f"\n{BOLD}📊 Results:{RESET} {GREEN}{total_pass} passed{RESET}, {RED}{total_fail} failed{RESET}, {YELLOW}{total_error} skipped{RESET}")

    if target == "buggy":
        if total_fail > 0:
            print(f"  {DIM}(Expected: buggy versions should fail tests){RESET}")
    elif target == "fixed":
        if total_fail > 0:
            print(f"  {RED}⚠  Some fixed versions are failing — check your fixes!{RESET}")

    return 1 if (target == "fixed" and total_fail > 0) else 0


def cmd_validate(args):
    """Validate all challenges: buggy should fail, fixed should pass."""
    challenges = get_challenges()

    print(f"\n{BOLD}🔍 Validating all challenges...{RESET}\n")

    valid = 0
    invalid = 0

    for ch_dir in challenges:
        test_file = ch_dir / "test_challenge.py"
        buggy_file = ch_dir / "buggy.py"
        fixed_file = ch_dir / "fixed.py"

        if not all(f.exists() for f in [test_file, buggy_file, fixed_file]):
            print(f"  {YELLOW}⏭  {ch_dir.name}: incomplete challenge{RESET}")
            invalid += 1
            continue

        # Test buggy (should FAIL)
        env_buggy = os.environ.copy()
        env_buggy["CHALLENGE_TARGET"] = "buggy"
        r_buggy = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=no"],
            capture_output=True, text=True, cwd=str(ch_dir), env=env_buggy,
        )

        # Test fixed (should PASS)
        env_fixed = os.environ.copy()
        env_fixed["CHALLENGE_TARGET"] = "fixed"
        r_fixed = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q", "--tb=no"],
            capture_output=True, text=True, cwd=str(ch_dir), env=env_fixed,
        )

        buggy_fails = r_buggy.returncode != 0
        fixed_passes = r_fixed.returncode == 0

        if buggy_fails and fixed_passes:
            print(f"  {GREEN}✅ {ch_dir.name}: valid (buggy fails ✓, fixed passes ✓){RESET}")
            valid += 1
        else:
            issues = []
            if not buggy_fails:
                issues.append("buggy should fail but passes")
            if not fixed_passes:
                issues.append("fixed should pass but fails")
            print(f"  {RED}❌ {ch_dir.name}: INVALID — {'; '.join(issues)}{RESET}")
            invalid += 1

    print(f"\n{BOLD}📊 Validation:{RESET} {GREEN}{valid} valid{RESET}, {RED}{invalid} invalid{RESET} out of {len(challenges)} challenges")
    return 1 if invalid > 0 else 0


def main():
    parser = argparse.ArgumentParser(
        prog="python runner.py",
        description="CodeDebugArena — Run and validate debugging challenges",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list
    subparsers.add_parser("list", help="List all available challenges")

    # test
    test_parser = subparsers.add_parser("test", help="Run challenge tests")
    test_parser.add_argument("--target", choices=["buggy", "fixed"], default="fixed",
                            help="Which version to test (default: fixed)")
    test_parser.add_argument("--challenge", "-c", help="Run a specific challenge (number or name)")
    test_parser.add_argument("--verbose", "-v", action="store_true", help="Show test output on failure")

    # validate
    subparsers.add_parser("validate", help="Validate all challenges (buggy fails, fixed passes)")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "list":
        cmd_list(args)
    elif args.command == "test":
        sys.exit(cmd_test(args))
    elif args.command == "validate":
        sys.exit(cmd_validate(args))


if __name__ == "__main__":
    main()
