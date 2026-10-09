"""Run multiple command-line coding agents against isolated benchmark challenges.

Each agent command is a shell command template. Supported placeholders:
    {workspace}   isolated working directory for this agent/challenge pair
    {challenge}   challenge directory name
    {prompt_file} task prompt file path
    {buggy_file}  path to the buggy implementation in the workspace

Example:
    python multi_agent_runner.py \
      --agent 'codex=codex exec --full-auto "$(cat {prompt_file})"' \
      --agent 'claude=claude -p "$(cat {prompt_file})"' \
      --timeout 120 --output results.json

Agent commands must be installed and authenticated locally. This runner does not
assume every CLI accepts the same flags; configure a command template per agent.
"""
import argparse
import concurrent.futures
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import runner

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_CONCURRENCY = 4
REPORT_SCHEMA_VERSION = "1.0"


def parse_agent(value: str) -> Tuple[str, str]:
    """Parse NAME=COMMAND, allowing '=' inside the command portion."""
    if "=" not in value:
        raise argparse.ArgumentTypeError("agent must use NAME=COMMAND format")
    name, command = value.split("=", 1)
    name, command = name.strip(), command.strip()
    if not name or not command:
        raise argparse.ArgumentTypeError("agent name and command must be non-empty")
    return name, command


def _safe_format_command(template: str, values: Dict[str, str]) -> str:
    """Substitute placeholders with shell-quoted paths and values."""
    return template.format(**{key: shlex.quote(value) for key, value in values.items()})


def _prepare_workspace(challenge: Path, workspace: Path) -> Path:
    """Copy only agent-visible challenge context, excluding tests and the known fix."""
    workspace.mkdir(parents=True, exist_ok=True)
    for filename in ("buggy.py", "README.md"):
        source = challenge / filename
        if source.is_file():
            shutil.copy2(str(source), str(workspace / filename))
    prompt = (
        "Fix the bug in buggy.py while preserving its public interface. "
        "Use the challenge README as context. Modify buggy.py directly. "
        "Do not create or modify tests. Finish by leaving the corrected implementation "
        "in buggy.py. Do not access files outside this workspace.\n"
    )
    prompt_path = workspace / "AGENT_TASK.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _validate_agent_patch(challenge: Path, workspace: Path) -> Dict[str, Any]:
    """Validate the agent-edited buggy.py against the challenge tests as fixed.py."""
    candidate = workspace / "buggy.py"
    if not candidate.is_file():
        return {
            "status": "missing_patch",
            "passed": False,
            "validation_seconds": 0.0,
            "output_excerpt": "Agent did not leave a buggy.py file in its workspace.",
        }

    with tempfile.TemporaryDirectory(prefix="codedebugarena-validate-") as temp:
        validation_dir = Path(temp)
        shutil.copy2(str(candidate), str(validation_dir / "fixed.py"))
        shutil.copy2(str(challenge / "test_challenge.py"), str(validation_dir / "test_challenge.py"))
        env = os.environ.copy()
        env["CHALLENGE_TARGET"] = "fixed"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "test_challenge.py", "-q", "--tb=short"],
                cwd=str(validation_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=runner.DEFAULT_TEST_TIMEOUT_SECONDS,
                check=False,
            )
            elapsed = round(time.monotonic() - started, 3)
            output = completed.stdout or ""
            passed = completed.returncode == 0
            return {
                "status": "passed" if passed else "failed_tests",
                "passed": passed,
                "validation_seconds": elapsed,
                "output_excerpt": output[-2000:],
            }
        except subprocess.TimeoutExpired as exc:
            elapsed = round(time.monotonic() - started, 3)
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return {
                "status": "validation_timeout",
                "passed": False,
                "validation_seconds": elapsed,
                "output_excerpt": str(output)[-2000:],
            }


def run_one(challenge: Path, agent_name: str, command_template: str, timeout: int) -> Dict[str, Any]:
    """Execute one agent on one challenge and validate its patch."""
    record: Dict[str, Any] = {
        "agent": agent_name,
        "challenge": challenge.name,
        "timeout_seconds": timeout,
        "status": "runner_error",
        "completion_seconds": None,
        "validation_seconds": None,
        "passed": False,
        "return_code": None,
        "output_excerpt": "",
    }
    required = ("buggy.py", "test_challenge.py")
    missing = [name for name in required if not (challenge / name).is_file()]
    if missing:
        record["status"] = "invalid_challenge"
        record["output_excerpt"] = "Missing required files: " + ", ".join(missing)
        return record

    with tempfile.TemporaryDirectory(prefix="codedebugarena-agent-") as temp:
        workspace = Path(temp)
        prompt_path = _prepare_workspace(challenge, workspace)
        values = {
            "workspace": str(workspace),
            "challenge": challenge.name,
            "prompt_file": str(prompt_path),
            "buggy_file": str(workspace / "buggy.py"),
        }
        try:
            command = _safe_format_command(command_template, values)
        except (KeyError, ValueError) as exc:
            record["status"] = "invalid_command_template"
            record["output_excerpt"] = str(exc)
            return record

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            record["completion_seconds"] = round(time.monotonic() - started, 3)
            record["return_code"] = completed.returncode
            record["output_excerpt"] = (completed.stdout or "")[-2000:]
            if completed.returncode != 0:
                record["status"] = "agent_error"
                return record
        except subprocess.TimeoutExpired as exc:
            record["completion_seconds"] = round(time.monotonic() - started, 3)
            record["status"] = "timed_out"
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            record["output_excerpt"] = str(output)[-2000:]
            return record
        except OSError as exc:
            record["completion_seconds"] = round(time.monotonic() - started, 3)
            record["status"] = "runner_error"
            record["output_excerpt"] = str(exc)
            return record

        validation = _validate_agent_patch(challenge, workspace)
        record["validation_seconds"] = validation["validation_seconds"]
        record["passed"] = validation["passed"]
        record["validation_status"] = validation["status"]
        if not record["output_excerpt"]:
            record["output_excerpt"] = validation["output_excerpt"]
        record["status"] = "passed" if validation["passed"] else validation["status"]
        return record


def build_report(
    agents: List[Tuple[str, str]],
    challenges: Optional[List[Path]] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> Dict[str, Any]:
    """Run the agent/challenge matrix concurrently and return a JSON report."""
    if timeout < 1:
        raise ValueError("timeout must be at least 1 second")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    selected_challenges = runner.get_challenges() if challenges is None else challenges
    started = time.monotonic()
    tasks = []
    for challenge in selected_challenges:
        for agent_name, command in agents:
            tasks.append((challenge, agent_name, command))

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(run_one, challenge, name, command, timeout): (challenge.name, name)
            for challenge, name, command in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                challenge_name, agent_name = futures[future]
                results.append({
                    "agent": agent_name,
                    "challenge": challenge_name,
                    "timeout_seconds": timeout,
                    "status": "runner_error",
                    "completion_seconds": None,
                    "validation_seconds": None,
                    "passed": False,
                    "return_code": None,
                    "output_excerpt": str(exc)[-2000:],
                })

    results.sort(key=lambda item: (item["challenge"], item["agent"]))
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
        "concurrency": concurrency,
        "summary": {
            "total_runs": total,
            "passed": passed,
            "not_passed": total - passed,
            "wall_clock_seconds": round(time.monotonic() - started, 3),
        },
        "results": results,
    }


def write_csv(path: Path, report_data: Dict[str, Any]) -> None:
    """Write one row per agent/challenge result."""
    fields = [
        "agent", "challenge", "status", "completion_seconds",
        "validation_seconds", "passed", "timeout_seconds", "return_code",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in report_data["results"]:
            writer.writerow(item)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent", action="append", type=parse_agent, default=[],
        metavar="NAME=COMMAND", help="Agent command template; repeat for each agent",
    )
    parser.add_argument("--challenge", help="Exact challenge number or name substring")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help="Agent time limit per challenge in seconds (default: 120)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help="Maximum simultaneous agent/challenge runs (default: 4)")
    parser.add_argument("--output", type=Path, default=Path("agent-results.json"),
                        help="JSON report path (default: agent-results.json)")
    parser.add_argument("--csv", type=Path, help="Optional CSV report path")
    args = parser.parse_args(argv)

    if not args.agent:
        parser.error("provide at least one --agent NAME=COMMAND")
    if args.timeout < 1 or args.concurrency < 1:
        parser.error("--timeout and --concurrency must be positive integers")

    selected = runner._select_challenges(runner.get_challenges(), args.challenge)
    if not selected:
        print("No matching challenges found.", file=sys.stderr)
        return 2

    report_data = build_report(args.agent, selected, args.timeout, args.concurrency)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report_data, indent=2) + "\n", encoding="utf-8")
    if args.csv:
        write_csv(args.csv, report_data)

    print("Agent benchmark results")
    print("Runs: {total_runs} | Passed: {passed} | Not passed: {not_passed} | Wall time: {wall_clock_seconds}s".format(**report_data["summary"]))
    for item in report_data["results"]:
        elapsed = item["completion_seconds"]
        elapsed_text = "{:.3f}s".format(elapsed) if elapsed is not None else "n/a"
        print("{agent:16} {challenge:38} {elapsed:>9} {status}".format(
            agent=item["agent"], challenge=item["challenge"],
            elapsed=elapsed_text, status=item["status"],
        ))
    print("JSON report: {}".format(args.output))
    if args.csv:
        print("CSV report: {}".format(args.csv))
    return 0 if report_data["summary"]["not_passed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
