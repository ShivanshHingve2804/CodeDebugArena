import os, importlib, pytest
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
parse_config = mod.parse_config

def test_valid_config():
    assert parse_config('{"name": "app", "version": "1.0"}') == {"name": "app", "version": "1.0"}

def test_invalid_json_returns_empty():
    assert parse_config("not json") == {}

def test_missing_required_field_raises():
    with pytest.raises(KeyError):
        parse_config('{"name": "app"}')  # missing 'version'

def test_empty_string():
    assert parse_config("") == {}
