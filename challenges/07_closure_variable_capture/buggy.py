"""Callback generators — BUGGY: closure captures loop variable by reference."""

def make_multipliers(n: int) -> list:
    multipliers = []
    for i in range(n):
        multipliers.append(lambda x: x * i)  # BUG: all closures share 'i'
    return multipliers
