"""Engine for evaluating AST nodes with scope stack architecture.

The Engine provides scope management for AST node coordination.
Scopes are used for both variable bindings and parent→child coordination.

The engine doesn't know about language semantics - it just provides primitives.
AST nodes orchestrate everything using these tools.
"""

__all__ = ["Engine", "Compute"]

import comp.engine as comp
from . import _value, _function


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
        # Funcs and fail are temporarily stored here in the engine.
        # They have a future home elsewhere.
        # Function registry: name -> Function
        # Functions can be Python-implemented or Comp-defined
        self.functions = _function.create_builtin_functions()

        # Failure handling
        self.fail_tag = _value.FAIL

    # Function management is temporary until the module system can take over
    def get_function(self, name: str):
        """Look up a function by name.

        Args:
            name: Function name (without | prefix)

        Returns:
            Function object or None if not found
        """
        return self.functions.get(name)

    def register_function(self, func):
        """Register a function in the engine.

        Args:
            func: Function object with .name attribute
        """
        self.functions[func.name] = func

    def call_function(self, name: str, input_value: _value.Value, args: _value.Value | None = None):
        """Call a function by name.

        Args:
            name: Function name (without | prefix)
            input_value: Input value from pipeline
            args: Optional argument structure

        Returns:
            Value result or fail value
        """
        func = self.get_function(name)
        if func is None:
            return comp.fail(f"Unknown function: |{name}")

        return func(self, input_value, args)

    def run(self, node, **scopes):
        """Run a node and return its result (frame-based evaluation).

        This is the main entry point for evaluation. It handles the generator
        protocol: yielding children, sending results back, getting final result.

        The op generator builds a list of Frame objects describing the
        execution path while processing.

        Fail values immediately stop processing UNLESS the parent frame
        has allow_failures set, in which case the fail is sent to it via send().

        Args:
            node: AST node to evaluate
            scopes: Keyword arguments to define initial scopes

        Returns:
            Final Value result from node evaluation
        """
        result = _value.Value({})  # Set by first StopIteration before use
        result_is_fail = False  # Track if result contains a failure

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
                result.ast = current.node  # Minimal temporary tracking of source
                result_is_fail = current.is_fail(result)
                current = current.previous

        return result


    # Later this should become a more generic "engine skip these shapes"
    # but for not its hardcoded to failures
    def is_fail(self, value):
        """Check if a value is a fail value."""
        return value.tag == self.fail_tag


class Compute:
    """Request to evaluate a child AST node.

    This is yielded from `AstNode.evaluate` when further processing is requested.
    The engine receives this request and creates an internal _Frame to track execution.

    Args:
        node: AST node to evaluate (required)
        scopes: Scope bindings for this evaluation (optional)
        allow_failures: Whether this evaluation can receive fail values (default: False)
    """

    __slots__ = ('node', 'allow_failures', 'scopes')

    def __init__(self, node: 'comp.ast.AstNode', allow_failures: bool = False, **scopes):
        self.node = node
        self.scopes = {k.rstrip('_'): v for k, v in scopes.items()}
        self.allow_failures = allow_failures

    def __repr__(self):
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
        node: AST node being evaluated
        previous: Parent frame (None for root)
        scopes: Scope bindings for this frame (merged with parent)
        allow_failures: Whether this frame can receive failures
        engine: Engine reference for function registry and fail_tag
    """
    __slots__ = ('node', 'gen', 'previous', 'scopes', 'allowed', 'engine')

    def __init__(self, node, previous: '_Frame | None', scopes: dict, allow_failures: bool, engine: Engine):
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
        """Look up a scope value."""
        return self.scopes.get(key)

    def is_fail(self, value):
        """Check if a value is a fail value."""
        # TODO one day perform this operation without an engine reference
        return value.tag == self.engine.fail_tag

    def call_function(self, name: str, input_value, args=None):
        """Call a function by name."""
        # TODO one day move this to a module lookup (from the scope, not part of frame)
        func = self.engine.functions.get(name)
        if func is None:
            return comp.fail(f"Unknown function: |{name}")
        return func(self, input_value, args)

    def __repr__(self):
        depth = 0
        frame = self
        while frame.previous:
            depth += 1
            frame = frame.previous
        return f"_Frame(depth={depth}, node={self.node!r})"

