"""File processor — FIXED: uses context manager."""

def read_and_process(filepath: str) -> list:
    lines = []
    with open(filepath, "r") as f:
        for line in f:
            processed = line.strip().upper()
            if not processed:
                raise ValueError("Empty line found")
            lines.append(processed)
    return lines
