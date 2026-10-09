"""Local web UI and agent evaluation server for CodeDebugArena.

The server binds to loopback only. Agent commands are configured by the user
and launched without a shell in a temporary copy of each challenge.
"""

from __future__ import annotations

import copy
import difflib
import importlib.util
import json
import os
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


WEB_ROOT = Path(__file__).resolve().parent
CHALLENGES_ROOT = WEB_ROOT.parent / "challenges"
AGENT_TIMEOUT_SECONDS = 180
TEST_TIMEOUT_SECONDS = 20
MAX_REQUEST_BYTES = 1_000_000
MAX_RUNS = 50

_runs: dict[str, dict] = {}
_runs_lock = threading.RLock()
_run_cancel_events: dict[str, threading.Event] = {}
_active_processes: dict[str, subprocess.Popen] = {}
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="arena-run")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _challenge_dirs() -> list[Path]:
    return sorted(
        (p for p in CHALLENGES_ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit()),
        key=lambda p: p.name,
    )


def _resolve_executable(command: str) -> str | None:
    """Resolve an agent CLI, including the Windows Codex desktop install."""
    resolved = shutil.which(command)
    if resolved:
        return resolved

    if os.name != "nt" or command.casefold() not in {"codex", "codex.exe"}:
        return None

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    install_root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    candidates = list(install_root.glob("*/codex.exe"))
    candidates = [candidate for candidate in candidates if candidate.is_file()]
    if not candidates:
        return None
    return str(max(candidates, key=lambda candidate: candidate.stat().st_mtime))


def _run_process(run_id: str, argv: list[str], *, timeout: int, **kwargs):
    """Run a child process that the stop endpoint can terminate."""
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    with _runs_lock:
        cancel_event = _run_cancel_events.get(run_id)
        if cancel_event and cancel_event.is_set():
            return None, "", ""

    process = subprocess.Popen(argv, **kwargs)
    with _runs_lock:
        _active_processes[run_id] = process
        cancel_event = _run_cancel_events.get(run_id)
        should_stop = bool(cancel_event and cancel_event.is_set())
    if should_stop:
        _terminate_process(process)

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process, stdout, stderr
    except subprocess.TimeoutExpired:
        _terminate_process(process)
        process.communicate()
        raise
    finally:
        with _runs_lock:
            if _active_processes.get(run_id) is process:
                _active_processes.pop(run_id, None)


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        else:
            process.send_signal(signal.SIGTERM)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def _stop_requested(run_id: str) -> bool:
    with _runs_lock:
        event = _run_cancel_events.get(run_id)
        return bool(event and event.is_set())


def _finish_stopped_run(run_id: str) -> None:
    run = _snapshot(run_id)
    if not run:
        return
    for index, agent in enumerate(run["agents"]):
        if agent["status"] in {"queued", "running"}:
            _set_agent(run_id, index, status="stopped")
    _set_run(run_id, status="stopped", current=None, finished_at=_utc_now())
    with _runs_lock:
        _run_cancel_events.pop(run_id, None)


def _request_stop(run_id: str) -> tuple[int, dict]:
    with _runs_lock:
        run = _runs.get(run_id)
        if not run:
            return 404, {"error": "Run not found."}
        if run["status"] in {"complete", "stopped"}:
            return 200, {"status": run["status"]}
        event = _run_cancel_events.get(run_id)
        if event:
            event.set()
        run["status"] = "stopping"
        process = _active_processes.get(run_id)
    if process:
        _terminate_process(process)
    return 202, {"status": "stopping"}


def _snapshot(run_id: str, *, public: bool = False) -> dict | None:
    with _runs_lock:
        run = _runs.get(run_id)
        result = copy.deepcopy(run) if run else None
    if result and public:
        for agent in result["agents"]:
            # Commands can accidentally contain credentials; never echo them
            # back through the status endpoint.
            agent.pop("command", None)
    return result


def _set_run(run_id: str, **updates) -> None:
    with _runs_lock:
        if run_id in _runs:
            _runs[run_id].update(updates)


def _set_agent(run_id: str, agent_index: int, **updates) -> None:
    with _runs_lock:
        run = _runs.get(run_id)
        if run:
            run["agents"][agent_index].update(updates)


def _append_result(run_id: str, agent_index: int, result: dict) -> None:
    with _runs_lock:
        run = _runs.get(run_id)
        if run:
            run["agents"][agent_index]["challenges"].append(result)
            run["completed_pairs"] += 1


def _line_changes(before: str, after: str) -> int:
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="")
    return sum(
        1
        for line in diff
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    )


def _run_one(run_id: str, agent: dict, challenge: Path) -> dict:
    before = (challenge / "buggy.py").read_text(encoding="utf-8")
    prompt_context = (challenge / "README.md").read_text(encoding="utf-8")
    prompt = (
        "You are fixing one CodeDebugArena Python challenge. Read README.md and "
        "buggy.py in the current working directory. Diagnose the defect, then make "
        "and save the code change directly in buggy.py so the evaluator can test it. "
        "Do not only explain the fix, print suggested code, or return a patch in your "
        "response: the buggy.py file itself must contain your fix before you exit. "
        "Preserve the documented behavior. Modify only buggy.py; do not create or "
        "modify tests or any other files. The evaluator will run the trusted "
        "benchmark tests after you finish.\n\nChallenge: "
        + challenge.name
        + "\n\nChallenge README:\n"
        + prompt_context
    )

    with tempfile.TemporaryDirectory(prefix="code-debug-arena-") as temp:
        work_dir = Path(temp)
        (work_dir / "buggy.py").write_text(before, encoding="utf-8")
        (work_dir / "README.md").write_text(prompt_context, encoding="utf-8")
        try:
            argv = shlex.split(agent["command"], posix=True)
        except ValueError as exc:
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "agent_error",
                "error": "Could not parse the agent command: " + str(exc),
                "agent_time_s": 0,
                "test_time_s": 0,
                "lines_changed": 0,
            }
        if not argv:
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "agent_error",
                "error": "Agent command is empty.",
                "agent_time_s": 0,
                "test_time_s": 0,
                "lines_changed": 0,
            }
        if "{prompt}" not in agent["command"]:
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "agent_error",
                "error": 'Agent command must include the "{prompt}" placeholder.',
                "agent_time_s": 0,
                "test_time_s": 0,
                "lines_changed": 0,
            }

        argv = [
            token.replace("{prompt}", prompt)
            .replace("{challenge}", challenge.name)
            .replace("{challenge_dir}", str(work_dir))
            for token in argv
        ]
        started = time.monotonic()
        try:
            agent_proc, agent_stdout, agent_stderr = _run_process(
                run_id,
                argv,
                timeout=AGENT_TIMEOUT_SECONDS,
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        except FileNotFoundError:
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "agent_error",
                "error": "Agent CLI was not found. Check that it is installed and on PATH.",
                "agent_time_s": round(time.monotonic() - started, 2),
                "test_time_s": 0,
                "lines_changed": 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "agent_error",
                "error": f"Agent timed out after {AGENT_TIMEOUT_SECONDS} seconds.",
                "agent_time_s": round(time.monotonic() - started, 2),
                "test_time_s": 0,
                "lines_changed": 0,
            }
        if agent_proc is None or _stop_requested(run_id):
            return {
                "challenge_id": challenge.name,
                "challenge": challenge.name[3:].replace("_", " ").title(),
                "status": "stopped",
                "error": "Evaluation stopped by user.",
                "agent_time_s": round(time.monotonic() - started, 2),
                "test_time_s": 0,
                "lines_changed": 0,
            }
        agent_time = round(time.monotonic() - started, 2)
        after = (work_dir / "buggy.py").read_text(encoding="utf-8")
        lines_changed = _line_changes(before, after)

        # Copy the trusted test file only after the agent exits, so it cannot
        # change the evaluator's assertions or inspect tests during its run.
        (work_dir / "test_challenge.py").write_bytes(
            (challenge / "test_challenge.py").read_bytes()
        )
        env = os.environ.copy()
        env["CHALLENGE_TARGET"] = "buggy"
        test_started = time.monotonic()
        try:
            test_proc, test_stdout, test_stderr = _run_process(
                run_id,
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "test_challenge.py",
                    "-q",
                    "--tb=short",
                    "--import-mode=importlib",
                ],
                timeout=TEST_TIMEOUT_SECONDS,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            if test_proc is None or _stop_requested(run_id):
                return {
                    "challenge_id": challenge.name,
                    "challenge": challenge.name[3:].replace("_", " ").title(),
                    "status": "stopped",
                    "error": "Evaluation stopped by user.",
                    "agent_time_s": agent_time,
                    "test_time_s": round(time.monotonic() - test_started, 2),
                    "lines_changed": lines_changed,
                }
            test_time = round(time.monotonic() - test_started, 2)
            output = (test_stdout + "\n" + test_stderr).strip()
            passed = test_proc.returncode == 0
            error = "" if passed else (output[-2400:] or "Tests failed without output.")
            if not passed and "No module named pytest" in output:
                error = 'pytest is not installed. Install project dependencies with: python -m pip install -e ".[dev]"'
            if agent_proc.returncode != 0 and passed:
                error = f"Agent exited with status {agent_proc.returncode}, but tests passed."
        except FileNotFoundError:
            test_time = round(time.monotonic() - test_started, 2)
            passed = False
            error = 'pytest is not installed. Install project dependencies with: python -m pip install -e ".[dev]"'
        except subprocess.TimeoutExpired:
            test_time = round(time.monotonic() - test_started, 2)
            passed = False
            error = f"Tests timed out after {TEST_TIMEOUT_SECONDS} seconds."

        return {
            "challenge_id": challenge.name,
            "challenge": challenge.name[3:].replace("_", " ").title(),
            "status": "passed" if passed else "failed",
            "error": error,
            "agent_time_s": agent_time,
            "test_time_s": test_time,
            "lines_changed": lines_changed,
        }


def _execute_run(run_id: str, challenges: list[Path]) -> None:
    if _stop_requested(run_id):
        _finish_stopped_run(run_id)
        return
    _set_run(run_id, status="running", started_at=_utc_now())
    run = _snapshot(run_id)
    if not run:
        return
    for agent_index, agent in enumerate(run["agents"]):
        if _stop_requested(run_id):
            _finish_stopped_run(run_id)
            return
        _set_agent(run_id, agent_index, status="running")
        for challenge in challenges:
            if _stop_requested(run_id):
                _finish_stopped_run(run_id)
                return
            with _runs_lock:
                if run_id not in _runs:
                    return
                _runs[run_id]["current"] = {
                    "agent": agent["name"],
                    "challenge": challenge.name,
                    "started_at": _utc_now(),
                }
            try:
                result = _run_one(run_id, agent, challenge)
            except Exception as exc:  # Keep a single bad workspace from wedging a run.
                result = {
                    "challenge_id": challenge.name,
                    "challenge": challenge.name[3:].replace("_", " ").title(),
                    "status": "agent_error",
                    "error": "Runner error: " + str(exc),
                    "agent_time_s": 0,
                    "test_time_s": 0,
                    "lines_changed": 0,
                }
            _append_result(run_id, agent_index, result)
            if result["status"] == "stopped" or _stop_requested(run_id):
                _finish_stopped_run(run_id)
                return
        current = _snapshot(run_id)
        if current:
            results = current["agents"][agent_index]["challenges"]
            passed = sum(item["status"] == "passed" for item in results)
            total_time = round(sum(item["agent_time_s"] for item in results), 2)
            _set_agent(
                run_id,
                agent_index,
                status="complete",
                passed=passed,
                failed=len(results) - passed,
                total_time_s=total_time,
                average_time_s=round(total_time / len(results), 2) if results else 0,
                success_rate=round(100 * passed / len(results), 1) if results else 0,
                lines_changed=sum(item["lines_changed"] for item in results),
            )
    with _runs_lock:
        cancel_event = _run_cancel_events.get(run_id)
        if cancel_event and cancel_event.is_set():
            should_finish_stopped = True
        else:
            should_finish_stopped = False
            if run_id in _runs:
                _runs[run_id].update(
                    status="complete", current=None, finished_at=_utc_now()
                )
        _run_cancel_events.pop(run_id, None)
    if should_finish_stopped:
        _finish_stopped_run(run_id)


class Handler(SimpleHTTPRequestHandler):
    server_version = "CodeDebugArenaLocal/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format, *args):
        # Avoid echoing prompts or agent output into the terminal log.
        super().log_message(format, *args)

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/challenges":
            self._json(
                200,
                {
                    "challenges": [
                        {
                            "id": p.name,
                            "name": p.name[3:].replace("_", " ").title(),
                        }
                        for p in _challenge_dirs()
                    ]
                },
            )
            return
        if path.startswith("/api/runs/"):
            run = _snapshot(path.rsplit("/", 1)[-1], public=True)
            self._json(200, run) if run else self._json(404, {"error": "Run not found."})
            return
        if path in {"/", "/index.html"}:
            self.path = "/index.html"
        if path.endswith(".py") or path.startswith("/api/"):
            self._json(404, {"error": "Not found."})
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        is_stop_request = (
            len(parts) == 4
            and parts[0:2] == ["api", "runs"]
            and parts[3] == "stop"
        )
        if path != "/api/runs" and not is_stop_request:
            self._json(404, {"error": "Not found."})
            return
        host = self.headers.get("Host", "").lower()
        hostname = urlparse("http://" + host).hostname
        origin = self.headers.get("Origin")
        if hostname not in {"localhost", "127.0.0.1"}:
            self._json(403, {"error": "Requests must use the local dashboard host."})
            return
        if origin:
            parsed_origin = urlparse(origin)
            if (
                parsed_origin.scheme != "http"
                or parsed_origin.hostname not in {"localhost", "127.0.0.1"}
                or parsed_origin.netloc.lower() != host
            ):
                self._json(403, {"error": "Cross-origin run requests are not allowed."})
                return
        if is_stop_request:
            status, response = _request_stop(parts[2])
            self._json(status, response)
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"error": "Send run requests as application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid request length."})
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._json(413, {"error": "Request is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "Request body must be valid JSON."})
            return

        agents = payload.get("agents") if isinstance(payload, dict) else None
        challenge_ids = payload.get("challenges") if isinstance(payload, dict) else None
        if not isinstance(agents, list) or not 1 <= len(agents) <= 8:
            self._json(400, {"error": "Select between 1 and 8 agents."})
            return
        if not isinstance(challenge_ids, list) or not 1 <= len(challenge_ids) <= 12:
            self._json(400, {"error": "Select between 1 and 12 challenges."})
            return

        available = {p.name: p for p in _challenge_dirs()}
        if len(set(challenge_ids)) != len(challenge_ids) or any(
            not isinstance(item, str) or item not in available for item in challenge_ids
        ):
            self._json(400, {"error": "One or more challenge selections are invalid."})
            return
        normalized_agents = []
        for item in agents:
            if not isinstance(item, dict):
                self._json(400, {"error": "Agent entries must include a name and command."})
                return
            name = str(item.get("name", "")).strip()[:80]
            model_name = str(item.get("model_name", "")).strip()[:120]
            command = str(item.get("command", "")).strip()[:2000]
            if not name or not model_name or not command or "{prompt}" not in command:
                self._json(
                    400,
                    {"error": 'Each agent needs a name, model name and command containing "{prompt}".'},
                )
                return
            try:
                argv = shlex.split(command, posix=True)
            except ValueError as exc:
                self._json(400, {"error": f"{name}: command could not be parsed ({exc})."})
                return
            executable = _resolve_executable(argv[0]) if argv else None
            if not executable:
                self._json(400, {"error": f"{name}: agent executable was not found on PATH."})
                return
            argv[0] = executable
            command = shlex.join(argv)
            normalized_agents.append({"name": name, "model_name": model_name, "command": command})

        if importlib.util.find_spec("pytest") is None:
            self._json(
                424,
                {
                    "error": 'pytest is required before agent runs can start. Install it with: python -m pip install -e ".[dev]"'
                },
            )
            return

        run_id = uuid.uuid4().hex[:12]
        pairs = len(normalized_agents) * len(challenge_ids)
        run = {
            "id": run_id,
            "status": "queued",
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "current": None,
            "challenge_ids": challenge_ids,
            "total_pairs": pairs,
            "completed_pairs": 0,
            "agents": [
                {
                    "name": item["name"],
                    "model_name": item["model_name"],
                    "command": item["command"],
                    "status": "queued",
                    "passed": 0,
                    "failed": 0,
                    "success_rate": 0,
                    "total_time_s": 0,
                    "average_time_s": 0,
                    "lines_changed": 0,
                    "challenges": [],
                }
                for item in normalized_agents
            ],
        }
        with _runs_lock:
            _runs[run_id] = run
            _run_cancel_events[run_id] = threading.Event()
            while len(_runs) > MAX_RUNS:
                oldest = next(iter(_runs))
                if oldest == run_id:
                    break
                _runs.pop(oldest, None)
        _executor.submit(_execute_run, run_id, [available[key] for key in challenge_ids])
        self._json(202, {"id": run_id})

    def do_HEAD(self):
        path = unquote(urlparse(self.path).path)
        if path.endswith(".py"):
            self.send_error(404)
            return
        return super().do_HEAD()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the local CodeDebugArena web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (loopback by default).")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port.")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("the local agent runner can only bind to 127.0.0.1 or localhost")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CodeDebugArena dashboard: http://{args.host}:{args.port}/")
    print("Agent CLI commands run locally in isolated temporary challenge copies.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CodeDebugArena dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
