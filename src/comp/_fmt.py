"""Format text parsing and value formatting for the fmt builtin.

Provides accessible building blocks for format text processing so each
layer can be tested, extended, or replaced independently.

Public API
----------
parse_format_text(s)      → list[str | FmtToken]
resolve_fmt_ref(val, ref)   → Value
format_fmt_value(val, spec) → str
apply_format(parsed, val)   → str

Token syntax in a format text
---------------------------------
  %()       whole input value
  %(#N)     Nth unnamed (positional) field of the input, 1-based
  %(name)   named field 'name' of the input

Anything outside a token is literal text.
"""

import re
import comp
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FmtRef:
    """A reference within a format token.

    Attributes:
        kind:  'input' | 'positional' | 'field'
        index: 1-based index for unnamed positional fields  (kind='positional')
        name:  field name text                            (kind='field')
    """
    kind: str
    index: Optional[int] = None
    name: Optional[str] = None


@dataclass
class FmtToken:
    """A substitution token extracted from a format text.

    Attributes:
        ref:  what to substitute (resolved via resolve_fmt_ref)
        spec: format specifier text — reserved for future formatting units,
              ignored for now
    """
    ref: FmtRef
    spec: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches %(inner) tokens.
_TOKEN_RE = re.compile(r'%\(([^)]*)\)')


def _parse_ref(inner: str) -> FmtRef:
    """Parse the text inside %(...) into a FmtRef."""
    inner = inner.strip()
    if not inner:
        return FmtRef('input')
    if inner.startswith('#'):
        rest = inner[1:]
        try:
            n = int(rest)
        except ValueError:
            raise comp.CodeError(f"fmt: invalid positional index {inner!r}")
        return FmtRef('positional', index=n)
    # Otherwise it's a named field reference
    return FmtRef('field', name=inner)


def parse_format_text(s: str) -> list:
    """Parse a format text into an ordered list of literals and FmtTokens.

    Returns a list where each element is either:
      str       — literal text to pass through unchanged
      FmtToken  — a substitution token to be resolved at runtime
    """
    result = []
    pos = 0
    for m in _TOKEN_RE.finditer(s):
        if m.start() > pos:
            result.append(s[pos:m.start()])
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        ref = _parse_ref(inner)
        result.append(FmtToken(ref=ref))
        pos = m.end()
    if pos < len(s):
        result.append(s[pos:])
    return result


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

def resolve_fmt_ref(input_val, ref: FmtRef):
    """Resolve a FmtRef to a Value drawn from input_val.

    Positional refs (#N, 1-based) count only unnamed struct fields.
    Field refs (name) look up by name in a struct.
    Input refs return the whole input_val.

    Raises comp.CodeError on invalid access.
    """
    if ref.kind == 'input':
        return input_val

    if ref.kind == 'positional':
        n = ref.index  # 1-based, unnamed fields only
        if input_val.shape is not comp.shape_struct:
            raise comp.CodeError(
                f"fmt: %(#{n}) requires a struct input, got {input_val.shape.qualified}"
            )
        count = 0
        for k, v in input_val.data.items():
            if isinstance(k, comp.Unnamed):
                count += 1
                if count == n:
                    return v
        raise comp.CodeError(
            f"fmt: no positional #{n} in value (has {count} unnamed fields)"
        )

    if ref.kind == 'field':
        if input_val.shape is not comp.shape_struct:
            raise comp.CodeError(
                f"fmt: %(name) requires a struct input, got {input_val.shape.qualified}"
            )
        try:
            return input_val.field(ref.name)
        except KeyError:
            raise comp.CodeError(f"fmt: field '{ref.name}' not found in value")

    raise comp.CodeError(f"fmt: unknown ref kind {ref.kind!r}")


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def format_fmt_value(val, spec: Optional[str] = None) -> str:
    """Convert a Value to a plain text for insertion into a format result.

    Text values are returned as-is (no surrounding quotes).
    Everything else uses Value.format(), which gives the natural Comp representation.

    The spec parameter is reserved for future formatting units and is currently
    ignored.
    """
    if val is None:
        return ""
    if val.shape is comp.shape_text:
        return val.data  # raw Python text, no enclosing quotes
    return val.format()


# ---------------------------------------------------------------------------
# Top-level apply
# ---------------------------------------------------------------------------

def apply_format(parsed: list, input_val) -> str:
    """Apply a parsed format text to input_val, returning the result text.

    parsed:    result of parse_format_text
    input_val: the Value piped into fmt
    """
    parts = []
    for segment in parsed:
        if isinstance(segment, str):
            parts.append(segment)
        else:  # FmtToken
            val = resolve_fmt_ref(input_val, segment.ref)
            parts.append(format_fmt_value(val, segment.spec))
    return "".join(parts)
