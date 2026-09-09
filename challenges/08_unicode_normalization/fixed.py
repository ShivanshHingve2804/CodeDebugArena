"""Unicode string matcher — FIXED: normalizes to NFC form."""
import unicodedata

def strings_match(a: str, b: str) -> bool:
    return unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b)

def deduplicate(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        normalized = unicodedata.normalize("NFC", item)
        if normalized not in seen:
            seen.add(normalized)
            result.append(item)
    return result
