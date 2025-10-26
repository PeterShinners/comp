"""Handle related features"""

__all__ = ["HandleInstance"]


class HandleInstance:
    """An actual grabbed handle instance with state tracking.

    Represents an acquired resource that can be grabbed and dropped.
    Created by the !grab operator and invalidated by the !drop operator.

    Handles track which frames can reach them through bidirectional references,
    enabling automatic cleanup when no frames reference the handle.

    Attributes:
        handle_def: The HandleDefinition this instance was grabbed from
        is_dropped: Whether this handle has been dropped (invalidated)
        frames: Set of frames that can reach this handle (for automatic cleanup)
    """

    def __init__(self, handle_def):
        """Create a handle instance.

        Args:
            handle_def: A HandleDefinition object from a module
        """
        self.handle_def = handle_def
        self.is_dropped = False
        self.frames = set()  # Frames that can reach this handle

    @property
    def full_name(self) -> str:
        """Get the full hierarchical name (e.g., 'file.readonly.text')."""
        return self.handle_def.full_name

    def drop(self):
        """Drop (invalidate) this handle.

        Idempotent - safe to call multiple times.
        After dropping, this handle can no longer be used for morphing.
        Unregisters from all frames.
        """
        if self.is_dropped:
            return
            
        self.is_dropped = True
        
        # Unregister from all frames
        for frame in list(self.frames):
            frame.handles.discard(self)
        self.frames.clear()

    def __repr__(self):
        status = " (dropped)" if self.is_dropped else ""
        return f"@{self.full_name}{status}" if self.handle_def else "@<placeholder>"

    def __eq__(self, other):
        if not isinstance(other, HandleInstance):
            return False
        # Two handle instances are equal if they point to the same definition
        # and have the same dropped state
        return (self.full_name == other.full_name and
                self.is_dropped == other.is_dropped)

    def __hash__(self):
        return hash((self.full_name, self.is_dropped))


def is_handle_compatible(input_handle_def, field_handle_def):
    """Check if an input handle is compatible with a field's handle type.

    Compatible means the input handle is either:
    - The same handle as the field's handle type
    - A child (descendant) of the field's handle type

    Args:
        input_handle_def: HandleDefinition of the input handle value
        field_handle_def: HandleDefinition of the field's handle type constraint

    Returns:
        True if input handle is compatible with field handle type

    Examples:
        @file.readonly.text compatible with @file.readonly (child)
        @file.readonly compatible with @file.readonly (same)
        @file.readonly compatible with @file (child)
        @network.socket NOT compatible with @file (different hierarchy)
    """
    # Same handle - always compatible
    if input_handle_def.path == field_handle_def.path:
        return True

    # Check if input is a child of field's handle (field's path is a prefix)
    if len(field_handle_def.path) >= len(input_handle_def.path):
        return False

    # Compare prefixes - field's path should be a prefix of input's path
    return input_handle_def.path[:len(field_handle_def.path)] == field_handle_def.path
