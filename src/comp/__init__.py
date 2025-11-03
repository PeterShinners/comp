"""
Comp Programming Language Implementation

A functional, interpreted programming language designed for general purpose computing.
"""

__version__ = "0.0.2"


from ._error import *
from ._entity import *
from ._value import *
from ._function import *
from ._engine import *
from ._module import *
from ._tag import *
from ._handle import *
from ._morph import *
from ._parser import *
from ._pybridge import *
from . import builtin, ast, corelib