"""Price checker — BUGGY: floating point comparison."""

def is_price_equal(a: float, b: float) -> bool:
    return a == b  # BUG: direct float comparison

def total_matches_expected(prices: list, expected_total: float) -> bool:
    return sum(prices) == expected_total  # BUG: float sum accumulates error
