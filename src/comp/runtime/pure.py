"""Pure struct-manipulation functions callable via py.pure-call from Comp.

These functions take and return plain Python objects (str, int, float, bool,
None, dict, list).  They carry no side effects and are registered in the
py.pure-call allowlist (comp.runtime.pure. prefix).

Struct calling conventions
--------------------------
When a Comp struct is the piped input to py.pure-call its *fields* are
unpacked — unnamed fields become positional args, named fields become
keyword args.  This works well for all-unnamed structs (Python lists) but
loses named structure when a named struct is the piped input.

To pass an entire struct as a single Python argument the calling site must
wrap it first::

    {value} | py.pure-call :"comp.runtime.pure.some_fn"

This creates a 1-element unnamed struct so ``some_fn`` receives the inner
value as its sole positional argument.  The runtime.comp module provides
properly-shaped wrappers for each function here.

Return values
-------------
Return a Python list to produce an all-unnamed Comp struct.
Return a Python dict (string keys) to produce a named-field Comp struct.
Mixing int keys in a returned dict will produce integer-keyed struct fields,
*not* unnamed/positional fields — avoid this for now.
"""

import math
import fractions


def cop_tag(node):
    """Return the stripped COP tag name from a Python COP-node dict."""
    if not isinstance(node, dict):
        return None
    tag = node.get(0)
    if isinstance(tag, str) and tag.startswith("cop-type."):
        return tag[9:]
    return tag if isinstance(tag, str) else None


def walk_cop(node, filter=None, fields=None, order="all", recurse="deep", stop_on_match=True):
    """Walk a Python COP-node tree and return matching contexts.

    The return value is a list of dicts. Each dict contains:
      - path: list[int] path from root to the matching node
      - parent: list[int] path from root to the parent, or None at root
      - depth: integer depth
      - position: index among siblings
      - order: one of "all", "first", "last"
    """

    def _norm_tag_name(value):
        if value is None:
            return None
        qualified = value if isinstance(value, str) else str(value)
        if qualified.startswith("cop-type."):
            return qualified[9:]
        prefix = "copwalk.order."
        if qualified.startswith(prefix):
            return qualified[len(prefix):]
        prefix = "copwalk.recurse."
        if qualified.startswith(prefix):
            return qualified[len(prefix):]
        return qualified

    def _boolish(value, default=False):
        if value is None:
            return default
        return bool(value)

    def _kids_for(current):
        kids = current.get("kids", []) if isinstance(current, dict) else []
        if isinstance(kids, list):
            return kids
        if isinstance(kids, dict):
            if all(isinstance(k, int) for k in kids):
                return [kids[k] for k in sorted(kids)]
            return list(kids.values())
        return []

    def _matches_fields(current, expected_fields):
        if not isinstance(expected_fields, dict) or not expected_fields:
            return True
        if not isinstance(current, dict):
            return False
        for key, expected in expected_fields.items():
            if isinstance(key, int):
                continue
            if current.get(key) != expected:
                return False
        return True

    def _mode_allows_descend(mode, depth, tag_name):
        if mode == "shallow":
            return depth == 0
        if mode == "near":
            return depth == 0 or tag_name in ("statement.define", "statement.field")
        return True

    def _order_matches(which, position, sibling_count):
        if which == "first":
            return position == 0
        if which == "last":
            return position == (sibling_count - 1)
        return True

    filter_name = _norm_tag_name(filter)
    order_name = _norm_tag_name(order) or "all"
    recurse_mode = _norm_tag_name(recurse) or "deep"
    stop = _boolish(stop_on_match, default=True)
    found = []

    def _walk(current, path, parent_path, depth, position, sibling_count):
        tag_name = cop_tag(current)
        matches = (
            (filter_name is None or filter_name == tag_name)
            and _order_matches(order_name, position, sibling_count)
            and _matches_fields(current, fields)
        )

        skip_children = False
        if matches:
            found.append({
                "path": list(path),
                "parent": None if parent_path is None else list(parent_path),
                "depth": depth,
                "position": position,
                "order": "first" if position == 0 else "last" if position == (sibling_count - 1) else "all",
            })
            if stop:
                skip_children = True

        if _mode_allows_descend(recurse_mode, depth, tag_name) and not skip_children:
            kids = _kids_for(current)
            count = len(kids)
            for idx, kid in enumerate(kids):
                _walk(kid, path + [idx], path, depth + 1, idx, count)

    _walk(node, [], None, 0, 0, 1)
    return found


def merge(*structs):
    """Merge any number of structs into one, in left-to-right order.

    Later values override earlier ones for shared named (dict) keys.
    All-unnamed (list) structs are concatenated in arrival order.
    If any input is a named dict the result is always a dict.

    Args:
        *structs: Python dicts (named Comp structs) or lists
            (all-unnamed Comp structs) to merge.

    Returns:
        (dict or list) Merged result.
    """
    if not structs:
        return []
    all_lists = all(isinstance(s, list) for s in structs)
    if all_lists:
        result = []
        for s in structs:
            result.extend(s)
        return result
    result = {}
    for s in structs:
        if isinstance(s, list):
            for item in s:
                result[len(result)] = item
        elif isinstance(s, dict):
            result.update(s)
    return result


def item_at(struct, index):
    """Return the single item at a positional index from a struct.

    The result is a single-item list (for unnamed fields) or single-item
    dict (for named fields), mirroring the Comp single-item struct format
    that field-at produces.

    Args:
        struct: (dict or list) The Comp struct as a Python object.
        index: (int or float) Zero-based positional index.  Negative
            indices count from the end.

    Returns:
        (dict or list) Single-item collection.

    Raises:
        IndexError: If ``index`` is out of range.
        TypeError: If ``struct`` is not a dict or list.
    """
    index = int(index)
    if isinstance(struct, list):
        return [struct[index]]
    if isinstance(struct, dict):
        items = list(struct.items())
        k, v = items[index]
        if isinstance(k, int):
            return [v]
        return {k: v}
    raise TypeError(
        "item_at: struct must be a list (unnamed) or dict (named), "
        f"got {type(struct).__name__}"
    )


def field_name(struct):
    """Return the field name from a single-item named struct.

    Intended for use with the output of item_at on a named struct.

    Args:
        struct: (dict) Single-item Python dict representing a named
            Comp struct field.

    Returns:
        (str) The field name.

    Raises:
        ValueError: If the struct is not a single-item named dict.
    """
    if not isinstance(struct, dict):
        raise ValueError(
            f"field_name: expected a named struct (dict), got {type(struct).__name__}"
        )
    if len(struct) != 1:
        raise ValueError(
            f"field_name: expected exactly one field, got {len(struct)}"
        )
    key = next(iter(struct))
    if not isinstance(key, str):
        raise ValueError(
            "field_name: struct field has no name (positional/unnamed field)"
        )
    return key


def field_value(struct):
    """Return the value from a single-item struct (named or unnamed).

    Intended for use with the output of item_at.

    Args:
        struct: (dict or list) Single-item Python dict or list.

    Returns:
        The field value.

    Raises:
        ValueError: If the collection does not contain exactly one item.
        TypeError: If the collection is neither a dict nor a list.
    """
    if isinstance(struct, list):
        if len(struct) != 1:
            raise ValueError(
                f"field_value: expected exactly one item, got {len(struct)}"
            )
        return struct[0]
    if isinstance(struct, dict):
        if len(struct) != 1:
            raise ValueError(
                f"field_value: expected exactly one field, got {len(struct)}"
            )
        return next(iter(struct.values()))
    raise TypeError(
        f"field_value: expected a dict or list, got {type(struct).__name__}"
    )


def contains_field(struct, name):
    """Check whether a named field exists in a struct.

    Only works for named (dict) structs.  All-unnamed (list) structs
    always return False because they have no named fields.

    Args:
        struct: (dict or list) A Comp struct as a Python object.
        name: (str) The field name to search for.

    Returns:
        (bool) True if ``name`` is a key in ``struct``, False otherwise.
    """
    if isinstance(struct, dict):
        return name in struct
    return False


def find_duplicates(items):
    """Return values that appear more than once in a list or dict.

    Comparison uses str() of each value for equality, consistent with
    the internal Comp implementation that compares via Value.format().
    Each duplicated value appears exactly once in the result.

    Args:
        items: (list or dict) The Comp struct values to inspect.
            Dicts are treated as an ordered sequence of their values.

    Returns:
        (list) Duplicate values in first-seen order, each appearing once.
    """
    if isinstance(items, dict):
        items = list(items.values())
    elif not isinstance(items, list):
        return []
    seen = {}
    dupes = []
    seen_dupe_keys = set()
    for item in items:
        key = str(item)
        if key in seen:
            if key not in seen_dupe_keys:
                dupes.append(item)
                seen_dupe_keys.add(key)
        else:
            seen[key] = item
    return dupes


def parse_uri(text):
    """Parse a URI string into a dict with fully decomposed fields.

    Uses urllib.parse.urlparse for RFC-compliant parsing, unpacks the
    authority into user/password/host/port, and splits the path into
    directory/stem/extension using posixpath.

    Args:
        text: (str) URI or path string to parse.

    Returns:
        (dict) With keys: protocol, user, password, host, port, path,
            stem, extension, query, fragment.
            Empty strings become None.
    """
    import urllib.parse
    import posixpath
    text = text.replace("\\", "/")
    parsed = urllib.parse.urlparse(text)
    def _or_none(s):
        return s if s else None
    # Single-letter schemes are Windows drive letters, not protocols
    if len(parsed.scheme) == 1:
        # Re-parse as a bare path (no scheme)
        parsed = urllib.parse.urlparse("", scheme="", allow_fragments=True)._replace(
            path=text, query="", fragment="",
        )
    port = parsed.port
    raw_path = parsed.path
    has_protocol = bool(parsed.scheme)
    is_dir = raw_path.endswith("/") and raw_path != "/"
    if is_dir:
        if has_protocol:
            directory = raw_path
        else:
            directory = raw_path.rstrip("/")
        stem = None
        extension = None
    else:
        stripped = raw_path.rstrip("/") if raw_path != "/" else raw_path
        directory, filename = posixpath.split(stripped)
        if filename:
            stem, extension = _split_filename(filename)
        else:
            stem = None
            extension = None
    return {
        "protocol": _or_none(parsed.scheme),
        "user": _or_none(parsed.username),
        "password": _or_none(parsed.password),
        "host": _or_none(parsed.hostname),
        "port": str(port) if port is not None else None,
        "path": directory,
        "stem": stem,
        "extension": extension,
        "query": _or_none(parsed.query),
        "fragment": _or_none(parsed.fragment),
    }


def parse_path(text):
    """Parse a path string into directory, stem, and extension.

    Args:
        text: (str) A filesystem path or URI path component.

    Returns:
        (dict) With keys: path, stem, extension.
    """
    import posixpath
    text = text.replace("\\", "/")
    directory, filename = posixpath.split(text.rstrip("/") if text != "/" else text)
    if filename:
        stem, extension = _split_filename(filename)
    else:
        stem = None
        extension = None
    return {
        "path": directory,
        "stem": stem,
        "extension": extension,
    }


def pack_uri(**fields):
    """Reassemble a ~uri dict into a URI string.

    Args:
        **fields: Keyword args matching the ~uri shape fields.

    Returns:
        (str) The assembled URI or bare path string.
    """
    path_str = _join_path_fields(fields.get("path", ""),
                                  fields.get("stem"),
                                  fields.get("extension"))
    protocol = fields.get("protocol")
    if not protocol:
        return path_str
    authority = _build_authority(fields)
    result = protocol + "://"
    if authority:
        result += authority
    result += path_str
    query = fields.get("query")
    if query:
        result += "?" + query
    fragment = fields.get("fragment")
    if fragment:
        result += "#" + fragment
    return result


def pack_path(**fields):
    """Reassemble a ~uri-path dict into a path string.

    Args:
        **fields: Keyword args with keys: path, stem, extension.

    Returns:
        (str) The assembled path string.
    """
    return _join_path_fields(fields.get("path", ""),
                              fields.get("stem"),
                              fields.get("extension"))


def _split_filename(filename):
    """Split a filename into (stem, extension), dotfile-aware.

    Files like `.env` are stem-only with no extension.
    Extension is returned without the leading dot, or None.

    Returns:
        (tuple) (stem, extension) where either may be None.
    """
    import posixpath
    if filename.startswith(".") and "." not in filename[1:]:
        return (filename, None)
    stem, dot_ext = posixpath.splitext(filename)
    if not stem:
        return (filename, None)
    return (stem, dot_ext[1:] if dot_ext else None)


def _join_path_fields(path, stem, extension):
    """Combine path + stem + extension into a single path string.

    Ensures exactly one slash between path and stem when both present.
    """
    if not stem:
        return path
    if extension:
        filename = stem + "." + extension
    else:
        filename = stem
    if not path or path.endswith("/"):
        return path + filename
    return path + "/" + filename

# ---------------------------------------------------------------------------
# Number helpers for tuple-backed Comp numbers
# ---------------------------------------------------------------------------

def _as_fraction(value):
    if isinstance(value, tuple) and len(value) >= 2:
        n, d = int(value[0]), int(value[1])
        return fractions.Fraction(n, d)
    if isinstance(value, fractions.Fraction):
        return value
    if isinstance(value, int):
        return fractions.Fraction(value, 1)
    if isinstance(value, float):
        return fractions.Fraction(str(value))
    raise TypeError(f"expected number-like value, got {type(value).__name__}")


def _dp_hint(*values):
    dp = 0
    for v in values:
        if isinstance(v, tuple) and len(v) >= 3:
            dp = max(dp, int(v[2]))
    return dp


def _make_num(n, d, dp=0):
    n = int(n)
    d = int(d)
    if d == 0:
        raise ZeroDivisionError("division by zero")
    if d < 0:
        n, d = -n, -d
    g = math.gcd(abs(n), d)
    if g > 1:
        n //= g
        d //= g
    return (n, d, int(dp))


def _from_fraction(frac, dp=0):
    return _make_num(frac.numerator, frac.denominator, dp=dp)


def _from_float(value, places=12):
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    if not text:
        text = "0"
    if "." in text:
        whole, frac = text.split(".", 1)
        sign = -1 if whole.startswith("-") else 1
        whole_abs = whole[1:] if whole.startswith("-") else whole
        n = int((whole_abs or "0") + frac) * sign
        d = 10 ** len(frac)
        return _make_num(n, d, dp=len(frac) + 1)
    return _make_num(int(text), 1, dp=0)


def num_round(value, digits=0):
    frac = _as_fraction(value)
    digits_i = int(_as_fraction(digits))
    scaled = frac * (10 ** digits_i)
    rounded = int(round(float(scaled)))
    result = fractions.Fraction(rounded, 10 ** digits_i)
    dp = 0 if digits_i <= 0 else (digits_i + 1)
    return _from_fraction(result, dp=dp)


def num_floor(value):
    frac = _as_fraction(value)
    return _make_num(math.floor(float(frac)), 1, dp=0)


def num_ceil(value):
    frac = _as_fraction(value)
    return _make_num(math.ceil(float(frac)), 1, dp=0)


def num_trunc(value):
    frac = _as_fraction(value)
    return _make_num(math.trunc(float(frac)), 1, dp=0)


def num_abs(value):
    frac = _as_fraction(value)
    return _from_fraction(abs(frac), dp=_dp_hint(value))


def num_divmod(value, divisor):
    left = _as_fraction(value)
    right = _as_fraction(divisor)
    if right == 0:
        raise ZeroDivisionError("division by zero")
    q = math.floor(left / right)
    r = left - (fractions.Fraction(q, 1) * right)
    return {
        "quotient": _make_num(q, 1, dp=0),
        "remainder": _from_fraction(r, dp=_dp_hint(value, divisor)),
    }


def num_pow(value, exp):
    base = _as_fraction(value)
    exponent = _as_fraction(exp)
    if exponent.denominator == 1:
        n = exponent.numerator
        if n >= 0:
            return _from_fraction(base ** n, dp=_dp_hint(value, exp))
        return _from_fraction(fractions.Fraction(1, 1) / (base ** abs(n)), dp=_dp_hint(value, exp))
    return _from_float(math.pow(float(base), float(exponent)))


def num_sqrt(value):
    frac = _as_fraction(value)
    if frac < 0:
        raise ValueError("sqrt requires non-negative input")
    return _from_float(math.sqrt(float(frac)))


def num_log(value, base=None):
    v = float(_as_fraction(value))
    if base is None:
        return _from_float(math.log(v))
    b = float(_as_fraction(base))
    return _from_float(math.log(v, b))


def num_log2(value):
    return _from_float(math.log2(float(_as_fraction(value))))


def num_log10(value):
    return _from_float(math.log10(float(_as_fraction(value))))


def num_sin(value):
    return _from_float(math.sin(float(_as_fraction(value))))


def num_cos(value):
    return _from_float(math.cos(float(_as_fraction(value))))


def cop_pattern_key(branch_node):
    """Extract a position-independent string key from an op.on.branch pattern.

    Drills into the pattern shape to extract the identifier path as a
    dot-joined string (e.g. "true", "false", "any", "ord.less").
    Returns None (nil) for complex patterns like struct shapes or unions.

    Args:
        branch_node: (dict) op.on.branch COP node as a plain Python dict.

    Returns:
        (str or None) Pattern key string, or None for complex patterns.
    """
    if not isinstance(branch_node, dict):
        return None
    branch_kids = branch_node.get("kids", [])
    if not branch_kids:
        return None
    shape_node = branch_kids[0]  # shape.define
    if not isinstance(shape_node, dict):
        return None
    shape_kids = shape_node.get("kids", [])
    if not shape_kids:
        return None
    first_kid = shape_kids[0]
    if not isinstance(first_kid, dict):
        return None
    tag = first_kid.get(0, "")
    if isinstance(tag, str) and tag.startswith("cop-type."):
        tag = tag[9:]
    if tag == "value.identifier":
        parts = []
        for kid in first_kid.get("kids", []):
            if not isinstance(kid, dict):
                continue
            kid_tag = kid.get(0, "")
            if isinstance(kid_tag, str) and kid_tag.startswith("cop-type."):
                kid_tag = kid_tag[9:]
            if kid_tag in ("ident.token", "ident.text"):
                val = kid.get("value")
                if isinstance(val, str):
                    parts.append(val)
        if parts:
            return ".".join(parts)
    return None


def _build_authority(fields):
    """Build the authority portion (user:pass@host:port) from fields."""
    host = fields.get("host")
    if not host:
        return ""
    user = fields.get("user")
    password = fields.get("password")
    port = fields.get("port")
    result = ""
    if user:
        result += user
        if password:
            result += ":" + password
        result += "@"
    result += host
    if port:
        result += ":" + str(port)
    return result
