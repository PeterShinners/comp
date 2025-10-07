"""Shape morphing and type checking logic."""

__all__ = ["MorphResult", "morph"]

from . import _tag, _value, _shape


class MorphResult:
    """Result of a morph operation containing both score and morphed value.

    The score tuple: (named_matches, tag_depth, assignment_weight, positional_matches)
    determines how well the value matched the shape. Higher scores are better matches.

    The value is the morphed result, or None if morphing failed.
    """
    __slots__ = ("named_matches", "tag_depth", "assignment_weight", "positional_matches", "value")

    def __init__(self, named_matches=0, tag_depth=0, assignment_weight=0, positional_matches=-1, value=None):
        self.named_matches = named_matches
        self.tag_depth = tag_depth
        self.assignment_weight = assignment_weight
        self.positional_matches = positional_matches
        self.value = value

    def as_tuple(self):
        """Get the score components as a tuple for comparison."""
        return (self.named_matches, self.tag_depth, self.assignment_weight, self.positional_matches)

    def __gt__(self, other):
        """Lexicographic comparison - earlier components more important."""
        return self.as_tuple() > other.as_tuple()

    def __lt__(self, other):
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other):
        if not isinstance(other, MorphResult):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        value_info = f" value={self.value}" if self.value else " (no match)"
        return (f"MorphResult(named={self.named_matches}, tag={self.tag_depth}, "
                f"weight={self.assignment_weight}, pos={self.positional_matches}{value_info})")

    @property
    def success(self):
        """True if morphing succeeded (value is not None)."""
        return self.value is not None


def morph(value, shape):
    """Morph a value to match a shape, returning both score and morphed value.

    Non-struct values are wrapped in single-item unfielded structures first,
    so the morphing logic only needs to handle structures.

    Returns a MorphResult with:
    - Score components (named_matches, tag_depth, assignment_weight, positional_matches)
    - value: the morphed Value, or None if morphing failed

    For unions, tries all variants and returns the best match.
    """
    # Wrap non-struct values in a single-item structure
    if not value.is_struct:
        wrapped = _value.Value({})
        wrapped.struct = {_value.Unnamed(): value}
        value = wrapped

    # Delegate to internal morphing (handles unions and structs)
    return _morph_any(value, shape)


def _morph_any(value, shape):
    """Internal morph function that handles any value without wrapping.

    This is used for recursive morphing of field values where we don't want
    to wrap non-struct values in an extra layer.

    Args:
        value: The value to morph (struct or non-struct)
        shape: The shape to morph to

    Returns:
        MorphResult with the morphed value or failure
    """
    # Handle unions by trying all variants and picking the best
    if isinstance(shape, _shape.ShapeUnion):
        best_result = MorphResult()  # Zero score, no value

        for variant in shape.variants:
            variant_result = _morph_any(value, variant)
            if variant_result > best_result:
                best_result = variant_result

        return best_result

    # For non-union shapes, delegate to the appropriate handler
    # Struct values go to _morph_struct, primitives to _morph_primitive
    return _morph_struct(value, shape)


def _morph_primitive(value, type_name):
    """Morph a value to a primitive type (~num, ~str).

    Rules:
    1. If value is a structure with exactly one unnamed field, unwrap it
    2. If value matches the expected type, return it
    3. Otherwise, fail (no type conversion)

    Args:
        value: The value to morph (may be struct or primitive)
        type_name: The primitive type name ("num" or "str")

    Returns:
        MorphResult with the morphed value or failure
    """
    # Step 1: Unwrap single-item structures (for top-level morph calls)
    # If called from recursive morph, value may already be a primitive
    if value.is_struct and value.struct and len(value.struct) == 1:
        single_key = next(iter(value.struct.keys()))
        if isinstance(single_key, _value.Unnamed):
            # Unwrap the single unnamed value
            value = value.struct[single_key]

    # Step 2: Check if value matches the expected type
    if type_name == "num":
        if value.is_num:
            # Value is already a number - success with high score
            return MorphResult(named_matches=1, value=value)
    elif type_name == "str":
        if value.is_str:
            # Value is already a string - success with high score
            return MorphResult(named_matches=1, value=value)

    # Step 3: Type mismatch - fail the morph
    return MorphResult()


def _morph_struct(value, shape):
    """Internal morphing logic for structures.

    This is where the actual morphing algorithm lives. Assumes value is already
    a structure (caller should wrap non-structs first).

    Returns both the match score and the morphed value in a single pass.

    Note: This function should NOT receive ShapeUnion - unions are handled
    in the outer morph() function.
    """
    # Handle ShapeTagRef separately - it's a constraint, not a structural shape
    if isinstance(shape, _shape.ShapeTagRef):
        # Check if the value itself is a tag that matches the shape's tag requirement
        if value.is_tag and shape._resolved and value.tag:
            # Create a Tag object from the resolved TagDef for comparison
            # TagDef has identifier (list of strings) that we can use to make a Tag
            shape_tag = _tag.TagValue(shape._resolved.identifier, "builtin")  # TODO: Get proper namespace
            value_tag = value.tag

            # Check if value's tag equals or is a child of the shape's tag
            distance = _tag.is_parent_or_equal(shape_tag, value_tag)
            if distance >= 0:
                # Match! Return tag_depth as the distance (0 for equal, 1+ for parent)
                return MorphResult(tag_depth=distance, value=value)
            else:
                # No match - tags are unrelated
                return MorphResult()

        # Check if value is a struct with a tag (tagged struct)
        if value.is_struct and value.struct and shape._resolved:
            # Look for the tag in the struct's unnamed fields
            for field_key, field_value in value.struct.items():
                if isinstance(field_key, _value.Unnamed) and field_value.is_tag and field_value.tag:
                    # Create a Tag object from the resolved TagDef
                    shape_tag = _tag.TagValue(shape._resolved.identifier, "builtin")  # TODO: Get proper namespace
                    value_tag = field_value.tag

                    # Check if struct's tag equals or is a child of the shape's tag
                    distance = _tag.is_parent_or_equal(shape_tag, value_tag)
                    if distance >= 0:
                        # Match! Return tag_depth as the distance
                        return MorphResult(tag_depth=distance, value=value)
                    break  # Only check first unnamed tag field

            # No matching tag found in struct
            return MorphResult()

        # Unresolved shape or value doesn't have a tag
        return MorphResult()

    # Handle primitive type shapes (~num, ~str)
    # These are special ShapeRef instances that morph to/from basic types
    if isinstance(shape, _shape.ShapeRef) and shape.name in ("num", "str"):
        return _morph_primitive(value, shape.name)

    # For structural shapes, we need field definitions
    shape_fields = None

    if isinstance(shape, _shape.ShapeInline):
        # Use inline field definitions directly
        shape_fields = shape.fields
    elif isinstance(shape, _shape.ShapeRef):
        # Get fields from resolved shape definition
        if shape._resolved:
            # Check if this is a non-structural shape (e.g., tag constraint or shape alias)
            if shape._resolved.shape:
                # Delegate to the actual shape type
                return _morph_any(value, shape._resolved.shape)
            shape_fields = shape._resolved.fields
        else:
            # Unresolved reference - for now, accept any struct with minimal score
            # TODO: Decide on proper semantics for unresolved shapes
            return MorphResult(positional_matches=0, value=value)
    else:
        # Unknown shape type or ShapeUnion (shouldn't happen)
        return MorphResult()

    # If shape has no fields, accept any struct with minimal score
    if not shape_fields:
        return MorphResult(positional_matches=0, value=value)

    # PHASE 1 & 2: Extract shape fields and match named fields
    named_matches = 0
    matched_fields = {}  # Maps field_key -> (value_field_key, value_field, field_shape)
    unmatched_value_fields = dict(value.struct)  # Copy to track what's left
    missing_shape_fields = []  # Track shape fields not matched by name
    matched_value_keys = set()  # Track id() of matched value keys to prevent Phase 5 duplication

    # Iterate through shape fields in order (for named fields)
    for field_key, field_def in shape_fields.items():
        # Shape field keys are now always:
        # - Value objects with .str attribute (named fields)
        # - Unnamed instances (positional fields)

        if isinstance(field_key, _value.Unnamed):
            # Unnamed shape field - will be handled in positional matching
            continue

        # Extract the field name string from Value
        # field_key should be a Value with .str attribute
        if not hasattr(field_key, 'str') or field_key.str is None:
            # Invalid field key - skip
            continue

        field_name = field_key.str

        # Look for matching field in value
        # Value struct keys are Value objects or Unnamed instances
        matching_value_key = None
        matching_value_field = None
        for value_key, value_field in value.struct.items():
            # Check if this value key matches the field name
            if not isinstance(value_key, _value.Unnamed) and hasattr(value_key, 'str') and value_key.str == field_name:
                matching_value_key = value_key
                matching_value_field = value_field
                break

        if matching_value_key is not None:
            named_matches += 1
            matched_fields[field_key] = (matching_value_key, matching_value_field, field_def.shape)
            # Track this key as matched using id() for Unnamed instances
            matched_value_keys.add(id(matching_value_key))
            # Remove from unmatched tracking
            del unmatched_value_fields[matching_value_key]
        else:
            # Field missing in value - might be filled positionally
            missing_shape_fields.append((field_key, field_def.shape))

    # PHASE 3: Positional matching (unnamed fields AND unfilled named fields)
    positional_matches = 0

    # Collect all unfilled shape fields in order (named + unnamed)
    unfilled_shape_fields = []
    for field_key, field_def in shape_fields.items():
        if field_key not in matched_fields:
            # This field wasn't matched by name, so it can be filled positionally
            unfilled_shape_fields.append((field_key, field_def.shape))

    # Collect remaining value fields for positional matching
    # Store (key, value) tuples so we can track which keys were matched
    # Rules:
    # - Unnamed value fields can fill ANY unfilled shape field positionally
    # - Named value fields can ONLY fill unnamed shape fields positionally
    #   (they cannot fill differently-named shape fields)
    remaining_value_fields = []
    for field_key, field_value in unmatched_value_fields.items():
        remaining_value_fields.append((field_key, field_value))

    # Match positionally: unfilled shape fields get filled by remaining value fields
    for i, (shape_field_key, shape_field_type) in enumerate(unfilled_shape_fields):
        if i < len(remaining_value_fields):
            value_field_key, value_field = remaining_value_fields[i]

            # Check if this positional match is allowed:
            # - If shape field is unnamed, any value field can fill it
            # - If shape field is named, only unnamed value fields can fill it
            if not isinstance(shape_field_key, _value.Unnamed):
                # Shape field is named - only allow unnamed value fields
                if not isinstance(value_field_key, _value.Unnamed):
                    # Value field is also named - this is a mismatch
                    # (if names matched, it would have been caught in Phase 2)
                    return MorphResult()

            positional_matches += 1
            # Track the match - store the actual value field key so we can exclude it from Phase 5
            matched_fields[shape_field_key] = (value_field_key, value_field, shape_field_type)
            # Track this key as matched using id() for Unnamed instances
            matched_value_keys.add(id(value_field_key))
            # Remove from unmatched tracking to prevent duplication in Phase 5
            del unmatched_value_fields[value_field_key]
        else:
            # Not enough positional values for this shape field
            # TODO: Check for defaults
            return MorphResult()

    # PHASE 4: Recursive morphing of each field
    morphed_struct = {}

    # Process all shape fields in shape order
    for field_key, _field_def in shape_fields.items():
        if field_key in matched_fields:
            value_field_key, value_field, field_shape = matched_fields[field_key]

            if field_shape:
                # Recursively morph the field value to its shape
                # Use _morph_any to avoid wrapping non-struct values
                field_result = _morph_any(value_field, field_shape)
                if field_result.success:
                    # Use the morphed value
                    morphed_value = field_result.value
                else:
                    # Recursive morph failed - this means the value doesn't match
                    # the shape constraint (e.g., string value for ~num field)
                    # The entire struct morph must fail
                    return MorphResult()

                # Determine result key:
                # - If shape field is named (Value), use the shape's field key
                # - If shape field is unnamed, preserve the value's original field key
                if isinstance(field_key, _value.Unnamed):
                    # Unnamed shape field - preserve value's field key
                    result_key = value_field_key
                else:
                    # Named shape field (Value object) - use shape's key
                    result_key = field_key

                morphed_struct[result_key] = morphed_value
            else:
                # No shape constraint - use value as-is
                # Same key selection logic as above
                if isinstance(field_key, _value.Unnamed):
                    # Unnamed shape field - preserve value's field key
                    result_key = value_field_key
                else:
                    # Named shape field (Value object) - use shape's key
                    result_key = field_key

                morphed_struct[result_key] = value_field

    # PHASE 5: Preserve extra fields from value (regular morph behavior)
    # Extra fields that weren't in the shape are passed through unchanged
    # Use id() to check if a field was matched (handles Unnamed instances which don't compare equal)
    for field_key, field_value in value.struct.items():
        if id(field_key) not in matched_value_keys:
            # This field wasn't matched by the shape - preserve it
            morphed_struct[field_key] = field_value

    # Build result value
    result_value = _value.Value({})
    result_value.struct = morphed_struct

    return MorphResult(
        named_matches=named_matches,
        positional_matches=positional_matches,
        value=result_value
    )
