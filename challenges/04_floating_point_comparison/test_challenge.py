import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
is_price_equal = mod.is_price_equal
total_matches_expected = mod.total_matches_expected

def test_obvious_equal():
    assert is_price_equal(1.0, 1.0)

def test_float_arithmetic():
    assert is_price_equal(0.1 + 0.2, 0.3)

def test_sum_of_prices():
    prices = [0.1] * 10
    assert total_matches_expected(prices, 1.0)

def test_not_equal():
    assert not is_price_equal(1.0, 2.0)
