"""Test block invoke, define, and morph."""

import os
import re
import comp
import comptest


def test_comp_files(module_content_and_func):
    """Test functions in a comp file."""
    module_ast = comp.parse_module(module_content_and_func[0])
    engine = comp.Engine()
    module = comp.Module()
    module.prepare(module_ast, engine)
    engine.run(module_ast, module=module)
    
    # module_content_and_func[1] is a tuple like ("test-", "numba") or ("assert-", "thing")
    func_prefix, func_suffix = module_content_and_func[1]
    func_name = func_prefix + func_suffix
    
    funcs = module.lookup_function([func_name])
    assert funcs
    func = funcs[0]

    result = engine.run_function(func)
    if result.is_fail:
        raise AssertionError(f"Function failed with: {result.to_python()}")
    if func_prefix == "assert-":
        value = result.as_scalar().to_python()
        if value is not True:
            raise AssertionError(f"Assertion failed")


def pytest_generate_tests(metafunc):
    if "module_content_and_func" in metafunc.fixturenames:
        test_dir = os.path.dirname(os.path.abspath(__file__))
        comps = [c for c in os.listdir(test_dir) if c.endswith(".comp") and c.startswith("ct_")]
        contents_and_func = []
        names = []
        for base in comps:
            short = os.path.splitext(base)[0][3:]
            content = open(os.path.join(test_dir, base)).read()
            funcs = re.findall(r"!func \|(test-|assert-)(\w+)", content)
            for func in funcs:
                names.append(f"{short}-{func[1]}")
                contents_and_func.append((content, func))

        metafunc.parametrize("module_content_and_func", contents_and_func, ids=names)
