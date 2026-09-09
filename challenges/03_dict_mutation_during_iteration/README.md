# Challenge 03: Dict Mutation During Iteration
**Category:** Data Structure | **Difficulty:** ⭐⭐ | **Root Cause:** Modifying a dict while iterating raises RuntimeError
## The Bug
`del inventory[item]` inside `for item, qty in inventory.items()` modifies the dict size during iteration.
## Why AI Agents Struggle
- The error is a RuntimeError, not a logic error — requires understanding Python's iterator invalidation rules.
