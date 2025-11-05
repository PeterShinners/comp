"""Test block invoke, define, and morph."""

import os
import re
import comp
import pytest
import comptest


# Cache for parsed and prepared modules: {module_content_hash: (module_ast, module)}
_module_cache = {}


def test_comp_files(module_content_and_func):
    """Test functions in a comp file."""
    module_content = module_content_and_func[0]
    
    # Use content hash as cache key
    cache_key = hash(module_content)
    
    if cache_key not in _module_cache:
        # Parse and prepare module (first time for this content)
        module_ast = comp.parse_module(module_content)
        engine = comp.Engine()
        module = comp.Module()
        module.prepare(module_ast, engine)
        engine.run(module_ast, module=module)
        _module_cache[cache_key] = (module_ast, module, engine)
    
    # Get cached module
    module_ast, module, engine = _module_cache[cache_key]
    
    # module_content_and_func[1] is a tuple like ("test-", "numba") or ("assert-", "thing")
    func_prefix, func_suffix = module_content_and_func[1]
    func_name = func_prefix + func_suffix
    
    funcs = module.lookup_function([func_name])
    assert funcs
    func = funcs[0]

    result = engine.run_function(func)
    if func_prefix == "fail-":
        # Expect the function to fail
        if not result.is_fail:
            raise AssertionError(f"Expected failure but succeeded with: {result.unparse()}")
        # If function has a doc string, expect it as substring in fail message
        if func.doc:
            data = result.to_python()
            if isinstance(data, dict):
                fail_message = data.get("message", "")
                if func.doc not in fail_message:
                    raise AssertionError(f"Expected fail message to contain '{func.doc}', but got: {fail_message}")
        return
    else:
        # Non-fail tests should not return a failure value
        if result.is_fail:
            raise AssertionError(f"Function failed with: {result.to_python()}")
        if func_prefix == "assert-":
            scalar = result.as_scalar()
            value = scalar.to_python()
            if value is not True:
                raise AssertionError(f"Assertion failed: got {scalar.unparse()}")
            elif func_prefix == "equal-":
                data = result.as_struct().to_python()
                # Handle both list (all unnamed fields) and dict (named/mixed fields)
                if isinstance(data, list):
                    values = data
                else:
                    values = list(data.values())
                if len(values) != 2:
                    raise AssertionError(f"Expected 2 values for equality check, got {result.unparse()}")
                if values[0] != values[1]:
                    raise AssertionError(f"Equality check failed: {values[0]!r} != {values[1]!r}")
def pytest_generate_tests(metafunc):
    if "module_content_and_func" in metafunc.fixturenames:
        test_dir = os.path.dirname(os.path.abspath(__file__))
        comps = [c for c in os.listdir(test_dir) if c.endswith(".comp") and c.startswith("ct_")]
        contents_and_func = []
        names = []
        for base in comps:
            short = os.path.splitext(base)[0][3:]
            content = open(os.path.join(test_dir, base)).read()
            # Support function names with optional '|' and prefixes: test-, assert-, fail-
            funcs = re.findall(r"!func\s+\|?(test-|assert-|fail-|equal-)([-\w]+)", content)
            for func in funcs:
                names.append(f"{short}-{func[1]}")
                contents_and_func.append((content, func))

        metafunc.parametrize("module_content_and_func", contents_and_func, ids=names)
