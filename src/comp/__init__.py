"""
Comp Programming Language Implementation

A functional, interpreted programming language designed for general purpose computing.
"""

__version__ = "0.0.1"


from ._ast import *
from ._parser import *

# Debug utilities
from ._parser import debug_parse
