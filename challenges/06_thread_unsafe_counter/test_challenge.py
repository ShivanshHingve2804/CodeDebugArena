import os, importlib, threading
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
Counter = mod.Counter

def test_concurrent_increments():
    counter = Counter()
    threads = []
    for _ in range(100):
        t = threading.Thread(target=lambda: [counter.increment() for _ in range(100)])
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert counter.get() == 10000, f"Expected 10000 but got {counter.get()}"

def test_single_thread():
    c = Counter()
    for _ in range(50):
        c.increment()
    assert c.get() == 50
