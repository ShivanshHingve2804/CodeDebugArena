"""Data processor — FIXED: catches only expected exceptions."""
import json

def parse_config(data: str) -> dict:
    try:
        config = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return {}
    
    # Let KeyError propagate — missing required fields is a real error
    result = {"name": config["name"], "version": config["version"]}
    return result
