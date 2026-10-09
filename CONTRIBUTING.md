# Contributing to CodeDebugArena

Thank you for helping improve the benchmark. A good challenge should test a specific debugging skill and reliably distinguish the buggy implementation from the corrected one.

## Challenge checklist

Each new challenge must include:

- `buggy.py`: a small implementation that contains the intended defect.
- `fixed.py`: a corrected implementation with the same public interface.
- `test_challenge.py`: tests that expose the intended bug, cover relevant edge cases, and pass on the fixed version.
- `README.md`: category, difficulty, root cause, explanation, and common incorrect fixes.

Name challenge folders with a two-digit numeric prefix, for example `13_safe_division`.

## Test requirements

1. Run the tests against the fixed version and confirm they pass.
2. Run the tests against the buggy version and confirm at least one test fails for the intended reason.
3. Avoid tests that rely on timing or scheduling unless the expected behavior is deterministic and has an explicit bounded timeout.
4. Keep tests isolated: clean up temporary files, close resources, and reset shared state.
5. Do not count import failures, test-collection errors, or missing files as successful bug detection.
6. If a challenge is intentionally slow, document it and add a bounded timeout policy in `runner.py`.

## Validate locally

```bash
python -m pip install -e ".[dev]"
python runner.py test --target fixed
python -m pytest tests/ -v --tb=short
python runner.py validate
```

All four commands should succeed before opening a pull request.

## Challenge README template

```markdown
# Challenge XX: Name

**Category:** ...
**Difficulty:** ...
**Root Cause:** ...

## The Bug

Describe the incorrect behavior and a minimal example that exposes it.

## The Fix

Explain the corrected invariant or design.

## Why AI Agents Struggle

Explain what makes the issue subtle.

## Common Wrong Fixes

- Describe a plausible but incomplete correction.
```

Keep fixes focused. The goal is to evaluate debugging reasoning, not reward unrelated rewrites.
