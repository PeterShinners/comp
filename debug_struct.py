#!/usr/bin/env python3
"""Debug structure creation with computed fields."""

import comp
from comp import run

code = """
!func |test-func ~_ = {
    data = {
        '8' = "eight"
    }
    result = data.'4+4'
}
"""

ast_module = comp.parse_module(code)
module = run.Module("test")
module.process_ast(ast_module)
module.resolve_all()

func_def = module.funcs["test-func"]

print("About to invoke function...")
try:
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    print(f"Result: {result}")
    print(f"Result struct keys: {list(result.struct.keys())}")
    
    data = result.struct[run.Value("data")]
    print(f"\nData value: {data}")
    print(f"Data struct keys: {list(data.struct.keys())}")
    for k in data.struct.keys():
        print(f"  Key: {k}, type: {type(k)}, num: {k.num}, str: {k.str}")
        print(f"  Hash: {hash(k)}")
        print(f"  Value: {data.struct[k]}")
    
    # Try to access with a new Value(8)
    test_key = run.Value(8)
    print(f"\nTest key: {test_key}, hash: {hash(test_key)}")
    print(f"Test key in struct: {test_key in data.struct}")
    print(f"Test key == first key: {test_key == list(data.struct.keys())[0]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
