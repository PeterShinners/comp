"""
Comp Programming Language Implementation

Interpreted programming language designed to interoperate with Python.
"""

__version__ = "0.8.0"


from ._error import *
from ._num import *
from ._value import *
from ._module import *
from ._internal import *
from ._tag import *
from ._shape import *
from ._block import *
from ._interp import *
from ._parse import *
from ._cop import *
from ._fold import *
from ._pure import *
from ._resolve import *
from ._codegen import *
from ._ops import *
from ._import import *
from ._scan import *
from ._morph import *
from ._describe import *
from ._instructions import *
from ._callout import *

from . import _compiler
from ._cob import *
from ._py import *
from . import _unit_conv

# Deferred initialization: shape_failure fields reference Value objects and
# comp.Shape/Block/etc., which aren't available during _shape.py import.
_shape._init_shape_failure()

from . import runtime