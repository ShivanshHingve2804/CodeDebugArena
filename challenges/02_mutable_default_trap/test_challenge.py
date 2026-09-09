"""Tests for Challenge 02: Mutable Default Trap."""
import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
UserRegistry = mod.UserRegistry


def test_independent_registries():
    r1 = UserRegistry()
    r2 = UserRegistry()
    r1.add_user("Alice")
    assert r2.count() == 0, "Registries should be independent"

def test_add_and_get():
    r = UserRegistry()
    r.add_user("Bob")
    assert r.get_users() == ["Bob"]

def test_multiple_instances_isolated():
    r1 = UserRegistry()
    r1.add_user("A")
    r1.add_user("B")
    r2 = UserRegistry()
    r2.add_user("C")
    assert r1.get_users() == ["A", "B"]
    assert r2.get_users() == ["C"]

def test_empty_registry():
    r = UserRegistry()
    assert r.count() == 0
    assert r.get_users() == []
