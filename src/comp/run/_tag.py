"""Tag types and operations."""

__all__ = ["Tag"]


class Tag:
    """Tag value in Comp.
    
    Tags use identity-based equality (default Python object equality).
    This is important for builtin tags like #true and #false which should
    be singleton instances - comparison operators will return the exact
    same Tag instance, not a new tag with the same name.
    
    TODO: When implementing comparison operators and tag references:
      - Ensure builtin tags remain singletons across module boundaries
      - Tag equality is based on instance identity, not name/namespace
      - Module resolution must return references to tag definitions,
        not create new Tag instances
    """
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

    # NOTE: No __eq__ defined - uses identity equality (is)
    # This ensures builtin tags like #true and #false are singletons
    # def __hash__(self):
    #     return hash((self.name, self.namespace))

