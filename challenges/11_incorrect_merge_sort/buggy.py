"""Merge sort — BUGGY: off-by-one in merge loses elements."""

def merge_sort(arr: list) -> list:
    if len(arr) <= 1:
        return arr[:]
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return _merge(left, right)

def _merge(left: list, right: list) -> list:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    # BUG: only appends remaining from left, forgets right
    while i < len(left):
        result.append(left[i])
        i += 1
    # Missing: while j < len(right) ...
    return result
