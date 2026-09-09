"""Thread-safe counter — FIXED: uses a lock."""
import threading

class Counter:
    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self.value += 1

    def get(self) -> int:
        return self.value
