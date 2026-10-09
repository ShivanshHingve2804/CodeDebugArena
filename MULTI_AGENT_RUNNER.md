# Multi-agent benchmark runner

The multi-agent runner measures **each agent's time to finish each challenge independently**. It records solution-generation time as `completion_seconds`, then separately records test-validation time as `validation_seconds`. It also reports whether the produced patch passes the challenge tests.

## Configure agents

Agent command-line tools differ in their flags and prompt handling. Register each installed/authenticated CLI with a command template:

```bash
python multi_agent_runner.py \
  --agent 'codex=codex exec --full-auto "$(cat {prompt_file})"' \
  --agent 'claude=claude -p "$(cat {prompt_file})"' \
  --timeout 120 \
  --concurrency 2 \
  --output reports/agent-results.json \
  --csv reports/agent-results.csv
```

Check the installed CLI's own help output and adapt its command template as needed. These are examples, not universal command syntax. Each command runs from an isolated temporary workspace containing only `buggy.py`, the challenge README, and a task prompt. The known fix and challenge tests are withheld until the agent has finished. The runner then copies the candidate into a validation workspace and executes the challenge tests.

## Timer and timeout semantics

- `completion_seconds`: elapsed wall-clock time from process launch until the agent CLI exits successfully or fails. A timeout is recorded at approximately the configured limit.
- `validation_seconds`: separate time spent running the challenge tests after the agent exits.
- `timeout_seconds`: defaults to **120 seconds per agent per challenge**.
- `wall_clock_seconds`: total elapsed time for the complete selected agent/challenge matrix.
- `status`: `passed`, `failed_tests`, `timed_out`, `agent_error`, `runner_error`, or another explicit validation state.

A solution only counts as passed if the agent command exits successfully, leaves a `buggy.py` candidate, and the challenge tests pass against that candidate. Agent output time and validation time are kept separate so benchmark timing is comparable.

## Parallelism and isolation

Each agent/challenge pair gets its own temporary workspace. The `--concurrency` option limits how many pairs run simultaneously; the default is 4. The runner does not assume that different agents share a command interface. It uses configurable command templates, and the agent's CLI must already be installed and authenticated.

`subprocess` timeout limits the local CLI process. Some CLIs may launch child processes that outlive their parent; for stronger process cleanup and security, run agents in dedicated containers with resource limits before using untrusted agents.

## Output

JSON includes one result for each agent/challenge pair. Optional CSV is convenient for spreadsheet analysis and charts. Use the `agent`, `challenge`, `completion_seconds`, `validation_seconds`, and `status` columns to compare speed and correctness.
