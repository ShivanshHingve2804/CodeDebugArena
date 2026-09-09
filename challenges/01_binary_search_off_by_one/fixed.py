"""Binary search implementation — FIXED VERSION."""


def binary_search(arr: list, target: int) -> int:
    """Return the index of target in sorted array, or -1 if not found."""
    left = 0
    right = len(arr) - 1

    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
