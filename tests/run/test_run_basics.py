"""Test basic runtime: field access, scopes, expressions, operators."""

import comp
import runtest


# Field Access Tests
@runtest.params(
    "code, input_data, expected",
    # Named fields
    named=("result = name", {"name": "Alice"}, "Alice"),
    # Index fields
    index_0=("result = $in.#0", {"x": 10, "y": 20}, 10),
    index_1=("result = $in.#1", {"x": 10, "y": 20}, 20),
    # Bare index
    bare_0=("result = #0", {"a": 100}, 100),
    # Nested
    nested=("result = user.name", {"user": {"name": "Bob"}}, "Bob"),
)
def test_field_access(key, code, input_data, expected):
    """Test various field access patterns."""
    full_code = f"!func |test ~_ = {{ {code} }}"
    result = runtest.run_function(full_code, "test", input_data)
    assert runtest.get_field_python(result, "result") == expected


# Scope Access Tests
@runtest.params(
    "code, in_val, ctx_val, mod_val, arg_val, expected",
    in_scope=("result = $in.x", {"x": 10}, {}, {}, {}, 10),
    ctx_scope=("result = $ctx.y", {}, {"y": 20}, {}, {}, 20),
    mod_scope=("result = $mod.z", {}, {}, {"z": 30}, {}, 30),
    arg_scope=("result = $arg.a", {}, {}, {}, {"a": 40}, 40),
    # Chained scope: $arg -> $ctx -> $mod
    chain_arg=("result = ^x", {}, {"x": 20}, {"x": 30}, {"x": 10}, 10),
    chain_ctx=("result = ^y", {}, {"y": 20}, {"y": 30}, {}, 20),
    chain_mod=("result = ^z", {}, {}, {"z": 30}, {}, 30),
)
def test_scopes(key, code, in_val, ctx_val, mod_val, arg_val, expected):
    """Test scope access patterns."""
    full_code = f"!func |test ~_ = {{ {code} }}"
    result = runtest.run_function(full_code, "test", in_val, ctx_val, mod_val, arg_val)
    assert runtest.get_field_python(result, "result") == expected


# Expression Tests
@runtest.params(
    "code, expected",
    # Literals
    number=("result = 42", 42),
    string=('result = "hello"', "hello"),
    empty=("result = {}", {}),
    # Arithmetic
    add=("result = 10 + 5", 15),
    sub=("result = 10 - 3", 7),
    mul=("result = 6 * 7", 42),
    div=("result = 20 / 4", 5),
)
def test_expressions(key, code, expected):
    """Test expression evaluation."""
    full_code = f"!func |test ~_ = {{ {code} }}"
    result = runtest.run_function(full_code, "test", {})
    assert runtest.get_field_python(result, "result") == expected


def test_python_func():
    """Test Python-implemented function works."""
    def double(in_value: comp.run.Value, arg_value: comp.run.Value) -> comp.run.Value:
        if in_value.is_struct and in_value.struct:
            x = in_value.struct.get(comp.run.Value("x"))
            if x and x.is_num:
                return comp.run.Value({"result": x.num * 2})
        return comp.run.Value({})
    
    module = comp.run.Module("test")
    func_def = comp.run.FuncDef(identifier=["double"])
    func_def.implementations.append(comp.run.PythonFuncImpl(double, "double"))
    module.funcs["double"] = func_def
    
    code = "!func |test ~_ = { value = [{x=5} |double] }"
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    func_def = module.funcs["test"]
    result = comp.run.invoke(func_def, module,
        comp.run.Value({}), comp.run.Value({}),
        comp.run.Value({}), comp.run.Value({}))
    
    value_field = result.struct[comp.run.Value("value")]
    assert runtest.get_field_python(value_field, "result") == 10
