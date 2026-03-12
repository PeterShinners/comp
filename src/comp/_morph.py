"""Morph and mask operations for shape-based data transformation."""

import comp


__all__ = ["MorphResult", "morph", "mask"]


class MorphResult:
    """Result of a morph operation.

    Contains the morphed value and a score indicating match quality.
    The score is used for ranking when multiple shapes could match.

    Args:
        value: (Value) The morphed value result
        named_matches: (int) Number of fields matched by name
        tag_depth: (int) Total tag depth for tag-matched fields
        unit_score: (int) Total unit compatibility score across matched fields
        positional_matches: (int) Number of fields matched positionally

    Attributes:
        value: (Value) The morphed value result
        score: (tuple) (named_matches, tag_depth, unit_score, positional_matches)
        failure_reason: (str | None) Error message if morph failed
    """

    __slots__ = ("value", "score", "failure_reason", "failure_value")

    def __init__(self, value, named_matches=0, tag_depth=0, unit_score=0, positional_matches=0):
        self.value = value
        self.score = (named_matches, tag_depth, unit_score, positional_matches)
        self.failure_reason = None
        self.failure_value = None

    @classmethod
    def failed(cls, reason, failure_value=None):
        """Create a failed morph result.

        Args:
            reason: (str) Description of why morph failed
            failure_value: (Value | None) Original fail Value to re-raise at call sites

        Returns:
            MorphResult: Failed result with no value
        """
        result = cls(None, 0, 0, 0)
        result.failure_reason = reason
        result.failure_value = failure_value
        return result

    def __repr__(self):
        if self.failure_reason:
            fv = " (has failure_value)" if self.failure_value is not None else ""
            return f"MorphResult<failed: {self.failure_reason}{fv}>"
        return f"MorphResult<score={self.score}>"


def _unit_match_score(val_unit, shape_unit):
    """Score unit compatibility between a value's unit and a shape field's unit.

    Returns:
        4  — exact unit match or no shape unit constraint
        3  — value's unit is a child of the shape's unit tag
        2  — bare value (no unit) matched against a unit-constrained field
        1  — value's unit is a sibling of the shape's unit (same family, convertible)
        -1 — incompatible units (different families); morph should fail
    """
    if shape_unit is None:
        return 4  # No constraint — unit is irrelevant

    if val_unit is None:
        return 2  # Bare value matches any unit shape (moderate match)

    val_q = val_unit.qualified
    shape_q = shape_unit.qualified

    if val_q == shape_q:
        return 4  # Exact match

    val_parts = val_q.split(".")
    shape_parts = shape_q.split(".")

    # Child: value's unit is a child of shape's unit tag (e.g. second → time)
    if (len(val_parts) > len(shape_parts) and
            val_parts[:len(shape_parts)] == shape_parts):
        return 3

    # Sibling: same immediate parent → same family, convertible
    # e.g. measure.length.foot and measure.length.meter both under measure.length
    if len(val_parts) >= 2 and len(shape_parts) >= 2:
        if val_parts[:-1] == shape_parts[:-1]:
            return 1

    return -1  # Incompatible families — reject


def _get_field_key(key):
    """Extract the field name from a struct key.

    Args:
        key: Value or Unnamed key from struct dict

    Returns:
        (str | None) The field name if named, None if positional
    """
    if isinstance(key, comp.Unnamed):
        return None
    if isinstance(key, comp.Value) and key.shape == comp.shape_text:
        return key.data
    return None


def _get_value_tag(value):
    """Get the tag from a value if it has one.

    Args:
        value: (Value) The value to check

    Returns:
        (Tag | None) The tag if value is tagged, None otherwise
    """
    if isinstance(value.data, comp.Tag):
        return value.data
    return None


def _shape_name(shape):
    """Get a display name for a shape constraint.

    Args:
        shape: (Shape | Tag | ShapeUnion) The shape

    Returns:
        (str) Human-readable name for error messages
    """
    if hasattr(shape, "qualified"):
        return shape.qualified
    if hasattr(shape, "format"):
        return shape.format()
    return str(shape)


def _tag_matches_shape(tag, shape):
    """Check if a tag matches a shape constraint.

    Tags are shapes - a child tag matches its parent tag shape.
    For example, tag "http.status.ok" matches shape "http.status".

    Args:
        tag: (Tag) The tag to check
        shape: (Shape | Tag) The shape constraint

    Returns:
        (int | None) Tag depth if matches, None if no match
    """
    if not isinstance(shape, comp.Tag):
        return None

    # Check if tag qualified name starts with shape qualified name
    tag_parts = tag.qualified.split(".")
    shape_parts = shape.qualified.split(".")

    # Shape must be prefix of tag
    if len(shape_parts) > len(tag_parts):
        return None

    for i, part in enumerate(shape_parts):
        if tag_parts[i] != part:
            return None

    depth = len(tag_parts) - len(shape_parts)

    # A tag never matches its own ~shape constraint — only its children do.
    # ~bool matches bool.true / bool.false but never bare bool itself.
    # This means tag hierarchies are always abstract shape roots, not values.
    if depth == 0:
        return None

    return depth


def _resolve_shape_field(field, frame):
    """Resolve a ShapeField's shape constraint to an actual shape.

    Args:
        field: (ShapeField) The field with shape constraint (COP or resolved)
        frame: (ExecutionFrame) Frame for evaluation

    Returns:
        (Shape | Tag | None) The resolved shape, or None if no constraint
    """
    if field.shape is None:
        return None

    # Check if already resolved (from BuildShape instruction)
    if isinstance(field.shape, (comp.Shape, comp.ShapeUnion, comp.Tag)):
        return field.shape

    # String name reference — look up at morph time (deferred resolution)
    if isinstance(field.shape, str):
        name = field.shape
        try:
            shape_val = comp._instructions._load_name(name, frame)
        except (NameError, AttributeError):
            return None
        # Unwrap Callable (may contain a shape)
        if shape_val and isinstance(shape_val.data, comp.Callable):
            if shape_val.data.shape is not None:
                field.shape = shape_val.data.shape
                return field.shape
        # Unwrap DefinitionSet (legacy path)
        if shape_val and isinstance(shape_val.data, comp.DefinitionSet):  # type: ignore[union-attr]
            for defn in shape_val.data.definitions:  # type: ignore[union-attr]
                dv = comp._instructions._ensure_definition_value(defn, frame)
                if dv and isinstance(dv.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):  # type: ignore[union-attr]
                    field.shape = dv.data  # type: ignore[union-attr]
                    return field.shape
        if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):  # type: ignore[union-attr]
            field.shape = shape_val.data  # type: ignore[union-attr]
            return field.shape
        return None

    # The shape is a COP node that needs evaluation
    shape_cop = field.shape
    tag = comp.cop_tag(shape_cop)

    if tag == "ref":
        # Simple reference to a shape name
        name = shape_cop.field("name").data
        # Look up in frame's namespace
        defn = frame.lookup(name)
        if defn and defn.value:
            val = defn.value.data
            if isinstance(val, (comp.Shape, comp.Tag)):
                return val
        return None

    # For other cases, try to evaluate
    # This is a simplified approach
    return None


def _extract_fail_message(val):
    """Extract a human-readable message string from a fail Value.

    Args:
        val: (Value) A fail struct that may have a 'message' field

    Returns:
        (str) The message string, or a generic fallback
    """
    if val is not None and isinstance(val.data, dict):
        for k, v in val.data.items():
            if (isinstance(k, comp.Value) and isinstance(k.data, str)
                    and k.data == "message" and isinstance(v.data, str)):
                return v.data
    return "limit check failed"


def _invoke_limits(field, value, frame):
    """Invoke all limit functions on a matched field value.

    Limit functions are pre-resolved at codegen time and stored on the ShapeField
    as (func_val, param_val_or_None) tuples — no runtime name lookup needed.

    Args:
        field: (ShapeField) The field whose limits to check
        value: (Value) The matched value to validate
        frame: (ExecutionFrame) The current interpreter frame

    Returns:
        (Value | None) The original fail Value if a limit fails, None if all pass
    """
    if not field.limits:
        return None

    _empty_args = comp.Value({})

    for func_val, param_val in field.limits:
        if func_val is None:
            continue

        args = comp.Value({comp.Unnamed(): param_val}) if param_val is not None else _empty_args

        try:
            frame.invoke_block(func_val, args, piped=value)
        except comp._interp.CompFail as exc:
            return exc.value

    return None


def _eval_default(default_val, frame):
    """Evaluate a default value.

    Args:
        default_val: (COP | Value) The default value expression or resolved value
        frame: (ExecutionFrame) Frame for evaluation

    Returns:
        (Value) The evaluated default value
    """
    # Check if already a Value (from BuildShape instruction)
    if isinstance(default_val, comp.Value):
        return default_val

    # Otherwise it's a COP that needs evaluation
    return frame.eval(default_val)


def _resolve_raw_tag(raw_tag, shape_tag):
    """Resolve a RawTag to a regular Tag via the shape tag's module namespace.

    The lookup key is the raw tag's qualified name, which the namespace can
    match via any suffix permutation (so "true" finds "bool.true", etc.).
    Only succeeds when the lookup produces a Tag definition that is a child
    of (or exact match for) shape_tag.

    Args:
        raw_tag: (RawTag) The raw tag to resolve
        shape_tag: (Tag) The shape tag whose module namespace to search

    Returns:
        (Value | None, str | None) (resolved_value, failure_reason)
    """
    module = shape_tag.module
    if module is None:
        return None, f"Tag {shape_tag.qualified!r} has no owning module for raw-tag resolution"

    try:
        ns = module.namespace()
    except Exception as e:
        return None, f"Failed to build namespace for {shape_tag.qualified!r}: {e}"

    entry = ns.get(raw_tag.qualified)
    if entry is None:
        return None, f"No definition {raw_tag.qualified!r} found in module namespace"

    # Unwrap DefinitionSet to a single unambiguous Definition
    defn = None
    if isinstance(entry, comp.DefinitionSet):
        defn = entry.scalar()
    elif hasattr(entry, "value"):  # plain Definition
        defn = entry

    if defn is None:
        return None, f"Ambiguous or empty definition for {raw_tag.qualified!r}"

    if defn.value is None:
        return None, f"Definition {raw_tag.qualified!r} has no value"

    if not isinstance(defn.value.data, comp.Tag):
        return None, f"Definition {raw_tag.qualified!r} is not a tag"

    resolved_tag = defn.value.data

    # Verify the resolved tag is within the shape's hierarchy (child or exact)
    depth = _tag_matches_shape(resolved_tag, shape_tag)
    if depth is None and resolved_tag.qualified != shape_tag.qualified:
        return None, (
            f"Resolved tag {resolved_tag.qualified!r} is not within "
            f"shape {shape_tag.qualified!r}"
        )

    return defn.value, None


def _check_type(value, shape_constraint, frame):
    """Check if a value matches a shape constraint.

    Args:
        value: (Value) The value to check
        shape_constraint: (Shape | Tag | ShapeUnion | None) The constraint
        frame: (ExecutionFrame) Frame for lookups

    Returns:
        (bool) True if value matches constraint
    """
    if shape_constraint is None:
        return True  # No constraint means any value matches

    # Check union shapes - match if any member matches
    if isinstance(shape_constraint, comp.ShapeUnion):
        for member_shape in shape_constraint.shapes:
            if _check_type(value, member_shape, frame):
                return True
        return False

    # Get value's shape
    value_shape = value.shape

    # Check builtin shapes
    if shape_constraint is comp.shape_any:
        return True
    if shape_constraint is comp.shape_num:
        return value_shape is comp.shape_num
    if shape_constraint is comp.shape_text:
        return value_shape is comp.shape_text
    if shape_constraint is comp.shape_struct:
        return value_shape is comp.shape_struct
    if shape_constraint is comp.shape_block:
        return value_shape is comp.shape_block
    if shape_constraint is comp.shape_handle:
        return isinstance(value.data, comp.HandleInstance)

    # Check tag matching
    if isinstance(shape_constraint, comp.Tag):
        value_tag = _get_value_tag(value)
        if value_tag:
            # Allow exact leaf-tag equality (e.g. nil matches ~nil)
            # _tag_matches_shape rejects depth-0 for dispatch purposes,
            # but type validation should accept exact matches.
            if value_tag.qualified == shape_constraint.qualified:
                return True
            depth = _tag_matches_shape(value_tag, shape_constraint)
            return depth is not None
        return False

    # For user-defined shapes, would need structural matching
    # For now, accept any struct for struct shapes
    if isinstance(shape_constraint, comp.Shape):
        if shape_constraint.fields:
            # User-defined shape with fields - check structure
            return value_shape is comp.shape_struct
        return True

    return True


def _morph_collection(value, shape, frame):
    """Morph a value into a ShapeCollection (homogeneous typed sequence).

    Args:
        value: (Value) Input — struct with positional elements, or a scalar
        shape: (ShapeCollection) Target collection shape
        frame: (ExecutionFrame) Frame for limit invocation

    Returns:
        MorphResult: Result with morphed struct and positional match score
    """
    # Collect elements: struct → list of values, scalar → single-element list
    if isinstance(value.data, dict):
        elements = list(value.data.values())
    else:
        elements = [value]

    count = len(elements)
    if count < shape.min_count:
        return MorphResult.failed(
            f"Collection requires at least {shape.min_count} element(s), got {count}"
        )
    if shape.max_count is not None and count > shape.max_count:
        return MorphResult.failed(
            f"Collection allows at most {shape.max_count} element(s), got {count}"
        )

    constraint = _resolve_shape_field(shape.element, frame)
    unit_score_total = 0
    result_data = {}

    for i, elem in enumerate(elements):
        if not _check_type(elem, constraint, frame):
            return MorphResult.failed(f"Element {i} has wrong type for collection")
        us = _unit_match_score(elem.unit, shape.element.unit)
        if us == -1:
            return MorphResult.failed(f"Element {i} has incompatible unit for collection")
        limit_fail = _invoke_limits(shape.element, elem, frame)
        if limit_fail is not None:
            return MorphResult.failed(_extract_fail_message(limit_fail), failure_value=limit_fail)
        unit_score_total += us
        result_data[comp.Unnamed()] = elem

    return MorphResult(comp.Value(result_data), 0, 0, unit_score_total, count)


def morph(value, shape, frame):
    """Morph a value to match a shape.

    Transforms input value to match the target shape using three-phase
    field matching: named -> tag -> positional. Validates types against
    shape constraints. Keeps extra fields not in shape.

    For union shapes, tries each member and returns the best scoring match.

    Scalar values are automatically promoted to single-element structs.

    Args:
        value: (Value) The input value to morph
        shape: (Shape) The target shape
        frame: (ExecutionFrame) Frame for evaluating defaults

    Returns:
        MorphResult: Result with morphed value and match score
    """
    # Handle collection shapes
    if isinstance(shape, comp.ShapeCollection):
        return _morph_collection(value, shape, frame)

    # Handle union shapes - try each member and return best scoring match
    if isinstance(shape, comp.ShapeUnion):
        best_result = None
        for member_shape in shape.shapes:
            result = morph(value, member_shape, frame)
            if result.failure_reason:
                continue  # This member didn't match; failures (including limits) are discarded
            if best_result is None or result.score > best_result.score:
                best_result = result
        if best_result is None:
            # All members failed — return a generic message only.
            # Individual member failures (including limit failures) are not surfaced
            # because the value might have been valid for a different member.
            return MorphResult.failed(f"Value does not match any member of {_shape_name(shape)}")
        return best_result

    # Get shape fields (Tags have no fields, they just act as type constraints)
    shape_fields = getattr(shape, "fields", None) or []

    # Handle non-struct values by promoting to single-element struct
    if not isinstance(value.data, dict):
        if not shape_fields:
            # RawTag → Tag: resolve via the shape tag's module namespace
            if isinstance(value.data, comp.RawTag) and isinstance(shape, comp.Tag):
                resolved, reason = _resolve_raw_tag(value.data, shape)
                if resolved is None:
                    return MorphResult.failed(reason)
                depth = _tag_matches_shape(resolved.data, shape)
                tag_depth = depth if depth is not None else 0
                return MorphResult(resolved, 0, tag_depth, 4, 1)
            # Primitive shape (num, text, etc.) or Tag - validate type
            if not _check_type(value, shape, frame):
                return MorphResult.failed(f"Value does not match shape {_shape_name(shape)}")
            # ~any matches everything but with minimum score so specific shapes win
            if shape is comp.shape_any:
                return MorphResult(value, 0, 0, 0, 0)
            # For primitive shapes, get the shape's unit if it has one
            shape_unit = getattr(shape, "unit", None)
            us = _unit_match_score(value.unit, shape_unit)
            if us == -1:
                return MorphResult.failed(f"Value has incompatible unit for shape {_shape_name(shape)}")
            return MorphResult(value, 0, 0, us, 1)
        # Promote scalar to (scalar) - single positional field
        promoted_data = {comp.Unnamed(): value}
        value = comp.Value(promoted_data)
    else:
        # Struct value with primitive shape (no defined fields)
        if not shape_fields:
            # If the shape accepts struct values directly (e.g. ~struct, ~any),
            # pass through without demoting to scalar.
            if _check_type(value, shape, frame):
                return MorphResult(value, 0, 0, 0, 1)
            # Allow single-element struct to demote to scalar
            if len(value.data) == 1:
                inner_val = next(iter(value.data.values()))
                if not _check_type(inner_val, shape, frame):
                    return MorphResult.failed(f"Value does not match shape {_shape_name(shape)}")
                shape_unit = getattr(shape, "unit", None)
                us = _unit_match_score(inner_val.unit, shape_unit)
                if us == -1:
                    return MorphResult.failed(f"Value has incompatible unit for shape {_shape_name(shape)}")
                return MorphResult(inner_val, 0, 0, us, 1)
            return MorphResult.failed(f"Cannot morph struct to scalar shape {_shape_name(shape)}")

    # Build list of input fields
    input_fields = []
    for key, val in value.data.items():  # type: ignore[union-attr]
        name = _get_field_key(key)
        tag = _get_value_tag(val)
        input_fields.append({"key": key, "name": name, "tag": tag, "value": val, "matched": False})

    # Track which shape fields are satisfied
    shape_matches = {}  # shape_field_index -> input_field
    named_matches = 0
    tag_depth_total = 0
    unit_score_total = 0
    positional_matches = 0

    # Phase 1: Named matching
    for i, shape_field in enumerate(shape_fields):
        if shape_field.name is None:
            continue  # Skip positional shape fields in named phase

        for inp in input_fields:
            if inp["matched"]:
                continue
            if inp["name"] == shape_field.name:
                # Resolve shape constraint
                constraint = _resolve_shape_field(shape_field, frame)
                # Validate type
                if not _check_type(inp["value"], constraint, frame):
                    return MorphResult.failed(
                        f"Field '{shape_field.name}' has wrong type"
                    )
                # Validate unit compatibility
                us = _unit_match_score(inp["value"].unit, shape_field.unit)
                if us == -1:
                    return MorphResult.failed(
                        f"Field '{shape_field.name}' has incompatible unit"
                    )
                shape_matches[i] = inp
                inp["matched"] = True
                named_matches += 1
                unit_score_total += us
                # Invoke limits on the matched value
                limit_fail_val = _invoke_limits(shape_field, inp["value"], frame)
                if limit_fail_val is not None:
                    return MorphResult.failed(_extract_fail_message(limit_fail_val), failure_value=limit_fail_val)
                break

    # Phase 2: Tag matching
    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue  # Already matched

        constraint = _resolve_shape_field(shape_field, frame)
        if not isinstance(constraint, comp.Tag):
            continue  # Only tag constraints participate in tag matching

        best_match = None
        best_depth = None
        best_us = 4

        for inp in input_fields:
            if inp["matched"]:
                continue
            if inp["tag"] is None:
                continue

            depth = _tag_matches_shape(inp["tag"], constraint)
            if depth is not None:
                us = _unit_match_score(inp["value"].unit, shape_field.unit)
                if us == -1:
                    continue
                if best_depth is None or depth < best_depth:
                    best_match = inp
                    best_depth = depth
                    best_us = us

        if best_match and best_depth is not None:
            shape_matches[i] = best_match
            best_match["matched"] = True
            tag_depth_total += best_depth
            unit_score_total += best_us
            # Invoke limits on the matched value
            limit_fail_val = _invoke_limits(shape_field, best_match["value"], frame)
            if limit_fail_val is not None:
                return MorphResult.failed(_extract_fail_message(limit_fail_val), failure_value=limit_fail_val)

    # Phase 3: Positional matching
    # Only match positional (unnamed) input fields - named fields that didn't match stay as extras
    unmatched_positional = [inp for inp in input_fields if not inp["matched"] and inp["name"] is None]
    unmatched_input_idx = 0

    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue  # Already matched

        # Find next unmatched positional input
        while unmatched_input_idx < len(unmatched_positional):
            inp = unmatched_positional[unmatched_input_idx]
            unmatched_input_idx += 1

            # Validate type
            constraint = _resolve_shape_field(shape_field, frame)
            if _check_type(inp["value"], constraint, frame):
                # Validate unit compatibility
                us = _unit_match_score(inp["value"].unit, shape_field.unit)
                if us == -1:
                    return MorphResult.failed(
                        f"Positional field has incompatible unit for shape field '{shape_field.name or i}'"
                    )
                shape_matches[i] = inp
                inp["matched"] = True
                positional_matches += 1
                unit_score_total += us
                # Invoke limits on the matched value
                limit_fail_val = _invoke_limits(shape_field, inp["value"], frame)
                if limit_fail_val is not None:
                    return MorphResult.failed(_extract_fail_message(limit_fail_val), failure_value=limit_fail_val)
                break
            else:
                # Try recursive coercion (e.g. RawTag → Tag via sub-shape)
                sub_result = morph(inp["value"], constraint, frame)
                if not sub_result.failure_reason:
                    coerced = sub_result.value
                    us = _unit_match_score(coerced.unit, shape_field.unit)
                    if us == -1:
                        return MorphResult.failed(
                            f"Positional field has incompatible unit for shape field '{shape_field.name or i}'"
                        )
                    shape_matches[i] = dict(inp, value=coerced)
                    inp["matched"] = True
                    positional_matches += 1
                    unit_score_total += us
                    limit_fail_val = _invoke_limits(shape_field, coerced, frame)
                    if limit_fail_val is not None:
                        return MorphResult.failed(_extract_fail_message(limit_fail_val), failure_value=limit_fail_val)
                    break
                return MorphResult.failed(
                    f"Positional field has wrong type for shape field '{shape_field.name or i}'"
                )

    # Apply defaults for unmatched shape fields
    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue

        if shape_field.default is not None:
            # Evaluate explicit default on the shape field
            default_val = _eval_default(shape_field.default, frame)
            shape_matches[i] = {"value": default_val, "name": shape_field.name}
        else:
            # No explicit default — check if the field's type is a ShapeUnion
            # with its own default (e.g. ~tree | nil = nil)
            constraint = _resolve_shape_field(shape_field, frame)
            if isinstance(constraint, comp.ShapeUnion) and constraint.default is not None:
                shape_matches[i] = {"value": constraint.default, "name": shape_field.name}
            else:
                # Required field missing
                field_name = shape_field.name or f"positional {i}"
                return MorphResult.failed(f"Required field '{field_name}' missing")

    # Build result struct
    result_data = {}

    # Add matched fields with shape field names
    for i, shape_field in enumerate(shape_fields):
        if i not in shape_matches:
            continue
        inp = shape_matches[i]
        if shape_field.name:
            key = comp.Value.from_python(shape_field.name)
        else:
            key = comp.Unnamed()
        result_data[key] = inp["value"]

    # Add extra fields (morph keeps extras)
    for inp in input_fields:
        if inp["matched"]:
            continue
        # Keep with original key
        result_data[inp["key"]] = inp["value"]

    result_value = comp.Value(result_data)
    return MorphResult(result_value, named_matches, tag_depth_total, unit_score_total, positional_matches)


def mask(value, shape, frame):
    """Mask a value to match a shape, dropping extra fields.

    Like morph but drops fields not in shape.

    Args:
        value: (Value) The input value to mask
        shape: (Shape) The target shape
        frame: (ExecutionFrame) Frame for evaluating defaults

    Returns:
        (Value | None, str | None) Tuple of (result value, error message)
    """
    # Handle collection shapes
    if isinstance(shape, comp.ShapeCollection):
        result = _morph_collection(value, shape, frame)
        if result.failure_reason:
            return None, result.failure_reason
        return result.value, None

    # Handle union shapes - try each member, return first successful match
    if isinstance(shape, comp.ShapeUnion):
        for member_shape in shape.shapes:
            result_val, error = mask(value, member_shape, frame)
            if error is None:
                return result_val, None
        return None, f"Value does not match any member of {_shape_name(shape)}"

    # Get shape fields (Tags have no fields, they just act as type constraints)
    shape_fields = getattr(shape, "fields", None) or []

    # Handle non-struct values by promoting to single-element struct
    if not isinstance(value.data, dict):
        if not shape_fields:
            # RawTag → Tag: resolve via the shape tag's module namespace
            if isinstance(value.data, comp.RawTag) and isinstance(shape, comp.Tag):
                resolved, reason = _resolve_raw_tag(value.data, shape)
                if resolved is None:
                    return None, reason
                return resolved, None
            # Primitive shape or Tag - validate type
            if not _check_type(value, shape, frame):
                return None, f"Value does not match shape {_shape_name(shape)}"
            return value, None
        # Promote scalar to (scalar) - single positional field
        promoted_data = {comp.Unnamed(): value}
        value = comp.Value(promoted_data)
    else:
        # Struct value with primitive shape
        if not shape_fields:
            # Allow single-element struct to demote to scalar
            if len(value.data) == 1:
                inner_val = next(iter(value.data.values()))
                if not _check_type(inner_val, shape, frame):
                    return None, f"Value does not match shape {_shape_name(shape)}"
                return inner_val, None
            return None, f"Cannot mask struct to scalar shape {_shape_name(shape)}"

    # Build list of input fields
    input_fields = []
    for key, val in value.data.items():  # type: ignore[union-attr]
        name = _get_field_key(key)
        tag = _get_value_tag(val)
        input_fields.append({"key": key, "name": name, "tag": tag, "value": val, "matched": False})

    # Track which shape fields are satisfied
    shape_matches = {}

    # Phase 1: Named matching
    for i, shape_field in enumerate(shape_fields):
        if shape_field.name is None:
            continue

        for inp in input_fields:
            if inp["matched"]:
                continue
            if inp["name"] == shape_field.name:
                # Validate type
                constraint = _resolve_shape_field(shape_field, frame)
                if not _check_type(inp["value"], constraint, frame):
                    return None, f"Field '{shape_field.name}' has wrong type"
                shape_matches[i] = inp
                inp["matched"] = True
                break

    # Phase 2: Tag matching
    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue

        constraint = _resolve_shape_field(shape_field, frame)
        if not isinstance(constraint, comp.Tag):
            continue

        best_match = None
        best_depth = None

        for inp in input_fields:
            if inp["matched"]:
                continue
            if inp["tag"] is None:
                continue

            depth = _tag_matches_shape(inp["tag"], constraint)
            if depth is not None:
                if best_depth is None or depth < best_depth:
                    best_match = inp
                    best_depth = depth

        if best_match:
            shape_matches[i] = best_match
            best_match["matched"] = True

    # Phase 3: Positional matching
    # Only match positional (unnamed) input fields - named fields that didn't match are dropped
    unmatched_positional = [inp for inp in input_fields if not inp["matched"] and inp["name"] is None]
    unmatched_input_idx = 0

    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue

        if unmatched_input_idx < len(unmatched_positional):
            inp = unmatched_positional[unmatched_input_idx]
            unmatched_input_idx += 1

            # Validate type
            constraint = _resolve_shape_field(shape_field, frame)
            if not _check_type(inp["value"], constraint, frame):
                # Try recursive coercion (e.g. RawTag → Tag via sub-shape)
                sub_result = morph(inp["value"], constraint, frame)
                if sub_result.failure_reason:
                    field_name = shape_field.name or f"positional {i}"
                    return None, f"Positional field has wrong type for shape field '{field_name}'"
                inp = dict(inp, value=sub_result.value)

            shape_matches[i] = inp
            inp["matched"] = True

    # Apply defaults for unmatched shape fields
    for i, shape_field in enumerate(shape_fields):
        if i in shape_matches:
            continue

        if shape_field.default is not None:
            default_val = _eval_default(shape_field.default, frame)
            shape_matches[i] = {"value": default_val, "name": shape_field.name}
        else:
            field_name = shape_field.name or f"positional {i}"
            return None, f"Required field '{field_name}' missing"

    # Build result struct (mask drops extras)
    result_data = {}

    for i, shape_field in enumerate(shape_fields):
        if i not in shape_matches:
            continue
        inp = shape_matches[i]
        if shape_field.name:
            key = comp.Value.from_python(shape_field.name)
        else:
            key = comp.Unnamed()
        result_data[key] = inp["value"]

    result_value = comp.Value(result_data)
    return result_value, None
