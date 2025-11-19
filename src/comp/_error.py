"""Error classes and helpers"""

__all__ = ["EvalError", "ModuleError", "ParseError"]



class EvalError(Exception):
    """Error in internal processing of Comp engine.
    
    Args:
        message (str): Error description
    """


class ModuleError(Exception):
    """Error building module.
    
    Args:
        message (str): Error description
    """

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
        super().__init__(message)


