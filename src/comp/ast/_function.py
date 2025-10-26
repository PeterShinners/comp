"""AST nodes for function definitions and references."""

__all__ = ["FuncDef", "FuncRef", "MainDef", "EntryDef"]

import comp

from . import _base
from ._tag import ModuleOp


class FuncDef(ModuleOp):
    """Function definition: !func |path.to.name ~input ^args = {...}

    Defines a function with input shape, optional arguments, and a body.
    Functions use hierarchical paths like tags and shapes.
    Functions are stored in the module and can have multiple overloaded implementations.

    Examples:
        !func |double ~{~num} = {$in * 2}
        !func |math.add ~{~num} ^{n ~num} = {$in + ^n}
        !func |process ~user-data ^config = {...}

    Args:
        path: Full path as list, e.g., ["math", "geometry", "area"]
        body: Structure definition AST node (the function body)
        input_shape: Optional shape for input structure
        arg_shape: Optional shape for arguments
        is_pure: True if function has no side effects
        doc: Optional documentation string
        impl_doc: Optional implementation-specific documentation
    """

    def __init__(self, path: list[str], body: _base.AstNode,
                 input_shape: _base.ShapeNode | None = None,
                 arg_shape: _base.ShapeNode | None = None,
                 is_pure: bool = False,
                 doc: str | None = None,
                 impl_doc: str | None = None,
                 is_private: bool = False):
        if not isinstance(path, list):
            raise TypeError("Function path must be a list")
        if not path:
            raise ValueError("Function path cannot be empty")
        if not all(isinstance(p, str) for p in path):
            raise TypeError("Function path must be list of strings")
        if not isinstance(body, _base.AstNode):
            raise TypeError("Function body must be AstNode")
        if input_shape is not None and not isinstance(input_shape, _base.ShapeNode):
            raise TypeError("Input shape must be ShapeNode or None")
        if arg_shape is not None and not isinstance(arg_shape, _base.ShapeNode):
            raise TypeError("Arg shape must be ShapeNode or None")

        self.path = path
        self.body = body
        self.input_shape = input_shape
        self.arg_shape = arg_shape
        self.is_pure = is_pure
        self.doc = doc
        self.impl_doc = impl_doc
        self.is_private = is_private

    def evaluate(self, frame):
        """Register this function in the module.

        1. Get module from module scope
        2. Consume any pending documentation from !doc statements
        3. Resolve input and arg shapes if present
        4. Register function (body is stored as AST, not evaluated)
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("FuncDef requires module scope")

        # Consume pending documentation from !doc statements
        # This overrides any documentation passed to __init__
        doc = self.doc
        impl_doc = self.impl_doc
        if module.pending_doc is not None:
            doc = module.pending_doc
            module.pending_doc = None  # Clear after consuming
        if module.pending_impl_doc is not None:
            impl_doc = module.pending_impl_doc
            module.pending_impl_doc = None  # Clear after consuming

        # Resolve input shape if present
        input_shape = None
        if self.input_shape is not None:
            input_shape = yield comp.Compute(self.input_shape)
            if frame.bypass_value(input_shape):
                return input_shape

        # Resolve arg shape if present
        arg_shape = None
        if self.arg_shape is not None:
            arg_shape = yield comp.Compute(self.arg_shape)
            if frame.bypass_value(arg_shape):
                return arg_shape

        # Register function (body is NOT evaluated - it's stored as AST)
        module.define_function(
            path=self.path,
            body=self.body,  # Store AST node
            input_shape=input_shape,
            arg_shape=arg_shape,
            is_pure=self.is_pure,
            doc=doc,
            impl_doc=impl_doc,
            is_private=self.is_private
        )

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = []

        if self.is_pure:
            parts.append("!pure")

        path_str = ".".join(self.path)
        parts.append(f"!func |{path_str}")

        if self.input_shape:
            parts.append(self.input_shape.unparse())

        if self.arg_shape:
            parts.append("arg")
            parts.append(self.arg_shape.unparse())

        parts.append("=")
        parts.append(self.body.unparse())

        return " ".join(parts)

    def __repr__(self):
        pure_str = "!pure " if self.is_pure else ""
        path_str = ".".join(self.path)
        return f"{pure_str}FuncDef(|{path_str})"


class FuncRef(_base.ValueNode):
    """Function reference: |path.to.function or |path.to.function/namespace

    References a defined function for use in pipelines or introspection.
    References use reversed paths (leaf first) like tags and shapes.
    Returns the function definition (or all overloads).

    Examples:
        |double          # Reference to function (single element path)
        |area.geometry   # Reference with reversed path (leaf first)
        |double/math     # Reference from math namespace
        [data |double]   # Invoke in pipeline
        [|describe |double]  # Introspection

    Args:
        path: Reversed partial path (leaf first), e.g., ["area", "geometry"]
        namespace: Optional namespace for cross-module references

    Attributes:
        _resolved: Pre-resolved list of FunctionDefinitions (set by Module.prepare())
    """

    def __init__(self, path: list[str], namespace: str | None = None):
        if not isinstance(path, list):
            raise TypeError("Function path must be a list")
        if not path:
            raise ValueError("Function path cannot be empty")
        if not all(isinstance(p, str) for p in path):
            raise TypeError("Function path must be list of strings")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("Function namespace must be string or None")

        self.path = path
        self.namespace = namespace
        self._resolved = None  # Pre-resolved definitions (set by Module.prepare())

    def evaluate(self, frame):
        """Look up function in module.

        Returns a list of FunctionDefinition objects (for overloads).
        For now, returns a simple structure with function metadata.

        Uses pre-resolved definition if available (from Module.prepare()),
        otherwise falls back to runtime lookup.

        If namespace is provided (/namespace), searches only in that namespace.
        Otherwise, searches local module first, then all imported namespaces.
        """
        # Fast path: use pre-resolved definitions if available
        if self._resolved is not None:
            func_defs = self._resolved
            
            # Return structure with metadata about the function(s)
            overloads = []
            for func_def in func_defs:
                overload_info = {
                    comp.Value('name'): comp.Value(func_def.name),
                    comp.Value('is_pure'): comp.Value(func_def.is_pure),
                }
                if func_def.doc:
                    overload_info[comp.Value('doc')] = comp.Value(func_def.doc)
                if func_def.impl_doc:
                    overload_info[comp.Value('impl_doc')] = comp.Value(func_def.impl_doc)

                overloads.append(comp.Value(overload_info))

            path_str = ".".join(reversed(self.path))
            result = {
                comp.Value('name'): comp.Value(path_str),
                comp.Value('overloads'): comp.Value([comp.Value(o) for o in overloads]),
            }

            return comp.Value(result)
            yield  # Make this a generator

        # Slow path: runtime lookup (for modules not prepared)
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("Function references require module scope")

        # Look up function with namespace support (returns list of overloads)
        # Uses partial path matching (suffix matching on reversed path)
        try:
            func_defs = module.lookup_function(self.path, self.namespace)
        except ValueError as e:
            # Not found or ambiguous reference
            return comp.fail(str(e))

        # For now, return a structure with metadata about the function(s)
        # TODO: Return actual callable function object
        overloads = []
        for func_def in func_defs:
            overload_info = {
                comp.Value('name'): comp.Value(func_def.name),
                comp.Value('is_pure'): comp.Value(func_def.is_pure),
            }
            if func_def.doc:
                overload_info[comp.Value('doc')] = comp.Value(func_def.doc)
            if func_def.impl_doc:
                overload_info[comp.Value('impl_doc')] = comp.Value(func_def.impl_doc)

            overloads.append(comp.Value(overload_info))

        path_str = ".".join(reversed(self.path))
        result = {
            comp.Value('name'): comp.Value(path_str),
            comp.Value('overloads'): comp.Value([comp.Value(o) for o in overloads]),
        }

        return comp.Value(result)
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code (reversed path order for references)."""
        path_str = ".".join(reversed(self.path))
        ref = f"|{path_str}"
        if self.namespace:
            ref += "/" + self.namespace
        return ref

    def __repr__(self):
        path_str = ".".join(reversed(self.path))
        if self.namespace:
            return f"FuncRef(|{path_str}/{self.namespace})"
        return f"FuncRef(|{path_str})"


class MainDef(ModuleOp):
    """Main entry point definition: !main = {...}

    Defines the program's main entry point. Only valid in executable modules.
    Has no input shape or argument shape - just a body that runs when the program starts.
    Stored separately in the module (not in the function registry).

    Examples:
        !main = {
            @args = [|parse/cli]
            [@args.command |run]
        }

    Args:
        body: Structure definition AST node (the main body)
    """

    def __init__(self, body: _base.AstNode):
        if not isinstance(body, _base.AstNode):
            raise TypeError("Main body must be AstNode")
        self.body = body

    def evaluate(self, frame):
        """Store the main function in the module.

        The body is stored as-is (AST node) and will be evaluated when
        the program is executed.
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("MainDef requires module scope")

        # Store the main function body in the module
        module.main_func = self.body

        return comp.Value(True)
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"!main = {self.body.unparse()}"

    def __repr__(self):
        return "MainDef"


class EntryDef(ModuleOp):
    """Entry point definition: !entry = {...}

    Defines the module's entry point that runs when the module is imported.
    Has no input shape or argument shape - just a body that runs during import.
    Stored separately in the module (not in the function registry).

    All imports will have been loaded and their entry functions executed before
    this entry function runs.

    Examples:
        !entry = {
            $mod.cache = [|initialize-cache]
            $mod.validators = [|build-validators]
        }

    Args:
        body: Structure definition AST node (the entry body)
    """

    def __init__(self, body: _base.AstNode):
        if not isinstance(body, _base.AstNode):
            raise TypeError("Entry body must be AstNode")
        self.body = body

    def evaluate(self, frame):
        """Store the entry function in the module.

        The body is stored as-is (AST node) and will be evaluated when
        the module is imported.
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("EntryDef requires module scope")

        # Store the entry function body in the module
        module.entry_func = self.body

        return comp.Value(True)
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"!entry = {self.body.unparse()}"

    def __repr__(self):
        return "EntryDef"
