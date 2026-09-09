# Challenge 10: File Handle Leak
**Category:** Resource Management | **Difficulty:** ⭐⭐ | **Root Cause:** `f.close()` is never reached when an exception is raised mid-iteration
