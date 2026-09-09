import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
get_user_settings = mod.get_user_settings
clear_cache = mod.clear_cache

def test_mutation_doesnt_poison_cache():
    clear_cache()
    settings = get_user_settings("user1")
    settings["theme"] = "dark"  # mutate returned dict
    fresh = get_user_settings("user1")
    assert fresh["theme"] == "light", "Cache was poisoned by caller mutation"

def test_independent_calls():
    clear_cache()
    s1 = get_user_settings("user1")
    s2 = get_user_settings("user1")
    s1["lang"] = "fr"
    assert s2["lang"] == "en"

def test_basic_fetch():
    clear_cache()
    s = get_user_settings("user1")
    assert s["theme"] == "light"
    assert s["notifications"] is True
