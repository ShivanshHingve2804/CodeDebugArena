"""Thread-safe counter — BUGGY: race condition."""
import threading

class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        # BUG: read-modify-write is not atomic
        current = self.value
        self.value = current + 1

    def get(self) -> int:
        return self.value
