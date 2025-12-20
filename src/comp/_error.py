"""Error classes and helpers"""

__all__ = ["EvalError", "ModuleError", "ParseError"]


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


