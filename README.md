# 🐛 CodeDebugArena

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/github/license/ShivanshHingve2804/CodeDebugArena)](LICENSE)
[![Challenges](https://img.shields.io/badge/challenges-12-orange.svg)]()
[![CI](https://github.com/ShivanshHingve2804/CodeDebugArena/actions/workflows/ci.yml/badge.svg)](https://github.com/ShivanshHingve2804/CodeDebugArena/actions)

**A curated benchmark of real-world Python bugs designed to evaluate and challenge AI coding agents.**

CodeDebugArena provides a structured set of debugging challenges — each containing a buggy program, a failing test suite, a verified fix, and a detailed writeup explaining *why* the bug is hard to find. These are the kinds of problems that frontier AI models still struggle with.

> Built for the AI data & evaluation community — inspired by the need for realistic, auditable debugging benchmarks that go beyond simple syntax errors.

---

## 🎯 Why This Exists

Most coding benchmarks test code *generation*. Very few test **debugging** — the ability to:
- Read existing code and understand intent
- Identify the root cause (not just the symptom)
- Produce a minimal, correct fix
- Avoid introducing new bugs

CodeDebugArena fills this gap with challenges sourced from real bug patterns that appear in production Python code.

---

## 📁 Challenge Structure

Each challenge lives in its own directory under `challenges/`:

```
challenges/
├── 01_binary_search_off_by_one/
│   ├── buggy.py           # The buggy implementation
│   ├── fixed.py           # The correct implementation
│   ├── test_challenge.py  # Test suite (passes on fixed, fails on buggy)
│   └── README.md          # Bug analysis & explanation
├── 02_mutable_default_trap/
│   └── ...
└── ...
```

---

## 🧩 Challenge Catalog

| # | Challenge | Category | Difficulty | Bug Type |
|---|-----------|----------|------------|----------|
| 01 | Binary Search Off-by-One | Logic | ⭐⭐ | Boundary condition error in search bounds |
| 02 | Mutable Default Trap | Language Pitfall | ⭐⭐ | Shared mutable default argument |
| 03 | Dict Mutation During Iteration | Data Structure | ⭐⭐ | RuntimeError from modifying dict while iterating |
| 04 | Floating Point Comparison | Numeric | ⭐⭐⭐ | IEEE 754 precision loss in equality check |
| 05 | Silent Exception Swallowing | Error Handling | ⭐⭐⭐ | Bare except hiding real failures |
| 06 | Thread-Unsafe Counter | Concurrency | ⭐⭐⭐ | Race condition in shared counter |
| 07 | Closure Variable Capture | Language Pitfall | ⭐⭐ | Late binding closure captures loop variable |
| 08 | Unicode Normalization Bug | String/Encoding | ⭐⭐⭐ | Visually identical strings fail equality |
| 09 | Recursive Fibonacci Overflow | Algorithm | ⭐⭐ | Missing memoization causes exponential blowup |
| 10 | File Handle Leak | Resource Mgmt | ⭐⭐ | File not closed on exception path |
| 11 | Incorrect Merge Sort | Algorithm | ⭐⭐⭐ | Off-by-one in merge step loses elements |
| 12 | Cache Poisoning | State Mgmt | ⭐⭐⭐ | Mutable cache values shared across callers |

---

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/ShivanshHingve2804/CodeDebugArena.git
cd CodeDebugArena

# Install (no external dependencies needed for challenges)
pip install -e ".[dev]"

# Run all challenge tests against the BUGGY versions (should fail)
python runner.py test --target buggy

# Run all challenge tests against the FIXED versions (should pass)
python runner.py test --target fixed

# Run a specific challenge
python runner.py test --challenge 01 --target buggy

# List all challenges
python runner.py list

# Validate that all fixes are correct
python runner.py validate
```

---

## 🏗️ How to Use for AI Agent Evaluation

### For Researchers & Evaluators

1. Present the agent with `buggy.py` and `test_challenge.py`
2. Ask: *"Fix the bug so all tests pass"*
3. Compare the agent's fix against `fixed.py`
4. Score based on:
   - ✅ Does the fix make all tests pass?
   - ✅ Is the fix minimal (not a rewrite)?
   - ✅ Does the fix handle edge cases?
   - ✅ Does the agent explain the root cause?

### For Dataset Builders

Each challenge includes structured metadata in its README:
- **Bug Category** — for stratified sampling
- **Difficulty** — for progressive evaluation
- **Root Cause** — ground truth for explanation evaluation
- **Common Wrong Fixes** — to detect superficial patches

---

## 🧪 Running Tests

```bash
# Test all challenges (fixed versions should pass)
pytest challenges/ -v --tb=short

# Test with coverage
pytest challenges/ --cov=challenges --cov-report=term-missing

# Test a single challenge
pytest challenges/01_binary_search_off_by_one/test_challenge.py -v
```

---

## 📊 Challenge Difficulty Distribution

```
⭐⭐    Easy    — 5 challenges (common patterns, single-line fixes)
⭐⭐⭐  Medium  — 7 challenges (subtle bugs, multi-line reasoning required)
```

---

## 🤝 Contributing

Want to add a challenge? Follow this template:

1. Create a new directory: `challenges/XX_descriptive_name/`
2. Add `buggy.py` — the buggy implementation
3. Add `fixed.py` — the correct implementation
4. Add `test_challenge.py` — tests that pass on fixed, fail on buggy
5. Add `README.md` — analysis using the template in `CONTRIBUTING.md`
6. Run `python runner.py validate` to verify

---

## 📄 License

MIT License — Shivansh Hingve

---

## 👤 Author

**Shivansh Hingve** — [GitHub](https://github.com/ShivanshHingve2804)

Built to advance the quality of AI coding agent benchmarks. If you find this useful for your research, consider giving it a ⭐!
