"""Module loader for importing .comp files."""

__all__ = ["load_comp_module"]

from pathlib import Path

import comp


# Hardcoded base directory for .comp modules
# This will be configurable later, but for MVP we use a fixed location
# __file__ is src/comp/ast/_loader.py, so parent.parent.parent.parent gives us the repo root
_COMP_MODULES_DIR = Path(__file__).parent.parent.parent.parent / "stdlib"


def load_comp_module(path: str, engine: 'comp.Engine') -> 'comp.Module':
    """Load a .comp module from the filesystem.

    Args:
        path: Relative path to the module (e.g., "utils/math" or "./lib/utils")
        engine: Engine instance to use for evaluating the module

    Returns:
        Evaluated Module object with all definitions populated

    Raises:
        FileNotFoundError: If the module file doesn't exist
        comp.ParseError: If the module has syntax errors
        Exception: For other loading or evaluation errors
    """
    # Resolve the full path
    if path.startswith("./"):
        # Relative to current directory
        full_path = Path.cwd() / path[2:]
    else:
        # Relative to stdlib directory
        full_path = _COMP_MODULES_DIR / path

    # Add .comp extension if not present
    if not full_path.suffix:
        full_path = full_path.with_suffix(".comp")

    # Check if file exists
    if not full_path.exists():
        raise FileNotFoundError(f"Module file not found: {full_path}")

    # Read the module source
    source = full_path.read_text(encoding="utf-8")

    # Parse the module
    module_ast = comp.parse_module(source)

    # Evaluate the module to populate its definitions
    result = engine.run(module_ast)

    # The result should be a Module object
    if not isinstance(result, comp.Module):
        raise TypeError(f"Expected Module from evaluation, got {type(result)}")

    return result

