import os, importlib
mod = importlib.import_module(os.environ.get("CHALLENGE_TARGET", "fixed"))
make_multipliers = mod.make_multipliers

def test_multipliers_distinct():
    fns = make_multipliers(5)
    assert fns[0](10) == 0
    assert fns[1](10) == 10
    assert fns[2](10) == 20
    assert fns[3](10) == 30
    assert fns[4](10) == 40

def test_multiplier_zero():
    fns = make_multipliers(3)
    assert fns[0](100) == 0

def test_single():
    fns = make_multipliers(1)
    assert fns[0](5) == 0
