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


def test_package_import():
    """Ensure the comp fixture works."""
    import comp


def test_package_version():
    """Test that the package version is accessible."""
    import comp
    assert hasattr(comp, "__version__")
    assert comp.__version__ == "0.0.1"


def test_package_docstring():
    """Test that the package has a proper docstring."""
    import comp
    assert comp.__doc__ is not None
    assert "Comp Programming Language" in comp.__doc__

