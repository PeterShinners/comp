"""Runtime values for the generator-based engine."""

__all__ = ["Value", "fail", "Unnamed", "ChainedScope"]

import decimal

import comp

from . import _entity


class Value(_entity.Entity):
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (comp.TagRef, dict).
    This is a simplified version for the new engine. Uses .data for the
    underlying value, and provides .struct as an alias when it's a dict.

    Inherits from Entity, making it passable through scopes and returnable
    from evaluate() methods.
    
    Attributes:
        data: The underlying data (primitives, tags, structs, etc.)
        ast: Optional AST node that created this value (for error messages)
        private: Module-private data storage dict
        handles: Frozenset of HandleInstance objects contained in this value
    """

    def __init__(self, data, ast=None):
        """Create a value from Python types or Comp values.

        Args:
            data: The underlying data. Can be:
                - Value (copied)
                - None (empty struct)
                - bool (converted to TRUE/FALSE tags)
                - int/float (converted to Decimal)
                - Decimal (stored directly)
                - str (stored directly)
                - comp.TagRef (stored directly)
                - comp.HandleInstance (stored directly)
                - Block/RawBlock (stored directly)
                - dict (recursively converted)
                - list/tuple (converted to unnamed struct fields)
            ast: Optional AST node that created this value (for error messages and source tracking)
        """
        # Module-private data storage
        # Maps module_id -> Value (structure containing private data)
        # Used by the & syntax for module-scoped private data
        self.private = {}
        
        # AST node tracking (for error messages)
        self.ast = ast
        
        # Handle Value copying
        if isinstance(data, Value):
            self.data = data.data
            # Share private data reference - values are immutable, no need to copy
            self.private = data.private
            # Copy the handles set (also immutable)
            self.handles = data.handles
            # Copy AST node reference
            self.ast = data.ast
            return

        # Handle None -> empty struct
        if data is None:
            self.data = {}
            self.handles = frozenset()
            return

        # Handle bool -> Tag conversion
        if isinstance(data, bool):
            self.data = comp.builtin.TRUE if data else comp.builtin.FALSE
            self.handles = frozenset()
            return

        # Handle numeric types -> Decimal
        if isinstance(data, int):
            self.data = decimal.Decimal(data)
            self.handles = frozenset()
            return
        if isinstance(data, float):
            self.data = decimal.Decimal(str(data))  # Convert via string to avoid precision issues
            self.handles = frozenset()
            return
        if isinstance(data, decimal.Decimal):
            self.data = data
            self.handles = frozenset()
            return

        # Handle string
        if isinstance(data, str):
            self.data = data
            self.handles = frozenset()
            return

        # Handle comp.TagRef
        if isinstance(data, comp.TagRef):
            self.data = data
            self.handles = frozenset()
            return

        # Handle comp.HandleInstance (actual grabbed handles)
        if isinstance(data, comp.HandleInstance):
            self.data = data
            # This value contains exactly one handle
            self.handles = frozenset([data])
            return

        # Handle Block and RawBlock (can be wrapped in Value)
        from . import _function
        if isinstance(data, (_function.Block, _function.RawBlock)):
            self.data = data
            self.handles = frozenset()
            return

        # Handle dict -> struct (recursively convert keys and values)
        if isinstance(data, dict):
            self.data = {
                k if isinstance(k, Unnamed) else Value(k): Value(v)
                for k, v in data.items()
            }
            # Compute handles from all field values (recursively)
            self.handles = self._compute_struct_handles()
            return

        # Handle list/tuple -> unnamed struct fields
        if isinstance(data, (list, tuple)):
            self.data = {Unnamed(): Value(v) for v in data}
            # Compute handles from all field values (recursively)
            self.handles = self._compute_struct_handles()
            return

        # Handle other Python objects directly (for Python bridge)
        # Store them as-is without conversion
        self.data = data
        self.handles = frozenset()
        return

    def _compute_struct_handles(self) -> frozenset:
        """Recursively collect all handles from struct fields.
        
        Since Values are immutable and handles are computed at construction,
        we can just collect the handles sets from all field values.
        
        Returns:
            frozenset of HandleInstance objects, or empty frozenset
        """
        all_handles = set()
        for field_value in self.data.values():
            if field_value.handles:
                all_handles.update(field_value.handles)
        return frozenset(all_handles) if all_handles else frozenset()

    @property
    def is_number(self) -> bool:
        return isinstance(self.data, decimal.Decimal)

    @property
    def is_string(self) -> bool:
        return isinstance(self.data, str)

    @property
    def is_struct(self) -> bool:
        return isinstance(self.data, dict)

    @property
    def is_tag(self) -> bool:
        return isinstance(self.data, comp.TagRef)

    @property
    def is_handle(self) -> bool:
        """Check if this Value wraps a HandleInstance (grabbed handle)."""
        return isinstance(self.data, comp.HandleInstance)

    @property
    def is_block(self) -> bool:
        """Check if this Value wraps a Block (typed, ready to invoke)."""
        return isinstance(self.data, comp.Block)

    @property
    def is_raw_block(self) -> bool:
        """Check if this Value wraps a RawBlock (untyped, needs morphing)."""
        return isinstance(self.data, comp.RawBlock)

    @property
    def is_fail(self):
        """Check if a value is a fail value.
        
        Returns True if the struct contains a #fail tag or any child of #fail
        in its unnamed fields. Uses proper tag hierarchy checking.
        """
        if not self.is_struct:
            return False

        # Import here to avoid circular dependency
        from .builtin import get_builtin_module
        from ._tag import is_tag_compatible

        # Get the builtin #fail tag definition
        try:
            builtin = get_builtin_module()
            fail_tag_def = builtin.lookup_tag(["fail"])
        except (ValueError, AttributeError):
            # Fallback during early initialization when builtin module may not be ready
            # Use string matching as fallback
            for val in self.data.values():
                if val.is_tag:
                    name = val.data.full_name
                    if name == "fail" or name.startswith("fail."):
                        return True
            return False

        # Look for #fail tag or any child of #fail in unnamed fields
        for key, val in self.data.items():
            # Only check unnamed fields - named fields can contain fail tags without being failures
            if isinstance(key, Unnamed) and val.is_tag:
                # Check if this tag is #fail or a descendant of #fail
                if is_tag_compatible(val.data.tag_def, fail_tag_def):
                    return True
        return False

    @property
    def struct(self) -> dict | None:
        """Alias for .data when it's a dict (for compatibility with AST nodes)."""
        return self.data if isinstance(self.data, dict) else None

    def as_scalar(self):
        """Return value as a scalar value or itself.

        Unwraps single-element structs (named or unnamed).
        Returns self if already scalar (preserves object identity).
        Preserves private data when unwrapping.
        """
        # Already scalar - return self
        if not self.is_struct:
            return self
            
        # Check if struct can be unwrapped
        if isinstance(self.data, dict) and len(self.data) == 1:
            value = list(self.data.values())[0]
            if value.is_number or value.is_string or value.is_tag or value.is_handle or value.is_block or value.is_raw_block:
                # Check if we need to preserve private data
                if self.private:
                    # If the inner value already has the same private reference, return it directly
                    # (this happens when as_struct() was called on a value with private data)
                    if value.private is self.private:
                        return value
                    # Otherwise, create new value with combined private data
                    unwrapped = Value(value.data)
                    unwrapped.private = self.private
                    # Preserve the ast attribute from the inner value
                    unwrapped.ast = value.ast if hasattr(value, 'ast') else None
                    return unwrapped
                # No private data - return the inner value directly
                return value
        
        # Can't unwrap - return self
        return self

    def as_struct(self):
        """Wrap scalar values into single field structure.
        
        Returns self if already a struct (preserves object identity).
        Preserves private data when wrapping.
        """
        # Already struct - return self
        if self.is_struct:
            return self
            
        # Wrap scalar and preserve private data
        # Important: Create the dict manually to avoid Value() constructor
        # converting self into a copy
        wrapped = Value.__new__(Value)
        wrapped.data = {Unnamed(): self}
        wrapped.private = self.private
        wrapped.ast = self.ast
        # Compute handles from the wrapped value
        wrapped.handles = self.handles
        return wrapped

    def get_private(self, module_id):
        """Get module-private data for a specific module.
        
        Args:
            module_id: Module identifier (from Module.module_id)
            
        Returns:
            Value | None: Private data structure for the module, or None if not set
        """
        return self.private.get(module_id)
    
    def set_private(self, module_id, data: 'Value'):
        """Set module-private data for a specific module.
        
        Args:
            module_id: Module identifier (from Module.module_id)
            data: Value containing the private data (typically a structure)
            
        Notes:
            - Mutates the private dict in place
            - Private data is shared across value transformations (as_struct, etc.)
            - Data must already be a Value instance
        """
        if not isinstance(data, Value):
            raise TypeError(f"Private data must be a Value, got {type(data).__name__}")
        self.private[module_id] = data

    def unparse(self) -> str:
        """Convert value back to a source-like representation.

        Similar to AST node unparse() methods, this produces a string that
        represents the value in a human-readable form. For simple values
        (numbers, strings, tags), returns the data. For structs with a single
        unnamed field, extracts that field's representation.

        Returns:
            String representation suitable for display
        """
        if self.is_number:
            return str(self.data)
        if self.is_string:
            return repr(self.data).replace('"', '\\"').replace("'", '"')
        if self.is_tag:
            return f"#{self.data.full_name}"
        if self.is_handle:
            return f"@{self.data.full_name}"
        if self.is_struct:
            fields = []
            for k, v in self.data.items():
                if isinstance(k, Unnamed):
                    fields.append(v.unparse())
                elif isinstance(k, Value):
                    if k.is_string:
                        key = k.unparse()[1:-1]
                        # Check if key is a valid Comp identifier (TOKEN pattern: /[^\W\d][\w-]*[?]?/)
                        # Must start with letter/underscore, contain only alphanumeric/underscore/hyphen, optional trailing ?
                        import re
                        if re.match(r'^[^\W\d][\w-]*\??$', key):
                            fields.append(f"{key}={v.unparse()}")
                        else:
                            # Need to quote the key
                            fields.append(f'"{key}"={v.unparse()}')
                    else:
                        fields.append(f"{k.unparse()}={v.unparse()}")

            return "{" + " ".join(fields) + "}"

        # Return the data, converting tags and decimals to strings
        if isinstance(self.data, comp.TagRef):
            return str(self.data)
        if isinstance(self.data, decimal.Decimal):
            return str(self.data)
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, dict):
            # For complex structs, return the full representation
            return str(self.data)
        return str(self.data)

    def to_python(self):
        """Convert this value to a Python equivalent.

        Returns:
            - Decimal for numbers
            - str for strings
            - bool for #true/#false tags
            - comp.TagRef for other tags
            - dict for structures (with recursively converted keys/values)
        """
        if isinstance(self.data, comp.TagRef):
            # Convert #true and #false to Python booleans
            if self.data.full_name == "true":
                return True
            elif self.data.full_name == "false":
                return False
            # Other tags remain as TagRef
            return self.data
        if isinstance(self.data, (decimal.Decimal, str)):
            return self.data
        if isinstance(self.data, dict):
            # Recursively convert struct fields
            result = {}
            for key, val in self.data.items():
                if isinstance(key, Unnamed):
                    # For unnamed keys, use numeric indices
                    result[len(result)] = val.to_python()
                else:
                    # Convert Value keys to Python
                    result[key.to_python()] = val.to_python()
            return result
        return None

    def __repr__(self):
        return f"Value({self.data!r})"

    def __eq__(self, other):
        if not isinstance(other, Value):
            return False
        return self.data == other.data

    def __hash__(self):
        """Make Value hashable so it can be used as dict keys."""
        if isinstance(self.data, dict):
            # Dicts aren't hashable, use tuple of items
            return hash(tuple(sorted(self.data.items())))
        return hash(self.data)


def fail(message, ast=None, **extra_fields):
    """Create a failure structure with the given message.

    The structure has the #fail tag as an unnamed field, plus named fields
    for type and message. Additional fields can be added via kwargs.
    This allows morphing against #fail to detect failures.
    
    Args:
        message: The failure message
        ast: Optional AST node that generated this failure (for error messages and source tracking)
        **extra_fields: Additional named fields to include in the failure struct
    """
    # Import here to avoid circular dependency
    from .builtin import get_builtin_module

    # Get the #fail tag from builtin module
    builtin = get_builtin_module()
    try:
        fail_tag_def = builtin.lookup_tag(["fail"])
    except ValueError as e:
        # This should never happen - builtin module must have #fail tag
        raise RuntimeError(f"Critical error: builtin #fail tag not found: {e}") from e

    # Create Value directly without going through constructor conversion
    result = Value.__new__(Value)
    result.data = {
        Unnamed(): Value(comp.TagRef(fail_tag_def)),  # Tag as unnamed field for morphing
        Value('type'): Value('fail'),
        Value('message'): Value(message)
    }
    
    # Add any extra fields
    for key, value in extra_fields.items():
        result.data[Value(key)] = Value(value)
    
    result.private = {}
    result.ast = ast
    # Compute handles from field values
    result.handles = frozenset()  # fail values don't contain handles
    return result


class Unnamed:
    """Marker for unnamed/positional fields in structures.

    Each instance has unique identity - unnamed fields are distinguishable
    by their position, not their key. This allows multiple unnamed fields
    in a struct without key conflicts.

    Comparison always returns False - unnamed fields are never "equal"
    as keys, they're distinguished by position/identity.
    """
    __slots__ = ()

    def __repr__(self):
        return "_"

    def __hash__(self):
        """Use object identity for hashing - each instance is unique."""
        return id(self)

    def __eq__(self, other):
        """Unnamed keys are never equal - they're distinguished by identity."""
        return False


class ChainedScope:
    """A scope that chains multiple Value structs for field lookup.

    When looking up a field, tries each scope in order and returns the first match.
    This is used for the 'unnamed' scope to chain $out (accumulator) with $in.
    """

    def __init__(self, *scopes):
        """Create a chained scope from multiple Value structs.

        Args:
            *scopes: Value objects to chain. Earlier scopes have priority.
        """
        self.scopes = scopes

    def lookup_field(self, field_key):
        """Look up a field in the chained scopes.

        Args:
            field_key: The field key to look up (as a Value)

        Returns:
            The value if found in any scope, None otherwise
        """
        for scope in self.scopes:
            if scope is not None and scope.is_struct:
                struct = scope.struct
                if struct is not None and field_key in struct:
                    return struct[field_key]
        return None
