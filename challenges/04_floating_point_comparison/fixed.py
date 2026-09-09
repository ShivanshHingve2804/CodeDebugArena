"""Price checker — FIXED: uses epsilon-based comparison."""
import math

def is_price_equal(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)

def total_matches_expected(prices: list, expected_total: float) -> bool:
    return math.isclose(sum(prices), expected_total, rel_tol=1e-9, abs_tol=1e-9)
