# Machine-readable benchmark reports

CodeDebugArena can produce a JSON validation report for dashboards, experiment tracking, or comparing AI coding agents across benchmark runs.

## Generate a report

From the repository root, after installing the development dependencies:

```bash
python -m pip install -e ".[dev]"
python report.py
```

The default writes JSON to standard output, so it can be piped into another tool. For a readable report saved to disk:

```bash
python report.py --output reports/validation.json --pretty
```

The command exits with code `0` only when every discovered challenge is valid; it returns `1` if one or more challenges are invalid. Missing challenge files, test collection/import errors, unexpected timeouts, and fixed-version failures are reported as invalid rather than counted as successful bug detection.

## Report schema

- `schema_version`: report format version for downstream consumers.
- `generated_at`: UTC generation timestamp.
- `summary`: total, valid, invalid, and elapsed time.
- `challenges`: per-challenge validity, buggy/fixed run status, a bounded output excerpt, and actionable issues.

A buggy implementation is considered caught only when pytest reports a real test failure, or when a challenge's documented expected timeout occurs. A fixed implementation must pass. This report is evidence against the current test suite, not a guarantee of universal correctness.
