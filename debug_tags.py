import comp

# Test what tokens we actually get from parsing
mod1 = comp.parse_module("!tag #status")
mod2 = comp.parse_module("!tag #status.active")
mod3 = comp.parse_module("!tag #ui.button.primary")

tag1 = mod1.statements[0]
tag2 = mod2.statements[0]
tag3 = mod3.statements[0]

print(f"#status tokens: {tag1.tokens}")
print(f"#status.active tokens: {tag2.tokens}")
print(f"#ui.button.primary tokens: {tag3.tokens}")

# Test body children
mod4 = comp.parse_module("""
!tag #status = {
    #active
    #pending.error
}
""")

tag4 = mod4.statements[0]
child1 = tag4.body.kids[0]
child2 = tag4.body.kids[1]

print(f"Parent #status tokens: {tag4.tokens}")
print(f"Child #active tokens: {child1.tokens}")
print(f"Child #pending.error tokens: {child2.tokens}")
