"""Tests for Challenge 06: Thread-Unsafe Counter."""

import importlib
import os
import threading

mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
Counter = mod.Counter


def test_concurrent_increments_are_not_lost():
    counter = Counter()
    worker_count = 2
    increments_per_worker = 100
    barrier = threading.Barrier(worker_count, timeout=3)

    # Instrument reads of the counter so unsynchronized implementations are
    # forced to perform each pair of reads before either write can proceed.
    # Implementations that serialize increments with a lock do not wait at the
    # barrier and are evaluated normally.
    counter._value = counter.__dict__.pop("value", 0)

    def get_value(instance):
        value = instance._value
        if not hasattr(instance, "_lock"):
            barrier.wait()
        return value

    def set_value(instance, value):
        instance._value = value

    type(counter).value = property(get_value, set_value)
    try:
        threads = [
            threading.Thread(
                target=lambda: [
                    counter.increment() for _ in range(increments_per_worker)
                ]
            )
            for _ in range(worker_count)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert all(not thread.is_alive() for thread in threads), "Worker thread hung"
        assert counter.get() == worker_count * increments_per_worker
    finally:
        # The challenge runs in its own pytest subprocess, but restore the
        # class descriptor to avoid leaking state to other tests in that run.
        delattr(type(counter), "value")


def test_single_thread():
    counter = Counter()
    for _ in range(50):
        counter.increment()
    assert counter.get() == 50
