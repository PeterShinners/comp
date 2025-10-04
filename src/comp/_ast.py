"""
AST node definitions for Comp language

This module defines a simplified Abstract Syntax Tree for the Comp language.

"""

__all__ = [
    "ParseError",
    "AstNode",
    "Root",
    "Module",
    "Number",
    "String",
    "BinaryOp",
    "UnaryOp",
    "Structure",
    "Block",
    "StructAssign",
    "StructUnnamed",
    "StructSpread",
    "Identifier",
    "ScopeField",
    "TokenField",
    "IndexField",
    "ComputeField",
    "StringField",
    "FieldAccess",
    "Placeholder",
    "Pipeline",
    "EmptyPipelineSeed",
    "PipeFallback",
    "PipeStruct",
    "PipeBlock",
    "PipeFunc",
    "PipeWrench",
    "TagRef",
    "ShapeRef",
    "FuncRef",
    "TagChild",
    "TagBody",
    "TagDefinition",
    "ShapeDefinition",
    "ShapeField",
    "ShapeSpread",
    "ShapeUnion",
    "ShapeInline",
    "MorphOp",
]

import decimal


class ParseError(Exception):
    """Exception raised for parsing errors."""

    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        super().__init__(f"Parse error: {message}")


class AstNode:
    """Base class for all AST nodes."""

    def __init__(self, kids: list["AstNode"] | None = None):
        """Initialize node with arbitrary attributes.

        The 'kids' attribute should be a list of child AstNode objects.
        Other attributes are node-specific (value, op, path, etc.).

        Args:
            kids: List of child nodes
            _lark_tree: Internal - Lark tree to extract position info from
        """
        self.kids = list(kids) if kids else []
        self.position = (None, None)

    def __repr__(self):
        """Compact representation showing type and key attributes."""
        attrs = []
        if self.kids:
            attrs.append(f'*{len(self.kids)}')
        for key, value in self.__dict__.items():
            if key not in ('kids', 'position'):
                attrs.append(f'{key}={value!r}')
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    def tree(self, indent=0):
        """Print tree structure."""
        print(f"{'  '*indent}{self!r}")
        for kid in self.kids:
            kid.tree(indent + 1)

    def find(self, node_type):
        """Find first descendant of given type, including self."""
        if isinstance(self, node_type):
            return self
        for kid in self.kids:
            if result := kid.find(node_type):
                return result
        return None

    def find_all(self, node_type):
        """Find all descendants of given type, including self."""
        results = [self] if isinstance(self, node_type) else []
        for kid in self.kids:
            results.extend(kid.find_all(node_type))
        return results

    def matches(self, other) -> bool:
        """Hierarchical comparison of AST structure.

        Compares node types, attributes (excluding position), and recursively
        compares all children. Useful for testing round-trip parsing.

        Args:
            other: Another AstNode to compare against

        Returns:
            True if nodes have same type, attributes, and children structure
        """
        # Must be same type
        if not isinstance(other, type(self)):
            return False

        # Must have same number of children
        if len(self.kids) != len(other.kids):
            return False

        # Compare all attributes except kids and position
        for key in self.__dict__:
            if key in ('kids', 'position'):
                continue
            if key not in other.__dict__:
                return False
            if self.__dict__[key] != other.__dict__[key]:
                return False

        # Check other doesn't have extra attributes
        for key in other.__dict__:
            if key in ('kids', 'position'):
                continue
            if key not in self.__dict__:
                return False

        # Recursively compare all children
        for self_kid, other_kid in zip(self.kids, other.kids, strict=True):
            if not self_kid.matches(other_kid):
                return False

        return True

    def unparse(self) -> str:
        """Convert back to Comp source representation."""
        return "???"

    @classmethod
    def fromGrammar(cls, lark_tree):
        """Create node from Lark parse tree.

        Default implementation for nodes that just need to collect children.
        Override for nodes with specific parsing logic.
        """
        return cls()


class Root(AstNode):
    """Root of grammar Ast for expressions."""
    def unparse(self) -> str:
        return " ".join(kid.unparse() for kid in self.kids)


class Module(AstNode):
    """Root of grammar Ast for modules.

    Contains module-level statements like tag definitions, function definitions,
    imports, and potentially expressions (for REPL/testing compatibility).
    """
    @property
    def statements(self) -> list['AstNode']:
        """Access module statements (alias for kids)."""
        return self.kids

    def unparse(self) -> str:
        return "\n".join(kid.unparse() for kid in self.kids)


# === MODULE-LEVEL DEFINITIONS ===


class TagChild(AstNode):
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
    def fromGrammar(cls, tree):
        kids = tree.children
        tokens = [t.value for t in kids[0].children[1].children[::2]]
        assign_op = _tokenValue(kids, 1, "")
        self = cls(tokens=tokens, assign_op=assign_op)
        self._valIdx, self._bodIdx = _enumMatches(kids, 'tag_value', 'tag_body')
        return self


class TagBody(AstNode):
    def unparse(self):
        tags = " ".join(t.unparse() for t in self.kids)
        return f"{{{tags}}}"


class TagDefinition(AstNode):
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
    def fromGrammar(cls, tree):
        """Parse TagDefinition from Lark tree."""
        kids = tree.children
        tokens = [t.value for t in kids[1].children[1].children[::2]]
        assign_op = _tokenValue(kids, 2, "")
        self = cls(tokens=tokens, assign_op=assign_op)
        self._genIdx, self._valIdx, self._bodIdx = _enumMatches(kids, 'tag_generator', 'tag_value', 'tag_body')
        return self


class ShapeDefinition(AstNode):
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
        if len(self.kids) == 2 and isinstance(self.kids[0], (ShapeRef, TagRef)):
            # Alias with default: !shape ~one = ~num=1
            return f"!shape {shape_path} = {self.kids[0].unparse()}={self.kids[1].unparse()}"

        # Check if this is a simple alias or union (single child that's a type reference/union)
        if len(self.kids) == 1 and isinstance(self.kids[0], (ShapeRef, TagRef)):
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
    def fromGrammar(cls, tree):
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


class FunctionDefinition(AstNode):
    """Function definition at module level.

    Examples:
        !func |add ~num ^{a ~num b ~num} = {a + b}
        !func |process ~data = {data | validate | transform}
        !func |greet ~nil ^greeting = {"Hello " + name}

    The function name is stored as a list of tokens (e.g., ["add"] or ["math", "add"]).
    The shape is always present (use ~nil if no input needed).
    The args is always a Structure node (may be empty if no arguments).
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
        """Get the args structure (second child, always present)."""
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
    def fromGrammar(cls, tree):
        tokens = [t.value for t in tree.children[1].children[1::2]]
        assign_op = tree.children[-2].value
        self = cls(tokens=tokens, assign_op=assign_op)

        self._argIdx, = _enumMatches(tree.children, 'arg_shape', offset=1)
        self._bodIdx = -1
        return self


class ShapeField(AstNode):
    """Single field in a shape definition.

    Examples:
        x ~num
        y ~num = 0
        email? ~str
        pos ~{x ~num y ~num}

    Attributes:
        name: Field name (e.g., "x", "email")
        optional: Whether field has ? suffix (from TOKEN like "email?")
        type_ref: Optional child node for the type (ShapeRef, TagRef, inline shape, etc.)
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
    def fromGrammar(cls, tree):
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


class ShapeSpread(AstNode):
    """Shape spread in definition: ..~shape

    Examples:
        ..~point
        ..~base

    The spread type is stored as the first child (usually a ShapeRef).
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
    def fromGrammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_spread: SPREAD shape_type
        """
        return cls()


class ShapeUnion(AstNode):
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
    def fromGrammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_union: shape_type_atom (PIPE shape_type_atom)+
        """
        return cls()


class ShapeInline(AstNode):
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
    def fromGrammar(cls, tree):
        """Parse from Lark tree.

        Grammar: shape_type_atom: TILDE LBRACE shape_field* RBRACE
        """
        return cls()


class MorphOp(AstNode):
    """Shape morph operation: expr ~shape, expr ~* shape, expr ~? shape

    Transforms a value to match a shape specification.

    Examples:
        data ~point
        {x=1 y=2 z=3} ~* point-2d
        partial ~? user

    Children:
        [0] - Expression to morph
        [1] - Shape type (ShapeRef, ShapeUnion, ShapeInline, etc.)
    """

    def __init__(self, mode: str = "normal"):
        """Initialize morph operation.

        Args:
            mode: "normal" (~), "strong" (~*), or "weak" (~?)
        """
        self.mode = mode
        super().__init__()

    @property
    def expr(self):
        """The expression being morphed (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def shape(self):
        """The target shape (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        """Unparse morph operation back to source code."""
        if len(self.kids) != 2:
            return "<?morph?>"

        expr_str = self.expr.unparse()

        # Handle different shape type formats
        if isinstance(self.shape, ShapeUnion):
            # For unions, keep ~ on each member: val ~cat | ~dog
            shape_str = " | ".join(kid.unparse() for kid in self.shape.kids)
            # Union already has ~ on members, so we need special formatting
            if self.mode == "strong":
                return f"{expr_str} ~* {shape_str}"
            elif self.mode == "weak":
                return f"{expr_str} ~? {shape_str}"
            else:
                # For normal morph with union, no ~ prefix (members have it)
                return f"{expr_str} {shape_str}"
        else:
            # Single shape reference or inline shape
            shape_str = self.shape.unparse()
            # Strip leading ~ since it's part of our operator
            if (isinstance(self.shape, (ShapeRef, ShapeInline)) and
                shape_str.startswith("~")):
                shape_str = shape_str[1:]

            if self.mode == "strong":
                return f"{expr_str} ~* {shape_str}"
            elif self.mode == "weak":
                return f"{expr_str} ~? {shape_str}"
            else:
                # Normal morph - no space between ~ and shape
                return f"{expr_str} ~{shape_str}"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree.

        Grammar:
            morph_expr TILDE shape_type -> morph_op
            morph_expr STRONG_MORPH shape_type -> strong_morph_op
            morph_expr WEAK_MORPH shape_type -> weak_morph_op
        """
        # Mode determined by which grammar rule matched
        mode = "normal"
        if tree.data == "strong_morph_op":
            mode = "strong"
        elif tree.data == "weak_morph_op":
            mode = "weak"

        return cls(mode=mode)


# === LITERALS ===


class Number(AstNode):
    """Numeric literal."""

    def __init__(self, value: decimal.Decimal = decimal.Decimal(0)):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return str(self.value)

    @classmethod
    def fromGrammar(cls, tree):
        """Parse number from Lark tree: number -> INTBASE | DECIMAL"""
        token = tree.children[0]
        try:
            if token.type == "INTBASE":
                python_int = int(token.value, 0)  # Auto-detect base
                value = decimal.Decimal(python_int)
            else:  # DECIMAL
                value = decimal.Decimal(token.value)
            return cls(value=value)
        except (ValueError, decimal.InvalidOperation) as e:
            raise ParseError(f"Invalid number: {token.value}") from e


class String(AstNode):
    """String literal."""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        # Use repr() for proper escaping, but force double quotes
        # repr() may choose single quotes if the string contains double quotes,
        # so we need to handle that case
        r = repr(self.value)
        if r.startswith("'"):
            # repr chose single quotes, convert to double quotes
            # Remove outer single quotes and escape inner double quotes
            # Must also unescape single quotes since \' is not valid in double-quoted strings
            inner = r[1:-1].replace('"', '\\"').replace("\\'", "'")
            return f'"{inner}"'
        else:
            # Already using double quotes
            return r

    @classmethod
    def fromGrammar(cls, tree):
        """Parse string from Lark tree: string -> QUOTE content? QUOTE"""
        import ast as python_ast

        kids = tree.children
        # kids: [QUOTE, content, QUOTE] or [QUOTE, QUOTE] for empty string
        if len(kids) == 3:
            # Use Python's ast.literal_eval to decode escape sequences
            # Wrap the content in quotes to make it a valid Python string literal
            raw_value = kids[1].value
            python_string = f'"{raw_value}"'
            try:
                decoded = python_ast.literal_eval(python_string)
            except (ValueError, SyntaxError) as e:
                # Check if this is a unicode escape error
                error_msg = str(e)
                if "unicode" in error_msg.lower() or "escape" in error_msg.lower():
                    raise ParseError(f"Invalid unicode escape sequence in string: {error_msg}") from e
                # For other errors, keep the raw value
                decoded = raw_value
            return cls(value=decoded)
        else:
            return cls(value="")


class BinaryOp(AstNode):
    """Binary operation."""

    def __init__(self, op: str = "?"):
        self.op = op
        super().__init__()

    @property
    def left(self):
        return self.kids[0]

    @property
    def right(self):
        return self.kids[1]

    def unparse(self) -> str:
        # Escape quotes and backslashes
        left = self.left.unparse()
        if isinstance(self.left, BinaryOp):
            left = f"({left})"
        right = self.right.unparse()
        if isinstance(self.right, BinaryOp):
            right = f"({right})"
        return f'{left} {self.op} {right}'

    @classmethod
    def fromGrammar(cls, tree):
        """Parse binary operation from Lark tree."""
        return cls(tree.children[1].value)


class UnaryOp(AstNode):
    """Unary operation."""

    def __init__(self, op: str = ""):
        self.op = op
        super().__init__()

    @property
    def right(self):
        return self.kids[0]

    def unparse(self) -> str:
        right = self.right.unparse()
        if isinstance(self.right, BinaryOp):
            right = f"({right})"
        return f'{self.op}{right}'

    @classmethod
    def fromGrammar(cls, tree):
        """Parse string from Lark tree: string -> QUOTE content? QUOTE"""
        return cls(tree.children[0].value)


# === STRUCTURES ===


class Structure(AstNode):
    """Structure literal: { ... }"""

    def unparse(self) -> str:
        if not self.kids:
            return "{}"
        items = " ".join(kid.unparse() for kid in self.kids)
        return f"{{{items}}}"


class Block(Structure):
    """Block literal: :{ ... }"""

    def unparse(self) -> str:
        return ":" + super().unparse()


class StructAssign(AstNode):
    """Structure assignment: key = value"""

    def __init__(self, op: str = "="):
        self.op = op
        super().__init__()

    @property
    def key(self):
        """The key/identifier (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def value(self):
        """The assigned value (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        # First kid is the identifier/key, second is the value
        if len(self.kids) >= 2:
            key = self.key.unparse()
            value = self.value.unparse()
            return f"{key} {self.op} {value}"
        return "??? = ???"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: structure_assign -> _qualified _assignment_op expression"""
        kids = tree.children
        op_token = next((k for k in kids if hasattr(k, 'type')), None)
        return cls(op=op_token.value if op_token else '=')


class StructUnnamed(AstNode):
    """Structure unnamed value: expression"""

    @property
    def value(self):
        """The unnamed value expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return self.value.unparse()
        return "???"


class StructSpread(AstNode):
    """Structure spread: ..expression"""

    @property
    def value(self):
        """The spread expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"..{self.value.unparse()}"
        return "..???"


# === IDENTIFIERS AND FIELDS ===


class TokenField(AstNode):
    """Token field: simple name like 'foo' or 'bar-baz'"""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: tokenfield -> TOKEN"""
        return cls(value=tree.children[0].value)


class IndexField(AstNode):
    """Index field: #0, #1, #2, etc."""

    def __init__(self, value: int = 0):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return f"#{self.value}"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: indexfield -> INDEXFIELD"""
        return cls(value=int(tree.children[0].value[1:]))


class ComputeField(AstNode):
    """Computed field: 'expression' in single quotes"""

    @property
    def expr(self):
        """The computed expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"'{self.expr.unparse()}'"
        return "'???'"


class Identifier(AstNode):
    """Identifier: chain of fields like foo.bar or @foo.bar or foo."baz".#0"""

    def unparse(self) -> str:
        if not self.kids:
            return "???"

        tokens = [kid.unparse() for kid in self.kids]
        if len(tokens) >= 2 and tokens[0] in ("@", "^"):
            tokens[:2] = [tokens[0] + tokens[1]]
        return ".".join(tokens)


class ScopeField(AstNode):
    """Scope marker field: @, ^, or $name - used as first field in an Identifier"""

    def __init__(self, value: str = "@"):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: localscope/argscope/namescope"""
        if tree.data == 'localscope':
            return cls(value="@")
        elif tree.data == 'argscope':
            return cls(value="^")
        elif tree.data == 'namescope':
            # kids[0] is namescope, kids[1] should be TOKEN
            return cls(value="$" + tree.children[1].value)


class StringField(String):
    """String literal used in an identifier"""


class FieldAccess(AstNode):
    """Field access on an expression: (expr).field"""

    def unparse(self) -> str:
        return ".".join(kid.unparse() for kid in self.kids)


# === PLACEHOLDER ===


class Placeholder(AstNode):
    """Placeholder: ??? for unknown values"""

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        return "???"


# === PIPELINES ===


class EmptyPipelineSeed(AstNode):
    """Placeholder for pipelines without an explicit seed expression.

    Used when a pipeline starts with a pipe operator like ( |process)
    rather than having an explicit seed value like (data |process).
    This ensures Pipeline.kids[0] is always the seed expression.
    """

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        return ""


class Pipeline(AstNode):
    """Pipeline expression: expr | op1 | op2

    The first child (kids[0]) is always the seed expression. If no explicit
    seed is provided, an EmptyPipelineSeed node is inserted automatically.
    Remaining children are PipelineOp subclasses (PipeFunc, PipeFallback, etc).
    """

    @property
    def seed(self):
        """The seed expression (first child, may be EmptyPipelineSeed)."""
        return self.kids[0] if self.kids else None

    @property
    def operations(self):
        """List of pipeline operations (all children after seed)."""
        return self.kids[1:] if len(self.kids) > 1 else []

    def unparse(self) -> str:
        # Skip EmptyPipelineSeed in output, but include other seeds
        parts = []
        for i, kid in enumerate(self.kids):
            if i == 0 and isinstance(kid, EmptyPipelineSeed):
                continue
            parts.append(kid.unparse())

        value = " ".join(parts)
        # Pipelines now use square brackets
        return f"[{value}]"

    @classmethod
    def fromGrammar(cls, tree):
        """Create Pipeline node, inserting EmptyPipelineSeed if needed.

        Scans the lark tree to check if the first child is a pipe operation.
        If so, inserts an EmptyPipelineSeed as the first child before the
        tree is walked.

        The tree passed is:
        - 'pipeline_expr': LBRACKET pipeline RBRACKET or LBRACKET expression pipeline RBRACKET
        """
        node = cls()

        # pipeline_expr has either:
        # 1. LBRACKET, pipeline, RBRACKET (no seed - starts with pipe op)
        # 2. LBRACKET, expression, pipeline, RBRACKET (has seed)

        # Skip token children (LBRACKET, RBRACKET) and find the first non-token child
        children = [c for c in tree.children if hasattr(c, 'data')]

        if children:
            first_child = children[0]
            # Check if first child is a pipeline (contains pipe operations)
            if first_child.data == 'pipeline':
                # No seed - pipeline starts immediately
                # Insert EmptyPipelineSeed
                node.kids.append(EmptyPipelineSeed())
            # Otherwise, first child is the seed expression, no EmptyPipelineSeed needed

        return node
class PipelineOp(AstNode):
    """Shared base class for all pipeline operators."""


class PipeFallback(PipelineOp):
    """Pipe fallback: |? expr"""

    @property
    def fallback(self):
        """The fallback expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|? {self.fallback.unparse()}"
        return "|? ???"


class PipeStruct(PipelineOp):
    """Pipe struct: |{ ops }"""

    def unparse(self) -> str:
        if self.kids:
            items = " ".join(kid.unparse() for kid in self.kids)
            return f"|{{{items}}}"
        return "|{ }"


class PipeBlock(PipelineOp):
    """Pipe block: |: qualified"""

    @property
    def block(self):
        """The block identifier (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|: {self.block.unparse()}"
        return "|: ???"


class PipeFunc(PipelineOp):
    """Pipe function: | func args"""

    @property
    def func(self):
        """The function reference (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def args(self):
        """The function arguments structure (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        if self.args and self.args.kids:
            return f"{self.func.unparse()} {self.args.unparse()[1:-1]}"
        else:
            return f"{self.func.unparse()}"


class PipeWrench(PipelineOp):
    """Pipe wrench: |-| func"""

    @property
    def wrench(self):
        """The wrench function reference (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|-| {self.wrench.unparse()}"
        return "|-| ???"


# === REFERENCES ===


class _BaseRef(AstNode):
    """Base class for references: TagRef, ShapeRef, FuncRef"""
    SYMBOL = "?"
    def __init__(self, tokens:list[str]|None=None, namespace:str|None=None):
        self.tokens = tokens
        self.namespace = namespace
        super().__init__()

    def unparse(self) -> str:
        path = ".".join(self.tokens)
        full = "/".join((path, self.namespace)) if self.namespace else path
        return f"{self.SYMBOL}{full}"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: tag_reference -> "#" _reference_path"""
        tokens = []
        namespace = None
        for token in tree.children[1].children:
            value = token.value
            if value != ".":
                tokens.append(value)
        if len(tree.children) > 2:
            namespace = tree.children[2].children[1].value
        return cls(tokens=tuple(tokens), namespace=namespace)


class TagRef(_BaseRef):
    """Tag reference: #path"""
    SYMBOL = "#"


class ShapeRef(_BaseRef):
    """Shape reference: ~path"""
    SYMBOL = "~"


class FuncRef(_BaseRef):
    """Function reference: |path"""
    SYMBOL = "|"


def _maybe_unparse(parts, val):
    """Add unparsed value to array if not None"""
    if val is not None:
        parts.append(val.unparse())


def _enumMatches(kids, *rules, offset=0):
    """Find ordering of optional rules in tree children"""
    ruleCount = len(rules)
    found = [None] * ruleCount
    rule = 0
    count = 0
    # print("MATCHES:", rules, len(kids), kids)
    for kid in kids:
        data = getattr(kid, 'data', None)
        # print("  KID:", data, rule, count)
        for hunt in range(rule, ruleCount):
            if data == rules[hunt]:
                rule = hunt + 1
                found[hunt] = count
                # print("MATCH:", hunt, found)
                count += 1
                break
        if rule >= ruleCount:
            break
    found = [f + offset if f is not None else None for f in found]
    return found


def _tokenValue(kids, offset=0, default=None):
    """Find first token value in tree children after offset"""
    for kid in kids[offset:]:
        if hasattr(kid, 'type'):
            return kid.value
    return default
