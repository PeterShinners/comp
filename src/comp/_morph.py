"""Shape morphing and type checking logic."""

__all__ = ["MorphResult", "morph", "strong_morph", "weak_morph"]

import comp

from . import _tag


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
    # Try to unwrap scalar values from single-element structs
    # This handles cases like {{5}} ~num or {{RawBlock}} ~:{}
    scalar_value = value.as_scalar()
    
    # Special handling for block morphing: RawBlock + BlockShapeDefinition → Block
    if scalar_value.is_block and isinstance(scalar_value.data, comp.RawBlock):
        # Check if shape is a BlockShapeDefinition
        if isinstance(shape, comp.BlockShapeDefinition):
            # Create a Block with the raw block and the shape fields as input shape
            block = comp.Block(scalar_value.data, input_shape=shape.fields)
            return MorphResult(named_matches=1, value=comp.Value(block))
        
        # Check if shape is a ShapeDefinition with a single positional BlockShapeDefinition field
        # This handles: :{...} ~nil-block where ~nil-block = ~:{}
        if isinstance(shape, comp.ShapeDefinition):
            if len(shape.fields) == 1 and not shape.fields[0].is_named:
                # The field shape might be wrapped in a Value
                field_shape = shape.fields[0].shape
                if isinstance(field_shape, comp.Value):
                    field_shape = field_shape.data
                
                if isinstance(field_shape, comp.BlockShapeDefinition):
                    # Extract the BlockShapeDefinition from the shape field
                    block = comp.Block(scalar_value.data, input_shape=field_shape.fields)
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
    result = _morph_any(value, shape, was_wrapped=was_wrapped)

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


def _morph_any(value, shape, was_wrapped=False):
    """Internal morph function that handles any value without wrapping.

    This is used for recursive morphing of field values where we don't want
    to wrap non-struct values in an extra layer.

    Args:
        value: The value to morph (struct or non-struct)
        shape: The shape to morph to
        was_wrapped: True if the value was wrapped by the outer morph() call

    Returns:
        MorphResult with the morphed value or failure
    """
    # Handle unions by trying all variants and picking the best
    if hasattr(shape, 'variants'):  # ShapeUnion check
        best_result = MorphResult()  # Zero score, no value

        for variant in shape.variants:
            variant_result = _morph_any(value, variant, was_wrapped=was_wrapped)
            if variant_result.success and variant_result > best_result:
                best_result = variant_result

        return best_result

    # For non-union shapes, delegate to the appropriate handler
    # Struct values go to _morph_struct, primitives to _morph_primitive
    return _morph_struct(value, shape, was_wrapped=was_wrapped)


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

    # Step 1b: Extract tag value if morphing a tag to a primitive type
    if value.is_tag:
        tag_ref = value.data
        if tag_ref.tag_def.value is not None:
            # Use the tag's associated value (ensure it's wrapped in Value)
            tag_value = tag_ref.tag_def.value
            if not isinstance(tag_value, comp.Value):
                tag_value = comp.Value(tag_value)
            value = tag_value
        else:
            # Tag has no value - can't morph to primitive
            return MorphResult()

    # Step 2: Check if value matches the expected type
    if type_name == "num":
        if value.is_number:
            return MorphResult(positional_matches=0, value=value)

    elif type_name == "str":
        if value.is_string:
            return MorphResult(positional_matches=0, value=value)


    # Step 3: Type mismatch - fail the morph
    return MorphResult()


def _morph_struct(value, shape, was_wrapped=False):
    """Internal morphing logic for structures.

    This is where the actual morphing algorithm lives. Assumes value is already
    a structure (caller should wrap non-structs first).

    Args:
        value: The value to morph (should be a struct)
        shape: The shape to morph to
        was_wrapped: True if the value was wrapped by the outer morph() call

    Returns both the match score and the morphed value in a single pass.
    """
    # Handle primitive type shapes (~num, ~str, ~bool, ~tag, ~any, ~struct)
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
        elif shape.full_name == "struct":
            # ~struct requires an actual struct, rejecting primitives that would be promoted
            # Only reject if the wrapping was done by morph() (was_wrapped=True)
            # This means: 5~struct fails, but {5}~struct succeeds
            if was_wrapped:
                return MorphResult()
            # Accept the struct (it came in already as a struct)
            return MorphResult(positional_matches=0, value=value)
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

    # PHASE 2: Tag field matching
    # Match unnamed tag values to shape fields with tag type constraints
    
    # Identify shape fields with tag types and unnamed tag values
    tag_shape_fields = {}  # field_name -> (shape_field, tag_def)
    for field in shape_fields:
        if field.is_named and field.name in named_shape_fields and field.shape is not None:
            # Check if the shape constraint is a TagRef (tag type)
            if isinstance(field.shape, comp.Value) and field.shape.is_tag:
                tag_def = field.shape.data.tag_def
                tag_shape_fields[field.name] = (field, tag_def)
    
    # Find unnamed tag values in input
    unnamed_tags = [(k, v) for k, v in unmatched_value_fields 
                    if isinstance(k, comp.Unnamed) and isinstance(v, comp.Value) and v.is_tag]
    
    # Match tags to fields
    matched_tag_keys = []
    tag_depth_sum = 0
    for pos_key, tag_value in unnamed_tags:
        input_tag_def = tag_value.data.tag_def
        
        # Try to find a compatible tag field
        matched_field = None
        for field_name, (shape_field, field_tag_def) in tag_shape_fields.items():
            # Check if input tag is compatible with field's tag type
            # Compatible means: same tag or input is a child of field's tag
            if _tag.is_tag_compatible(input_tag_def, field_tag_def):
                matched_field = (field_name, shape_field, field_tag_def)
                break
        
        if matched_field:
            field_name, shape_field, field_tag_def = matched_field
            field_key = comp.Value(field_name)
            
            # Assign the tag value to this field
            matched_fields[field_key] = (shape_field, tag_value)
            
            # Count this as a named match (filling a named field)
            named_matches += 1
            
            # Track tag depth for specificity (deeper tags = more specific)
            tag_depth_sum += len(input_tag_def.path)
            
            # Remove from unmatched collections
            del named_shape_fields[field_name]
            del tag_shape_fields[field_name]
            matched_tag_keys.append(pos_key)
    
    # Remove matched tags from unmatched_value_fields
    unmatched_value_fields = [(k, v) for k, v in unmatched_value_fields 
                              if k not in matched_tag_keys]

    # PHASE 3: Positional matching
    # Match positional (unnamed) value fields to shape fields by position
    positional_matches = 0
    positional_value_fields = [(k, v) for k, v in unmatched_value_fields if isinstance(k, comp.Unnamed)]

    # PHASE 3a: Match unnamed value fields to positional shape fields
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
            # More positional values than shape fields - will try named field pairing next
            break

    # Remove matched positional shape fields
    positional_shape_fields = positional_shape_fields[matched_positional_count:]
    
    # Remove matched positional value fields from unmatched list
    remaining_unnamed_values = positional_value_fields[matched_positional_count:]

    # PHASE 3b: Pair remaining unnamed value fields with unfilled named shape fields
    # This handles cases like {a=1 2 c=3} ~{a~num b~num c~num} where 2 should fill b
    paired_positional_keys = []
    if remaining_unnamed_values and named_shape_fields:
        # Get list of unfilled named fields in definition order
        unfilled_named_fields = [field for field in shape_fields 
                                if field.is_named and field.name in named_shape_fields]
        
        for (pos_key, pos_value), shape_field in zip(remaining_unnamed_values, unfilled_named_fields):
            # Create named key for this field
            field_key = comp.Value(shape_field.name)
            
            # Recursively morph
            if shape_field.shape is not None:
                field_result = _morph_any(pos_value, shape_field.shape)
                if not field_result.success:
                    return MorphResult()
                matched_fields[field_key] = (shape_field, field_result.value)
            else:
                matched_fields[field_key] = (shape_field, pos_value)
            
            # This counts as a named match since we're filling a named field
            named_matches += 1
            
            # Remove from unfilled named fields
            del named_shape_fields[shape_field.name]
            
            # Track this positional key so we don't add it again as an extra field
            paired_positional_keys.append(pos_key)

    # PHASE 4: Default application
    # Apply defaults for unmatched shape fields that weren't matched
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

    # Build result structure (matched fields + extra fields)
    result_struct = {}

    # Add all matched fields
    for field_key, (_shape_field, morphed_value) in matched_fields.items():
        result_struct[field_key] = morphed_value

    # Add extra fields (not in shape) - pass through unchanged
    # Exclude positional fields that were paired with named fields in Phase 2.5
    for field_key, field_value in unmatched_value_fields:
        if field_key not in matched_fields and field_key not in paired_positional_keys:
            result_struct[field_key] = field_value

    # Build result value
    result_value = comp.Value(result_struct)

    return MorphResult(
        named_matches=named_matches,
        tag_depth=tag_depth_sum,
        positional_matches=positional_matches,
        value=result_value
    )


def strong_morph(value, shape):
    """Strong morph (~*): exact structural conformance with strict validation.

    Like normal morph but rejects extra fields not defined in the shape.

    Behavior:
    - Applies unnamed→named field pairing (Phase 3b)
    - Applies default values for missing fields
    - FAILS if extra fields remain in morphed result (not in shape)
    - FAILS if required fields are missing

    Example:
        {host="localhost" port=3000} ~* {host ~str port ~num timeout ~num = 30}
        # Success: {host="localhost" port=3000 timeout=30}

        {host="localhost" extra="bad"} ~* {host ~str}
        # FAILS: Extra field 'extra' not allowed
        
        {5 7} ~* {x ~num y ~num}
        # Success: {x=5 y=7} - unnamed fields paired to named fields
    """
    # First do normal morph (includes Phase 3b unnamed→named pairing)
    result = morph(value, shape)

    if not result.success:
        return result

    # Now check the morphed result for extra fields
    # Extra fields are those not consumed by the morphing process
    if not isinstance(shape, comp.ShapeDefinition):
        return result

    # Build set of allowed field names from shape
    allowed_names = {field.name for field in shape.fields if field.is_named}
    has_positional = any(field.is_positional for field in shape.fields)

    # Check morphed result for extra fields
    # Morphing should have paired unnamed→named or added them as extra
    if result.value.is_struct:
        for field_key in result.value.data.keys():
            if isinstance(field_key, comp.Unnamed):
                # Unnamed field in result means it wasn't paired/consumed
                if not has_positional:
                    return MorphResult()
            elif field_key.is_string:
                if field_key.data not in allowed_names:
                    # Extra named field not allowed
                    return MorphResult()

    return result


def weak_morph(value, shape):
    """Weak morph (~?): filter value to intersection of data and shape fields.

    Returns only fields that exist in BOTH the value and the shape.
    Does NOT apply defaults for missing fields.
    Does NOT validate type constraints.
    Does NOT restructure data.
    Always succeeds for struct values (may return empty struct).

    This is conceptually similar to "field masking" - it filters fields
    without any validation or transformation.

    Example:
        data = {user="alice" session="abc" debug=#true admin="secret"}
        shape = {user ~str session ~str}
        result = weak_morph(data, shape)
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
            continue  # Weak morph only filters named fields
        if key.is_string and key.data in shape_field_names:
            filtered_struct[key] = val
            matched_count += 1

    filtered_value = comp.Value(filtered_struct)

    # Always succeeds (even if empty)
    return MorphResult(named_matches=matched_count, value=filtered_value)
