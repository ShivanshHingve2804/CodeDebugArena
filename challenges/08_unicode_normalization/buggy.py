"""Unicode string matcher — BUGGY: doesn't normalize unicode."""
def strings_match(a: str, b: str) -> bool:
    return a == b  # BUG: 'é' (U+00E9) != 'e' + '́' (U+0065 + U+0301)

def deduplicate(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        if item not in seen:  # BUG: unnormalized strings appear different
            seen.add(item)
            result.append(item)
    return result
