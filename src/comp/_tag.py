"""Tag definitions and operations"""

import comp


__all__ = [
    "Tag",
    "tag_nil", "tag_bool", "tag_true", "tag_false", "tag_fail",
    "create_tagdef",
    "HandleInstance",
    "grab_handle", "drop_handle", "pull_handle", "push_handle",
]


class Tag:
    """A tag definition.

    Tags are lightweight identifiers used to represent various states,
    types, or conditions in the comp language. They are often used for
    error handling, type tagging, and control flow.

    Args:
        qualified: (str) Fully qualified tag name
        private: (bool) Tag is private to its module

    Attributes:
        qualified: (str) Fully qualified tag name
        private: (bool) Tag is private to its module
        module: (Module | None) The module that defined this tag
    """

    __slots__ = ("qualified", "private", "module")

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.module = None
        self.private = private

    def __repr__(self):
        return f"Tag<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


tag_nil = Tag("nil", False)
tag_bool = Tag("bool", False)
tag_true = Tag("bool.true", False)
tag_false = Tag("bool.false", False)
tag_fail = Tag("fail", False)


def create_tagdef(qualified_name, private, cop_node, parent_tag=None):
    """Create a Tag from a value.tag COP node and wrap in a Value.

    This is a pure initialization function that doesn't depend on Module or Interp.

    Args:
        qualified_name: (str) Fully qualified tag name (e.g., "server.status.ok")
        private: (bool) Whether tag is private
        cop_node: (Struct) The value.tag COP node
        parent_tag: (Tag | None) Parent tag for hierarchical tags

    Returns:
        Value: Initialized tag definition wrapped in a Value with cop attribute set

    Raises:
        CodeError: If cop_node is not a value.tag node
    """
    # Validate node type
    tag_value = cop_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "value.tag":
        raise comp.CodeError(
            f"Expected value.tag node, got {tag.qualified if isinstance(tag, comp.Tag) else type(tag)}",
            cop_node
        )

    # Create Tag
    tag_def = Tag(qualified_name, private)

    # TODO: Handle hierarchical tags and child tags from cop_node
    # For now, just create the basic definition

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(tag_def)
    value.cop = cop_node

    return value


class HandleInstance:
    """A live handle created by the !grab operator.

    A handle wraps a tag and carries module-private hidden data. The tag
    identifies the handle type. Only the module that defined the tag is
    permitted to use !grab, !drop, !pull, and !push on it.

    Handles are tracked by the interpreter and automatically released when
    they go out of scope, or explicitly released with !drop.

    The handle itself is an opaque value that can be passed freely through
    any functions. Only the owning module can read or write the private data.

    Args:
        tag: (Tag) The tag identifying the handle type
        module_id: (str | None) Module resource id of the module that owns this handle
        private_data: (Value | None) Initial hidden private data

    Attributes:
        tag: (Tag) The handle type tag
        module_id: (str | None) Owning module identifier
        private_data: (Value | None) Module-private hidden data
        released: (bool) True if this handle has been dropped
    """

    __slots__ = ("tag", "module_id", "private_data", "released")

    def __init__(self, tag, module_id, private_data=None):
        self.tag = tag
        self.module_id = module_id
        self.private_data = private_data
        self.released = False

    def format(self):
        """Return display representation of this handle.

        Returns:
            (str) A printable description of the handle
        """
        qualifier = self.tag.qualified if self.tag else "unknown"
        status = "released" if self.released else "live"
        return f"<handle:{qualifier} {status}>"

    def __repr__(self):
        return self.format()

    def __hash__(self):
        """Use object identity - each handle instance is unique."""
        return id(self)

    def __eq__(self, other):
        """Identity equality - handles are only equal to themselves."""
        return self is other


# ---------------------------------------------------------------------------
# Handle runtime operations
# ---------------------------------------------------------------------------

def _check_handle_ownership(handle, module_id, op):
    """Verify the current module owns the given handle.

    Args:
        handle: (HandleInstance) The handle to check
        module_id: (str) Current module token
        op: (str) Operator name for error messages

    Raises:
        comp.EvalError: If the module does not own the handle
    """
    if handle.module_id != module_id:
        raise comp.EvalError(
            f"Cannot !{op} handle {handle.tag.qualified!r}: "
            f"handle belongs to module {handle.module_id!r}, "
            f"not current module {module_id!r}"
        )


def grab_handle(tag_value, frame):
    """Create a new handle instance for the given tag (!grab).

    The tag must belong to the currently executing module. Cannot be used
    in pure functions.

    Args:
        tag_value: (Value) Value containing a Tag
        frame: (ExecutionFrame) Current execution frame

    Returns:
        (Value) Value wrapping a new HandleInstance

    Raises:
        comp.EvalError: If tag_value is not a Tag, or module ownership fails
    """
    if not isinstance(tag_value.data, Tag):
        raise comp.EvalError(f"!grab requires a tag value, got {tag_value.format()}")

    tag = tag_value.data
    module_id = frame.module.token if frame.module else None

    # Module ownership: the tag must belong to the current module.
    # Every user-defined tag must have tag.module set (by _process_tag_statement).
    if tag.module is None:
        raise comp.EvalError(
            f"Cannot !grab handle for tag {tag.qualified!r}: tag has no owning module"
        )
    if module_id is None:
        raise comp.EvalError(
            f"Cannot !grab handle for tag {tag.qualified!r}: cannot determine current module"
        )
    if tag.module.token != module_id:
        raise comp.EvalError(
            f"Cannot !grab handle for tag {tag.qualified!r}: "
            f"tag belongs to module {tag.module.token!r}, "
            f"not current module {module_id!r}"
        )

    handle = HandleInstance(tag=tag, module_id=module_id)
    return comp.Value(handle)


def drop_handle(handle_value, frame):
    """Release a handle, marking it as dropped (!drop).

    The handle must belong to the currently executing module. After dropping,
    the handle can no longer be used with !pull or !push.

    Args:
        handle_value: (Value) Value containing a HandleInstance
        frame: (ExecutionFrame) Current execution frame

    Returns:
        (Value) nil

    Raises:
        comp.EvalError: If handle_value is not a handle, already released,
            or owned by a different module
    """
    if not isinstance(handle_value.data, HandleInstance):
        raise comp.EvalError(f"!drop requires a handle value, got {handle_value.format()}")

    handle = handle_value.data
    module_id = frame.module.token if frame.module else None

    _check_handle_ownership(handle, module_id, "drop")

    # Re-dropping an already-released handle is a safe no-op
    if handle.released:
        return comp.Value(tag_nil)

    handle.released = True
    return comp.Value(tag_nil)


def pull_handle(handle_value, frame):
    """Get the private data stored in a handle (!pull).

    The handle must belong to the currently executing module.

    Args:
        handle_value: (Value) Value containing a HandleInstance
        frame: (ExecutionFrame) Current execution frame

    Returns:
        (Value) The private data, or nil if no data has been pushed yet

    Raises:
        comp.EvalError: If handle_value is not a handle, released,
            or owned by a different module
    """
    if not isinstance(handle_value.data, HandleInstance):
        raise comp.EvalError(f"!pull requires a handle value, got {handle_value.format()}")

    handle = handle_value.data
    module_id = frame.module.token if frame.module else None

    _check_handle_ownership(handle, module_id, "pull")

    if handle.released:
        raise comp.EvalError(f"Cannot !pull from released handle {handle.format()}")

    if handle.private_data is None:
        return comp.Value(tag_nil)
    return handle.private_data


def push_handle(handle_value, data_value, frame):
    """Store private data in a handle, replacing any existing data (!push).

    The handle must belong to the currently executing module.

    Args:
        handle_value: (Value) Value containing a HandleInstance
        data_value: (Value) The data to store as private handle data
        frame: (ExecutionFrame) Current execution frame

    Returns:
        (Value) nil

    Raises:
        comp.EvalError: If handle_value is not a handle, released,
            or owned by a different module
    """
    if not isinstance(handle_value.data, HandleInstance):
        raise comp.EvalError(f"!push requires a handle as first argument, got {handle_value.format()}")

    handle = handle_value.data
    module_id = frame.module.token if frame.module else None

    _check_handle_ownership(handle, module_id, "push")

    if handle.released:
        raise comp.EvalError(f"Cannot !push to released handle {handle.format()}")

    handle.private_data = data_value
    return comp.Value(tag_nil)
