"""Tests for Challenge 10: File Handle Leak."""

import builtins
import importlib
import os
import tempfile

import pytest

mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
read_and_process = mod.read_and_process


def _make_file(contents: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(contents)
    return path


def test_normal_read():
    path = _make_file("hello\nworld\n")
    try:
        assert read_and_process(path) == ["HELLO", "WORLD"]
    finally:
        os.unlink(path)


def test_file_closed_on_error(monkeypatch):
    path = _make_file("hello\n\nworld\n")
    real_open = builtins.open
    opened_handles = []

    def tracking_open(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        opened_handles.append(handle)
        return handle

    monkeypatch.setattr(builtins, "open", tracking_open)
    try:
        with pytest.raises(ValueError):
            read_and_process(path)

        assert len(opened_handles) == 1, "Expected one file handle to be opened"
        assert opened_handles[0].closed, "File handle remained open after exception"
    finally:
        # Explicitly close any leaked handle so the test cleanup works on
        # Windows as well as POSIX systems.
        for handle in opened_handles:
            if not handle.closed:
                handle.close()
        os.unlink(path)
