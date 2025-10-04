"""
Comp Programming Language Implementation

A functional, interpreted programming language designed for general purpose computing.
"""

__version__ = "0.0.2"


from . import ast
from . import run
from ._error import *
from ._parser import *