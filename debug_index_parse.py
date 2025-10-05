import comp

code = """
!func |test-func ~_ = {
    data = {10 20 30}
    first = data#0
}
"""

ast_module = comp.parse_module(code)
print("Module:", ast_module)
print()

func = ast_module.kids[0]
print("Function:", func)
print()

body = func.kids[2]  # body is third child usually
print("Body:", body)
print("Body kids:", len(body.kids))
print()

# Second statement: first = data#0
second_stmt = body.kids[1]
print("Second statement:", second_stmt)
print("  key:", second_stmt.key)
print("  value:", second_stmt.value)
print()

# The value should be an identifier with fields
identifier = second_stmt.value
print("Identifier:", identifier)
print("Identifier kids:", identifier.kids if hasattr(identifier, 'kids') else "NO KIDS")
if hasattr(identifier, 'kids'):
    for i, kid in enumerate(identifier.kids):
        print(f"  Field {i}: {kid} (type: {type(kid).__name__})")
        if hasattr(kid, 'value'):
            print(f"    value: {kid.value}")
