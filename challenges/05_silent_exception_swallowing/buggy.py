"""Data processor — BUGGY: bare except swallows real errors."""
import json

def parse_config(data: str) -> dict:
    try:
        config = json.loads(data)
        result = {"name": config["name"], "version": config["version"]}
        return result
    except:  # BUG: bare except swallows KeyError, TypeError, etc.
        return {}
