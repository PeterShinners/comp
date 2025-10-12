"""Generator execution engine for comp.

Use `import comp.engine as comp` to access.

"""


class ParseError(Exception):
    """Error raised when parsing fails."""
    pass


from ._entity import *
from ._value import *
from ._function import *
from ._engine import *
from ._module import *
from ._builtin import *
from ._parser import parse_module, parse_expr
from . import ast
