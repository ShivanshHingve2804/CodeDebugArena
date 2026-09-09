"""Cache system — FIXED: returns a copy of cached values."""
import copy

_cache = {}

def get_user_settings(user_id: str) -> dict:
    if user_id not in _cache:
        _cache[user_id] = {"theme": "light", "lang": "en", "notifications": True}
    return copy.deepcopy(_cache[user_id])  # FIX: return a copy

def clear_cache():
    _cache.clear()
