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
