"""Build Comp cop structures into executable code.

This is sort of a sort of high level bytecode that is made up of a series
of callables with support for branching. 
The build process does extensive validation and resolving of the cop
structures while building.

To build the code a module and namespace is needed to resolve references.

Code is not intended to be introspectable or modifiable. This data is 
internal to the implementation, it is not exposed to the language.

"""

import decimal



__all__ = [
    "build", "Code",
]

import comp


def build(code, cop, namespace):
    """Build cop structures into code.
    
    Args:
        code (Code): Code object to populate
        cop (Value): Cop structure to build
        namespace (Value): Namespace provided by module
    """
    tag = cop.positional(0).data.qualified
    match tag:
        case "value.constant":
            index = code.add_const(comp.field("value"))
            step = (code.load_const, (index,))
            code.add_step(step)
        case _:
            raise ValueError(f"Cannot build code for: {cop.format()}")


class Code:
    """Executable code object.

    Code objects are made up of a series of instructions that can be
    executed by the interpreter.

    Args:
        instructions: (list) List of instructions
    """
    def __init__(self):
        self.consts = []
        self.steps = []

    def add_const(self, value):
        """Add a constant to the code object and returns index"""
        try:
            index = self.consts.find(value)
        except ValueError:
            self.consts.append(value)
            index = len(self.consts) - 1
        return index

    def load_const(self, index):
        """Load a constant by index."""
        return self.consts[index]

    def add_step(self, step):
        """Add an instruction step to the code object."""
        self.steps.append(step)
        index = len(self.steps) - 1
        return index

