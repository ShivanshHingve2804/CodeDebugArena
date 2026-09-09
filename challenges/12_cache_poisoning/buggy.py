"""Cache system — BUGGY: returns mutable cached values that callers can modify."""

_cache = {}

def get_user_settings(user_id: str) -> dict:
    if user_id not in _cache:
        # Simulate DB fetch
        _cache[user_id] = {"theme": "light", "lang": "en", "notifications": True}
    return _cache[user_id]  # BUG: returns reference to cached dict

def clear_cache():
    _cache.clear()
