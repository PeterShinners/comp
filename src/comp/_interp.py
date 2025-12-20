"""Main interpreter"""

import comp

__all__ = ["Interp"]


class Interp:
    """Interpreter and state for Comp.

    An interpreter must be created to do most anything with comp objects
    or the language.
    """

    def __init__(self):
        self.system = comp._module.SystemModule.get()

    def __repr__(self):
        return "Interp<>"

    def __hash__(self):
        return id(self)
