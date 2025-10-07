"""Runtime module with definitions and namespace mappings."""

__all__ = ["Module", "TagDef", "FuncDef", "ShapeDef", "ShapeField", "FuncImpl", "PythonFuncImpl"]


from typing import Callable

from .. import ast
from . import _shape, _value


class Module:
    """Runtime module containing tag, function, and shape definitions.

    A module represents a compiled Comp source file with all its definitions
    resolved and ready for execution. Modules track their own definitions
    and imported modules with local namespace aliases.

    Examples:
        >>> import comp
        >>> mod = comp.run.Module("myapp")
        >>> ast = comp.parse_module("!tag #status.active")
        >>> mod.process_ast(ast)
        >>> mod.dump_contents()
        Module: myapp
        Tags:
          #status
          #status.active
    """
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.tags = {}
        self.funcs = {}
        self.shapes = {}
        self.mods = {}

    def process_ast(self, module_ast: 'ast.Module'):
        """Process a module AST and extract all definitions."""

        # Process tag definitions
        for stmt in module_ast.statements:
            if isinstance(stmt, ast.TagDefinition):
                self._process_tag_definition(stmt)
            elif isinstance(stmt, ast.FuncDef):
                self._process_func_definition(stmt)
            elif isinstance(stmt, ast.ShapeDef):
                self._process_shape_definition(stmt)

    def resolve_all(self):
        """Resolve all definitions (evaluate tag expressions, resolve shapes, etc.)."""
        # Resolve tag values
        for tag in self.tags.values():
            tag.resolve(self)

        # Resolve shapes
        for shape in self.shapes.values():
            shape.resolve(self)

        # Resolve function implementations
        for func in self.funcs.values():
            for impl in func.implementations:
                impl.resolve(self)

    def process_builtins(self):
        """Add builtin module namespace to this module.

        Instead of copying builtin functions and tags into this module,
        we add a reference to the shared builtin module in self.mods.
        This ensures singleton tag behavior and proper namespace resolution.

        References without a namespace (e.g., |print, #true) will search:
        1. Current module first
        2. Then all modules in self.mods (including builtin)

        References with a namespace (e.g., |print/builtin) will only search
        that specific namespace.
        """
        from . import _builtin

        # Add reference to the shared builtin module
        self.mods["builtin"] = _builtin.get_builtin_module()

    def resolve_tag(self, tokens: list[str], namespace: str | None = None) -> 'TagDef | None':
        """Resolve a tag reference with namespace support.

        Args:
            tokens: Tag identifier path (e.g., ["status", "active"])
            namespace: Optional namespace (e.g., "builtin" for #tag/builtin)

        Returns:
            TagDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
        """
        tag_name = ".".join(tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self.mods[namespace].tags.get(tag_name)
            return None

        # No namespace: search current module first
        if tag_name in self.tags:
            return self.tags[tag_name]

        # Then search all referenced modules
        for mod in self.mods.values():
            if tag_name in mod.tags:
                return mod.tags[tag_name]

        return None

    def resolve_func(self, tokens: list[str], namespace: str | None = None) -> 'FuncDef | None':
        """Resolve a function reference with namespace support.

        Args:
            tokens: Function identifier path (e.g., ["http", "get"])
            namespace: Optional namespace (e.g., "builtin" for |func/builtin)

        Returns:
            FuncDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
        """
        func_name = ".".join(tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self.mods[namespace].funcs.get(func_name)
            return None

        # No namespace: search current module first
        if func_name in self.funcs:
            return self.funcs[func_name]

        # Then search all referenced modules
        for mod in self.mods.values():
            if func_name in mod.funcs:
                return mod.funcs[func_name]

        return None

    def resolve_shape(self, tokens: list[str], namespace: str | None = None) -> 'ShapeDef | None':
        """Resolve a shape reference with namespace support.

        Args:
            tokens: Shape identifier path (e.g., ["user", "profile"])
            namespace: Optional namespace (e.g., "models" for ~shape/models)

        Returns:
            ShapeDef if found, None otherwise

        Resolution rules:
            - If namespace is specified: only search that namespace module
            - If no namespace: search current module first, then all mods
        """
        shape_name = ".".join(tokens)

        if namespace:
            # Only search the specified namespace
            if namespace in self.mods:
                return self.mods[namespace].shapes.get(shape_name)
            return None

        # No namespace: search current module first
        if shape_name in self.shapes:
            return self.shapes[shape_name]

        # Then search all referenced modules
        for mod in self.mods.values():
            if shape_name in mod.shapes:
                return mod.shapes[shape_name]

        return None

    def _process_tag_definition(self, tag_def: 'ast.TagDefinition'):
        """Extract tag definitions from AST node."""
        parent_path = tag_def.tokens
        parent_key = ".".join(parent_path)
        self._ensure_tag_hierarchy(parent_path)
        # Store the value expression for later resolution
        if tag_def.value:
            self.tags[parent_key]._value_expr = tag_def.value
        body = tag_def.body
        if body:
            for child in body.kids:
                if isinstance(child, ast.TagChild):
                    self._process_tag_child(child, parent_path)

    def _process_tag_child(self, tag_child: 'ast.TagChild', parent_path: list[str]):
        """Extract tag from child node relative to parent."""
        child_tokens = tag_child.tokens
        full_path = parent_path + child_tokens
        full_key = ".".join(full_path)
        self._ensure_tag_hierarchy(full_path)
        # Store the value expression for later resolution
        if tag_child.value:
            self.tags[full_key]._value_expr = tag_child.value
        body = tag_child.body
        if body:
            for nested_child in body.kids:
                if isinstance(nested_child, ast.TagChild):
                    self._process_tag_child(nested_child, full_path)

    def _ensure_tag_hierarchy(self, identifier: list[str]):
        """Ensure tag and all parent tags exist in this module."""
        for i in range(1, len(identifier) + 1):
            path = identifier[:i]
            key = ".".join(path)
            if key not in self.tags:
                self.tags[key] = TagDef(identifier=path)

    def _process_func_definition(self, func_def):
        """Extract function definition from AST node."""
        key = ".".join(func_def.tokens)
        func = self.funcs.get(key)
        if not func:
            func = self.funcs[key] = FuncDef(identifier=func_def.tokens)
        impl = FuncImpl(ast_node=func_def)
        func.implementations.append(impl)

    def _process_shape_definition(self, shape_def):
        """Extract shape definition from AST node."""
        from . import _shape_build
        
        key = ".".join(shape_def.tokens)
        runtime_shape = ShapeDef(identifier=shape_def.tokens)
        self.shapes[key] = runtime_shape
        
        # Populate fields from the AST node
        _shape_build.populate_shape_def_fields(runtime_shape, shape_def, self)

    def dump_contents(self):
        """Print formatted contents of this module."""
        print(f"Module: {self.identifier}")
        if self.tags:
            print()
            print(f"Tags {len(self.tags)}:")
            for name, tag in sorted(self.tags.items()):
                print(f"  #{name} = {tag.value}") if tag.value is not None else print(f"  #{name}")
        if self.funcs:
            print()
            print(f"Functions {len(self.funcs)}:")
            for name, func in sorted(self.funcs.items()):
                print(f"  |{name}")
        if self.shapes:
            print()
            print(f"Shapes {len(self.shapes)}:")
            for name, shape in sorted(self.shapes.items()):
                print(f"  ~{name}")
        if self.mods:
            print()
            print(f"Namespaces {len(self.mods)}:")
            for name, module in sorted(self.mods.items()):
                print(f"  {name} -> {module.identifier}")
        if not (self.tags or self.funcs or self.shapes or self.mods):
            print("  (empty)")

    def __repr__(self):
        counts = []
        if self.tags:
            counts.append(f"{len(self.tags)} tags")
        if self.funcs:
            counts.append(f"{len(self.funcs)} funcs")
        if self.shapes:
            counts.append(f"{len(self.shapes)} shapes")

        contents = ", ".join(counts) if counts else "empty"
        return f"Module({self.identifier!r}, {contents})"


class TagDef:
    """Tag definition - immutable, belongs to defining module."""
    def __init__(self, identifier):
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.value = None
        self._value_expr = None
        self._resolved = False

    def resolve(self, module: 'Module'):
        """Resolve tag value expression."""
        if self._resolved:
            return

        if self._value_expr:
            from . import _eval
            self.value = _eval.evaluate(self._value_expr, module)

        self._resolved = True

    def __repr__(self):
        if self.value is not None:
            return f"TagDef(#{self.name} = {self.value!r})"
        return f"TagDef(#{self.name})"


class FuncDef:
    """Function definition - immutable, belongs to defining module."""
    def __init__(self, identifier):
        """Create a function definition."""
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.implementations = []

    def __repr__(self):
        return f"FuncDef(|{self.name})"


class FuncImpl:
    """Implementation of a function for a specific shape."""

    def __init__(self, ast_node: ast.FuncDef):
        self._ast_node = ast_node
        self.shape: _shape.ShapeType | None = None
        self._resolved = False

    def resolve(self, module: 'Module'):
        """Resolve shape references in module context."""
        if self._resolved:
            return

        if self.shape:
            self.shape.resolve(module)

        self._resolved = True

    def matches(self, value) -> tuple[int, int]:
        """Check if this implementation matches the value's shape.

        Returns (specificity, quality) tuple. Higher = better match.
        """
        if not self.shape:
            return (0, 1)  # No shape = matches anything (low priority)

        return self.shape.matches(value)

    def __repr__(self):
        shape_str = f" shape={self.shape}" if self.shape else ""
        return f"FuncImpl({shape_str})"


class PythonFuncImpl:
    """Python-implemented function that can be called from Comp code.

    This allows implementing built-in functions in Python that integrate
    seamlessly with Comp's runtime system.
    """

    def __init__(self, python_func: 'Callable[[_value.Value, _value.Value], _value.Value]', name: str | None = None):
        """Create a Python function implementation.

        Args:
            python_func: Python callable that takes (in_value, arg_value) and returns Value
            name: Optional name for debugging/display
        """
        self.python_func = python_func
        self.name = name or (python_func.__name__ if hasattr(python_func, '__name__') else "python_func")
        self.shape: _shape.ShapeType | None = None
        self._resolved = True  # Python funcs don't need resolution

    def resolve(self, module: 'Module'):
        """Resolve shape references in module context."""
        # Python functions are already resolved
        pass

    def matches(self, value) -> tuple[int, int]:
        """Check if this implementation matches the value's shape.

        Returns (specificity, quality) tuple. Higher = better match.
        """
        if not self.shape:
            return (0, 1)  # No shape = matches anything (low priority)

        return self.shape.matches(value)

    def __repr__(self):
        shape_str = f" shape={self.shape}" if self.shape else ""
        return f"PythonFuncImpl({self.name}{shape_str})"


class ShapeDef:
    """Shape definition - immutable, belongs to defining module."""
    def __init__(self, identifier):
        """Create a shape definition."""
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.fields = {}
        self.shape = None  # For non-structural shapes (TagRef, ShapeDefRef, etc.)
        self._resolved = False

    def resolve(self, module: 'Module'):
        """Resolve shape references and expand field definitions."""
        if self._resolved:
            return

        # Resolve the base shape if this is a non-structural shape
        if self.shape:
            self.shape.resolve(module)

        # Resolve each field's shape type
        for _field_name, field in self.fields.items():
            if field.shape:
                field.shape.resolve(module)
                # Expand fields from referenced shapes
                self._expand_shape_fields(field.shape, module)

        self._resolved = True

    def _expand_shape_fields(self, shape_type: _shape.ShapeType, module: 'Module'):
        """Walk through shape references to expand fields."""
        if isinstance(shape_type, _shape.ShapeDefRef):
            # Follow reference to expand fields from that shape
            if shape_type._resolved:
                target_shape = shape_type._resolved
                if not target_shape._resolved:
                    target_shape.resolve(module)
                # Copy fields from referenced shape
                for field_name, field in target_shape.fields.items():
                    if field_name not in self.fields:
                        self.fields[field_name] = field

        elif isinstance(shape_type, _shape.ShapeModRef):
            # Follow cross-module reference
            if shape_type._resolved:
                target_shape = shape_type._resolved
                if not target_shape._resolved:
                    # Need the other module for resolution context
                    if shape_type.namespace in module.mods:
                        other_module = module.mods[shape_type.namespace]
                        target_shape.resolve(other_module)
                # Copy fields from referenced shape
                for field_name, field in target_shape.fields.items():
                    if field_name not in self.fields:
                        self.fields[field_name] = field

        elif isinstance(shape_type, _shape.ShapeTagRef):
            # Tags don't expand fields - they act as constraints
            pass

        elif isinstance(shape_type, _shape.ShapeInline):
            # Inline shapes may have nested shape types
            for _field_name, field_type in shape_type.fields.items():
                if isinstance(field_type, _shape.ShapeType):
                    self._expand_shape_fields(field_type, module)

        elif isinstance(shape_type, _shape.ShapeUnion):
            # Union: expand fields from all variants
            for variant in shape_type.variants:
                self._expand_shape_fields(variant, module)

    def __repr__(self):
        field_count = len(self.fields)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeDef(~{self.name}, {field_count} fields{status})"


class ShapeField:
    """Field within a shape definition."""
    def __init__(self, name: str, shape: _shape.ShapeType | None = None):
        self.name = name
        self.shape = shape

    def __repr__(self):
        shape_str = f": {self.shape}" if self.shape else ""
        return f"ShapeField({self.name}{shape_str})"
