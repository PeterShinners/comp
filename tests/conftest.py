import pytest

@pytest.fixture(scope="package")
def comp():
    import comp
    return comp
