"""Fibonacci — BUGGY: no memoization, exponential time."""

def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)  # BUG: exponential time, unusable for n > 35
