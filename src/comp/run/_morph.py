"""Shape morphing and type checking logic."""

__all__ = ["MorphResult", "morph", "strong_morph", "weak_morph", "mask", "strict_mask"]

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
    # Track if we wrapped a non-struct value
    was_wrapped = False

    # Wrap non-struct values in a single-item structure
    if not value.is_struct:
        was_wrapped = True
        wrapped = _value.Value({})
        wrapped.struct = {_value.Unnamed(): value}
        value = wrapped

    # Delegate to internal morphing (handles unions and structs)
    result = _morph_any(value, shape)

    # Unwrap if we wrapped AND the target shape is a primitive (not structural)
    # This handles cases like: 5 ~num (stay unwrapped)
    # But NOT: 5 ~{~num} (should stay wrapped in struct)
    if was_wrapped and result.success and result.value is not None:
        # Only unwrap for primitive target shapes (~num, ~str, tag constraints)
        is_primitive_target = (
            isinstance(shape, _shape.ShapeRef) and
            shape.name in ("num", "str")
        ) or isinstance(shape, _shape.ShapeTagRef)

        if is_primitive_target and result.value.is_struct:
            if len(result.value.struct) == 1:
                # Get the single value
                single_key = next(iter(result.value.struct.keys()))
                if isinstance(single_key, _value.Unnamed):
                    # Unwrap to the original non-struct value
                    result.value = result.value.struct[single_key]

    return result


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
    # Accept both unnamed and named single fields: {5} ~num or {a=5} ~num
    if value.is_struct and value.struct and len(value.struct) == 1:
        single_key = next(iter(value.struct.keys()))
        # Unwrap regardless of whether field is named or unnamed
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
        # Step 1: Unwrap single-field structures (for scalar target)
        # Accept both unnamed and named single fields: {#status} ~#tag or {state=#status} ~#tag
        if value.is_struct and value.struct and len(value.struct) == 1:
            single_key = next(iter(value.struct.keys()))
            # Unwrap regardless of whether field is named or unnamed
            value = value.struct[single_key]

        # Step 2: Check if the value itself is a tag that matches the shape's tag requirement
        if value.is_tag and shape._resolved and value.tag:
            # Use the tag_value from the resolved TagDef which has proper namespace
            shape_tag = shape._resolved.tag_value
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
                    # Use the tag_value from the resolved TagDef which has proper namespace
                    shape_tag = shape._resolved.tag_value
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
            # This field wasn't matched by name, so it can be filled positionally or with defaults
            unfilled_shape_fields.append((field_key, field_def))

    # Collect remaining value fields for positional matching
    # Store (key, value) tuples so we can track which keys were matched
    # Rules:
    # - Unnamed value fields can fill ANY unfilled shape field positionally
    # - Named value fields can ONLY fill unnamed shape fields positionally
    #   (they cannot fill differently-named shape fields)
    remaining_value_fields = []
    for field_key, field_value in unmatched_value_fields.items():
        remaining_value_fields.append((field_key, field_value))

    # Match positionally: unfilled shape fields get filled by remaining value fields or defaults
    for i, (shape_field_key, shape_field_def) in enumerate(unfilled_shape_fields):
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
            matched_fields[shape_field_key] = (value_field_key, value_field, shape_field_def.shape)
            # Track this key as matched using id() for Unnamed instances
            matched_value_keys.add(id(value_field_key))
            # Remove from unmatched tracking to prevent duplication in Phase 5
            del unmatched_value_fields[value_field_key]
        else:
            # Not enough positional values - check for default
            if shape_field_def.default is not None:
                # Use the default value for this field
                # Create a synthetic match with the default value
                # The field_key is the shape field key, value is the default
                matched_fields[shape_field_key] = (shape_field_key, shape_field_def.default, shape_field_def.shape)
                # No need to track in matched_value_keys since this isn't from the input value
            else:
                # No positional value and no default - field is required but missing
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


def strong_morph(value, shape):
    """Strong morph (~*): exact structural conformance with strict validation.

    Like normal morph but rejects extra fields not defined in the shape.
    This enforces that the structure matches the shape exactly.

    Behavior:
    - Applies default values for missing fields
    - FAILS if extra fields are present (not in shape)
    - FAILS if required fields are missing
    - Restructures data to match shape (named↔positional)

    Use cases:
    - Configuration validation (no unexpected fields)
    - Security-critical inputs (whitelist exact structure)
    - API request validation (strict contracts)

    Args:
        value: The value to morph
        shape: The shape to morph to

    Returns:
        MorphResult with morphed value or failure if structure doesn't match exactly

    Example:
        # Success with defaults
        {host="localhost" port=3000} ~* {host ~str port ~num timeout ~num = 30}
        # Result: {host="localhost" port=3000 timeout=30}

        # Failure with extra fields
        {host="localhost" port=3000 extra="bad"} ~* {host ~str port ~num}
        # FAILS: Extra field 'extra' not allowed
    """
    # First do normal morph
    result = morph(value, shape)

    # If morph failed, propagate failure
    if not result.success:
        return result

    # Now check for extra fields
    if not result.value.is_struct:
        # Non-struct result, no extra fields possible
        return result

    # Resolve the shape to get field definitions
    if isinstance(shape, _shape.ShapeRef):
        if not shape._resolved:
            return MorphResult()  # Can't validate without resolved shape
        resolved_shape = shape._resolved
    elif isinstance(shape, _shape.ShapeDef):
        resolved_shape = shape
    else:
        # For non-struct shapes (primitives, tags), no extra field check needed
        return result

    # Build set of allowed field names from shape
    allowed_fields = set()
    has_positional = False
    for field_key in resolved_shape.fields.keys():
        if isinstance(field_key, _value.Unnamed):
            has_positional = True
        elif isinstance(field_key, _value.Value) and field_key.is_str:
            allowed_fields.add(field_key.str)

    # Check morphed result for extra fields
    for field_key in result.value.struct.keys():
        if isinstance(field_key, _value.Unnamed):
            # Unnamed/positional field
            if not has_positional:
                # Shape doesn't have positional fields, so this is extra
                return MorphResult()  # Fail due to extra positional field
        elif isinstance(field_key, _value.Value) and field_key.is_str:
            # Named field
            if field_key.str not in allowed_fields:
                # Extra field not in shape
                return MorphResult()  # Fail due to extra named field

    # All checks passed - return the morphed result
    return result


def weak_morph(value, shape):
    """Weak morph (~?): partial matching without defaults or required field checks.

    Like normal morph but allows missing fields and doesn't apply defaults.
    This enables type testing and pattern matching on partial data.

    Behavior:
    - Does NOT apply default values
    - Allows missing fields (partial match acceptable)
    - Ignores extra fields not in the shape
    - Only validates fields that are present
    - Used for pattern matching and type tests

    Use cases:
    - Pattern matching (check if data has certain fields)
    - Type testing (does this look like a User?)
    - Partial validation (validate what's there, ignore what's missing)
    - Progressive refinement (build up structure incrementally)

    Args:
        value: The value to check against shape
        shape: The shape to partially match

    Returns:
        MorphResult with matched fields only (no defaults added)

    Example:
        # Partial match - only validates present fields
        {name="Alice"} ~? {name ~str email ~str age ~num = 0}
        # Result: {name="Alice"}
        # Missing 'email' and 'age' are OK, no defaults applied

        # Type test
        data ~? user  ; Checks if data has user-like fields
    """
    # Wrap non-struct values
    was_wrapped = False
    if not value.is_struct:
        was_wrapped = True
        wrapped = _value.Value({})
        wrapped.struct = {_value.Unnamed(): value}
        value = wrapped

    # Resolve the shape
    if isinstance(shape, _shape.ShapeRef):
        if not shape._resolved:
            return MorphResult()
        resolved_shape = shape._resolved
    elif isinstance(shape, _shape.ShapeDef):
        resolved_shape = shape
    elif isinstance(shape, _shape.ShapeTagRef):
        # For tag refs, delegate to normal morph (tag checking doesn't need weak mode)
        result = morph(value, shape)
        if was_wrapped and result.success and result.value.is_struct:
            if len(result.value.struct) == 1:
                single_key = next(iter(result.value.struct.keys()))
                if isinstance(single_key, _value.Unnamed):
                    result.value = result.value.struct[single_key]
        return result
    else:
        # Unsupported shape type
        return MorphResult()

    # For struct shapes, validate only present fields (no defaults, missing OK)
    result_struct = {}
    named_matches = 0
    positional_matches = 0

    # Get shape fields
    shape_fields = resolved_shape.fields

    # Build a mapping of field names to their definitions for easier lookup
    shape_field_map = {}
    for shape_key, shape_def in shape_fields.items():
        if isinstance(shape_key, _value.Value) and shape_key.is_str:
            shape_field_map[shape_key.str] = shape_def

    # Match named fields first
    for field_key, field_value in value.struct.items():
        if isinstance(field_key, _value.Value) and field_key.is_str:
            field_name = field_key.str
            if field_name in shape_field_map:
                # Field exists in shape - validate it
                field_def = shape_field_map[field_name]
                # Recursively apply weak_morph to nested structures
                if field_value.is_struct and isinstance(field_def.shape, (_shape.ShapeRef, _shape.ShapeDef)):
                    field_morph = weak_morph(field_value, field_def.shape)
                else:
                    field_morph = _morph_any(field_value, field_def.shape)
                if field_morph.success:
                    result_struct[field_key] = field_morph.value
                    named_matches += 1
                else:
                    # Field validation failed - this is a hard failure
                    return MorphResult()
            # Else: extra field, just ignore it (weak morph allows extras)

    # Match positional fields
    value_positionals = [(k, v) for k, v in value.struct.items() if isinstance(k, _value.Unnamed)]
    shape_positionals = [(k, v) for k, v in shape_fields.items() if isinstance(k, _value.Unnamed)]

    for i, (pos_key, pos_value) in enumerate(value_positionals):
        if i < len(shape_positionals):
            shape_pos_key, shape_pos_def = shape_positionals[i]
            # Validate positional field
            field_morph = _morph_any(pos_value, shape_pos_def.shape)
            if field_morph.success:
                result_struct[_value.Unnamed()] = field_morph.value
                positional_matches += 1
            else:
                # Positional validation failed
                return MorphResult()
        # Else: extra positional field, ignore it

    # Create result value
    result_value = _value.Value({})
    result_value.struct = result_struct

    # Unwrap if needed
    if was_wrapped and result_value.is_struct:
        is_primitive_target = (
            isinstance(shape, _shape.ShapeRef) and
            shape.name in ("num", "str")
        ) or isinstance(shape, _shape.ShapeTagRef)

        if is_primitive_target and len(result_value.struct) == 1:
            single_key = next(iter(result_value.struct.keys()))
            if isinstance(single_key, _value.Unnamed):
                result_value = result_value.struct[single_key]

    # Return result with only matched fields (no indication of missing fields)
    return MorphResult(
        named_matches=named_matches,
        positional_matches=positional_matches,
        value=result_value
    )


def mask(value, shape):
    """Permissive mask (^): filter value to intersection of data and shape fields.

    Returns only fields that exist in BOTH the value and the shape.
    Does NOT apply defaults for missing fields.
    Does NOT fail if fields are missing or extra.
    Always succeeds for struct values (may return empty struct).

    This is the filtering operation used to mask $ctx and $mod scopes
    in function argument processing.

    Args:
        value: The value (typically a struct/scope) to filter
        shape: The shape defining allowed fields

    Returns:
        MorphResult with filtered value containing only intersecting fields.
        Success is always True for struct values. Score indicates number of matched fields.

    Example:
        data = {user="alice" session="abc" debug=#true admin="secret"}
        shape = {user ~str session ~str}
        result = mask(data, shape)
        # result.value = {user="alice" session="abc"}
        # Removed: debug, admin (not in shape)
    """
    # Only structs can be masked
    if not value.is_struct:
        return MorphResult()

    # Resolve shape reference
    if isinstance(shape, _shape.ShapeRef):
        if not shape._resolved:
            return MorphResult()
        resolved_shape = shape._resolved
    elif isinstance(shape, _shape.ShapeDef):
        resolved_shape = shape
    else:
        # Not a valid shape type
        return MorphResult()

    # Build set of field names from shape (only named fields)
    shape_field_names = set()
    for field_key in resolved_shape.fields.keys():
        # Field keys are Value objects (for named) or Unnamed (for positional)
        if not isinstance(field_key, _value.Unnamed) and hasattr(field_key, 'str'):
            shape_field_names.add(field_key.str)

    # Filter value to only include fields that are in the shape
    filtered_struct = {}
    matched_count = 0

    for key, val in value.struct.items():
        # Check if this is a named field that exists in the shape
        if isinstance(key, _value.Value) and key.is_str:
            field_name = key.str
            if field_name in shape_field_names:
                # This field is in both value and shape - keep it
                filtered_struct[key] = val
                matched_count += 1
        # Note: We ignore unnamed fields and fields not in the shape

    # Build result value
    filtered_value = _value.Value({})
    filtered_value.struct = filtered_struct

    # Always succeeds (even if empty) - score indicates quality of match
    return MorphResult(named_matches=matched_count, value=filtered_value)


def strict_mask(value, shape):
    """Strict mask (^*): validate exact shape match with defaults.

    Validates that the value exactly matches the shape structure:
    - Applies defaults for missing fields with defaults
    - FAILS if extra fields are present in value
    - FAILS if required fields are missing from value
    - Type mismatches cause failure

    This is functionally equivalent to strong morph (~*) but with
    masking semantics (filtering rather than transformation).
    Used for function argument validation.

    Args:
        value: The value to validate and complete
        shape: The shape to match exactly

    Returns:
        MorphResult with validated value (with defaults applied), or failure.

    Example:
        args = {host="localhost" port=3000}
        shape = {host ~str port ~num timeout ~num = 30}
        result = strict_mask(args, shape)
        # result.value = {host="localhost" port=3000 timeout=30}

        invalid = {host="localhost" extra="bad"}
        result = strict_mask(invalid, shape)
        # result.success = False (extra field 'extra')
    """
    # For now, strict mask is identical to strong morph
    # TODO: When strong morph (~*) is implemented, call it here
    # For now, use regular morph and manually check for extra fields

    # First, do regular morph to get the structure with defaults
    morph_result = morph(value, shape)

    if not morph_result.success:
        return morph_result

    # Now check if the original value had any extra fields not in the shape
    # (Regular morph allows extra fields, but strict mask should not)

    if not value.is_struct:
        # Non-struct values that morphed successfully are OK
        return morph_result

    # Resolve shape to get field names
    if isinstance(shape, _shape.ShapeRef):
        if not shape._resolved:
            return MorphResult()
        resolved_shape = shape._resolved
    elif isinstance(shape, _shape.ShapeDef):
        resolved_shape = shape
    else:
        return MorphResult()

    # Build set of allowed field names from shape
    allowed_field_names = set()
    has_positional = False

    for field_key in resolved_shape.fields.keys():
        # Field keys are Value objects (for named) or Unnamed (for positional)
        if isinstance(field_key, _value.Unnamed):
            has_positional = True
        elif hasattr(field_key, 'str'):
            allowed_field_names.add(field_key.str)

    # Check if value has any fields not in the shape
    for key in value.struct.keys():
        if isinstance(key, _value.Value) and key.is_str:
            field_name = key.str
            if field_name not in allowed_field_names:
                # Extra named field found - strict mask fails
                return MorphResult()
        elif isinstance(key, _value.Unnamed):
            # Unnamed field - only OK if shape has positional fields
            if not has_positional:
                return MorphResult()
        # Note: Other key types (tag values, etc.) are OK if morph succeeded

    # No extra fields found - strict mask succeeds
    return morph_result
