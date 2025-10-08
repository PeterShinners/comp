import pytest
import comp


@pytest.fixture(scope="session")
def module():
    """Dummy module for evaluation."""
    mod = comp.run.Module("test")
    mod.process_builtins()
    return mod

@pytest.fixture(scope="session")
def scopes():
    """Scopes for evaluation."""
    return {
        "in": comp.run.Value({}),
        "out": comp.run.Value({}),
        "ctx": comp.run.Value({}),
        "mod": comp.run.Value({}),
        "arg": comp.run.Value({}),
    }

