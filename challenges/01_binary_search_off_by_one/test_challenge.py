"""Tests for Challenge 01: Binary Search Off-by-One."""

import importlib
import os

target = os.environ.get("CHALLENGE_TARGET", "fixed")
mod = importlib.import_module(target)
binary_search = mod.binary_search


def test_find_first_element():
    assert binary_search([1, 3, 5, 7, 9], 1) == 0


def test_find_last_element():
    assert binary_search([1, 3, 5, 7, 9], 9) == 4


def test_find_middle_element():
    assert binary_search([1, 3, 5, 7, 9], 5) == 2


def test_find_second_element():
    # This was a missing regression case: the buggy loop stops before
    # checking the final candidate when left == right.
    assert binary_search([1, 3, 5, 7, 9], 3) == 1


def test_find_element_before_last():
    assert binary_search([1, 3, 5, 7, 9], 7) == 3


def test_not_found():
    assert binary_search([1, 3, 5, 7, 9], 4) == -1


def test_empty_array():
    assert binary_search([], 5) == -1


def test_single_element_found():
    assert binary_search([42], 42) == 0


def test_single_element_not_found():
    assert binary_search([42], 7) == -1


def test_two_elements():
    assert binary_search([1, 2], 2) == 1


def test_large_array():
    arr = list(range(0, 1000, 2))
    assert binary_search(arr, 500) == 250
    assert binary_search(arr, 998) == 499
