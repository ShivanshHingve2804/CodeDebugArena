# Challenge 12: Cache Poisoning
**Category:** State Management | **Difficulty:** ⭐⭐⭐ | **Root Cause:** Returning a reference to the cached dict lets callers mutate it, corrupting the cache for all future reads
