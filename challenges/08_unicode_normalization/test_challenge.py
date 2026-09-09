import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
strings_match = mod.strings_match
deduplicate = mod.deduplicate

def test_nfc_vs_nfd():
    nfc = "\u00e9"        # é as single char
    nfd = "e\u0301"       # e + combining accent
    assert strings_match(nfc, nfd)

def test_dedup_unicode():
    nfc = "caf\u00e9"
    nfd = "cafe\u0301"
    result = deduplicate([nfc, nfd])
    assert len(result) == 1

def test_ascii_still_works():
    assert strings_match("hello", "hello")
    assert not strings_match("hello", "world")
