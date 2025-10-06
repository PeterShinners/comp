"""Shape type system for runtime type checking and dispatch."""

from __future__ import annotations

__all__ = [
    "ShapeType",
    "ShapeDefRef",
    "ShapeModRef",
    "ShapeTagRef",
    "ShapeInline",
    "ShapeUnion",
    "MorphResult",
    "morph",
]

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import _module, _value


class MorphResult:
    """Result of a morph operation containing both score and morphed value.

    The score tuple: (named_matches, tag_depth, assignment_weight, positional_matches)
    determines how well the value matched the shape. Higher scores are better matches.

    The value is the morphed result, or None if morphing failed.
    """
    __slots__ = ("named_matches", "tag_depth", "assignment_weight", "positional_matches", "value")

    def __init__(
        self,
        named_matches: int = 0,
        tag_depth: int = 0,
        assignment_weight: int = 0,
        positional_matches: int = -1,
        value: _value.Value | None = None,
    ):
        self.named_matches = named_matches
        self.tag_depth = tag_depth
        self.assignment_weight = assignment_weight
        self.positional_matches = positional_matches
        self.value = value

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Get the score components as a tuple for comparison."""
        return (self.named_matches, self.tag_depth, self.assignment_weight, self.positional_matches)

    def __gt__(self, other: MorphResult) -> bool:
        """Lexicographic comparison - earlier components more important."""
        return self.as_tuple() > other.as_tuple()

    def __lt__(self, other: MorphResult) -> bool:
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MorphResult):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        value_info = f" value={self.value}" if self.value else " (no match)"
        return (f"MorphResult(named={self.named_matches}, tag={self.tag_depth}, "
                f"weight={self.assignment_weight}, pos={self.positional_matches}{value_info})")

    @property
    def success(self) -> bool:
        """True if morphing succeeded (value is not None)."""
        return self.value is not None


def morph(value: _value.Value, shape: ShapeType) -> MorphResult:
    """Morph a value to match a shape, returning both score and morphed value.

    Non-struct values are wrapped in single-item unfielded structures first,
    so the morphing logic only needs to handle structures.

    Returns a MorphResult with:
    - Score components (named_matches, tag_depth, assignment_weight, positional_matches)
    - value: the morphed Value, or None if morphing failed

    For unions, tries all variants and returns the best match.
    """
    from . import _struct

    # Wrap non-struct values in a single-item structure
    if not value.is_struct:
        from . import _value as value_mod
        wrapped = value_mod.Value({})
        wrapped.struct = {_struct.Unnamed(): value}
        value = wrapped

    # Delegate to internal morphing (handles unions and structs)
    return _morph_any(value, shape)


def _morph_any(value: _value.Value, shape: ShapeType) -> MorphResult:
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
    if isinstance(shape, ShapeUnion):
        best_result = MorphResult()  # Zero score, no value

        for variant in shape.variants:
            variant_result = _morph_any(value, variant)
            if variant_result > best_result:
                best_result = variant_result

        return best_result

    # For non-union shapes, delegate to the appropriate handler
    # Struct values go to _morph_struct, primitives to _morph_primitive
    return _morph_struct(value, shape)


def _morph_primitive(value: _value.Value, type_name: str) -> MorphResult:
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
    from . import _struct

    # Step 1: Unwrap single-item structures (for top-level morph calls)
    # If called from recursive morph, value may already be a primitive
    if value.is_struct and value.struct and len(value.struct) == 1:
        single_key = next(iter(value.struct.keys()))
        if isinstance(single_key, _struct.Unnamed):
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


def _morph_struct(value: _value.Value, shape: ShapeType) -> MorphResult:
    """Internal morphing logic for structures.

    This is where the actual morphing algorithm lives. Assumes value is already
    a structure (caller should wrap non-structs first).

    Returns both the match score and the morphed value in a single pass.

    Note: This function should NOT receive ShapeUnion - unions are handled
    in the outer morph() function.
    """
    from . import _struct, _tag

    # Handle ShapeTagRef separately - it's a constraint, not a structural shape
    if isinstance(shape, ShapeTagRef):
        # Check if the value itself is a tag that matches the shape's tag requirement
        if value.is_tag and shape._resolved and value.tag:
            # Create a Tag object from the resolved TagDef for comparison
            # TagDef has identifier (list of strings) that we can use to make a Tag
            shape_tag = _tag.Tag(shape._resolved.identifier, "builtin")  # TODO: Get proper namespace
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
                if isinstance(field_key, _struct.Unnamed) and field_value.is_tag and field_value.tag:
                    # Create a Tag object from the resolved TagDef
                    shape_tag = _tag.Tag(shape._resolved.identifier, "builtin")  # TODO: Get proper namespace
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
    # These are special ShapeDefRef instances that morph to/from basic types
    if isinstance(shape, ShapeDefRef) and shape.name in ("num", "str"):
        return _morph_primitive(value, shape.name)

    # For structural shapes, we need field definitions
    shape_fields = None

    if isinstance(shape, ShapeInline):
        # Use inline field definitions directly
        shape_fields = shape.fields
    elif isinstance(shape, (ShapeDefRef, ShapeModRef)):
        # Get fields from resolved shape definition
        if isinstance(shape, ShapeDefRef) and shape._resolved:
            # Check if this is a non-structural shape (e.g., tag constraint or shape alias)
            if shape._resolved.shape:
                # Delegate to the actual shape type
                return _morph_any(value, shape._resolved.shape)
            shape_fields = shape._resolved.fields
        elif isinstance(shape, ShapeModRef) and shape._resolved:
            # Check if this is a non-structural shape
            if shape._resolved.shape:
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
        # Determine the field name to match against
        # Shape field keys can now be:
        # - Value objects with .str attribute (from new shape building)
        # - Plain strings (from old/test code)
        # - Unnamed instances (positional fields - skip for now)

        if isinstance(field_key, _struct.Unnamed):
            # Unnamed shape field - will be handled in positional matching
            continue

        # Extract the field name string
        if isinstance(field_key, str):
            field_name = field_key
        elif hasattr(field_key, 'str') and field_key.str is not None:
            field_name = field_key.str
        else:
            # Unknown field key type - skip
            continue

        # Look for matching field in value
        # Value struct keys can be:
        # - Value objects with .str attribute (from Value.__init__ with dict)
        # - Plain strings (from manual struct creation in tests)
        # - Unnamed instances (positional fields)
        matching_value_key = None
        matching_value_field = None
        for value_key, value_field in value.struct.items():
            # Check if this value key matches the field name
            # Case 1: Plain string key
            if isinstance(value_key, str) and value_key == field_name:
                matching_value_key = value_key
                matching_value_field = value_field
                break
            # Case 2: Value object with .str attribute
            elif not isinstance(value_key, _struct.Unnamed) and hasattr(value_key, 'str') and value_key.str == field_name:
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
            if not isinstance(shape_field_key, _struct.Unnamed):
                # Shape field is named - only allow unnamed value fields
                if not isinstance(value_field_key, _struct.Unnamed):
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
                # - If shape field is named, use the shape's field name
                # - If shape field is unnamed, preserve the value's original field key
                if isinstance(field_key, _struct.Unnamed):
                    # Unnamed shape field - preserve value's field key
                    if isinstance(value_field_key, str):
                        from . import _value
                        result_key = _value.Value(value_field_key)
                    else:
                        result_key = value_field_key
                elif isinstance(field_key, str):
                    # Named shape field (string key) - convert to Value
                    from . import _value
                    result_key = _value.Value(field_key)
                else:
                    # Named shape field (already a Value object) - use as-is
                    result_key = field_key

                morphed_struct[result_key] = morphed_value
            else:
                # No shape constraint - use value as-is
                # Same key selection logic as above
                if isinstance(field_key, _struct.Unnamed):
                    # Unnamed shape field - preserve value's field key
                    if isinstance(value_field_key, str):
                        from . import _value
                        result_key = _value.Value(value_field_key)
                    else:
                        result_key = value_field_key
                elif isinstance(field_key, str):
                    # Named shape field (string key) - convert to Value
                    from . import _value
                    result_key = _value.Value(field_key)
                else:
                    # Named shape field (already a Value object) - use as-is
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
    from . import _value as value_mod
    result_value = value_mod.Value({})
    result_value.struct = morphed_struct

    return MorphResult(
        named_matches=named_matches,
        positional_matches=positional_matches,
        value=result_value
    )


class ShapeType(ABC):
    """Base class for all shape representations."""

    @abstractmethod
    def resolve(self, module: _module.Module):
        """Resolve forward references within module context."""
        pass

    @abstractmethod
    def matches(self, value: _value.Value) -> tuple[int, int]:
        """Check if value matches this shape.

        Returns (specificity, quality) tuple. (0, 0) = no match.
        TODO: Implement full scoring from design/shape.md
        """
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass


class ShapeDefRef(ShapeType):
    """Reference to a ShapeDef in current module."""

    def __init__(self, name: str):
        self.name = name
        self._resolved: _module.ShapeDef | None = None

    def resolve(self, module: _module.Module):
        if not self._resolved and self.name in module.shapes:
            self._resolved = module.shapes[self.name]

    def matches(self, value: _value.Value) -> tuple[int, int]:
        if not self._resolved:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeDefRef(~{self.name}{status})"


class ShapeModRef(ShapeType):
    """Reference to shape in another module."""

    def __init__(self, namespace: str, name: str):
        self.namespace = namespace
        self.name = name
        self._resolved: _module.ShapeDef | None = None

    def resolve(self, module: _module.Module):
        if not self._resolved and self.namespace in module.mods:
            other_mod = module.mods[self.namespace]
            if self.name in other_mod.shapes:
                self._resolved = other_mod.shapes[self.name]

    def matches(self, value: _value.Value) -> tuple[int, int]:
        if not self._resolved:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeModRef(~{self.name}/{self.namespace}{status})"


class ShapeTagRef(ShapeType):
    """Reference to a tag used as a shape constraint."""

    def __init__(self, name: str):
        self.name = name
        self._resolved: _module.TagDef | None = None

    def resolve(self, module: _module.Module):
        if not self._resolved:
            # Try to resolve tag using module's resolve_tag method
            # which searches both the current module and referenced modules
            tokens = self.name.split(".")
            self._resolved = module.resolve_tag(tokens, namespace=None)

    def matches(self, value: _value.Value) -> tuple[int, int]:
        """Check if value is or contains this tag."""
        if not self._resolved:
            return (0, 0)

        # Tag values match exactly
        if value.is_tag:
            # TODO: Check if value.data matches this tag
            return (2, 1)  # Higher specificity for exact tag match

        # Structures can contain tags
        if value.is_struct:
            # TODO: Check if structure has this tag in its fields
            return (1, 1)  # Lower specificity for structural match

        return (0, 0)  # No match

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeTagRef(#{self.name}{status})"


class ShapeInline(ShapeType):
    """Inline shape definition."""

    def __init__(self, fields: dict | None = None):
        """Initialize inline shape.

        Args:
            fields: Dictionary mapping field keys (Value or Unnamed) to ShapeField objects
        """
        self.fields = fields or {}
        self._resolved = False

    def resolve(self, module: _module.Module):
        if self._resolved:
            return

        for _field_key, field_def in self.fields.items():
            if hasattr(field_def, 'shape') and isinstance(field_def.shape, ShapeType):
                field_def.shape.resolve(module)

        self._resolved = True

    def matches(self, value: _value.Value) -> tuple[int, int]:
        if not value.is_struct:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        field_count = len(self.fields)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeInline(~{{{field_count} fields}}{status})"


class ShapeUnion(ShapeType):
    """Union of multiple shape types."""

    def __init__(self, variants: list[ShapeType]):
        self.variants = variants
        self._resolved = False

    def resolve(self, module: _module.Module):
        if self._resolved:
            return

        for variant in self.variants:
            variant.resolve(module)

        self._resolved = True

    def matches(self, value: _value.Value) -> tuple[int, int]:
        if not self.variants:
            return (0, 0)

        best_score = (0, 0)
        for variant in self.variants:
            score = variant.matches(value)
            if score > best_score:
                best_score = score

        return best_score

    def __repr__(self) -> str:
        variant_reprs = " | ".join(repr(v) for v in self.variants)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeUnion({variant_reprs}{status})"
