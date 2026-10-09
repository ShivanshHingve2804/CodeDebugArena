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

## Dashboard UI

A static dashboard prototype is available in [`web/`](web/). From the repository root, serve it locally with:

```bash
python -m http.server 8000 --directory web
```

Then open `http://localhost:8000`. The dashboard uses sample benchmark results and is not connected to model-provider APIs or `runner.py`; use the CLI commands below for actual challenge validation.

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
