# Challenge 02: Mutable Default Trap
**Category:** Language Pitfall | **Difficulty:** ⭐⭐ | **Root Cause:** Shared mutable default argument

## The Bug
`def __init__(self, users=[])` — the default list is created once at function definition time and shared across ALL instances.

## Why AI Agents Struggle
- Requires understanding Python's default argument evaluation semantics
- The bug only manifests when multiple instances are created — single-instance tests pass fine
