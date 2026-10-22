# CodeDebugArena dashboard

The dashboard supports Codex CLI, GitHub Copilot CLI, and multiple OpenAI-compatible API agents. API agents are configured with a name, model ID, HTTPS base URL, and API key. The endpoint must expose a compatible `/chat/completions` route. Cloud Codex agents use an OpenAI API key; Copilot CLI agents use a GitHub fine-grained token with `Copilot Requests` permission.

## Local run

```powershell
python -m pip install -e ".[dev]"
python web/server.py
```

Open <http://127.0.0.1:8000>. The supported CLI connections are Codex CLI and GitHub Copilot CLI. Other local CLIs are not exposed as built-in or custom-command options.

## Docker or cloud run

Copy `.env.example` to `.env`, generate a strong dashboard access token, and run `docker compose up --build`. The container installs Codex CLI, GitHub Copilot CLI, Python, and pytest. Both CLIs and API agents can run in cloud mode. Provider API keys and Copilot tokens stay in page memory and are cleared when the page reloads. For another Docker host, set `CDA_CLOUD_MODE=1`, `CDA_ACCESS_TOKEN`, `CDA_ALLOWED_HOSTS`, and the platform's `PORT`. The server rejects run requests without the dashboard token and accepts only API endpoints using HTTPS that resolve to public IP addresses.

The image runs as a non-root user and enables a read-only root filesystem, temporary workspace, and resource limits. In cloud mode, Codex uses its `workspace-write` sandbox with the Linux Landlock compatibility backend, so Docker does not need extra capabilities or an unconfined seccomp profile for nested Bubblewrap namespaces. Put the service behind HTTPS at the platform or reverse proxy. See the main [README](../README.md#docker-and-cloud-deployment) for deployment details.

## Evaluation behavior

Each selected agent/challenge pair gets a new temporary workspace containing only `buggy.py` and the challenge README. The trusted tests are added after the agent returns a complete corrected file, then pytest evaluates it. Results contain model names, timings, pass/fail outcomes, diagnostics, and changed lines; they never include the API key. Run history is held in memory until the server stops.

