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
    that item-at produces.

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
