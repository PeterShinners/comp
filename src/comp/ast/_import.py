"""AST nodes for import statements."""

__all__ = ["ImportDef"]

import comp

from ._tag import ModuleOp


class ImportDef(ModuleOp):
    """Import statement: !import /namespace = source "path"

    Imports a module and registers it in the current module's namespace.

    Examples:
        !import /math = std "core/math"
        !import /utils = comp "./lib/utils"
        !import /numpy = python "numpy"

    Args:
        namespace: Namespace identifier (without leading /)
        source: Source type ("std", "comp", "python", etc.)
        path: Path string for the module location
    """

    def __init__(self, namespace: str, source: str, path: str):
        if not isinstance(namespace, str):
            raise TypeError(f"ImportDef namespace must be str, got {type(namespace)}")
        if not isinstance(source, str):
            raise TypeError(f"ImportDef source must be str, got {type(source)}")
        if not isinstance(path, str):
            raise TypeError(f"ImportDef path must be str, got {type(path)}")

        self.namespace = namespace
        self.source = source
        self.path = path
        super().__init__()

    def evaluate(self, frame):
        """Load and register the imported module.

        Supported sources:
        - 'comp': Load from filesystem (.comp files)
        - 'stdlib': Load from Python-implemented standard library modules
        """
        # Get the module we're importing into
        module = frame.scope('module')
        if module is None:
            return comp.fail("ImportDef requires module scope", ast=self)

        # Handle different import sources
        if self.source == "stdlib":
            # Load from Python-implemented corelib
            from comp.corelib import get_stdlib_module
            try:
                imported_module = get_stdlib_module(self.path)
                if imported_module is None:
                    return comp.fail(f"Standard library module '{self.path}' not found", ast=self)

                # Register the module in our namespace
                module.add_namespace(self.namespace, imported_module)

                return comp.Value(True)

            except Exception as e:
                return comp.fail(f"Error loading stdlib module: {e}", ast=self)

        elif self.source == "comp":
            # Load the module from filesystem
            from ._loader import load_comp_module
            try:
                imported_module = load_comp_module(self.path, frame.engine)
                if imported_module is None:
                    return comp.fail(f"Failed to load module from '{self.path}'", ast=self)

                # Register the module in our namespace
                module.add_namespace(self.namespace, imported_module)

                return comp.Value(True)

            except FileNotFoundError as e:
                return comp.fail(f"Module not found: {e}")
            except Exception as e:
                return comp.fail(f"Error loading module: {e}")

        else:
            return comp.fail(f"Import source '{self.source}' not supported (use 'comp' or 'stdlib')")

        # Make this a generator (needed for engine protocol)
        yield

    def unparse(self) -> str:
        """Convert back to source code."""
        # Reconstruct the string literal with quotes
        path_str = f'"{self.path}"'
        return f"!import /{self.namespace} = {self.source} {path_str}"

    def __repr__(self):
        return f"ImportDef(/{self.namespace} = {self.source} \"{self.path}\")"

