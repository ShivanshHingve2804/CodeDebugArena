import os, importlib, tempfile, pytest
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
read_and_process = mod.read_and_process

def test_normal_read():
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("hello\nworld\n")
    try:
        assert read_and_process(path) == ["HELLO", "WORLD"]
    finally:
        os.unlink(path)

def test_file_closed_on_error():
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("hello\n\nworld\n")  # empty line triggers error
    try:
        with pytest.raises(ValueError):
            read_and_process(path)
        # Verify file handle is released by opening it again
        with open(path, "r") as f:
            f.read()
    finally:
        os.unlink(path)
