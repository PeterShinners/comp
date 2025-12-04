"""Compiler and loader for imports."""


__all__ = []

import inspect

import comp


def create_compiler(name):
    """Create a compiler by name."""
    comp = {
        "python": PythonCompiler,
        "comp": CompCompiler,
        "core": CoreCompiler,
    }.get(name)
    if not comp:
        raise ValueError(f"Unknown compiler {name!r}")
    return comp


class ScanResults:
    """Holds results of scanning phase."""

    def __init__(self):
        self.dependencies = set()
        self.metadata = {}

    def add_dependency(self, namespace, compiler, resource):
        """Add a dependency to results."""
        self.dependencies.add((namespace, compiler, resource))

    def add_metadata(self, key, value):
        """Add metadata to results."""
        self.metadata[key] = value


class CompileResults:
    """Holds results of compilation phase."""

    def __init__(self, module):
        self.module = module


# Compiler is created for each unique import. It should hold state to
# between the passes for efficiency. The compiler will be dropped when
# no longer needed.
class Compiler:
    """Base compiler definition."""
    name = None

    def loaders(self, resource):
        """Return list of loaders for given resource."""
        return []
    
    def scan(self, value, results):
        """Scan metadata and loaded resource for dependencies."""
        # The loader can provide any comp value
        # put dependencies and metadata into module

    def compile(self, results):
        """Build values into a module"""
        # put compiled values into module


class CoreCompiler(Compiler):
    """Core compiler for built-in modules."""
    
    def loaders(self, resource):
        return [CoreLoader(resource)]
    
    def scan(self, value, results):
        doc = inspect.getdoc(value)
        
        