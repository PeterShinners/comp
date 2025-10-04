"""
AST node definitions for Comp language

This module defines a simplified Abstract Syntax Tree for the Comp language.

"""

__all__ = [
    "Module",
    "TagChild",
    "TagBody",
    "TagDefinition",
    "FunctionDefinition",
    "ShapeDefinition",
    "ShapeField",
    "ShapeSpread",
    "ShapeUnion",
    "ShapeInline",
]

from . import _ast, _node, _mod


class Module(_node.Node):
    """Root of grammar Ast for modules.

    Contains module-level statements like tag definitions, function definitions,
    imports, and potentially expressions (for REPL/testing compatibility).
    """
    @property
    def statements(self) -> list['_node.Node']:
        """Access module statements (alias for kids)."""
        return self.kids

    def unparse(self) -> str:
        return "\n".join(kid.unparse() for kid in self.kids)



class TagChild(_node.Node):
    """Nested tag child in a tag hierarchy (no !tag prefix)."""

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        self._valIdx = self._bodIdx = None
        super().__init__()

    @property
    def value(self):
        return self.kids[self._valIdx] if self._valIdx is not None else None

    @property
    def body(self):
        return self.kids[self._bodIdx] if self._bodIdx is not None else None

    @property
    def body_kids(self):
        """Get all children after the assignment (value + body children)."""
        kids = []
        if self.value is not None:
            kids.append(self.value)
        body = self.body
        if body:
            kids.extend(body.kids)
        return kids

    def unparse(self) -> str:
        parts = ["#" + ".".join(self.tokens)]
        if self.assign_op:
            parts.append(self.assign_op)
        _maybe_unparse(parts, self.value)
        _maybe_unparse(parts, self.body)
        return " ".join(parts)

    @classmethod
    def from_grammar(cls, tree):
        """Parse TagChild from Lark tree using rule aliases."""
        kids = tree.children
        tokens = [t.value for t in kids[0].children[1].children[::2]]

        # Determine structure based on rule alias
        # After walk, kids will contain: [value?, body?] in order
        match tree.data:
            case 'tagchild_simple':
                # tag_path
                # Kids after walk: []
                self = cls(tokens=tokens, assign_op="")
                self._valIdx = self._bodIdx = None

            case 'tagchild_val_body':
                # tag_path ASSIGN tag_value tag_body
                # Kids after walk: [value, body]
                # ASSIGN is at tree.children[1]
                assign_op = kids[1].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._valIdx = 0
                self._bodIdx = 1

            case 'tagchild_val':
                # tag_path ASSIGN tag_value
                # Kids after walk: [value]
                # ASSIGN is at tree.children[1]
                assign_op = kids[1].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._valIdx = 0
                self._bodIdx = None

            case 'tagchild_body':
                # tag_path ASSIGN tag_body
                # Kids after walk: [body]
                # ASSIGN is at tree.children[1]
                assign_op = kids[1].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._valIdx = None
                self._bodIdx = 0

            case _:
                raise ValueError(f"Unknown tag_child variant: {tree.data}")

        return self


class TagBody(_node.Node):
    def unparse(self):
        tags = " ".join(t.unparse() for t in self.kids)
        return f"{{{tags}}}"


class TagDefinition(_node.Node):
    """Tag definition at module level (with !tag prefix)."""

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        self._genIdx = self._valIdx = self._bodIdx = None
        super().__init__()

    @property
    def generator(self):
        return self.kids[self._genIdx] if self._genIdx is not None else None

    @property
    def value(self):
        return self.kids[self._valIdx] if self._valIdx is not None else None

    @property
    def body(self):
        return self.kids[self._bodIdx] if self._bodIdx is not None else None

    @property
    def body_kids(self):
        """Get all children after the assignment (value + body children)."""
        kids = []
        if self.value is not None:
            kids.append(self.value)
        body = self.body
        if body:
            kids.extend(body.kids)
        return kids

    def unparse(self) -> str:
        parts = ["!tag", "#" + ".".join(self.tokens)]
        _maybe_unparse(parts, self.generator)
        if self.assign_op:
            parts.append(self.assign_op)
        _maybe_unparse(parts, self.value)
        _maybe_unparse(parts, self.body)
        return " ".join(parts)

    @classmethod
    def from_grammar(cls, tree):
        """Parse TagDefinition from Lark tree using rule aliases."""
        kids = tree.children
        tokens = [t.value for t in kids[1].children[1].children[::2]]

        # Determine structure based on rule alias
        # After walk, kids will contain: [generator?, value?, body?] in order
        match tree.data:
            case 'tag_simple':
                # BANG_TAG tag_path
                # Kids after walk: []
                self = cls(tokens=tokens, assign_op="")
                self._genIdx = self._valIdx = self._bodIdx = None

            case 'tag_gen_val_body':
                # BANG_TAG tag_path tag_generator ASSIGN tag_value tag_body
                # Kids after walk: [generator, value, body]
                # ASSIGN is at tree.children[3]
                assign_op = kids[3].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = 0
                self._valIdx = 1
                self._bodIdx = 2

            case 'tag_gen_val':
                # BANG_TAG tag_path tag_generator ASSIGN tag_value
                # Kids after walk: [generator, value]
                # ASSIGN is at tree.children[3]
                assign_op = kids[3].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = 0
                self._valIdx = 1
                self._bodIdx = None

            case 'tag_gen_body':
                # BANG_TAG tag_path tag_generator ASSIGN tag_body
                # Kids after walk: [generator, body]
                # ASSIGN is at tree.children[3]
                assign_op = kids[3].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = 0
                self._valIdx = None
                self._bodIdx = 1

            case 'tag_val_body':
                # BANG_TAG tag_path ASSIGN tag_value tag_body
                # Kids after walk: [value, body]
                # ASSIGN is at tree.children[2]
                assign_op = kids[2].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = None
                self._valIdx = 0
                self._bodIdx = 1

            case 'tag_val':
                # BANG_TAG tag_path ASSIGN tag_value
                # Kids after walk: [value]
                # ASSIGN is at tree.children[2]
                assign_op = kids[2].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = None
                self._valIdx = 0
                self._bodIdx = None

            case 'tag_body_only':
                # BANG_TAG tag_path ASSIGN tag_body
                # Kids after walk: [body]
                # ASSIGN is at tree.children[2]
                assign_op = kids[2].value
                self = cls(tokens=tokens, assign_op=assign_op)
                self._genIdx = None
                self._valIdx = None
                self._bodIdx = 0

            case _:
                raise ValueError(f"Unknown tag_definition variant: {tree.data}")

        return self


class ShapeDefinition(_node.Node):
    """Shape definition at module level.

    Examples:
        !shape ~point = {x ~num y ~num}
        !shape ~point = {x ~num = 0 y ~num = 0}
        !shape ~user = {name ~str email? ~str}
        !shape ~circle = {pos ~{x ~num y ~num} radius ~num}
        !shape ~point3d = {..~point z ~num}
        !shape ~result = ~success | ~error

    The shape name is stored as a list of tokens (e.g., ["point"] or ["geo", "point"]).
    The body can be a structure-like definition, a type reference, or a union.
    Children can be ShapeField, ShapeSpread, or other shape type nodes.
    """

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        """Initialize shape definition.

        Args:
            tokens: List of shape path components (e.g., ["point"] or ["geo", "point"])
            assign_op: Assignment operator used ("=", "=?", "=*")
        """
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        super().__init__()

    def unparse(self) -> str:
        shape_path = "~" + ".".join(self.tokens)

        if not self.kids:
            # Shape with no body (shouldn't happen in valid code)
            return f"!shape {shape_path}"

        # Check if this is an alias with default (2 kids: type + default expression)
        if len(self.kids) == 2 and isinstance(self.kids[0], (_ast.ShapeRef, _ast.TagRef)):
            # Alias with default: !shape ~one = ~num=1
            return f"!shape {shape_path} = {self.kids[0].unparse()}={self.kids[1].unparse()}"

        # Check if this is a simple alias or union (single child that's a type reference/union)
        if len(self.kids) == 1 and isinstance(self.kids[0], (_ast.ShapeRef, _ast.TagRef)):
            # Simple alias: !shape ~number = ~num
            return f"!shape {shape_path} = {self.kids[0].unparse()}"

        # Check if single child is a union or other shape_type expression
        if len(self.kids) == 1 and not isinstance(self.kids[0], (ShapeField, ShapeSpread)):
            # Union or complex type: !shape ~result = ~success | ~error
            return f"!shape {shape_path} = {self.kids[0].unparse()}"

        # Definition with fields: !shape ~point = {x ~num y ~num}
        fields_str = " ".join(kid.unparse() for kid in self.kids)
        return f"!shape {shape_path} = {{{fields_str}}}"

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_definition: BANG_SHAPE shape_path ASSIGN shape_body

        shape_path: "~" reference_identifiers
        shape_body: LBRACE shape_field* RBRACE | shape_type
        """
        # tree.children: [BANG_SHAPE, shape_path, ASSIGN, shape_body]
        shape_path_tree = tree.children[1]
        assign_op_token = tree.children[2]
        shape_body_tree = tree.children[3]

        # shape_path -> "~" reference_identifiers
        reference_identifiers = shape_path_tree.children[1]  # Skip "~" token

        # Extract tokens from reference_identifiers (TOKEN ("." TOKEN)*)
        tokens = []
        for child in reference_identifiers.children:
            if hasattr(child, 'value') and child.value != ".":
                tokens.append(child.value)

        # Extract assignment operator string
        assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)

        return cls(tokens=tokens, assign_op=assign_op)


class FunctionDefinition(_node.Node):
    """Function definition at module level.

    Examples:
        !func |add ~num ^{a ~num b ~num} = {a + b}
        !func |process ~data = {data | validate | transform}
        !func |greet ~nil ^~greeting-args = {"Hello " + name}
        !func |validate ~data ^~validator = {data | check}

    The function name is stored as a list of tokens (e.g., ["add"] or ["math", "add"]).
    The shape is always present (use ~nil if no input needed).
    The args can be any shape_type: shape reference (~args), inline shape (~{...}), 
    tag reference (#tag), or union. It may be None if no arguments defined.
    The assignment_op can be "=", "=*", or "=?" for different assignment semantics.
    """

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        """Initialize function definition.

        Args:
            tokens: List of function path components (e.g., ["add"] or ["math", "add"])
            assign_op: Assignment operator used ("=", "=*", "=?")
        """
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        self._argIdx = self._bodIdx = None
        super().__init__()

    @property
    def name(self):
        """Get the function name as a dotted string (for compatibility)."""
        return ".".join(self.tokens)

    @property
    def shape(self):
        """Get the input shape (first child, always present)."""
        return self.kids[0] if self.kids else None

    @property
    def args(self):
        """Get the args shape (can be shape reference, inline shape, etc., or None)."""
        return self.kids[self._argIdx] if self._argIdx is not None else None

    @property
    def body(self):
        """Get the function body structure (third child, always present)."""
        return self.kids[self._bodIdx] if self._bodIdx is not None else None

    def unparse(self) -> str:
        parts = ["!func", "|" + ".".join(self.tokens)]
        _maybe_unparse(parts, self.shape)
        args = self.args
        if args:
            parts.append("^" + args.unparse())
        if self.assign_op:
            parts.append(self.assign_op)
        _maybe_unparse(parts, self.body)
        return " ".join(parts)

    @classmethod
    def from_grammar(cls, tree):
        """Parse from grammar tree using rule aliases to distinguish cases."""
        tokens = [t.value for t in tree.children[1].children[1::2]]

        if tree.data == "func_with_args":
            # After walk, kids will be: [shape, args, body]
            assign_op_token = tree.children[4]  # Get from tree before walk
            assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)
            self = cls(tokens=tokens, assign_op=assign_op)
            self._argIdx = 1  # args is second in kids
            self._bodIdx = 2  # body is third in kids
        else:  # func_no_args
            # After walk, kids will be: [shape, body]
            assign_op_token = tree.children[3]  # Get from tree before walk
            assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)
            self = cls(tokens=tokens, assign_op=assign_op)
            self._argIdx = None  # No args
            self._bodIdx = 1  # body is second in kids

        return self


class ShapeField(_node.Node):
    """Single field in a shape definition.

    Examples:
        x ~num
        y ~num = 0
        email? ~str
        pos ~{x ~num y ~num}

    Attributes:
        name: Field name (e.g., "x", "email")
        optional: Whether field has ? suffix (from TOKEN like "email?")
        type_ref: Optional child node for the type (_ast.ShapeRef, _ast.TagRef, inline shape, etc.)
        default: Optional child node for default value expression
    """

    def __init__(self, name: str | None = "", optional: bool = False):
        """Initialize shape field.

        Args:
            name: Field name (None for positional fields, "" or string for named fields)
            optional: Whether field is optional (has ? suffix)
        """
        self.name = name
        self.optional = optional
        super().__init__()

    @property
    def type_ref(self):
        """First child is the type reference (if present)."""
        return self.kids[0] if self.kids else None

    @property
    def default(self):
        """Second child is the default value (if present)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        """Unparse shape field back to source code."""
        # Positional fields (no name) start with type directly
        if self.name is None:
            result = ""
        else:
            result = self.name
            # Note: optional ? is already part of the name token
            # (TOKEN regex includes optional trailing ?)

        if self.type_ref:
            if result:  # Named field: add space before type
                result += f" {self.type_ref.unparse()}"
            else:  # Positional field: no space, just type
                result = self.type_ref.unparse()

        if self.default:
            result += f" = {self.default.unparse()}"

        return result

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.

        Grammar:
            shape_field_def: TOKEN QUESTION? shape_type? (ASSIGN expression)?  // Named field
                           | shape_type (ASSIGN expression)?          // Positional field (no name)
        """
        children = tree.children

        # Check if first child is a TOKEN (named field) or shape_type (positional field)
        first_child = children[0] if children else None

        if first_child and hasattr(first_child, 'type') and first_child.type == 'TOKEN':
            # Named field: first child is TOKEN
            name = first_child.value
            # Check if name ends with ? (optional field)
            optional = name.endswith('?')
            return cls(name=name, optional=optional)
        else:
            # Positional field: no name token, starts with shape_type
            # Return field with empty name to indicate positional
            return cls(name=None, optional=False)


class ShapeSpread(_node.Node):
    """Shape spread in definition: ..~shape

    Examples:
        ..~point
        ..~base

    The spread type is stored as the first child (usually a _ast.ShapeRef).
    """

    def __init__(self):
        """Initialize shape spread."""
        super().__init__()

    @property
    def shape_type(self):
        """The shape type being spread (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        """Unparse shape spread back to source code."""
        if self.shape_type:
            return f"..{self.shape_type.unparse()}"
        return ".."

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_spread: SPREAD shape_type
        """
        return cls()


class ShapeUnion(_node.Node):
    """Union of shape types: ~type1 | ~type2 | ~type3

    Examples:
        ~success | ~error
        ~num | ~str | ~bool
        ~point | ~{x ~num y ~num}

    All union members are stored as children. The union is always flat,
    not nested (a | b | c becomes one ShapeUnion with 3 children).
    """

    def __init__(self):
        """Initialize shape union."""
        super().__init__()

    def unparse(self) -> str:
        """Unparse shape union back to source code."""
        if not self.kids:
            return "???"
        return " | ".join(kid.unparse() for kid in self.kids)

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_union: shape_type_atom (PIPE shape_type_atom)+
        """
        return cls()


class ShapeInline(_node.Node):
    """Inline anonymous shape definition: ~{...fields...}

    Examples:
        ~{x ~num y ~num}
        ~{name ~str age ~num = 0}
        ~{id ~str ..~timestamped}

    Children are ShapeField and ShapeSpread nodes.
    """

    def __init__(self):
        """Initialize inline shape."""
        super().__init__()

    def unparse(self) -> str:
        """Unparse inline shape back to source code."""
        if not self.kids:
            return "~{}"
        fields = " ".join(kid.unparse() for kid in self.kids)
        return f"~{{{fields}}}"

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_type_atom: TILDE LBRACE shape_field* RBRACE
        """
        return cls()


def _maybe_unparse(parts, val):
    """Add unparsed value to array if not None"""
    if val is not None:
        parts.append(val.unparse())
