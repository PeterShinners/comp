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
        positional_matches: (int) Number of fields matched positionally

    Attributes:
        value: (Value) The morphed value result
        score: (tuple) (named_matches, tag_depth, positional_matches)
        failure_reason: (str | None) Error message if morph failed
    """

    __slots__ = ("value", "score", "failure_reason")

    def __init__(self, value, named_matches=0, tag_depth=0, positional_matches=0):
        self.value = value
        self.score = (named_matches, tag_depth, positional_matches)
        self.failure_reason = None

    @classmethod
    def failed(cls, reason):
        """Create a failed morph result.

        Args:
            reason: (str) Description of why morph failed

        Returns:
            MorphResult: Failed result with no value
        """
        result = cls(None, 0, 0, 0)
        result.failure_reason = reason
        return result

    def __repr__(self):
        if self.failure_reason:
            return f"MorphResult<failed: {self.failure_reason}>"
        return f"MorphResult<score={self.score}>"


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

    # Return depth (how many levels deeper the tag is)
    return len(tag_parts) - len(shape_parts)


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
    if isinstance(field.shape, (comp.Shape, comp.Tag)):
        return field.shape

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


def _check_type(value, shape_constraint, frame):
    """Check if a value matches a shape constraint.

    Args:
        value: (Value) The value to check
        shape_constraint: (Shape | Tag | None) The constraint
        frame: (ExecutionFrame) Frame for lookups

    Returns:
        (bool) True if value matches constraint
    """
    if shape_constraint is None:
        return True  # No constraint means any value matches

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

    # Check tag matching
    if isinstance(shape_constraint, comp.Tag):
        value_tag = _get_value_tag(value)
        if value_tag:
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


def morph(value, shape, frame):
    """Morph a value to match a shape.

    Transforms input value to match the target shape using three-phase
    field matching: named -> tag -> positional. Validates types against
    shape constraints. Keeps extra fields not in shape.

    Scalar values are automatically promoted to single-element structs.

    Args:
        value: (Value) The input value to morph
        shape: (Shape) The target shape
        frame: (ExecutionFrame) Frame for evaluating defaults

    Returns:
        MorphResult: Result with morphed value and match score
    """
    # Handle non-struct values by promoting to single-element struct
    if not isinstance(value.data, dict):
        if not shape.fields:
            # Primitive shape (num, text, etc.) - validate type
            if not _check_type(value, shape, frame):
                return MorphResult.failed(f"Value does not match shape {shape.qualified}")
            return MorphResult(value, 0, 0, 0)
        # Promote scalar to (scalar) - single positional field
        promoted_data = {comp.Unnamed(): value}
        value = comp.Value(promoted_data)
    else:
        # Struct value with primitive shape
        if not shape.fields:
            # Allow single-element struct to demote to scalar
            if len(value.data) == 1:
                inner_val = next(iter(value.data.values()))
                if not _check_type(inner_val, shape, frame):
                    return MorphResult.failed(f"Value does not match shape {shape.qualified}")
                return MorphResult(inner_val, 0, 0, 0)
            return MorphResult.failed(f"Cannot morph struct to scalar shape {shape.qualified}")

    # Build list of input fields
    input_fields = []
    for key, val in value.data.items():
        name = _get_field_key(key)
        tag = _get_value_tag(val)
        input_fields.append({"key": key, "name": name, "tag": tag, "value": val, "matched": False})

    # Track which shape fields are satisfied
    shape_matches = {}  # shape_field_index -> input_field
    named_matches = 0
    tag_depth_total = 0
    positional_matches = 0

    # Phase 1: Named matching
    for i, shape_field in enumerate(shape.fields):
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
                shape_matches[i] = inp
                inp["matched"] = True
                named_matches += 1
                break

    # Phase 2: Tag matching
    for i, shape_field in enumerate(shape.fields):
        if i in shape_matches:
            continue  # Already matched

        constraint = _resolve_shape_field(shape_field, frame)
        if not isinstance(constraint, comp.Tag):
            continue  # Only tag constraints participate in tag matching

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

        if best_match and best_depth is not None:
            shape_matches[i] = best_match
            best_match["matched"] = True
            tag_depth_total += best_depth

    # Phase 3: Positional matching
    unmatched_inputs = [inp for inp in input_fields if not inp["matched"]]
    unmatched_input_idx = 0

    for i, shape_field in enumerate(shape.fields):
        if i in shape_matches:
            continue  # Already matched

        # Find next unmatched input
        while unmatched_input_idx < len(unmatched_inputs):
            inp = unmatched_inputs[unmatched_input_idx]
            unmatched_input_idx += 1

            # Validate type
            constraint = _resolve_shape_field(shape_field, frame)
            if _check_type(inp["value"], constraint, frame):
                shape_matches[i] = inp
                inp["matched"] = True
                positional_matches += 1
                break
            else:
                return MorphResult.failed(
                    f"Positional field has wrong type for shape field '{shape_field.name or i}'"
                )

    # Apply defaults for unmatched shape fields
    for i, shape_field in enumerate(shape.fields):
        if i in shape_matches:
            continue

        if shape_field.default is not None:
            # Evaluate default
            default_val = _eval_default(shape_field.default, frame)
            # Create synthetic input field
            shape_matches[i] = {"value": default_val, "name": shape_field.name}
        else:
            # Required field missing
            field_name = shape_field.name or f"positional {i}"
            return MorphResult.failed(f"Required field '{field_name}' missing")

    # Build result struct
    result_data = {}

    # Add matched fields with shape field names
    for i, shape_field in enumerate(shape.fields):
        if i not in shape_matches:
            continue
        inp = shape_matches[i]
        if shape_field.name:
            key = comp.Value.from_python(shape_field.name)
        else:
            key = comp.Unnamed()
        result_data[key] = inp["value"]

    # Add extra fields (morph keeps extras)
    extra_idx = len(shape.fields)
    for inp in input_fields:
        if inp["matched"]:
            continue
        # Keep with original key
        result_data[inp["key"]] = inp["value"]

    result_value = comp.Value(result_data)
    return MorphResult(result_value, named_matches, tag_depth_total, positional_matches)


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
    # Handle non-struct values by promoting to single-element struct
    if not isinstance(value.data, dict):
        if not shape.fields:
            # Primitive shape - validate type
            if not _check_type(value, shape, frame):
                return None, f"Value does not match shape {shape.qualified}"
            return value, None
        # Promote scalar to (scalar) - single positional field
        promoted_data = {comp.Unnamed(): value}
        value = comp.Value(promoted_data)
    else:
        # Struct value with primitive shape
        if not shape.fields:
            # Allow single-element struct to demote to scalar
            if len(value.data) == 1:
                inner_val = next(iter(value.data.values()))
                if not _check_type(inner_val, shape, frame):
                    return None, f"Value does not match shape {shape.qualified}"
                return inner_val, None
            return None, f"Cannot mask struct to scalar shape {shape.qualified}"

    # Build list of input fields
    input_fields = []
    for key, val in value.data.items():
        name = _get_field_key(key)
        tag = _get_value_tag(val)
        input_fields.append({"key": key, "name": name, "tag": tag, "value": val, "matched": False})

    # Track which shape fields are satisfied
    shape_matches = {}

    # Phase 1: Named matching
    for i, shape_field in enumerate(shape.fields):
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
    for i, shape_field in enumerate(shape.fields):
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
    unmatched_inputs = [inp for inp in input_fields if not inp["matched"]]
    unmatched_input_idx = 0

    for i, shape_field in enumerate(shape.fields):
        if i in shape_matches:
            continue

        if unmatched_input_idx < len(unmatched_inputs):
            inp = unmatched_inputs[unmatched_input_idx]
            unmatched_input_idx += 1

            # Validate type
            constraint = _resolve_shape_field(shape_field, frame)
            if not _check_type(inp["value"], constraint, frame):
                field_name = shape_field.name or f"positional {i}"
                return None, f"Positional field has wrong type for shape field '{field_name}'"

            shape_matches[i] = inp
            inp["matched"] = True

    # Apply defaults for unmatched shape fields
    for i, shape_field in enumerate(shape.fields):
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

    for i, shape_field in enumerate(shape.fields):
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
