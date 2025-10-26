"""AST nodes for handle definitions and references."""

__all__ = ["HandleDef", "HandleValueRef", "HandleShape", "GrabOp", "DropOp"]


import comp

from . import _base
from ._tag import ModuleOp


class HandleDef(ModuleOp):
    """Handle definition: !handle @path.to.handle {...}

    Defines a handle in the module hierarchy. Handles represent external
    resources or capabilities that require cleanup.

    The path is stored in definition order (root to leaf), e.g.,
    ["fs", "file", "readonly"] for !handle @fs.file.readonly

    The body can contain explicit keyword assignments for handle behavior:
    - drop: Block to call when handle is dropped (e.g., drop = :[|close-file])

    Example:
        !handle @filehandle = {
            drop = :[|close-file]
        }
        
        !handle @pyobject = {
            drop = :[|py-decref]
        }

    Args:
        path: Full path in definition order, e.g., ["fs", "file", "readonly"]
        drop_block: Optional AST node for drop block (RawBlock or Block)
    """

    def __init__(self, path: list[str], drop_block: _base.ValueNode | None = None, is_private: bool = False):
        if not path:
            raise ValueError("Handle path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Handle path must be list of strings")
        if drop_block is not None and not isinstance(drop_block, _base.AstNode):
            raise TypeError("Drop block must be AstNode or None")

        self.path = path
        self.drop_block = drop_block
        self.is_private = is_private

    def evaluate(self, frame):
        """Register this handle in the module.

        1. Get module from module scope
        2. Register handle with optional drop block
        
        This must be a generator even though it doesn't yield, because
        the Frame constructor expects all evaluate() methods to be generators.
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("HandleDef requires module scope")

        # Register this handle with optional drop block
        module.define_handle(self.path, drop_block=self.drop_block, is_private=self.is_private)

        # Return empty value (definitions don't produce values)
        return comp.Value({})
        yield  # Make this a generator (unreachable but required)

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        parts = ["!handle", "@" + ".".join(reversed(self.path))]  # Reverse for reference notation

        if self.drop_block:
            parts.append("=")
            parts.append(f"{{drop = {self.drop_block.unparse()}}}")

        return " ".join(parts)

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"HandleDef({path_str})"




class HandleValueRef(_base.ValueNode):
    """Handle reference: @handle.name or @handle.name/namespace

    Used ONLY within !grab operations, not as a standalone value.
    Handle references in shape contexts use HandleShape instead.

    Args:
        path: Handle path in natural reading order, e.g., ["fs", "file"]
        namespace: Optional namespace to search in (e.g., "std" for /std)
    """

    def __init__(self, path: list[str], namespace: str | None = None):
        if not path:
            raise ValueError("Handle reference path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Handle path must be list of strings")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("Namespace must be string or None")

        self.path = path
        self.namespace = namespace

    def evaluate(self, frame):
        """Should not be called - HandleValueRef is not an atom.
        
        This node should only appear within GrabOp, which accesses
        path and namespace directly without evaluation.
        """
        raise RuntimeError(
            "HandleValueRef.evaluate() should not be called - "
            "handle references are not standalone values. "
            "Use !grab @handle to create a handle instance."
        )
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        path_str = ".".join(self.path)
        if self.namespace:
            return f"@{path_str}/{self.namespace}"
        return f"@{path_str}"

    def __repr__(self):
        path_str = ".".join(self.path)
        if self.namespace:
            return f"HandleValueRef(@{path_str}/{self.namespace})"
        return f"HandleValueRef(@{path_str})"


class GrabOp(_base.ValueNode):
    """Grab operation: !grab @handle

    Creates an actual handle instance from a handle definition.
    Only the module that defines the handle can grab it.

    Args:
        handle_ref: HandleValueRef AST node identifying which handle to grab
    """

    def __init__(self, handle_ref: 'HandleValueRef'):
        if not isinstance(handle_ref, HandleValueRef):
            raise TypeError("GrabOp requires HandleValueRef")
        self.handle_ref = handle_ref

    def evaluate(self, frame):
        """Create a handle instance and register it with the current frame.

        Returns:
            comp.Value wrapping comp.HandleInstance
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("!grab requires module scope")

        # Look up the handle definition
        try:
            handle_def = module.lookup_handle(self.handle_ref.path, self.handle_ref.namespace)
        except ValueError as e:
            return comp.fail(str(e))

        # Verify that the handle is defined in the current module
        if handle_def.module != module:
            return comp.fail(
                f"Cannot !grab @{handle_def.full_name}: "
                f"handle must be defined in the current module"
            )

        # Create a HandleInstance
        handle_instance = comp.HandleInstance(handle_def)
        result = comp.Value(handle_instance)
        
        # Register the handle with the current frame (bidirectional)
        # This ensures the handle gets tracked even if never assigned to a scope
        frame.register_handles(result)
        
        return result
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"!grab {self.handle_ref.unparse()}"

    def __repr__(self):
        return f"GrabOp({self.handle_ref!r})"


class DropOp(_base.ValueNode):
    """Drop operation: !drop $var.field

    Invalidates a handle instance early (before automatic cleanup).
    Safe to call multiple times - only has effect on first call.

    Args:
        target: Identifier AST node pointing to the handle to drop
    """

    def __init__(self, target: _base.ValueNode):
        if not isinstance(target, _base.ValueNode):
            raise TypeError("DropOp target must be a ValueNode")
        self.target = target

    def evaluate(self, frame):
        """Drop a handle instance and execute its drop block if defined.

        Returns:
            comp.Value - the dropped handle (now invalid)
        """
        # Evaluate the target to get the handle
        handle_value = yield comp.Compute(self.target)
        if handle_value.is_fail:
            return handle_value

        # Check if it's a handle instance
        if not handle_value.is_handle:
            return comp.fail("!drop requires a handle value")

        handle_data = handle_value.data

        # Verify it's a HandleInstance (should always be true at this point)
        if not isinstance(handle_data, comp.HandleInstance):
            return comp.fail(
                f"Cannot !drop handle: invalid handle type"
            )

        # Only execute drop block if handle is not already dropped (idempotent)
        if not handle_data.is_dropped:
            # Execute drop block if one is defined on the handle definition
            drop_block = handle_data.handle_def.drop_block
            if drop_block is not None:
                # Evaluate the drop block AST to get a RawBlock
                drop_block_value = yield comp.Compute(drop_block)
                if frame.bypass_value(drop_block_value):
                    return drop_block_value
                
                # Morph RawBlock to Block with empty input shape (accepts any input)
                block_shape = comp.BlockShapeDefinition([])
                morph_result = comp.morph(drop_block_value, block_shape)
                
                if morph_result.value is None:
                    return comp.fail("Drop block must be a block")
                
                typed_block = morph_result.value
                
                # Invoke the drop block with empty input
                if typed_block.is_block:
                    block_entity = typed_block.data
                    invoke_compute = block_entity.invoke(comp.Value({}))
                    drop_result = yield invoke_compute
                    
                    # If drop block fails, return the failure
                    if frame.bypass_value(drop_result):
                        return drop_result

            # Drop the handle (mark as dropped, unregister from frames)
            handle_data.drop()

        # Return the handle value (now dropped)
        return handle_value

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"!drop {self.target.unparse()}"

    def __repr__(self):
        return f"DropOp({self.target!r})"


class HandleShape(_base.ShapeNode):
    """Handle reference used as a shape: @handle

    Represents a handle reference when used in a shape context (like shape field types).
    The handle itself serves as the type constraint - only values that are instances of
    this handle (or its descendants) can satisfy this shape.

    Examples:
        f @file            # Field must be @file handle instance
        f @file.readonly   # Field must be @file.readonly instance (or descendant)

    Args:
        path: Partial path in natural order, e.g., ["file"] or ["file", "readonly"]
        namespace: Optional namespace for cross-module references

    Attributes:
        _resolved: Pre-resolved HandleDefinition (set by Module.prepare())
    """

    def __init__(self, path: list[str], namespace: str | None = None):
        if not isinstance(path, list):
            raise TypeError("Handle path must be a list")
        if not path:
            raise ValueError("Handle path cannot be empty")
        if not all(isinstance(p, str) for p in path):
            raise TypeError("Handle path must be list of strings")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("Handle namespace must be string or None")

        self.path = path
        self.namespace = namespace
        self._resolved = None  # Pre-resolved definition (set by Module.prepare())

    def evaluate(self, frame):
        """Look up handle in module and return HandleDefinition.

        Returns the HandleDefinition directly, which the morphing system
        can use as a shape constraint for matching handle values.
        """
        # Fast path: use pre-resolved definition if available
        if self._resolved is not None:
            return self._resolved
            yield  # Unreachable but makes this a generator

        # Slow path: runtime lookup (for modules not prepared)
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("Handle shapes require module scope")

        # Look up handle with namespace support
        try:
            handle_def = module.lookup_handle(self.path, self.namespace)
        except ValueError as e:
            # Not found or ambiguous reference
            return comp.fail(str(e))

        # Return HandleDefinition directly (like ShapeRef returns ShapeDefinition)
        return handle_def
        yield  # Unreachable but makes this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        handle_str = "@" + ".".join(self.path)
        if self.namespace:
            handle_str += f"/{self.namespace}"
        return handle_str

    def __repr__(self):
        ns_str = f", namespace={self.namespace!r}" if self.namespace else ""
        return f"HandleShape({self.path!r}{ns_str})"
