import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
remove_out_of_stock = mod.remove_out_of_stock

def test_removes_zero_stock():
    inv = {"apple": 5, "banana": 0, "cherry": 3}
    result = remove_out_of_stock(inv)
    assert "banana" not in result
    assert "apple" in result

def test_multiple_zeros():
    inv = {"a": 0, "b": 0, "c": 10, "d": 0, "e": 5}
    result = remove_out_of_stock(inv)
    assert result == {"c": 10, "e": 5}

def test_no_zeros():
    inv = {"x": 1, "y": 2}
    result = remove_out_of_stock(inv)
    assert result == {"x": 1, "y": 2}

def test_all_zeros():
    inv = {"a": 0, "b": 0}
    result = remove_out_of_stock(inv)
    assert result == {}

def test_empty_dict():
    assert remove_out_of_stock({}) == {}
