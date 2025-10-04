"""Structure operations and helpers."""

__all__ = ["Unnamed"]


class Unnamed:
    """Unnamed field value."""
    __slots__ = ()

    def __init__(self):
        pass

    def __repr__(self):
        return "???"

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return False

