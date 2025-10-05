import comp
from comp import run

code = """
!func |test-func ~_ = {
    data = {one=1 2 three=3}
}
"""

ast_module = comp.parse_module(code)
module = run.Module("test")
module.process_ast(ast_module)
module.resolve_all()

func_def = module.funcs["test-func"]
result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

print("Result:", result)
print("Result struct:", result.struct)
print()

data = result.struct[run.Value("data")]
print("Data:", data)
print("Data struct:", data.struct)
print("Number of fields:", len(data.struct) if data.struct else 0)
print()

if data.struct:
    for i, (k, v) in enumerate(data.struct.items()):
        print(f"Field {i}: key={k}, value={v}")
