import os, importlib, pytest, time
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
fibonacci = mod.fibonacci

def test_base_cases():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1

def test_small_values():
    assert fibonacci(10) == 55

def test_large_value_performance():
    start = time.time()
    result = fibonacci(50)
    elapsed = time.time() - start
    assert result == 12586269025
    assert elapsed < 2.0, f"fibonacci(50) took {elapsed:.1f}s — too slow without memoization"

def test_negative_raises():
    with pytest.raises(ValueError):
        fibonacci(-1)
