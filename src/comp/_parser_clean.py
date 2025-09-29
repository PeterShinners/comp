"""
Clean parser and transformer for Comp language.

Simple, consistent design with minimal complexity.
Uses the clean AST nodes for consistent naming and structure.
"""

__all__ = ["parse"]

from pathlib import Path

from lark import Lark, Transformer, ParseError as LarkParseError

from ._ast_clean import (
    ParseError,
    Number,
    String,
    Identifier,
    Placeholder,
    FieldName,
    TagRef,
    ShapeRef,
    FunctionRef,
    Structure,
    Block,
    Pipeline,
    BinaryOp,
    UnaryOp,
    FieldAccess,
)

# Global parser instance
_lark_parser: Lark | None = None


def _get_parser() -> Lark:
    """Get the singleton Lark parser instance."""
    global _lark_parser
    if _lark_parser is None:
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        _lark_parser = Lark(
            grammar_path.read_text(encoding="utf-8"),
            parser="lalr",
            transformer=CompTransformer(),
        )
    return _lark_parser


def parse(text: str):
    """Parse Comp code and return an AST node."""
    try:
        parser = _get_parser()
        return parser.parse(text)
    except LarkParseError as e:
        raise ParseError(str(e)) from e


class CompTransformer(Transformer):
    """Thin transformer that routes Lark trees to AST node fromLark methods."""
    
    # Numbers - route tokens directly to Number.fromLark
    def DECIMAL(self, token):
        return Number.fromLark(token)
    
    def BASED(self, token):
        return Number.fromLark(token)
    
    # Strings - route tokens directly to String.fromLark
    def SINGLE_STRING(self, token):
        return String.fromLark(token)
    
    def DOUBLE_STRING(self, token):
        return String.fromLark(token)
    
    def MULTILINE_STRING(self, token):
        return String.fromLark(token)
    
    # Basic tokens
    def TOKEN(self, token):
        return Identifier.fromLark(token)
    
    def field_name(self, children):
        return FieldName.fromLark(children)
    
    # Placeholder
    def PLACEHOLDER(self, token):
        return Placeholder()
    
    # References
    def tag_reference(self, children):
        return TagRef.fromLark(children)
    
    def shape_reference(self, children):
        return ShapeRef.fromLark(children)
    
    def function_reference(self, children):
        return FunctionRef.fromLark(children)
    
    # Structures
    def structure(self, children):
        return Structure.fromLark(children)
    
    def block(self, children):
        return Block.fromLark(children)
    
    # Operations
    def binary_op(self, children):
        return BinaryOp.fromLark(children)
    
    def unary_op(self, children):
        return UnaryOp.fromLark(children)
    
    def field_access(self, children):
        return FieldAccess.fromLark(children)
    
    # Pipeline operations with specific operators
    def pipeline_fallback(self, children):
        return Pipeline(children[0], "??", children[1])
    
    def pipeline_pipe(self, children):
        return Pipeline(children[0], "|", children[1])
    
    def pipeline_block_invoke(self, children):
        return Pipeline(children[0], "|>", children[1])
    
    def pipeline_op(self, children):
        return Pipeline.fromLark(children)