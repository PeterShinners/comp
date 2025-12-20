"""Function definitions and operations"""

import comp


__all__ = ["FuncDef", "Func", "Block"]


class FuncDef:
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
        return f"FuncDef<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


class Func:
    """Reference to a Function definition.

    To use a function as a value there must be a reference to its definition.
    The reference stores additional information about where it came from
    and how it was named.

    Args:
        qualified: (str) Fully qualified name of the function
        namespace: (str) The name of the namespace used to reference this function
    """

    __slots__ = ("definition",)

    def __init__(self, definition):
        self.definition = definition

    def __repr__(self):
        suffix = self.definition.module.token if self.definition.module.token else ""
        return f"Func({self.definition.qualified}/{suffix})"


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
