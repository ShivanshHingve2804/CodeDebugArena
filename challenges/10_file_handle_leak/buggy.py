"""File processor — BUGGY: file handle leak on exception."""

def read_and_process(filepath: str) -> list:
    f = open(filepath, "r")  # BUG: not using context manager
    lines = []
    for line in f:
        processed = line.strip().upper()
        if not processed:
            raise ValueError("Empty line found")  # BUG: file never closed
        lines.append(processed)
    f.close()
    return lines
