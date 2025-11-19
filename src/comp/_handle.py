"""Handle definitions and operations"""

import comp


__all__ = ["HandleDef", "Handle"]


class HandleDef:
    """A handle definition.

    Handles are used to access external resources like operating
    system data. It is an opaque handle to modify anything outside
    of the language's control.

    When handles are grabbed they create a value with the given
    handle definition shape. The handle reference can also be used as 
    a shape, similar to tags.

    Args:
        qualified: (str) Fully qualified handle name
        private: (bool) Handle is private to its module

    Attributes:
        qualified: (str) Fully qualified handle name
        private: (bool) Handle is private to its module
        module: (Module | None) The module that defined this handle
    """
    __slots__ = ("qualified", "private", "module", "dropped", "impl")

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.private = private
        self.module = None

    def __repr__(self):
        return f"HandleDef<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


class Handle:
    """Reference to a Handle definition.

    To use a handle as a value there must be a reference to its definition.
    The reference stores additional information about where it came from
    and how it was named.

    Like shapes, handles are not serializable and don't need anchor logic.

    Args:
        definition: (HandleDef) Definition for this handle reference
        dropped: (bool) Whether the handle has been dropped
        data: (object) Internal implementation data

    """
    __slots__ = ("definition", "dropped", "data")

    def __init__(self, definition, data):
        self.definition = definition
        self.data = data
        self.dropped = False

    def __repr__(self):
        suffix = self.definition.module.token if self.definition.module.token else ""
        return f"Handle({self.definition.qualified}/{suffix})"
