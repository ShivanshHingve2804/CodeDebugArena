import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
merge_sort = mod.merge_sort

def test_basic_sort():
    assert merge_sort([3, 1, 4, 1, 5]) == [1, 1, 3, 4, 5]

def test_preserves_all_elements():
    arr = [5, 3, 8, 1, 9, 2, 7]
    result = merge_sort(arr)
    assert len(result) == len(arr), f"Lost elements: input {len(arr)}, output {len(result)}"
    assert sorted(arr) == result

def test_already_sorted():
    assert merge_sort([1, 2, 3, 4]) == [1, 2, 3, 4]

def test_reverse_sorted():
    assert merge_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

def test_single_and_empty():
    assert merge_sort([]) == []
    assert merge_sort([42]) == [42]

def test_right_heavy():
    # Array where right side has larger elements
    assert merge_sort([1, 2, 10, 20, 30]) == [1, 2, 10, 20, 30]
