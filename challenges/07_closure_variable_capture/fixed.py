"""Callback generators — FIXED: capture loop variable with default argument."""

def make_multipliers(n: int) -> list:
    multipliers = []
    for i in range(n):
        multipliers.append(lambda x, i=i: x * i)  # FIX: default arg captures current i
    return multipliers
