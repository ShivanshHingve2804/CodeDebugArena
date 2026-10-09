"""Generate a machine-readable validation report for CodeDebugArena.

Usage:
    python report.py
    python report.py --output validation-report.json
    python report.py --pretty
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import runner

SCHEMA_VERSION = "1.0"


def _run_status(challenge: Path, target: str):
    """Classify a challenge run without treating collection errors as bug catches."""
    code, timed_out, output = runner._run_challenge_tests(challenge, target)
    expected_timeout = (
        target == "buggy"
        and timed_out
        and challenge.name in runner.EXPECTED_BUGGY_TIMEOUT_CHALLENGES
    )
    if timed_out:
        status = "expected_timeout" if expected_timeout else "timeout"
        passed = expected_timeout
    elif code == 0:
        status = "passed"
        passed = target == "fixed"
    elif runner._has_pytest_failure(output):
        status = "failed_tests"
        passed = target == "buggy"
    else:
        status = "runner_error"
        passed = False
    return {"status": status, "accepted": passed, "output_excerpt": output.strip()[-2000:]}


def build_report(challenges: Optional[List[Path]] = None) -> Dict[str, Any]:
    """Validate challenge pairs and return a JSON-serializable report."""
    started = time.monotonic()
    discovered = runner.get_challenges() if challenges is None else challenges
    results = []

    for challenge in discovered:
        required = ("buggy.py", "fixed.py", "test_challenge.py")
        missing = [name for name in required if not (challenge / name).is_file()]
        if missing:
            results.append({
                "challenge": challenge.name,
                "valid": False,
                "buggy": {"status": "not_run", "accepted": False},
                "fixed": {"status": "not_run", "accepted": False},
                "issues": ["missing required files: " + ", ".join(missing)],
            })
            continue

        buggy = _run_status(challenge, "buggy")
        fixed = _run_status(challenge, "fixed")
        issues = []
        if not buggy["accepted"]:
            issues.append("buggy implementation was not caught by a test or documented timeout")
        if fixed["status"] != "passed":
            issues.append("fixed implementation did not pass its tests")
        results.append({
            "challenge": challenge.name,
            "valid": not issues,
            "buggy": buggy,
            "fixed": fixed,
            "issues": issues,
        })

    valid_count = sum(item["valid"] for item in results)
    elapsed = round(time.monotonic() - started, 3)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "ShivanshHingve2804/CodeDebugArena",
        "summary": {
            "total": len(results),
            "valid": valid_count,
            "invalid": len(results) - valid_count,
            "duration_seconds": elapsed,
        },
        "challenges": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the report to this file instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Indent the JSON for easier reading")
    args = parser.parse_args(argv)

    report = build_report()
    payload = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print("Wrote validation report to {}".format(args.output), file=sys.stderr)
    else:
        sys.stdout.write(payload)
    return 0 if report["summary"]["invalid"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
