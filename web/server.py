"""Web UI and agent evaluation server for CodeDebugArena."""

from __future__ import annotations

import copy
import difflib
import ast
import importlib.util
import hmac
import ipaddress
import json
import os
import re
import signal
import shutil
import socket
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
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from types import SimpleNamespace


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


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="arena-run")


def _agent_environment() -> dict[str, str]:
    """Build a minimal child environment for agents in cloud/container mode."""
    allowed = {
        "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE",
        "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not let a configured API endpoint redirect server-side requests."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _cloud_mode() -> bool:
    configured = os.environ.get("CDA_CLOUD_MODE", os.environ.get("CDA_API_ONLY", "0"))
    return configured.strip().lower() in {"1", "true", "yes"}


def _access_token() -> str:
    return os.environ.get("CDA_ACCESS_TOKEN", "").strip()


def _allowed_hosts() -> set[str]:
    configured = os.environ.get("CDA_ALLOWED_HOSTS", "localhost,127.0.0.1")
    return {host.strip().lower() for host in configured.split(",") if host.strip()}


def _is_public_https_endpoint(endpoint: str) -> bool:
    """Reject non-HTTPS and hostnames that resolve to private or local networks."""
    try:
        parsed = urlparse(endpoint)
        port = parsed.port or 443
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)}
    except OSError:
        return False
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


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
    input_data = kwargs.pop("input_data", None)
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
        stdout, stderr = process.communicate(input=input_data, timeout=timeout)
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
        for agent in _runs.get(run_id, {}).get("agents", []):
            agent.pop("api_key", None)
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
            # Never echo credentials or provider endpoints through the status API.
            agent.pop("api_key", None)
            agent.pop("endpoint", None)
            agent.pop("executable", None)
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


def _openai_compatible_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    # Some compatible providers expose /chat/completions directly below the API root.
    if endpoint.endswith("/v1") or endpoint.endswith("/openai"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def _run_openai_compatible(agent: dict, prompt: str, readme: str, source: str) -> str:
    """Ask a chat-completions-compatible model for the complete replacement file."""
    user_prompt = (
        prompt
        + "\n\nReturn the complete corrected contents of buggy.py in one python code block. "
        + "Do not return a diff or explanation.\n\nREADME.md:\n````text\n"
        + readme
        + "\n````\n\nCurrent buggy.py:\n````python\n"
        + source
        + "\n````"
    )
    payload = json.dumps(
        {
            "model": agent["model_name"],
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a code-editing agent. Return the complete requested file, not a patch.",
                },
                {"role": "user", "content": user_prompt},
            ],
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if agent.get("api_key"):
        headers["Authorization"] = "Bearer " + agent["api_key"]
    request = Request(_openai_compatible_url(agent["endpoint"]), data=payload, headers=headers)
    if _cloud_mode():
        response_context = build_opener(_NoRedirectHandler()).open(request, timeout=AGENT_TIMEOUT_SECONDS)
    else:
        response_context = urlopen(request, timeout=AGENT_TIMEOUT_SECONDS)
    with response_context as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The API returned an empty assistant response.")
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", content, flags=re.IGNORECASE | re.DOTALL)
    source_out = match.group(1).strip("\n") if match else content.strip()
    ast.parse(source_out)
    return source_out + "\n"


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
        temp_root = Path(temp)
        work_dir = temp_root / "workspace"
        work_dir.mkdir()
        (work_dir / "buggy.py").write_text(before, encoding="utf-8")
        (work_dir / "README.md").write_text(prompt_context, encoding="utf-8")
        started = time.monotonic()
        if agent.get("connection_type") == "openai_compatible":
            try:
                response_text = _run_openai_compatible(agent, prompt, prompt_context, before)
                (work_dir / "buggy.py").write_text(response_text, encoding="utf-8")
                agent_proc = SimpleNamespace(returncode=0)
                agent_stdout = "OpenAI-compatible model response was written to buggy.py."
                agent_stderr = ""
            except Exception as exc:
                return {
                    "challenge_id": challenge.name,
                    "challenge": challenge.name[3:].replace("_", " ").title(),
                    "status": "agent_error",
                    "error": "Custom API agent failed: " + str(exc),
                    "agent_time_s": round(time.monotonic() - started, 2),
                    "test_time_s": 0,
                    "lines_changed": 0,
                }
        elif agent.get("connection_type") == "codex_cli":
            argv = [agent["executable"]]
            if _cloud_mode():
                # Keep Docker capabilities dropped and avoid nested Bubblewrap
                # namespaces by selecting Codex's Landlock filesystem sandbox.
                argv.extend(["-c", "features.use_legacy_landlock=true"])
            argv.extend([
                "exec", "--skip-git-repo-check", "--sandbox", "workspace-write",
                "--ask-for-approval", "never", "--model", agent["model_name"], "-",
            ])
            agent_env = _agent_environment() if _cloud_mode() else os.environ.copy()
            if agent.get("api_key"):
                agent_env["OPENAI_API_KEY"] = agent["api_key"]
            if _cloud_mode() or agent.get("api_key"):
                # Keep cloud Codex state in this challenge's temporary directory;
                # local CLI sessions without an API key inherit the user's login.
                codex_home = temp_root / "codex-home"
                codex_home.mkdir()
                agent_env["HOME"] = str(codex_home)
                agent_env["CODEX_HOME"] = str(codex_home)
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
                    env=agent_env,
                    stdin=subprocess.PIPE,
                    input_data=prompt,
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
        else:
            copilot_home = temp_root / "copilot-home"
            copilot_home.mkdir()
            agent_env = _agent_environment() if _cloud_mode() else os.environ.copy()
            agent_env["COPILOT_GITHUB_TOKEN"] = agent["api_key"]
            agent_env["COPILOT_AUTO_UPDATE"] = "false"
            agent_env["HOME"] = str(copilot_home)
            agent_env["COPILOT_HOME"] = str(copilot_home)
            argv = [
                agent["executable"],
                "--model=" + agent["model_name"],
                "--no-ask-user",
                "--allow-tool=write(buggy.py)",
                "--deny-tool=shell",
                "--deny-tool=url",
                "-s",
                "-p",
                prompt,
            ]
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
                    env=agent_env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
            except FileNotFoundError:
                return {
                    "challenge_id": challenge.name,
                    "challenge": challenge.name[3:].replace("_", " ").title(),
                    "status": "agent_error",
                    "error": "GitHub Copilot CLI was not found. Check that it is installed in the runner image.",
                    "agent_time_s": round(time.monotonic() - started, 2),
                    "test_time_s": 0,
                    "lines_changed": 0,
                }
            except subprocess.TimeoutExpired:
                return {
                    "challenge_id": challenge.name,
                    "challenge": challenge.name[3:].replace("_", " ").title(),
                    "status": "agent_error",
                    "error": f"GitHub Copilot CLI timed out after {AGENT_TIMEOUT_SECONDS} seconds.",
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
            if not passed and "No module named pytest" in output:
                output = 'pytest is not installed. Install project dependencies with: python -m pip install -e ".[dev]"'
        except FileNotFoundError:
            test_time = round(time.monotonic() - test_started, 2)
            passed = False
            output = 'pytest is not installed. Install project dependencies with: python -m pip install -e ".[dev]"'
        except subprocess.TimeoutExpired:
            test_time = round(time.monotonic() - test_started, 2)
            passed = False
            output = f"Tests timed out after {TEST_TIMEOUT_SECONDS} seconds."

        diagnostics = []
        if agent_proc.returncode != 0:
            diagnostics.append(f"Agent exited with code {agent_proc.returncode}.")
        if lines_changed == 0:
            diagnostics.append("Agent left buggy.py unchanged (0 lines changed).")
        agent_output = (agent_stdout + "\n" + agent_stderr).strip()
        if agent_output:
            diagnostics.append("Agent stdout/stderr:\n" + agent_output[-3000:])
        if not passed:
            diagnostics.append("Pytest/evaluator output:\n" + (output[-2400:] or "Tests failed without output."))
        error = "\n\n".join(diagnostics)

        return {
            "challenge_id": challenge.name,
            "challenge": challenge.name[3:].replace("_", " ").title(),
            "status": "agent_error" if agent_proc.returncode != 0 else ("passed" if passed else "failed"),
            "error": error,
            "agent_exit_code": agent_proc.returncode,
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
            _set_agent(run_id, agent_index, api_key="")
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
    server_version = "CodeDebugArena/1.0"

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

    def _authorized(self) -> bool:
        expected = _access_token()
        if not expected:
            return True
        supplied = self.headers.get("Authorization", "")
        if supplied.startswith("Bearer ") and hmac.compare_digest(supplied[7:], expected):
            return True
        self._json(401, {"error": "Dashboard access token is missing or invalid."})
        return False

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path == "/api/config":
            self._json(200, {"auth_required": bool(_access_token()), "cloud_mode": _cloud_mode()})
            return
        if path.startswith("/api/") and not self._authorized():
            return
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
        if not self._authorized():
            return
        host = self.headers.get("Host", "").lower()
        hostname = urlparse("http://" + host).hostname
        origin = self.headers.get("Origin")
        allowed_hosts = _allowed_hosts()
        if hostname not in allowed_hosts:
            self._json(403, {"error": "Request host is not in CDA_ALLOWED_HOSTS."})
            return
        if origin:
            parsed_origin = urlparse(origin)
            if (
                parsed_origin.scheme not in {"http", "https"}
                or parsed_origin.hostname not in allowed_hosts
                or parsed_origin.netloc.lower() != host
            ):
                self._json(403, {"error": "Cross-origin run requests are not allowed; use the configured dashboard host."})
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
                self._json(400, {"error": "Agent entries must be configuration objects."})
                return
            name = str(item.get("name", "")).strip()[:80]
            model_name = str(item.get("model_name", "")).strip()[:120]
            connection_type = str(item.get("connection_type", "codex_cli"))
            endpoint = str(item.get("endpoint", "")).strip()[:1000]
            api_key = str(item.get("api_key", "")).strip()[:4000]
            if not name or not model_name:
                self._json(
                    400,
                    {"error": "Each agent needs a name and model name."},
                )
                return
            if connection_type not in {"codex_cli", "copilot_cli", "openai_compatible"}:
                self._json(400, {"error": f"{name}: unsupported connection type."})
                return
            if connection_type == "copilot_cli" and not api_key:
                self._json(400, {"error": f"{name}: a GitHub Copilot token is required."})
                return
            if _cloud_mode() and not api_key:
                self._json(400, {"error": f"{name}: a provider key or token is required in cloud mode."})
                return
            if connection_type in {"codex_cli", "copilot_cli"}:
                cli_name = "codex" if connection_type == "codex_cli" else "copilot"
                executable = _resolve_executable(cli_name)
                if not executable:
                    self._json(400, {"error": f"{name}: {cli_name} CLI was not found in this deployment."})
                    return
                normalized_agents.append({
                    "name": name,
                    "model_name": model_name,
                    "connection_type": connection_type,
                    "executable": executable,
                    "api_key": api_key,
                })
                continue
            elif connection_type == "openai_compatible":
                parsed_endpoint = urlparse(endpoint)
                local_http = parsed_endpoint.scheme == "http" and parsed_endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
                endpoint_ok = _is_public_https_endpoint(endpoint) if _cloud_mode() else bool(parsed_endpoint.hostname and not parsed_endpoint.username and not parsed_endpoint.password and (parsed_endpoint.scheme == "https" or local_http))
                if not endpoint_ok:
                    self._json(400, {"error": f"{name}: use an HTTPS API URL, or HTTP on localhost for a local service."})
                    return
                normalized_agents.append({
                    "name": name,
                    "model_name": model_name,
                    "connection_type": connection_type,
                    "endpoint": endpoint,
                    "api_key": api_key,
                })
                continue

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
                    "connection_type": item["connection_type"],
                    "executable": item.get("executable", ""),
                    "endpoint": item.get("endpoint", ""),
                    "api_key": item.get("api_key", ""),
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

    parser = argparse.ArgumentParser(description="Run the CodeDebugArena dashboard.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="Bind address (use 0.0.0.0 in a container).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")), help="HTTP port.")
    args = parser.parse_args()
    if _cloud_mode() and not _access_token():
        parser.error("CDA_ACCESS_TOKEN must be set when CDA_CLOUD_MODE=1.")
    if not (0 < args.port < 65536):
        parser.error("port must be between 1 and 65535")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CodeDebugArena dashboard: http://{args.host}:{args.port}/")
    print("Agents run against isolated temporary challenge copies.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CodeDebugArena dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

