import comp
from comp import run

code = """
!func |test-func ~_ = {
    $mod = {..$mod parent.child = 14}
    result = $mod
}
"""

ast_module = comp.parse_module(code)
print("AST:", ast_module)
print()

# Find the structure
func = ast_module.kids[0]
print("Function:", func)
print()

body = func.body
print("Body:", body)
print("Body kids:", body.kids)
print()

# First assignment: $mod = {..$mod parent.child = 14}
first_assign = body.kids[0]
print("First assign:", first_assign)
print("First assign key:", first_assign.key)
print("First assign value:", first_assign.value)
print()

# The structure
struct = first_assign.value
print("Structure:", struct)
print("Structure kids:", struct.kids)
for i, kid in enumerate(struct.kids):
    print(f"  Child {i}: {kid} (type: {type(kid).__name__})")
    if hasattr(kid, 'key'):
        print(f"    key: {kid.key}")
    if hasattr(kid, 'value'):
        print(f"    value: {kid.value}")
