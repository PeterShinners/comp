"""Function definitions and operations"""

import comp


__all__ = ["Func", "Block", "create_funcdef"]


class Func:
    """A function definition.

    Functions are the primary unit of computation in comp. They transform
    an input value to an output value, optionally taking an argument.

    Args:
        qualified: (str) Fully qualified function name
        private: (bool) Function is private to its module

    Attributes:
        qualified: (str) Fully qualified function name
        module: (Module | None) The module that defined this function
        private: (bool) Function is private to its module
        pure: (bool) Function has no side effects
        input_name: (str | None) Name for the input value
        input_shape: (Shape) Shape constraint for input
        arg_name: (str | None) Name for the argument
        arg_shape: (Shape) Shape constraint for argument
        body: (object) AST node for function body
    """

    __slots__ = (
        "qualified",
        "private",
        "module",
        "pure",
        "entry",
        "input_name",
        "input_shape",
        "arg_name",
        "arg_shape",
        "body",
    )

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.private = private
        self.module = None
        self.pure = False
        self.input_name = None
        self.input_shape = None
        self.arg_name = None
        self.arg_shape = None
        self.body = None

    def __repr__(self):
        return f"Func<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


class Block:
    """Executable block value.

    A block is generated in functions and captures the scopes that defined them.

    Args:
        frame: (Frame) Captured frame of definer
        shape: (Shape) Shape of block input value
        identifier: (str) Generated identifier for block
        body: (object) AST node for block body
    """

    __slots__ = (
        "frame",
        "shape",
        "identifier",
        "body",
    )

    def __init__(self, frame, shape, identifier, body):
        self.frame = frame
        self.shape = shape
        self.identifier = identifier
        self.body = body

    def __repr__(self):
        return f"Block<{self.identifier}>"


def create_funcdef(qualified_name, private, cop_node):
    """Create a Func from a value.block COP node and wrap in a Value.

    This is a pure initialization function that doesn't depend on Module or Interp.

    Args:
        qualified_name: (str) Fully qualified function name (e.g., "add.i001")
        private: (bool) Whether function is private
        cop_node: (Struct) The value.block COP node

    Returns:
        Value: Initialized function definition wrapped in a Value with cop attribute set

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

    # Create Func
    func_def = Func(qualified_name, private)

    # TODO: Parse block signature and body from cop_node
    # For now, store the COP node for later processing
    func_def.body = cop_node

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(func_def)
    value.cop = cop_node

    return value
