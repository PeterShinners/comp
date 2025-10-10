"""Engine for evaluating AST nodes with scope stack architecture.

The Engine provides scope management for AST node coordination.
Scopes are used for both variable bindings and parent→child coordination.

The engine doesn't know about language semantics - it just provides primitives.
AST nodes orchestrate everything using these tools.
"""

from contextlib import contextmanager

from .value import Value


class Engine:
    """Evaluation engine with scope stack.

    The engine is a toolkit for AST nodes. It provides:
    - Scope stack for variable bindings and coordination
    - Execution orchestration via run()

    Scopes are used for both:
    1. Variable bindings: @local, $in, $out, $mod, etc.
    2. Coordination: struct_accumulator, identifier, etc.

    The engine doesn't know about:
    - What identifiers are
    - What fields mean
    - Function call semantics
    - Pipeline stages
    - Tag dispatching

    AST nodes implement all language semantics using engine primitives.
    """

    def __init__(self):
        """Initialize engine with empty stacks.

        No default scopes - the caller must set up appropriate scopes
        for the execution context (module, function, pipeline, etc.).
        This prevents incorrect scope access and allows different
        entry points to provide exactly what they need.
        """
        # Active scopes (containers for variable bindings and coordination)
        # Caller must populate with appropriate scopes for context
        # Example: {'local': Value({}), 'mod': Value({})}
        self.scopes = {}

        # Scope stack for lexical scoping and coordination (list of scope binding dicts)
        # Each frame is {'scope_name': Value(...), ...}
        # Used for both variable bindings and parent→child coordination
        self._scope_stack = []

        # Failure handling
        from .value import FAIL
        self.fail_tag = FAIL

        # Stack of generators ignoring failures (most recent at end)
        # Padded with None so we can always safely check [-1]
        # Generators here will receive fail values via send()
        self._generators_allowing_failures = [None]

        # Current generator being evaluated (set by run_stackless)
        self._current_generator = None

    # === Scope Setup ===

    def set_scope(self, name: str, value: Value):
        """Set a scope by name.

        This is used to set up the execution environment before running code.

        Args:
            name: Scope name ('local', 'mod', 'in', 'out', 'ctx', etc.)
            value: Value to use as the scope (usually a struct)
        """
        self.scopes[name] = value

    # === Scope Operations ===

    def get_scope(self, name: str) -> Value | None:
        """Get a scope by name.

        Searches scope stack from innermost to outermost, then falls back
        to default scopes. This implements lexical scoping.

        Args:
            name: Scope name ('local', 'in', 'out', 'ctx', 'mod', etc.)

        Returns:
            Value containing the scope, or None if not found
        """
        # Search stack frames (innermost to outermost)
        for frame in reversed(self._scope_stack):
            if name in frame:
                return frame[name]

        # Fall back to default scopes
        return self.scopes.get(name)

    def set_scope_field(self, scope_name: str, field_key: str | Value, value: Value):
        """Set a field in a scope.

        This mutates the scope Value's struct. Used for variable assignment.

        Args:
            scope_name: Name of scope to modify
            field_key: Field key (will be wrapped in Value if string)
            value: Value to assign

        Raises:
            RuntimeError: If scope doesn't exist or isn't a struct
        """
        scope = self.get_scope(scope_name)
        if scope is None:
            raise RuntimeError(f"Scope {scope_name!r} not found")

        if not scope.is_struct:
            raise RuntimeError(f"Scope {scope_name!r} is not a struct")

        # Ensure field_key is a Value
        if isinstance(field_key, str):
            field_key = Value(field_key)

        # Mutate the scope's struct
        scope.struct[field_key] = value

    @contextmanager
    def scope_frame(self, **bindings: Value):
        """Create a new scope frame.

        Used for both variable bindings and parent→child coordination.

        Examples:
            # Variable bindings
            with engine.scope_frame(local=new_local, in=input_val):
                result = yield body

            # Coordination (accumulators, current values, etc.)
            with engine.scope_frame(struct_accumulator=Value({})):
                result = yield field

        Args:
            **bindings: Scope bindings for this frame

        Yields:
            None (just provides context manager)
        """
        # Push frame
        self._scope_stack.append(bindings)
        try:
            yield
        finally:
            # Pop frame (automatic cleanup even if generator abandoned)
            self._scope_stack.pop()

    @contextmanager
    def allow_failures(self):
        """Allow current generator to receive fail values via send().

        This allows nodes like fallback operators to receive and handle
        fail values instead of having them propagate immediately.

        Usage (in a node's evaluate method):
            with engine.allow_failures():
                left = yield self.left

            if engine._is_fail(left):
                return (yield self.right)
            return left

        While in the context, the current generator is pushed onto the
        ignoring stack. When a child evaluation produces a fail, it will be
        sent to this generator (if it's the most recent) instead of propagating.

        Yields:
            None (just provides context manager)
        """
        # Push current generator onto ignoring stack
        gen = self._current_generator
        self._generators_allowing_failures.append(gen)
        try:
            yield
        finally:
            # Pop from stack when context exits
            self._generators_allowing_failures.pop()

    # === Execution ===

    def run_recursive(self, node):
        """Run a node and return its result.

        This is the main entry point for evaluation. It handles the generator
        protocol: yielding children, sending results back, getting final result.

        Args:
            node: AST node to evaluate

        Returns:
            Final Value result from node evaluation
        """
        # Start the generator
        gen = node.evaluate(self)

        # Drive it to completion
        result = None
        try:
            # Get first yielded child (or StopIteration if node returns immediately)
            child = next(gen)

            while True:
                # Recursively evaluate the child
                child_result = self.run(child)

                # Send result back to parent, get next child
                child = gen.send(child_result)

        except StopIteration as e:
            # Generator returned - this is the final result
            result = e.value

        return result


    def run_stackless(self, node):
        """Run a node and return its result (stackless version).

        This is the main entry point for evaluation. It handles the generator
        protocol: yielding children, sending results back, getting final result.

        Unlike the recursive version, this manages an explicit stack of generators,
        avoiding Python's recursion limit and making execution state visible.

        Fail values immediately stop processing UNLESS the parent generator
        is in an allow_failures() context, in which case the fail is sent
        to it via send().

        Args:
            node: AST node to evaluate

        Returns:
            Final Value result from node evaluation
        """
        result = ...  # Set by first StopIteration before use
        result_is_fail = False

        generators = [newest := node.evaluate(self)]
        while generators:
            try:
                # Get and track current generator for who called allow_failures()
                gen = self._current_generator = generators[-1]

                # Failures bypass generators that don't allow them
                if result_is_fail and gen is not self._generators_allowing_failures[-1]:
                    gen.close()
                    generators.pop()
                    continue

                # Check if we're about to send a fail to an allowing generator
                # (need to check BEFORE send() since send is synchronous and may exit context)
                will_clear_fail = result_is_fail and gen is not newest and gen is self._generators_allowing_failures[-1]

                # Advance generator
                child = next(gen) if gen is newest else gen.send(result)

                # Clear the fail flag if we successfully sent it to an allowing generator
                if will_clear_fail:
                    result_is_fail = False

                generators.append(newest := child.evaluate(self))

            except StopIteration as e:
                result = e.value
                result_is_fail = self.is_fail(result)
                generators.pop()

        # Clear tracking
        self._current_generator = None
        self._generators_allowing_failures = [None]

        return result

    run = run_stackless

    # === Failure Handling ===

    def fail(self, message: str, fail_tag = None) -> Value:
        """Create a failure value.

        Args:
            message: Error message
            fail_tag: Tag for the failure type (defaults to engine.fail_tag)

        Returns:
            Value representing the failure
        """
        if fail_tag is None:
            fail_tag = self.fail_tag

        return Value(message, tag=fail_tag)

    def is_fail(self, value):
        """Check if a value is a fail value."""
        return value.tag == self.fail_tag


class ScopeFrame:
    """Context manager for scope frames.

    This is created by engine.scope_frame() and handles push/pop.
    Separated into its own class for clarity (though contextmanager works too).
    """

    def __init__(self, engine: Engine, bindings: dict[str, Value]):
        self.engine = engine
        self.bindings = bindings

    def __enter__(self):
        self.engine._scope_stack.append(self.bindings)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.engine._scope_stack.pop()
        return False  # Don't suppress exceptions
