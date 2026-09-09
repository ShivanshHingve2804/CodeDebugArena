# Challenge 07: Closure Variable Capture
**Category:** Language Pitfall | **Difficulty:** ⭐⭐ | **Root Cause:** Python closures capture variables by reference, not by value — all lambdas see the final value of `i`
