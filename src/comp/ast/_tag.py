"""Ast nodes for tags"""

__all__ = [
    "TagChild",
    "TagBody",
    "TagDef",
    "TagRef",
]

from . import _node
import comp


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
        if self.value:
            parts.append(self.value.unparse())
        if self.body:
            parts.append(self.body.unparse())
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


class TagDef(_node.Node):
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
        if self.generator:
            parts.append(self.generator.unparse())
        if self.assign_op:
            parts.append(self.assign_op)
        if self.value:
            parts.append(self.value.unparse())
        if self.body:
            parts.append(self.body.unparse())
        return " ".join(parts)

    @classmethod
    def from_grammar(cls, tree):
        """Parse TagDef from Lark tree using rule aliases."""
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


class TagRef(_node.BaseRef):
    """Tag reference: #path"""
    SYMBOL = "#"

