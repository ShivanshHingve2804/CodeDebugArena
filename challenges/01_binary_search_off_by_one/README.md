# Challenge 01: Binary Search Off-by-One

**Category:** Logic Bug  
**Difficulty:** ⭐⭐  
**Root Cause:** The search bounds mix an exclusive upper bound with inclusive-bound updates.

## The Bug

The buggy implementation sets `right = len(arr)` and uses `while left < right`, but then updates the upper bound with `right = mid - 1`. Those operations do not follow one consistent binary-search invariant.

When the only remaining candidate has `left == right`, the loop stops without checking it. For example, the buggy version can return `-1` for target `3` in `[1, 3, 5, 7, 9]`.

## The Fix

Use inclusive bounds consistently:
- Initialize `right = len(arr) - 1`.
- Continue while `left <= right`.
- When the middle element is too large, set `right = mid - 1`.

The tests include elements on both sides of the middle, absent targets, empty and single-element arrays, and a larger sorted array.

## Why AI Agents Struggle

- The implementation looks close to a valid binary search.
- Boundary mistakes often affect only a subset of inputs.
- The incorrect bound convention is mixed with an otherwise familiar algorithm.

## Common Wrong Fixes

- Change only the loop condition or only the initial upper bound.
- Switch to a half-open interval without also updating the bounds consistently.
