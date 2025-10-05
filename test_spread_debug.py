import comp
from comp import run

code = """
!func |test-func ~_ = {
    $mod = {..$mod parent.child = 14}
    result = $mod
}
"""

ast_module = comp.parse_module(code)
module = run.Module("test")
module.process_ast(ast_module)
module.resolve_all()

func_def = module.funcs["test-func"]

# Start with nested structure in $mod
mod_val = run.Value({"parent": run.Value({"child": 11})})

print("Initial $mod:")
print(mod_val)
print()

result = run.invoke(func_def, module, run.Value({}), run.Value({}), mod_val, run.Value({}))

print("Result:")
print(result)
print()

result_val = result.struct[run.Value("result")]
print("Result value:")
print(result_val)
print()

print("Result value struct:")
print(result_val.struct)
print()

parent = result_val.struct[run.Value("parent")]
print("Parent:")
print(parent)
print("Parent struct:")
print(parent.struct)
print()

child = parent.struct[run.Value("child")]
print("Child value:", child.to_python())
