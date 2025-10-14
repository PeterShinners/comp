"""Shape morphing and type checking logic."""

__all__ = ["MorphResult", "morph", "strong_morph", "weak_morph", "mask", "strict_mask"]

import comp


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
            return False
        return self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        value_info = f" value={self.value}" if self.value else " (no match)"
        return (f"MorphResult(named={self.named_matches}, tag={self.tag_depth}, "
                f"weight={self.assignment_weight}, pos={self.positional_matches}{value_info})")

    @property
    def success(self):
        """Check if the morph succeeded (has a value)."""
        return self.value is not None


def morph(value, shape):
    """Morph a value to match a shape, returning both score and morphed value.

    Non-struct values are wrapped in single-item unfielded structures first,
    so the morphing logic only needs to handle structures.

    Returns a MorphResult with:
    - Score components (named_matches, tag_depth, assignment_weight, positional_matches)
    - value: the morphed Value, or None if morphing failed

    For unions, tries all variants and returns the best match.
    
    Special case: RawBlock + BlockShape → Block
    """
    # Special handling for block morphing: RawBlock + BlockShapeDefinition → Block
    if value.is_entity and isinstance(value.data, comp.RawBlock):
        # Check if shape is a BlockShapeDefinition
        if isinstance(shape, comp.BlockShapeDefinition):
            # Create a Block with the raw block and the shape fields as input shape
            block = comp.Block(value.data, input_shape=shape.fields)
            return MorphResult(named_matches=1, value=comp.Value(block))
        # If shape is not a block type, morphing RawBlock fails
        return MorphResult()  # No match
    
    # Track if we wrapped a non-struct value
    was_wrapped = False

    # Wrap non-struct values in a single-item structure
    if not value.is_struct:
        was_wrapped = True
        wrapped = comp.Value({})
        wrapped.data[comp.Unnamed()] = value
        value = wrapped

    # Delegate to internal morphing (handles unions and structs)
    result = _morph_any(value, shape)

    # Unwrap if we wrapped AND the target shape is a primitive (not structural)
    # This handles cases like: 5 ~num (stay unwrapped)
    # But NOT: 5 ~{~num} (should stay wrapped in struct)
    if was_wrapped and result.success and result.value is not None:
        # Only unwrap for primitive target shapes (~num, ~str, tag constraints)
        is_primitive_target = (
            isinstance(shape, comp.ShapeDefinition) and
            shape.full_name in ("num", "str", "bool", "tag", "any")
        )

        if is_primitive_target and result.value.is_struct:
            # Unwrap single-item struct
            if len(result.value.data) == 1:
                single_key = next(iter(result.value.data.keys()))
                result.value = result.value.data[single_key]

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
    if hasattr(shape, 'variants'):  # ShapeUnion check
        best_result = MorphResult()  # Zero score, no value

        for variant in shape.variants:
            variant_result = _morph_any(value, variant)
            if variant_result.success and variant_result > best_result:
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
    if value.is_struct and len(value.data) == 1:
        single_key = next(iter(value.data.keys()))
        # Unwrap regardless of whether field is named or unnamed
        value = value.data[single_key]

    # Step 2: Check if value matches the expected type
    if type_name == "num":
        if value.is_number:
            return MorphResult(positional_matches=0, value=value)

    elif type_name == "str":
        if value.is_string:
            return MorphResult(positional_matches=0, value=value)


    # Step 3: Type mismatch - fail the morph
    return MorphResult()


def _morph_struct(value, shape):
    """Internal morphing logic for structures.

    This is where the actual morphing algorithm lives. Assumes value is already
    a structure (caller should wrap non-structs first).

    Returns both the match score and the morphed value in a single pass.
    """
    # Handle primitive type shapes (~num, ~str, ~bool, ~tag, ~any)
    if isinstance(shape, comp.ShapeDefinition):
        if shape.full_name in ("num", "str"):
            return _morph_primitive(value, shape.full_name)
        elif shape.full_name == "bool":
            # Bool requires #true or #false tags
            if value.is_struct and len(value.data) == 1:
                value = value.data[next(iter(value.data.keys()))]
            if value.is_tag:
                tag = value.data
                if tag.full_name in ("true", "false"):
                    return MorphResult(tag_depth=1, value=value)
            return MorphResult()
        elif shape.full_name == "tag":
            # Accept any tag
            if value.is_struct and len(value.data) == 1:
                value = value.data[next(iter(value.data.keys()))]
            if value.is_tag:
                return MorphResult(tag_depth=1, value=value)
            return MorphResult()
        elif shape.full_name == "any":
            # ~any accepts anything
            return MorphResult(positional_matches=0, value=value)

    # For structural shapes, we need field definitions
    if not isinstance(shape, comp.ShapeDefinition):
        # Unknown shape type
        return MorphResult()

    shape_fields = shape.fields

    # If shape has no fields, accept any struct with minimal score
    if not shape_fields:
        return MorphResult(positional_matches=0, value=value)

    # PHASE 1: Match named fields
    # Build a mapping from field names to ShapeField objects for quick lookup
    named_shape_fields = {field.name: field for field in shape_fields if field.is_named}
    positional_shape_fields = [field for field in shape_fields if field.is_positional]

    named_matches = 0
    matched_fields = {}  # Maps Value key -> (ShapeField, morphed_value)
    unmatched_value_fields = []  # List of (key, value) tuples not matched by name

    # Process value fields
    for field_key, field_value in value.data.items():
        if isinstance(field_key, comp.Unnamed):
            # Positional field - handle in Phase 2
            unmatched_value_fields.append((field_key, field_value))
        elif field_key.is_string:
            # Named field - try to match by name
            field_name = field_key.data
            if field_name in named_shape_fields:
                shape_field = named_shape_fields[field_name]
                # Recursively morph the field value if it has a type constraint
                if shape_field.shape is not None:
                    field_result = _morph_any(field_value, shape_field.shape)
                    if not field_result.success:
                        # Field type mismatch - morph fails
                        return MorphResult()
                    matched_fields[field_key] = (shape_field, field_result.value)
                else:
                    # No type constraint - pass through
                    matched_fields[field_key] = (shape_field, field_value)
                named_matches += 1
                # Mark this shape field as satisfied
                del named_shape_fields[field_name]
            else:
                # Named field not in shape - keep for Phase 3 (extra fields)
                unmatched_value_fields.append((field_key, field_value))
        else:
            # Non-string key - treat as extra field
            unmatched_value_fields.append((field_key, field_value))

    # PHASE 2: Match positional fields
    positional_matches = 0
    positional_value_fields = [(k, v) for k, v in unmatched_value_fields if isinstance(k, comp.Unnamed)]

    matched_positional_count = 0
    for i, (pos_key, pos_value) in enumerate(positional_value_fields):
        if i < len(positional_shape_fields):
            shape_field = positional_shape_fields[i]
            # Recursively morph
            if shape_field.shape is not None:
                field_result = _morph_any(pos_value, shape_field.shape)
                if not field_result.success:
                    return MorphResult()
                matched_fields[pos_key] = (shape_field, field_result.value)
            else:
                matched_fields[pos_key] = (shape_field, pos_value)
            positional_matches += 1
            matched_positional_count += 1
        else:
            # More positional values than shape fields - extra field
            pass

    # Remove matched positional shape fields
    positional_shape_fields = positional_shape_fields[matched_positional_count:]

    # PHASE 3: Apply defaults for missing required fields
    # Check remaining shape fields that weren't matched
    for field_name, shape_field in named_shape_fields.items():
        if shape_field.default is not None:
            # Apply default value
            field_key = comp.Value(field_name)
            matched_fields[field_key] = (shape_field, shape_field.default)
        else:
            # Required field missing - morph fails
            return MorphResult()

    # Check unmatched positional fields
    for shape_field in positional_shape_fields:
        if shape_field.default is not None:
            # Apply default (add as unnamed field)
            field_key = comp.Unnamed()
            matched_fields[field_key] = (shape_field, shape_field.default)
        else:
            # Required positional field missing - morph fails
            return MorphResult()

    # PHASE 4: Build result structure (matched fields + extra fields)
    result_struct = {}

    # Add all matched fields
    for field_key, (shape_field, morphed_value) in matched_fields.items():
        result_struct[field_key] = morphed_value

    # Add extra fields (not in shape) - pass through unchanged
    for field_key, field_value in unmatched_value_fields:
        if field_key not in matched_fields:
            result_struct[field_key] = field_value

    # Build result value
    result_value = comp.Value(result_struct)

    return MorphResult(
        named_matches=named_matches,
        positional_matches=positional_matches,
        value=result_value
    )


def strong_morph(value, shape):
    """Strong morph (~*): exact structural conformance with strict validation.

    Like normal morph but rejects extra fields not defined in the shape.

    Behavior:
    - Applies default values for missing fields
    - FAILS if extra fields are present (not in shape)
    - FAILS if required fields are missing

    Example:
        {host="localhost" port=3000} ~* {host ~str port ~num timeout ~num = 30}
        # Success: {host="localhost" port=3000 timeout=30}

        {host="localhost" extra="bad"} ~* {host ~str}
        # FAILS: Extra field 'extra' not allowed
    """
    # First do normal morph
    result = morph(value, shape)

    if not result.success:
        return result

    # Now check for extra fields
    if not isinstance(shape, comp.ShapeDefinition):
        return result

    # Build set of allowed field names from shape
    allowed_names = {field.name for field in shape.fields if field.is_named}
    has_positional = any(field.is_positional for field in shape.fields)

    # Check original value for extra fields
    if value.is_struct:
        for field_key in value.data.keys():
            if isinstance(field_key, comp.Unnamed):
                if not has_positional:
                    # Unnamed field not allowed
                    return MorphResult()
            elif field_key.is_string:
                if field_key.data not in allowed_names:
                    # Extra named field not allowed
                    return MorphResult()

    return result


def weak_morph(value, shape):
    """Weak morph (~?): partial matching without defaults or required field checks.

    Like normal morph but allows missing fields and doesn't apply defaults.

    Behavior:
    - Does NOT apply default values
    - Allows missing fields (partial match acceptable)
    - Ignores extra fields not in the shape
    - Only validates fields that are present

    Example:
        {name="Alice"} ~? {name ~str email ~str age ~num = 0}
        # Result: {name="Alice"}  (no defaults, missing fields OK)
    """
    # Wrap non-struct values
    was_wrapped = False
    if not value.is_struct:
        was_wrapped = True
        value = comp.Value({comp.Unnamed(): value})

    # For primitive shapes, delegate to normal morph
    if isinstance(shape, comp.ShapeDefinition) and shape.full_name in ("num", "str", "bool", "tag", "any"):
        result = morph(value, shape)
        if was_wrapped and result.success and result.value and result.value.is_struct:
            if len(result.value.data) == 1:
                result.value = result.value.data[next(iter(result.value.data.keys()))]
        return result

    # For struct shapes, validate only present fields (no defaults, missing OK)
    if not isinstance(shape, comp.ShapeDefinition):
        return MorphResult()

    result_struct = {}
    named_matches = 0
    positional_matches = 0

    # Build field map
    named_fields = {field.name: field for field in shape.fields if field.is_named}
    positional_fields = [field for field in shape.fields if field.is_positional]

    # Match named fields
    for field_key, field_value in value.data.items():
        if isinstance(field_key, comp.Unnamed):
            continue  # Handle positional separately
        if not field_key.is_string:
            continue

        field_name = field_key.data
        if field_name in named_fields:
            shape_field = named_fields[field_name]
            # Validate this field if it has a type constraint
            if shape_field.shape is not None:
                field_result = _morph_any(field_value, shape_field.shape)
                if field_result.success:
                    result_struct[field_key] = field_result.value
                    named_matches += 1
                # else: field validation failed, exclude from result
            else:
                result_struct[field_key] = field_value
                named_matches += 1

    # Match positional fields
    value_positionals = [(k, v) for k, v in value.data.items() if isinstance(k, comp.Unnamed)]
    for i, (_pos_key, pos_value) in enumerate(value_positionals):
        if i < len(positional_fields):
            shape_field = positional_fields[i]
            if shape_field.shape is not None:
                field_result = _morph_any(pos_value, shape_field.shape)
                if field_result.success:
                    result_struct[comp.Unnamed()] = field_result.value
                    positional_matches += 1
            else:
                result_struct[comp.Unnamed()] = pos_value
                positional_matches += 1

    result_value = comp.Value(result_struct)

    # Unwrap if needed
    if was_wrapped and result_value.is_struct and len(result_value.data) == 1:
        single_key = next(iter(result_value.data.keys()))
        if isinstance(single_key, comp.Unnamed):
            result_value = result_value.data[single_key]

    return MorphResult(
        named_matches=named_matches,
        positional_matches=positional_matches,
        value=result_value
    )


def mask(value, shape):
    """Permissive mask (^): filter value to intersection of data and shape fields.

    Returns only fields that exist in BOTH the value and the shape.
    Does NOT apply defaults for missing fields.
    Always succeeds for struct values (may return empty struct).

    Example:
        data = {user="alice" session="abc" debug=#true admin="secret"}
        shape = {user ~str session ~str}
        result = mask(data, shape)
        # result.value = {user="alice" session="abc"}
    """
    # Only structs can be masked
    if not value.is_struct:
        return MorphResult()

    if not isinstance(shape, comp.ShapeDefinition):
        return MorphResult()

    # Build set of field names from shape
    shape_field_names = {field.name for field in shape.fields if field.is_named}

    # Filter value to only include fields that are in the shape
    filtered_struct = {}
    matched_count = 0

    for key, val in value.data.items():
        if isinstance(key, comp.Unnamed):
            continue  # Mask only filters named fields
        if key.is_string and key.data in shape_field_names:
            filtered_struct[key] = val
            matched_count += 1

    filtered_value = comp.Value(filtered_struct)

    # Always succeeds (even if empty)
    return MorphResult(named_matches=matched_count, value=filtered_value)


def strict_mask(value, shape):
    """Strict mask (^*): validate exact shape match with defaults.

    Validates that the value exactly matches the shape structure:
    - Applies defaults for missing fields with defaults
    - FAILS if extra fields are present in value
    - FAILS if required fields are missing from value

    This is functionally equivalent to strong morph (~*).

    Example:
        args = {host="localhost" port=3000}
        shape = {host ~str port ~num timeout ~num = 30}
        result = strict_mask(args, shape)
        # result.value = {host="localhost" port=3000 timeout=30}
    """
    # Strict mask is identical to strong morph
    return strong_morph(value, shape)
