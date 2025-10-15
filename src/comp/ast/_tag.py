"""AST nodes for tag definitions and references."""

__all__ = ["Module", "ModuleOp", "TagDef", "TagChild", "TagValueRef"]


import comp

from . import _base


class Module(_base.AstNode):
    """Module node: collection of module-level definitions.

    Evaluates all module operations (tag definitions, function definitions, etc.)
    and builds a runtime Module object. The module operations are evaluated in
    order, allowing later definitions to reference earlier ones.

    Args:
        operations: List of module-level operations (TagDef, FuncDef, etc.)
    """

    def __init__(self, operations: list['ModuleOp']):
        if not isinstance(operations, list):
            raise TypeError("Module operations must be a list")
        if not all(isinstance(op, ModuleOp) for op in operations):
            raise TypeError("All operations must be ModuleOp instances")

        self.operations = operations

    def evaluate(self, frame):
        """Evaluate all module operations to build the runtime module.

        Uses existing prepared module from mod_* scopes if available,
        otherwise creates a new Module. This allows prepare() to pre-populate
        definitions that evaluation will then fill in with actual values.

        Returns:
            Module entity containing all registered definitions
        """
        # Try to get existing prepared module from scope
        # If prepare() was called and module was passed to engine.run(),
        # it will be available in the module scope
        module = frame.scope('module')
        
        # If no prepared module exists, create a new one
        if module is None:
            module = comp.Module()

        # Evaluate each operation with module in scope
        for op in self.operations:
            result = yield comp.Compute(op, module=module)
            if frame.is_fail(result):
                return result

        # Return the populated module
        return module

    def unparse(self) -> str:
        """Convert back to source code."""
        return "\n".join(op.unparse() for op in self.operations)

    def __repr__(self):
        return f"Module({len(self.operations)} ops)"


class ModuleOp(_base.AstNode):
    """Base class for module-level operations.

    Module operations register definitions in the module being built.
    They receive a 'module' scope containing the runtime Module with
    tags, shapes, and functions registries.

    Subclasses:
    - TagDef: Tag definitions
    - FuncDef: Function definitions
    - ShapeDef: Shape definitions
    - ImportDef: Import statements
    """
    pass


class TagDef(ModuleOp):
    """Tag definition: !tag #path.to.tag = value {...}

    Defines a tag in the module hierarchy. Tags can have:
    - A value (any expression that evaluates to a Value)
    - Children (nested tag definitions)
    - A generator function (for auto-generating values) - not implemented yet

    The path is stored in definition order (root to leaf), e.g.,
    ["status", "error", "timeout"] for !tag #timeout.error.status

    Multiple definitions of the same tag merge - later values override earlier ones.

    Args:
        path: Full path in definition order, e.g., ["status", "error", "timeout"]
        value: Optional expression that evaluates to tag's value
        children: List of nested TagChild definitions
        generator: Optional generator function (not implemented)
    """

    def __init__(self, path: list[str], value: _base.ValueNode | None = None,
                 children: list['TagChild'] | None = None,
                 generator: _base.ValueNode | None = None):
        if not path:
            raise ValueError("Tag path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Tag path must be list of strings")
        if value is not None and not isinstance(value, _base.ValueNode):
            raise TypeError("Tag value must be ValueNode or None")
        if children is not None:
            if not isinstance(children, list):
                raise TypeError("Tag children must be list or None")
            if not all(isinstance(c, TagChild) for c in children):
                raise TypeError("All children must be TagChild instances")
        if generator is not None and not isinstance(generator, _base.ValueNode):
            raise TypeError("Tag generator must be ValueNode or None")

        self.path = path
        self.value = value
        self.children = children or []
        self.generator = generator

    def evaluate(self, frame):
        """Register this tag and its children in the module.

        1. Get module from module scope
        2. Evaluate value expression if present
        3. Register tag in module
        4. Recursively process children
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("TagDef requires module scope")

        # Evaluate value if present
        tag_value = None
        if self.value is not None:
            tag_value = yield comp.Compute(self.value)
            if frame.is_fail(tag_value):
                return tag_value

        # Register this tag
        module.define_tag(self.path, tag_value)

        # Process children - they extend the path
        if self.children:
            for child in self.children:
                # Child paths are relative to this tag
                result = yield comp.Compute(child, module=module, parent_path=self.path)
                if frame.is_fail(result):
                    return result

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = ["!tag", "#" + ".".join(reversed(self.path))]  # Reverse for reference notation

        if self.generator:
            parts.append(self.generator.unparse())

        if self.value or self.children:
            parts.append("=")

        if self.value:
            parts.append(self.value.unparse())

        if self.children:
            children_str = " ".join(c.unparse() for c in self.children)
            parts.append(f"{{{children_str}}}")

        return " ".join(parts)

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"TagDef({path_str})"


class TagChild(ModuleOp):
    """Nested tag definition within a tag body.

    Similar to TagDef but used inside tag bodies. The path is relative
    to the parent tag's path.

    Example:
        !tag #status = {
            #active = 1      <- TagChild with path=["active"]
            #error = {       <- TagChild with path=["error"], has children
                #timeout     <- TagChild with path=["timeout"]
            }
        }

    Args:
        path: Relative path (single name or multiple for deep nesting)
        value: Optional expression for the tag's value
        children: Nested children (for hierarchies)
    """

    def __init__(self, path: list[str], value: _base.ValueNode | None = None,
                 children: list['TagChild'] | None = None):
        if not path:
            raise ValueError("TagChild path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("TagChild path must be list of strings")
        if value is not None and not isinstance(value, _base.ValueNode):
            raise TypeError("TagChild value must be ValueNode or None")
        if children is not None:
            if not isinstance(children, list):
                raise TypeError("TagChild children must be list or None")
            if not all(isinstance(c, TagChild) for c in children):
                raise TypeError("All children must be TagChild instances")

        self.path = path
        self.value = value
        self.children = children or []

    def evaluate(self, frame):
        """Register this child tag in the module.

        Combines parent_path from scope with this child's relative path.
        """
        # Get module and parent path from scope
        module = frame.scope('module')
        parent_path = frame.scope('parent_path')

        if module is None:
            return comp.fail("TagChild requires module scope")
        if parent_path is None:
            return comp.fail("TagChild requires parent_path scope")

        # Build full path: parent + child
        full_path = parent_path + self.path

        # Evaluate value if present
        tag_value = None
        if self.value is not None:
            tag_value = yield comp.Compute(self.value)
            if frame.is_fail(tag_value):
                return tag_value

        # Register tag
        module.define_tag(full_path, tag_value)

        # Process children
        if self.children:
            for child in self.children:
                result = yield comp.Compute(child, module=module, parent_path=full_path)
                if frame.is_fail(result):
                    return result

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = ["#" + ".".join(reversed(self.path))]  # Reverse for reference notation

        if self.value or self.children:
            parts.append("=")

        if self.value:
            parts.append(self.value.unparse())

        if self.children:
            children_str = " ".join(c.unparse() for c in self.children)
            parts.append(f"{{{children_str}}}")

        return " ".join(parts)

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"TagChild({path_str})"


class TagValueRef(_base.ValueNode):
    """Tag reference as a value: #timeout.error.status

    References are written in reverse order (leaf first), but stored
    as a list for matching. The lookup uses partial suffix matching.

    Examples:
        #active              -> ["active"]
        #timeout.error       -> ["timeout", "error"]
        #timeout.error.status -> ["timeout", "error", "status"]

    Args:
        path: Reversed path (leaf first), e.g., ["timeout", "error", "status"]
        namespace: Optional module namespace for cross-module refs (future)

    Attributes:
        _resolved: Pre-resolved TagDefinition (set by Module.prepare())
    """

    def __init__(self, path: list[str], namespace: str | None = None):
        if not path:
            raise ValueError("Tag reference path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Tag path must be list of strings")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("Tag namespace must be string or None")

        self.path = path
        self.namespace = namespace
        self._resolved = None  # Pre-resolved definition (set by Module.prepare())

    def evaluate(self, frame):
        """Look up tag in module and return as a Value.

        Uses pre-resolved definition if available (from Module.prepare()),
        otherwise falls back to runtime lookup.

        Uses partial path matching to find the tag. If the reference is
        ambiguous (multiple matches), returns a failure.

        If namespace is provided (/namespace), searches only in that namespace.
        Otherwise, searches local module first, then all imported namespaces.
        """
        # Fast path: use pre-resolved definition if available
        if self._resolved is not None:
            tag_def = self._resolved
            # Return the TagRef itself wrapped in a Value
            return comp.Value(comp.TagRef(tag_def))
            yield  # Make this a generator (unreachable)

        # Slow path: runtime lookup (for modules not prepared)
        # Get module from frame
        module = frame.scope('module')
        if module is None:
            return comp.fail("Tag references require module scope")

        # Look up tag by partial path with namespace support
        try:
            tag_def = module.lookup_tag_with_namespace(self.path, self.namespace)
        except ValueError as e:
            # Ambiguous reference
            return comp.fail(str(e))

        if tag_def is None:
            path_str = ".".join(reversed(self.path))
            if self.namespace:
                return comp.fail(f"Tag not found: #{path_str}/{self.namespace}")
            return comp.fail(f"Tag not found: #{path_str}")

        # Return the TagRef itself wrapped in a Value
        return comp.Value(comp.TagRef(tag_def))
        yield  # Make this a generator (unreachable)

    def unparse(self) -> str:
        """Convert back to source code."""
        ref = "#" + ".".join(reversed(self.path))
        if self.namespace:
            ref += "/" + self.namespace
        return ref

    def __repr__(self):
        path_str = ".".join(reversed(self.path))
        if self.namespace:
            return f"TagValueRef(#{path_str}/{self.namespace})"
        return f"TagValueRef(#{path_str})"

