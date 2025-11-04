"""AST nodes for handle definitions and references."""

__all__ = ["HandleDef", "HandleValueRef", "HandleShape", "GrabOp", "DropOp"]


import comp

from . import _base
from ._tag import ModuleOp


class HandleDef(ModuleOp):
    """Handle definition: !handle @path.to.handle

    Defines a handle in the module hierarchy. Handles represent external
    resources or capabilities that require cleanup.

    The path is stored in definition order (root to leaf), e.g.,
    ["fs", "file", "readonly"] for !handle @fs.file.readonly

    Drop behavior is now defined via the |drop-handle function dispatch
    mechanism, not in the handle body.

    Example:
        !handle @filehandle
        
        !func |drop-handle ~{} = {
            ; Check $in to determine which handle type
            ; Dispatch to appropriate cleanup function
        }

    Args:
        path: Full path in definition order, e.g., ["fs", "file", "readonly"]
        is_private: Whether the handle is private (& suffix)
        doc: Optional documentation string
    """

    def __init__(self, path: list[str], is_private: bool = False, doc: str | None = None):
        if not path:
            raise ValueError("Handle path cannot be empty")
        if not all(isinstance(name, str) for name in path):
            raise TypeError("Handle path must be list of strings")

        self.path = path
        self.is_private = is_private
        self.doc = doc

    def evaluate(self, frame):
        """Register this handle in the module.

        1. Get module from module scope
        2. Consume any pending documentation from !doc statements
        3. Register handle (no drop block - behavior via |drop-handle function)
        
        This must be a generator even though it doesn't yield, because
        the Frame constructor expects all evaluate() methods to be generators.
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("HandleDef requires module scope")

        # Consume pending documentation from !doc statements
        # This overrides any documentation passed to __init__
        doc = self.doc
        if module.pending_doc is not None:
            doc = module.pending_doc
            module.pending_doc = None  # Clear after consuming

        # Register this handle without drop block (use function dispatch instead)
        module.define_handle(self.path, is_private=self.is_private, doc=doc)

        # Return empty value (definitions don't produce values)
        return comp.Value({})
        yield  # Make this a generator (unreachable but required)

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        path_str = "@" + ".".join(reversed(self.path))  # Reverse for reference notation
        if self.is_private:
            path_str += "&"
        return f"!handle {path_str}"

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
        # Pure functions cannot grab handles (side effects)
        if frame.pure_context:
            return comp.fail("Cannot !grab in pure function (pure functions cannot have side effects)")
        
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
        """Drop a handle instance by dispatching to |drop-handle function.

        The !drop operator now exclusively uses function dispatch to the |drop-handle
        function defined in the handle's defining module. This allows protocol-style
        implementations where different handle types can have custom cleanup logic.

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

        # Only execute drop if handle is not already dropped (idempotent)
        if not handle_data.is_dropped:
            # Dispatch to |drop-handle function in the defining module
            defining_module = handle_data.handle_def.module
            drop_executed = False
            
            if defining_module is not None:
                # Look for |drop-handle function in the defining module
                func_list = defining_module.functions.get('drop-handle', [])
                if func_list:
                    # Try to find a matching function (could have multiple overloads)
                    # For now, try the first one that accepts this handle
                    for func_def in func_list:
                        try:
                            # Try to call the function with the handle
                            result = yield from func_def.invoke(
                                in_=handle_value,
                                args=None,
                                ctx=frame.scope('ctx')
                            )
                            
                            # If function succeeded, we're done
                            if not result.is_fail:
                                drop_executed = True
                                # If drop function fails, return the failure
                                if frame.bypass_value(result):
                                    return result
                                break
                        except Exception:
                            # Function didn't match, try next overload
                            continue
            
            # If no drop function found or executed, that's okay - handle just gets dropped
            # This allows handles to exist without requiring cleanup logic

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
