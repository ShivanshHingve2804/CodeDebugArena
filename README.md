# CodeDebugArena

[![CI](https://github.com/ShivanshHingve2804/CodeDebugArena/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivanshHingve2804/CodeDebugArena/actions/workflows/ci.yml)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Challenges](https://img.shields.io/badge/challenges-12-orange.svg)
![License: MIT](https://img.shields.io/github/license/ShivanshHingve2804/CodeDebugArena)

**CodeDebugArena is a reproducible benchmark of Python debugging challenges for evaluating AI coding agents.** Each challenge provides an intentionally buggy implementation, a corrected implementation, tests, and a root-cause explanation.

The goal is to test whether an agent can understand existing code, locate the underlying defect, make a minimal correction, and preserve expected behavior.

## Why this project exists

Code-generation benchmarks often focus on writing code from scratch. Debugging a real codebase additionally requires understanding context, following control flow, finding edge cases, and avoiding regressions. CodeDebugArena packages representative bug patterns into small, repeatable test tasks.

## Challenge catalogue

| # | Challenge | Area | Main concept |
|---|---|---|---|
| 01 | Binary Search Off-by-One | Algorithms | Boundary conditions and loop invariants |
| 02 | Mutable Default Trap | Python semantics | Shared mutable defaults |
| 03 | Dict Mutation During Iteration | Data structures | Iterator invalidation |
| 04 | Floating Point Comparison | Numeric | IEEE 754 precision and tolerant comparison |
| 05 | Silent Exception Swallowing | Error handling | Catch expected exceptions without hiding defects |
| 06 | Thread-Unsafe Counter | Concurrency | Lost updates and synchronization |
| 07 | Closure Variable Capture | Python semantics | Late binding in closures |
| 08 | Unicode Normalization | Text processing | NFC/NFD equivalence |
| 09 | Recursive Fibonacci Blowup | Algorithms | Exponential complexity and memoization |
| 10 | File Handle Leak | Resource management | Context managers and exception paths |
| 11 | Incorrect Merge Sort | Algorithms | Merging both remaining subarrays |
| 12 | Cache Poisoning | State management | Mutable references and defensive copying |

Every challenge follows this structure:

```text
challenges/XX_challenge_name/
├── buggy.py
├── fixed.py
├── test_challenge.py
└── README.md
```

## Agent evaluation dashboard

The dashboard in [`web/`](web/) evaluates Codex CLI and GitHub Copilot CLI in a local or cloud container, and supports multiple OpenAI-compatible API agents against the real benchmark tests. Install the development dependencies, then start the loopback-only server from the repository root:

```bash
python -m pip install -e ".[dev]"
python web/server.py
```

Open `http://127.0.0.1:8000`, add Codex, GitHub Copilot, or one or more OpenAI-compatible API agents, choose challenges, and start an evaluation. Copilot CLI needs a model ID and a fine-grained GitHub token with `Copilot Requests` permission. API agents need a display name, model ID, HTTPS API base URL, and API key. Each agent receives a temporary challenge copy without the tests. The trusted tests are added after the agent finishes, then pytest evaluates the edited `buggy.py`.

Local Codex CLI runs with the permissions of the user running the dashboard. Cloud Codex runs use the model ID and per-agent OpenAI API key entered for the run. Local dashboard mode binds to `127.0.0.1` by default and stores run results in memory. The existing CLI remains available for benchmark validation:

```bash
python runner.py list
python runner.py validate
```

### Docker and cloud deployment

The container installs Codex CLI, GitHub Copilot CLI, Python, and pytest, then runs as a non-root user with a read-only root filesystem, bounded temporary storage, and CPU, memory, and process limits. Cloud mode supports both CLIs and OpenAI-compatible API agents. Enter a provider key or token for each agent when starting a run; credentials are not saved to browser storage or included in run reports. A separate dashboard access token protects run and challenge API routes.

For local Docker testing, copy `.env.example` to `.env`, replace `CDA_ACCESS_TOKEN` with a long random secret, then run:

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000`. The browser will ask for the dashboard access token. Keep `.env` private; it is ignored by Git and excluded from the Docker build context.

For a cloud platform that deploys from a Dockerfile, configure these environment variables in its secret/configuration panel:

| Variable | Requirement |
|---|---|
| `CDA_CLOUD_MODE` | Set to `1` to require an API key per agent and enforce cloud endpoint checks. The Docker image enables this by default. |
| `CDA_ACCESS_TOKEN` | Required. Use a long random secret; users enter it in the dashboard. |
| `CDA_ALLOWED_HOSTS` | Comma-separated public hostnames accepted by the dashboard, without a scheme. |
| `PORT` | Optional; the server uses the platform-provided port or `8000`. |

Terminate public TLS at the hosting platform or reverse proxy and allow the dashboard hostname in `CDA_ALLOWED_HOSTS`. Keep the service behind private access or your platform's access control when possible. API-agent endpoints must use HTTPS and resolve to public IP addresses. Codex CLI uses the OpenAI API with its selected model ID and provided API key. Copilot CLI uses the GitHub account associated with the supplied Copilot token, and requires Copilot CLI access to be enabled for that account or organization.

## Quick start

Requires Python 3.9 or newer.

```bash
git clone https://github.com/ShivanshHingve2804/CodeDebugArena.git
cd CodeDebugArena

# Install the project metadata and development/test dependencies
python -m pip install -e ".[dev]"

# List challenges
python runner.py list

# Test the corrected implementations
python runner.py test --target fixed

# Check that the intentionally buggy versions are caught by tests
python runner.py test --target buggy

# Validate every challenge: buggy fails for a test reason, fixed passes
python runner.py validate
```

The runner applies per-challenge timeouts so a slow buggy implementation cannot hang the entire benchmark. Challenge 09's un-memoized Fibonacci implementation is expected to time out when tested as buggy; that timeout is bounded and explicitly accounted for during validation.

### Run a single challenge

Numeric selection is exact: `--challenge 1` selects Challenge 01, not 10, 11, or 12.

```bash
python runner.py test --challenge 1 --target fixed
python runner.py test --challenge 01 --target buggy
python runner.py test --challenge binary_search --target fixed
python runner.py test --challenge merge_sort --target fixed
```

You can also pass a case-insensitive name substring. If no challenge matches, or required files are missing, the runner returns a nonzero exit code.

## What validation means

`python runner.py validate` checks both implementations for each challenge:

- **Buggy version:** at least one test must fail as a test failure, rather than because pytest cannot import or collect the challenge. Challenge 09 has one documented, bounded performance timeout.
- **Fixed version:** the test suite must finish successfully before the timeout.
- **Challenge structure:** required files must exist; incomplete challenges are invalid.
- **Process safety:** a hanging test process is terminated by a timeout and reported rather than blocking the full run.

For a successful validation run, all 12 challenges must meet those criteria.

## Running tests directly

Challenge tests import `buggy.py` or `fixed.py` from their own directory, so use the runner to execute all challenges with the correct working directory and bounded timeouts.

```bash
# Run all challenge suites against fixed.py
python runner.py test --target fixed

# Run the runner's own regression tests
python -m pytest tests/ -v --tb=short

# Run one challenge
python runner.py test --challenge 1 --target fixed

# Validate that buggy versions fail and fixed versions pass
python runner.py validate
```

For a full benchmark run, prefer `python runner.py test --target buggy` or `python runner.py validate`, since those commands enforce timeouts.

## How to use it for AI-agent evaluation

1. Provide an agent with a challenge's `buggy.py`, `test_challenge.py`, and relevant README context.
2. Ask it to identify the root cause and produce a minimal fix.
3. Run the tests against its implementation.
4. Compare the behavior and patch against `fixed.py`.
5. Record whether the agent passed the tests, explained the cause correctly, handled edge cases, and avoided unrelated changes.

For a more rigorous evaluation, keep the tests hidden from the agent and add held-out edge cases. Passing the included tests is evidence of correctness against this challenge suite, not proof that an implementation is universally correct.

## Continuous integration

GitHub Actions validates the challenge set and runs the runner's regression tests on Ubuntu, Windows, and macOS with Python 3.9, 3.10, 3.11, and 3.12. This catches operating-system differences, packaging issues, and benchmark tests that fail to expose their intended defects.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the checklist and template for adding a challenge. New challenges must demonstrate both sides of the benchmark contract: the buggy version should fail for the intended reason, and the fixed version should pass.

## License

MIT. See [LICENSE](LICENSE).

## Author

**Shivansh Hingve** — [GitHub](https://github.com/ShivanshHingve2804)

