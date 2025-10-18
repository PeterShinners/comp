"""Engine for evaluating AST nodes with scope stack architecture.

The Engine provides scope management for AST node coordination.
Scopes are used for both variable bindings and parent→child coordination.

The engine doesn't know about language semantics - it just provides primitives.
AST nodes orchestrate everything using these tools.
"""

__all__ = ["Engine", "Compute"]

import comp


class Engine:
    """Evaluation engine with scope stack.

    The engine is a generic processor for nodes that contain `evaluate`
    generators. The generators return `Value` objects and yield child nodes for
    further evaluation.

    The engine comes with a generic system for evaluation to define a stack of
    scopes, which allows evaluation to provide context and coordination for
    evaluating child nodes.

    The engine has a simple concept of value that should be skip or bypass
    processing. These are usually associated with failure types, but could be
    expanded to anything the user want to the engine to handle specially.
    """

    def __init__(self):
        """Initialize the engine with an empty context scope.
        
        The context scope is persistent across function calls and stored
        as an empty struct (Value(None)).
        """
        # Context scope storage - persistent across function calls
        # Value(None) creates an empty struct
        self.ctx_scope = comp.Value(None)

    def run(self, node, **scopes):
        """Run a node and return its result (frame-based evaluation).

        This is the main entry point for evaluation. It handles the generator
        protocol: yielding children, sending results back, getting final result.

        The op generator builds a list of Frame objects describing the
        execution path while processing.

        Fail values immediately stop processing UNLESS the parent frame
        has allow_failures set, in which case the fail is sent to it via send().

        Args:
            node (AstNode): AST node to evaluate
            **scopes: Keyword arguments to define initial scopes (in_ becomes in)

        Returns:
            Value: Final Value result from node evaluation
        """
        result = comp.Value({})  # Set by first StopIteration before use
        result_is_fail = False  # Track if result contains a failure

        # Handle Python keyword workarounds: in_ -> in
        if 'in_' in scopes:
            scopes['in'] = scopes.pop('in_')

        # Create initial frame
        newest = _Frame(node, None, scopes, False, self)
        current = newest

        while current:
            try:
                # If current is allowed to receive failures and we have one
                if result_is_fail and current.allowed:
                    # Parent consumed the failure - clear both flags
                    current.allowed = False
                    result_is_fail = False

                # Failures bypass frames that don't allow them
                elif result_is_fail:
                    current.gen.close()
                    current = current.previous
                    continue

                # Advance generator - yields a Compute request
                if current is newest:
                    request = next(current.gen)
                else:
                    request = current.gen.send(result)

                # Mark the parent (current) as allowed to receive failures from the child (request)
                if request.allow_failures:
                    current.allowed = True

                # Create child frame - generator created automatically in __init__
                newest = _Frame(
                    request.node,
                    current,
                    request.scopes,
                    request.allow_failures,
                    self
                )
                current = newest

            except StopIteration as e:
                # Handle returned value and step out to parent
                result = e.value
                if result is None:
                    print("NONERESULT:", current, current.node)
                result.ast = current.node  # Minimal temporary tracking of source
                result_is_fail = current.is_fail(result)
                current = current.previous

        return result


    # Later this should become a more generic "engine skip these shapes"
    # but for not its hardcoded to failures
    def is_fail(self, value):
        """Check if a value is a fail value.

        A fail value is a structure that contains a #fail tag (or any child of #fail)
        as an unnamed field. This allows morphing against #fail to detect failures.

        Supports hierarchical tags: #fail, #fail.syntax, #fail.network, etc.
        
        Args:
            value (Value): Value to check for failure
            
        Returns:
            bool: True if value contains a #fail tag
        """
        if not value.is_struct:
            return False

        # Look for #fail tag or any child of #fail in unnamed fields
        for val in value.struct.values():
            if val.is_tag and self._is_fail_tag(val.data):
                return True
        return False

    def _is_fail_tag(self, tag):
        """Check if a tag is #fail or a child of #fail hierarchy.

        Args:
            tag (TagRef): A TagRef object to check

        Returns:
            bool: True if tag is #fail or a descendant (e.g., #fail.syntax, #fail.network)
        """
        # Check if tag name is "fail" or starts with "fail."
        return tag.full_name == comp.builtin.FAIL.full_name or tag.full_name.startswith(comp.builtin.FAIL.full_name + ".")


class Compute:
    """Request to evaluate a child AST node.

    This is yielded from `AstNode.evaluate` when further processing is requested.
    The engine receives this request and creates an internal _Frame to track execution.

    Args:
        node (AstNode): AST node to evaluate (required)
        allow_failures (bool): Whether this evaluation can receive fail values (default: False)
        **scopes: Scope bindings for this evaluation (keyword arguments)
    """

    __slots__ = ('node', 'allow_failures', 'scopes')

    def __init__(self, node, allow_failures=False, **scopes):
        self.node = node
        self.scopes = {k.rstrip('_'): v for k, v in scopes.items()}
        self.allow_failures = allow_failures

    def __repr__(self):
        """Return string representation of Compute request.
        
        Returns:
            str: Formatted string showing node, scopes, and allow_failures
        """
        parts = [f"node={self.node!r}"]
        if self.scopes:
            parts.append(f"scopes={list(self.scopes.keys())}")
        if self.allow_failures:
            parts.append("allow_failures=True")
        return f"Compute({', '.join(parts)})"


class _Frame:
    """Evaluation frame - represents one step in the call stack.

    This is a self-contained execution context that forms a linked list.
    Each frame knows its parent, eliminating the need for a separate stack.

    The frame provides all services needed by AST node generators:
    - Scope lookup (flattened dict with parent fallback)
    - Failure checking
    - Function calls

    The generator is created automatically during initialization.

    Args:
        node (AstNode): AST node being evaluated
        previous (_Frame | None): Parent frame (None for root)
        scopes (dict): Scope bindings for this frame (merged with parent)
        allow_failures (bool): Whether this frame can receive failures
        engine (Engine): Engine reference for function registry and fail_tag
    """
    __slots__ = ('node', 'gen', 'previous', 'scopes', 'allowed', 'engine')

    def __init__(self, node, previous, scopes, allow_failures, engine):
        self.node = node
        self.previous = previous
        self.allowed = allow_failures  # Can frame receive failure values? (modified as engine loops)
        self.engine = engine  # Temporary for function registry

        if not previous:
            self.scopes = scopes
        elif not scopes:
            self.scopes = previous.scopes  # No copy needed
        else:
            self.scopes = {**previous.scopes, **scopes}  # Flatten scope over previous

        # Create the generator now that the frame is fully initialized
        self.gen = node.evaluate(self)

    def scope(self, key):
        """Look up a scope value.
        
        Args:
            key (str): Scope name to look up
            
        Returns:
            Value | None: Scope value or None if not found
        """
        return self.scopes.get(key)

    def is_fail(self, value):
        """Check if a value is a fail value.
        
        Args:
            value (Value): Value to check
            
        Returns:
            bool: True if value is a fail value
        """
        # TODO one day perform this operation without an engine reference
        # Only Values can be failures - other Entities (Module, ShapeField, etc.) cannot
        return hasattr(value, 'is_struct') and self.engine.is_fail(value)

    def __repr__(self):
        """Return string representation showing frame depth.
        
        Returns:
            str: Formatted string with depth and node
        """
        depth = 0
        frame = self
        while frame.previous:
            depth += 1
            frame = frame.previous
        return f"_Frame(depth={depth}, node={self.node!r})"

