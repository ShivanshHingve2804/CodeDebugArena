# Challenge 01: Binary Search Off-by-One

**Category:** Logic Bug  
**Difficulty:** ⭐⭐  
**Root Cause:** Incorrect boundary initialization and loop condition  

## The Bug

The buggy version has two related errors:
1. `right = len(arr)` instead of `right = len(arr) - 1` — starts with an out-of-bounds index
2. `while left < right` instead of `while left <= right` — misses checking when `left == right`

Together, these cause the search to fail on the **last element** of the array and potentially access out-of-bounds indices.

## Why AI Agents Struggle

- The code *looks* correct at first glance
- It passes for most inputs — only fails on boundary cases
- The two bugs partially compensate for each other, masking the issue
- Off-by-one errors require careful reasoning about loop invariants

## Common Wrong Fixes
- Only fixing one of the two bugs (creates a different failure mode)
- Changing to `right = len(arr)` with `left < right` (a valid alternative, but then `right = mid` not `right = mid - 1`)
