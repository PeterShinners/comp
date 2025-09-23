"""
Test cases for project module.

SPECIFICATION SUMMARY:
The comp module must properly import and provide best practices and information
for a modern Python library.

- The 'comp' module imports properly
- It provides a sensible exposed api
    - no underscored internal names
    - docstrings on functions and classes
- The package provides standard metadata
    - name, version, author, license, description

"""


def test_package_import(comp):
    """Ensure the comp fixture works."""
    assert comp is not None


def test_package_version(comp):
    """Test that the package version is accessible."""
    assert hasattr(comp, "__version__")
    assert comp.__version__ == "0.0.1"


def test_package_docstring(comp):
    """Test that the package has a proper docstring."""
    assert comp.__doc__ is not None
    assert "Comp Programming Language" in comp.__doc__


def test_package_cleanness(comp):
    """Test no messy symbols exposed"""
    underscored = [n for n in dir(comp) if n.startswith("_") and not n.endswith("__")]
    for name in underscored:
        assert not name
