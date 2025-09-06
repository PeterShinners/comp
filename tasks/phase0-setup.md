# Phase 0: Foundation Setup Tasks

## Overview
Set up the basic project infrastructure and parse minimal Comp expressions.

## Task List

### 1. Project Setup
- [ ] Create directory structure
- [ ] Initialize git repository
- [ ] Create virtual environment
- [ ] Install dependencies: `lark`, `pytest`, `attrs`
- [ ] Create `setup.py` or `pyproject.toml`

### 2. AST Node Design
Create `src/comp/ast_nodes.py`:

```python
from dataclasses import dataclass
from typing import Any, List, Optional

@dataclass
class ASTNode:
    """Base class for all AST nodes"""
    pass

@dataclass
class NumberLiteral(ASTNode):
    value: float

@dataclass
class StringLiteral(ASTNode):
    value: str
    
@dataclass
class StructLiteral(ASTNode):
    fields: List['Field']

@dataclass
class Field(ASTNode):
    name: Optional[str]
    value: ASTNode
```

### 3. Lark Grammar Definition
Create `src/comp/grammar.lark`:

```lark
// Minimal grammar for Phase 0
start: expression

expression: struct
          | number
          | string
          | identifier

struct: "{" field_list? "}"

field_list: field ("," field)*

field: (IDENTIFIER "=")? expression

number: SIGNED_NUMBER

string: ESCAPED_STRING

identifier: IDENTIFIER

// Terminals
IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
SIGNED_NUMBER: /[+-]?\d+(\.\d+)?/
ESCAPED_STRING: /"([^"\\]|\\.)*"/

// Ignore whitespace and comments
%import common.WS
%ignore WS
COMMENT: "//" /[^\n]*/
%ignore COMMENT
```

### 4. Parser Wrapper
Create `src/comp/parser.py`:

```python
from lark import Lark, Transformer
from pathlib import Path
from .ast_nodes import *

class CompTransformer(Transformer):
    """Transform Lark parse tree to Comp AST"""
    
    def number(self, items):
        return NumberLiteral(float(items[0]))
    
    def string(self, items):
        # Remove quotes
        return StringLiteral(items[0][1:-1])
    
    def struct(self, items):
        fields = items[0] if items else []
        return StructLiteral(fields)
    
    def field(self, items):
        if len(items) == 2:  # Named field
            return Field(name=str(items[0]), value=items[1])
        else:  # Unnamed field
            return Field(name=None, value=items[0])

def create_parser():
    grammar_path = Path(__file__).parent / "grammar.lark"
    return Lark(
        grammar_path.read_text(),
        parser='lalr',
        transformer=CompTransformer()
    )
```

### 5. Basic Tests
Create `tests/test_parser.py`:

```python
import pytest
from comp.parser import create_parser
from comp.ast_nodes import *

@pytest.fixture
def parser():
    return create_parser()

def test_parse_number(parser):
    ast = parser.parse("42")
    assert isinstance(ast, NumberLiteral)
    assert ast.value == 42

def test_parse_string(parser):
    ast = parser.parse('"hello"')
    assert isinstance(ast, StringLiteral)
    assert ast.value == "hello"

def test_parse_empty_struct(parser):
    ast = parser.parse("{}")
    assert isinstance(ast, StructLiteral)
    assert len(ast.fields) == 0

def test_parse_struct_with_fields(parser):
    ast = parser.parse("{x=1 y=2}")
    assert isinstance(ast, StructLiteral)
    assert len(ast.fields) == 2
    assert ast.fields[0].name == "x"
    assert ast.fields[1].name == "y"
```

### 6. Pretty Printer
Create `src/comp/pretty.py`:

```python
from .ast_nodes import *

def pretty_print(node, indent=0):
    """Pretty print AST for debugging"""
    prefix = "  " * indent
    
    if isinstance(node, NumberLiteral):
        return f"{prefix}Number({node.value})"
    elif isinstance(node, StringLiteral):
        return f'{prefix}String("{node.value}")'
    elif isinstance(node, StructLiteral):
        if not node.fields:
            return f"{prefix}Struct{{}}"
        fields_str = "\n".join(
            pretty_print_field(f, indent+1) for f in node.fields
        )
        return f"{prefix}Struct{{\n{fields_str}\n{prefix}}}"
    # Add more node types as needed
```

### 7. Main Entry Point
Create `src/comp/__main__.py`:

```python
import sys
from .parser import create_parser
from .pretty import pretty_print

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m comp <expression>")
        sys.exit(1)
    
    parser = create_parser()
    try:
        ast = parser.parse(sys.argv[1])
        print(pretty_print(ast))
    except Exception as e:
        print(f"Parse error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Testing

Run tests:
```bash
pytest tests/test_parser.py -v
```

Test manually:
```bash
python -m comp "42"
python -m comp '{"hello"}'
python -m comp '{x=1 y=2}'
```

## Success Criteria

Phase 0 is complete when:
- [ ] Can parse numbers: `42`, `-3.14`
- [ ] Can parse strings: `"hello"`, `"world"`
- [ ] Can parse empty struct: `{}`
- [ ] Can parse struct with named fields: `{x=1 y=2}`
- [ ] Can parse struct with unnamed fields: `{1 2 3}`
- [ ] All tests pass
- [ ] Pretty printer shows AST structure

## Next Steps

Once Phase 0 is complete, move to Phase 1:
- Add pipeline operator (`->`)
- Add spread operator (`...`)
- Add variable bindings
- Begin evaluation