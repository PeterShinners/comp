"""Function definitions and operations"""

import comp


__all__ = ["Block", "create_blockdef"]


class Block:
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
        frame: (ExecutionFrame | None) Closure frame from defining scope
        decorators: (list) Decorators to apply to evaluation
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
        "frame",
        "decorators",
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
        self.frame = None
        self.decorators = []

    def __repr__(self):
        return f"Block<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))

    def format(self):
        """Format function as literal string representation.

        Returns:
            (str) Formatted function like ":a b (|val x)" or ":()"
        """
        sig = []
        if self.input_name:
            input = self.input_name
            if self.input_shape:
                shape_str = comp.cop_unparse(self.input_shape)
                if shape_str != "~()":
                    input += f"~{shape_str}"
            sig.append(input)
        if self.arg_name:
            arg = self.arg_name
            if self.arg_shape:
                shape_str = comp.cop_unparse(self.arg_shape)
                if shape_str != "~()":
                    arg += f"~{shape_str}"
            sig.append(arg)
        if self.pure:
            sig.append("pure")

        # Format body with decorators
        body_parts = []
        dec_parts = []
        for dec in self.decorators:
            dec_ident = comp.cop_unparse(dec)
            dec_parts.append(f"|{dec_ident}")
        body_parts.append("".join(dec_parts))

        if self.body:
            body_str = comp.cop_unparse(self.body)
            # Remove outer parentheses from struct.define
            if body_str.startswith("(") and body_str.endswith(")"):
                body_str = body_str[1:-1]
            if len(body_str) > 20:
                body_str = body_str[:17] + "..."
            body_parts.append(body_str)

        sig_str = " ".join(sig)
        body_str = " ".join(body_parts)
        return f":{sig_str}({body_str})"


def create_blockdef(qualified_name, private, cop_node):
    """Create a Block from a value.block COP node and wrap in a Value.

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

    # Create Block
    block = Block(qualified_name, private)

    # Parse signature and body from block
    # value.block has kids: s=shape.define (signature) and b=struct.define (body)
    kids = comp.cop_kids(cop_node)
    signature_cop = kids[0] if len(kids) > 0 else None
    body_cop = kids[1] if len(kids) > 1 else None

    # Parse signature to extract parameter names and shapes
    if signature_cop:
        sig_fields = comp.cop_kids(signature_cop)
        for field in sig_fields:
            field_name = field.to_python("name")
            if field_name == "pure":
                block.pure = True
            # elif field_name == "private":
            #     block.private = True
            else:
                field_kids = comp.cop_kids(field)
                if block.input_name is None:
                    block.input_name = field_name
                    block.input_shape = field_kids[0] if field_kids else None
                else:
                    block.arg_name = field_name
                    block.arg_shape = field_kids[0] if field_kids else None

    # Extract decorators from body (leading struct.decorator nodes)
    # and separate them from the actual body
    if body_cop:
        body_kids = list(comp.cop_kids(body_cop))
        for body_start, kid in enumerate(body_kids, 1):
            if comp.cop_tag(kid) == "struct.decorator":
                # Extract decorator identifier
                dec_kids = comp.cop_kids(kid)
                block.decorators.append(dec_kids[0])
            else:
                break

        # Create new body without decorators if we found any
        # Ugh, this is miserable and clumsy, needs to be elegent
        if block.decorators:
            # Reconstruct struct.define with remaining kids
            body_dict = dict(body_cop.data)
            # Remove old kids and create new kids list
            remaining_kids = body_kids[body_start:]
            if remaining_kids:
                # Build new kids struct
                new_kids = {}
                for kid in remaining_kids:
                    new_kids[comp.Unnamed()] = kid
                body_dict[comp.Value.from_python("kids")] = comp.Value.from_python(new_kids)
            else:
                # Empty body
                body_dict[comp.Value.from_python("kids")] = comp.Value.from_python({})
            block.body = comp.Value.from_python(body_dict)
        else:
            block.body = body_cop
    else:
        block.body = None

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(block)
    value.cop = cop_node

    return value
