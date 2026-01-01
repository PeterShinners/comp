"""Error classes and helpers"""

__all__ = ["EvalError", "ModuleError", "ParseError", "CodeError", "ModuleNotFoundError"]


class EvalError(Exception):
    """Error in internal processing of Comp engine."""


class ModuleError(Exception):
    """Error building module."""


class ParseError(Exception):
    """Exception raised for parsing errors.

    Args:
        message: (str) Error description
        position: (int | None) Optional character position where error occurred

    Attributes:
        message: (str) Error description
        position: (int | None) Character position where error occurred
    """

    def __init__(self, message, position=None):
        self.message = message
        self.position = position
        super().__init__(message)


class CodeError(Exception):
    """Exception raised for code analysis and definition extraction errors.

    Args:
        message: (str) Error description
        cop_node: (Struct | None) Optional COP node where error occurred

    Attributes:
        message: (str) Error description
        cop_node: (Struct | None) COP node where error occurred
    """

    def __init__(self, message, cop_node=None):
        self.message = message
        self.cop_node = cop_node
        super().__init__(message)


class ModuleNotFoundError(Exception):
    """Raised when a module cannot be located."""
    pass

