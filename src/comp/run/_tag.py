"""Tag types and operations."""

__all__ = ["Tag"]


class Tag:
    """Tag value in Comp."""
    __slots__ = ("name", "identifier", "namespace", "value")
    def __init__(self, identifier: list[str], namespace: str, value: "Value | None" = None):
        self.name = "#" + ".".join(identifier)
        self.identifier = identifier
        self.namespace = namespace
        self.value = value

    def __repr__(self):
        if self.namespace == "builtin":
            return f"{self.name}"
        else:
            return f"{self.name}/{self.namespace}"

    # def __hash__(self):
    #     return hash((self.name, self.namespace))

