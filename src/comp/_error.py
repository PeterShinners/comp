"""Error classes and helpers"""

__all__ = ["ParseError"]


class ParseError(Exception):
    """Exception raised for parsing errors.
    
    Args:
        message (str): Error description
        position (int | None): Optional character position where error occurred
    """

    def __init__(self, message, position=None):
        """Initialize parse error with message and optional position.
        
        Args:
            message (str): Error description
            position (int | None): Optional character position where error occurred
        """
        self.message = message
        self.position = position
        super().__init__(f"Parse error: {message}")

