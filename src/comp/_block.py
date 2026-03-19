"""Function definitions, callables, and pipelines."""

import comp


__all__ = ["Block", "Callable", "Pipeline", "create_blockdef"]


class Block:
    """A single function body — the unit of computation in Comp.

    A Block is always contained inside a Callable when stored as a Value.
    It is never wrapped in Value directly.

    Attributes:
        qualified: (str) Fully qualified name (e.g. "add", "tree-insert")
        module: (Module | None) The module that defined this block
        pure: (bool) Block has no side effects
        input_shape: (Shape | None) Shape constraint for input
        input_name: (str | None) Parameter name for piped input binding
        arg_name: (str | None) Parameter name for arguments binding
        arg_shape: (Shape | None) Shape for argument validation/masking
        dispatch_set_name: (str | None) Base name for Forward overload lookup
        body: (object) AST node for function body
        body_instructions: (list) Compiled bytecode for the body
        closure_env: (dict) Captured environment from definition site
        captured_dollar_vars: (dict) Captured dollar variables ($, $$, $$$)
        signature_cop: (Value) Original signature COP node
        param_names: (list) Names from signature.param nodes for env binding
        dependency_names: (list) Names from signature.depend nodes for env binding
        dependency_shape: (Shape | None) Shape used to validate incoming dependency values
        deliver_specs: (list) Outgoing dependency declarations for the next pipeline stage
    """

    __slots__ = (
        "qualified",
        "module",
        "pure",
        "input_shape",
        "input_name",
        "arg_name",
        "arg_shape",
        "dispatch_set_name",
        "body",
        "body_instructions",
        "closure_env",
        "captured_dollar_vars",
        "signature_cop",
        "param_names",
        "dependency_names",
        "dependency_shape",
        "deliver_specs",
    )

    def __init__(self, qualified):
        self.qualified = qualified
        self.module = None
        self.pure = False
        self.input_shape = None
        self.input_name = None
        self.arg_name = None
        self.arg_shape = None
        self.dispatch_set_name = None
        self.body = None
        self.body_instructions = None
        self.closure_env = {}
        self.captured_dollar_vars = {}
        self.signature_cop = None
        self.param_names = []
        self.dependency_names = []
        self.dependency_shape = None
        self.deliver_specs = []

    def __repr__(self):
        return f"Block<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))

    def format(self):
        """Format as literal string representation.

        Returns:
            (str) Formatted function like "decide(~num)" or "(...)"
        """
        sig = []
        if self.input_shape:
            sig.append(f"~{self.input_shape.qualified}")
        if self.pure:
            sig.append("pure")

        body_parts = []
        if self.body:
            body_str = comp.cop_unparse(self.body)
            if body_str.startswith("(") and body_str.endswith(")"):
                body_str = body_str[1:-1]
            if len(body_str) > 20:
                body_str = body_str[:17] + "..."
            body_parts.append(body_str)

        sig_str = " ".join(sig)
        body_str = " ".join(body_parts)

        name = self.qualified or ""
        if name and name != "anonymous":
            inner = f"{sig_str} {body_str}".strip() if sig_str or body_str else ""
            return f"{name}({inner})" if inner else f"{name}()"
        inner = f"{sig_str} {body_str}".strip() if sig_str or body_str else ""
        return f"({inner})" if inner else "()"


class Callable:
    """A collection of invokable entries sharing a name.

    This is the primary Value data type for namespace references. It
    collects one or more Blocks, InternalCallables, and/or Definitions
    (dispatched by morph score), an optional Shape (including tags), and
    an optional Pipeline.

    Namespace Callables hold Definition entries (lazy, not yet built).
    Runtime Callables hold Block/InternalCallable entries (ready to run).
    These two states are mutually exclusive in practice.

    Attributes:
        qualified: (str) Base qualified name for this callable
        entries: (list) Block, InternalCallable, or Definition instances
        shape: (Shape | Tag | None) Single shape or tag reference
        pipeline: (Pipeline | None) Single pipeline reference
    """

    __slots__ = ("qualified", "entries", "shape", "pipeline")

    def __init__(self, qualified):
        self.qualified = qualified
        self.entries = []
        self.shape = None
        self.pipeline = None

    def add(self, entry):
        """Append a Block, InternalCallable, or Definition to this callable."""
        self.entries.append(entry)

    def scalar(self):
        """Return the single entry if exactly one and no pipeline, else None."""
        if len(self.entries) == 1 and self.pipeline is None:
            return self.entries[0]
        return None

    def has_pending(self):
        """Return True if all entries are unresolved Definitions.

        Used to detect namespace Callables that need to be built before
        they can be invoked.
        """
        return bool(self.entries) and all(isinstance(e, comp.Definition) for e in self.entries)

    def invokables(self):
        """Return list of invokable Definitions (blocks, funcs, shapes), or None if ambiguous.

        Returns a list of Definition objects that are invokable (shape, block, or func
        definitions).  Returns None when the set contains conflicting non-invokable types
        or more than one shape definition.
        """
        shapes = [d for d in self.entries if d.shape is comp.shape_shape]
        blocks = [
            d for d in self.entries
            if d.shape is comp.shape_block
        ]
        if len(shapes) > 1:
            return None
        if len(blocks) + len(shapes) != len(self.entries):
            return None
        return shapes + blocks

    def __repr__(self):
        parts = []
        if self.entries:
            parts.append(f"{len(self.entries)} entries")
        if self.shape:
            parts.append(f"shape={self.shape}")
        if self.pipeline:
            parts.append("pipeline")
        detail = ", ".join(parts) if parts else "empty"
        return f"Callable<{self.qualified}: {detail}>"

    def format(self):
        """Format for display."""
        if self.entries:
            names = [getattr(b, "qualified", getattr(b, "name", "?")) for b in self.entries]
            return f"callable({', '.join(names)})"
        if self.shape:
            return f"callable(~{getattr(self.shape, 'qualified', str(self.shape))})"
        if self.pipeline:
            return "callable([...])"
        return f"callable({self.qualified})"


class Pipeline:
    """A reified pipeline that can be stored and invoked.

    Created from deferred pipeline syntax :[a | b | c].
    Kept as a distinct type (not compiled into Block) so pipelines
    can be introspected and potentially rewritten in the future.

    Attributes:
        body_cop: (Value) The pipeline COP node
        body_instructions: (list | None) Compiled bytecode
        closure_env: (dict) Captured environment from definition site
        captured_dollar_vars: (dict) Captured dollar variables
    """

    __slots__ = ("body_cop", "body_instructions", "closure_env", "captured_dollar_vars")

    def __init__(self, body_cop):
        self.body_cop = body_cop
        self.body_instructions = None
        self.closure_env = {}
        self.captured_dollar_vars = {}

    def __repr__(self):
        return "Pipeline<[...]>"

    def format(self):
        """Format for display."""
        if self.body_cop:
            body_str = comp.cop_unparse(self.body_cop)
            if len(body_str) > 30:
                body_str = body_str[:27] + "..."
            return f"[{body_str}]"
        return "[...]"


def create_blockdef(qualified_name, cop_node):
    """Create a Block from a value.block COP node.

    This is a pure initialization function that doesn't depend on Module or Interp.

    Args:
        qualified_name: (str) Fully qualified function name (e.g. "add")
        cop_node: (Struct) The value.block COP node

    Returns:
        (Block) Initialized block with signature and body set

    Raises:
        CodeError: If cop_node is not a value.block node
    """
    # Validate node type
    tag_value = cop_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "value.block":
        raise comp.CodeError(
            f"Expected value.block node, got {tag.qualified if isinstance(tag, comp.Tag) else type(tag)}",
            cop_node
        )

    block = Block(qualified_name)

    # value.block kids: signature (block.signature), body
    kids = comp.cop_kids(cop_node)
    signature_cop = kids[0] if len(kids) > 0 else None
    body_cop = kids[1] if len(kids) > 1 else None

    if signature_cop:
        block.signature_cop = signature_cop
        sig_fields = comp.cop_kids(signature_cop)
        for field in sig_fields:
            field_name = field.to_python("name")
            if field_name == "pure":
                block.pure = True

    block.body = body_cop
    return block