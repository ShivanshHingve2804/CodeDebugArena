"""Binary search implementation — BUGGY VERSION.

Bug: Off-by-one error in the search bounds causes the function
to miss elements at certain positions.
"""


def binary_search(arr: list, target: int) -> int:
    """Return the index of target in sorted array, or -1 if not found."""
    left = 0
    right = len(arr)  # BUG: should be len(arr) - 1

    while left < right:  # BUG: should be left <= right
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
