"""COB (Comp Object ASCII) serialization internal module.

Provides pack/unpack for Comp's native serialization format.
COB is valid Comp literal syntax — packed output can be read back
as Comp source code.

Restrictions:
- Handles are not allowed (detected via value.handles, instafail)
- Callables/blocks are not allowed (detected during walk, instafail)

Formatting:
- width=0  → compact, no whitespace
- width>0  → soft wrap target (default 80)
- indent   → indent string per level (default "  ")

String encoding:
- Always double-quoted
- \\ → \\\\, " → \\", newline → \\n, CR → \\r, tab → \\t
- No auto-switching to triple-quote (deferred)

Numbers:
- Decimal/Fraction use str() directly
- Preserves literal precision ("1.500" stays "1.500")

Tags and RawTags:
- Bare qualified name: bool.true, nil, unit.distance.meter

Units:
- value[unit]: 5[meter], "hello"[shell]

Null:
- nil  (built-in system tag, serializes as bare identifier)
"""

__all__ = []

import ast
import re

import lark
import comp


_IDENT_RE = re.compile(r"^[^\W\d][\w-]*\??$")


class _Packer:
    """Converts a Comp Value tree to COB text."""

    def __init__(self, width=80, indent="  "):
        self.width = width      # 0 = compact
        self.indent = indent
        self._depth = 0

    @property
    def _compact(self):
        return self.width == 0

    def pack(self, value):
        """Entry point. Returns COB string for value."""
        if value.handles:
            raise comp.CodeError(
                "cob.pack: value contains a handle and cannot be serialized"
            )
        return self._pack_value(value)

    def _pack_value(self, value):
        data = value.data

        if isinstance(data, comp.HandleInstance):
            raise comp.CodeError(
                "cob.pack: value contains a handle and cannot be serialized"
            )
        if isinstance(data, (comp.Callable, comp.InternalCallable)):
            raise comp.CodeError(
                "cob.pack: value contains a callable and cannot be serialized"
            )

        if isinstance(data, comp.Tag):
            result = data.qualified
        elif isinstance(data, comp.RawTag):
            result = data.qualified
        elif isinstance(data, tuple):
            result = comp.num_format(data)
        elif isinstance(data, str):
            result = self._pack_string(data)
        elif isinstance(data, dict):
            result = self._pack_struct(data)
        else:
            raise comp.CodeError(
                f"cob.pack: unexpected value type {type(data).__name__!r}"
            )

        # Attach unit tag if present
        if value.unit is not None:
            result = f"{result}[{value.unit.qualified}]"

        return result

    def _pack_string(self, s):
        escaped = (
            s
            .replace("\\", "\\\\")
            .replace('"',  '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'

    def _pack_key(self, k):
        """Pack a named struct field key as a bare identifier or quoted string."""
        if isinstance(k.data, str):
            key = k.data
            if _IDENT_RE.match(key):
                return key
            escaped = key.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        # Non-string key: wrap in single-quotes per Comp syntax
        return "'" + self._pack_value(k) + "'"

    def _pack_struct(self, data):
        if not data:
            return "{}"

        items = []
        for k, v in data.items():
            packed_v = self._pack_value(v)
            if isinstance(k, comp.Unnamed):
                items.append(packed_v)
            elif isinstance(k, comp.Value):
                packed_k = self._pack_key(k)
                items.append(f"{packed_k}={packed_v}")

        if self._compact:
            return "{" + " ".join(items) + "}"

        # Try fitting on a single line
        single = "{ " + " ".join(items) + " }"
        available = self.width - self._depth * len(self.indent)
        if len(single) <= available:
            return single

        # Multi-line
        self._depth += 1
        nl = "\n" + self.indent * self._depth
        body = nl.join(items)
        self._depth -= 1
        closing = "\n" + self.indent * self._depth
        return "{" + nl + body + closing + "}"


class _Unpacker(lark.Transformer):
    """Transforms a COB parse tree directly to Comp Value objects.

    All identifiers (single or dotted) become RawTag values.
    There is no module context — callers use morphing to resolve tags.
    """

    def start(self, items):
        return items[0]

    def cob_value(self, items):
        # items: [base_Value] or [base_Value, cob_tag_Value]
        # cob_tag_Value.data is RawTag; unit is attached via with_unit.
        base = items[0]
        if len(items) == 2:
            return base.with_unit(items[1].data)
        return base

    def cob_num(self, items):
        # items: [Value] or [Token('MINUS', '-'), Value]
        if len(items) == 1:
            return items[0]
        val = items[1]
        if isinstance(val.data, tuple):
            return comp.Value(comp.num_neg(val.data))
        raise comp.CodeError("cob.unpack: cannot negate a non-numeric value")

    def cob_fraction(self, items):
        # items: [Token(INTEGER), Token(INTEGER)]
        #     or [Token(MINUS), Token(INTEGER), Token(INTEGER)]
        token_ints = [t for t in items if isinstance(t, lark.Token) and t.type == "INTEGER"]
        negative = any(isinstance(t, lark.Token) and t.type == "MINUS" for t in items)
        num = int(str(token_ints[0]).replace("_", ""), 0)
        den = int(str(token_ints[1]).replace("_", ""), 0)
        if negative:
            num = -num
        return comp.Value(comp._make(num, den, 0))

    def cob_tag(self, items):
        # items: [Token(DOTTED_PATH | TOKENFIELD)]
        return comp.Value(comp.RawTag(str(items[0])))

    def cob_struct(self, items):
        # items: list of (key, value) tuples from cob_named_field / cob_pos_field
        result = {}
        for k, v in items:
            result[k] = v
        return comp.Value(result)

    def cob_named_field(self, items):
        # items: [key_str_from_cob_field_key, cob_value_result]
        # ("=" is anonymous → discarded)
        key_str = items[0]
        val = items[1]
        return (comp.Value(key_str), val)

    def cob_pos_field(self, items):
        return (comp.Unnamed(), items[0])

    def cob_field_key(self, items):
        token = items[0]
        if token.type == "STRING":
            return ast.literal_eval(str(token))
        return str(token)  # TOKENFIELD

    def text(self, items):
        result = ast.literal_eval(str(items[0]))
        if isinstance(result, bytes):
            result = result.decode("utf-8")
        return comp.Value(result)

    def number(self, items):
        token = items[0]
        s = str(token).replace("_", "")
        if token.type == "DECIMAL":
            return comp.Value(comp.num_from_decimal_str(s))
        # INTEGER — may be a base literal (0x, 0b, 0o)
        if s.lower().startswith(("0x", "0b", "0o")):
            return comp.Value((int(s, 0), 1, 0))
        return comp.Value((int(s), 1, 0))


@comp._internal.register_internal_module("cob")
def _create_cob_module(module):
    """COB: Comp Object ASCII format — pack and unpack."""

    def _pack(input_val, args_val, frame):
        """Serialize a Comp value to a COB string.

        Optional keyword args:
            width:  soft line-wrap target in columns; 0 = compact (default 80)
            indent: indent string per level (default "  ")

        Examples:
            $data | cob.pack
            $data | cob.pack {width=0}
            $data | cob.pack {width=120  indent="    "}
        """
        width = 80
        indent = "  "

        if isinstance(args_val.data, dict):
            for k, v in args_val.data.items():
                key = k.data if isinstance(k, comp.Value) else None
                if key == "width" and isinstance(v.data, tuple):
                    width = int(v.data[0] / v.data[1])
                elif key == "indent" and isinstance(v.data, str):
                    indent = v.data

        packer = _Packer(width=width, indent=indent)
        return comp.Value(packer.pack(input_val))

    def _unpack(input_val, args_val, frame):
        """Deserialize a COB string back to a Comp value.

        Identifiers and dotted names are returned as raw-tag values.
        Use morphing to resolve them to typed tags when a shape is known.

        Example:
            $text | cob.unpack
        """
        if not isinstance(input_val.data, str):
            raise comp.CodeError("cob.unpack: input must be a text value")
        tree = comp.lark_parse(input_val.data, "cob")
        return _Unpacker().transform(tree)

    module.add_callable("pack", _pack, pure=True)
    module.add_callable("unpack", _unpack)
