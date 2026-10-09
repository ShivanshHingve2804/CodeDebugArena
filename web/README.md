# Local agent evaluation dashboard

The dashboard starts a loopback-only Python web server and evaluates local command-line agents with the actual CodeDebugArena challenge tests.

## Start

From the repository root, install pytest and run the server:

```powershell
python -m pip install -e ".[dev]"
python web/server.py
```

Open <http://127.0.0.1:8000>. Stop the server with Ctrl+C.

## Configure an agent

Add an agent name and command that accepts a task prompt as an argument. The command must include `{prompt}`. Examples:

```text
codex exec --full-auto "{prompt}"
claude -p "{prompt}"
ollama run qwen2.5-coder "{prompt}"
```

The command is split into arguments and run without a shell. Authenticate the CLI before starting an evaluation. Keep API keys in the CLI's normal environment or credential store; do not paste keys into the command field.

## What an evaluation does

For each selected agent and challenge, the server creates a fresh temporary directory containing `buggy.py` and the challenge README. The agent is asked to edit only `buggy.py`; the trusted `test_challenge.py` is copied into the directory only after the agent exits. Pytest then evaluates the fix with `CHALLENGE_TARGET=buggy`. The dashboard reports actual pass/fail outcomes, agent time, test time, and changed lines. Temporary challenge workspaces are removed after each evaluation. Run history stays in memory until the server stops.

Agents run on the host with the same permissions as the user running the server. Use only trusted CLIs. The agent timeout is three minutes per challenge; test execution is limited to twenty seconds. The server binds to `127.0.0.1` by default.

