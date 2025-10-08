"""Test pipeline operations and evaluation."""

import pytest

import comp
import runtest


@runtest.params(
    "expr, seed, expected",
    # Basic seeded pipeline
    simple=('[10 |{result = $in * 2}]', None, {'result': 20}),
    # Multiple pipeline stages
    multi=('[5 |{x = $in + 1} |{result = x * 2}]', None, {'result': 12}),
    # Unseeded pipeline (uses $in from enclosing scope)
    unseeded=('[|{result = $in.value * 3}]', {'value': 7}, {'result': 21}),
    # Pipeline with field access in seed
    field_seed=('[data.x |{result = $in + 10}]', {'data': {'x': 15}}, {'result': 25}),
    # Pipeline with computation in seed
    expr_seed=('[(2 + 3) |{result = $in * $in}]', None, {'result': 25}),
    # Chained field access
    chain=('[{a=1 b=2} |{sum = a + b} |{doubled = sum * 2}]', None, {'doubled': 6}),
    # PipeStruct accessing previous fields
    accumulate=('[10 |{x = $in} |{y = x + 5} |{z = x + y}]', None, {'x': 10, 'y': 15, 'z': 25}),
    # Empty struct seed
    empty_seed=('[{} |{result = 42}]', None, {'result': 42}),
)
def test_pipeline_struct(key, expr, seed, expected, module, scopes):
    """Test pipeline with inline struct transformations."""
    if seed is not None:
        scopes = scopes.copy()
        scopes['in'] = comp.run.Value(seed)
    
    ast = comp.parse_expr(expr)
    pipeline = ast.find(comp.ast.Pipeline)
    
    result = comp.run._eval.evaluate(pipeline, module, scopes)
    assert result.is_struct
    assert result.to_python() == expected


@runtest.params(
    "code, input_data, expected",
    # Simple function call
    basic=(
        '!func |double ~_ = {result = $in.x * 2}\n!func |test ~_ = {value = [{x=5} |double]}',
        {},
        {'value': {'result': 10}}
    ),
    # Multiple function calls
    chain=(
        '''!func |add1 ~_ = {result = $in.x + 1}
           !func |mul2 ~_ = {result = $in.result * 2}
           !func |test ~_ = {value = [{x=5} |add1 |mul2]}''',
        {},
        {'value': {'result': 12}}
    ),
    # Function with PipeStruct
    mixed=(
        '''!func |process ~_ = {count = $in.x + 10}
           !func |test ~_ = {value = [{x=5} |process |{result = count * 2}]}''',
        {},
        {'value': {'count': 15, 'result': 30}}
    ),
    # Unseeded pipeline with function
    unseeded=(
        '''!func |double ~_ = {result = $in.value * 2}
           !func |test ~_ = {result = [|double]}''',
        {'value': 21},
        {'result': {'result': 42}}
    ),
    # Function accessing $arg fields
    with_args=(
        '''!func |compute ~_ = {result = $in.x + $arg.offset}
           !func |test ~_ = {value = [{x=10 offset=5} |compute]}''',
        {},
        {'value': {'result': 15}}
    ),
)
def test_pipeline_functions(key, code, input_data, expected):
    """Test pipeline with function invocations."""
    result = runtest.run_function(code, "test", input_data)
    assert result.to_python() == expected


@runtest.params(
    "expr, expected",
    # Nested pipeline in seed
    nested=('[{a=[2 |{x = $in * 3}]} |{result = a.x + 10}]', {'a': {'x': 6}, 'result': 16}),
    # Pipeline result as field value
    as_field=('{x=5 result=[x |{y = $in * 2}]}', {'x': 5, 'result': {'y': 10}}),
    # Multiple pipelines
    multi=('{a=[10 |{v = $in}] b=[20 |{v = $in}]}', {'a': {'v': 10}, 'b': {'v': 20}}),
)
def test_pipeline_nesting(key, expr, expected, module, scopes):
    """Test nested pipelines and pipelines as field values."""
    ast = comp.parse_expr(expr)
    result = comp.run._eval.evaluate(ast, module, scopes)
    assert result.to_python() == expected


@runtest.params(
    "expr, error_match",
    # Undefined function
    no_func=('[10 |undefined]', 'not found'),
    # Type error in transformation
    bad_type=('[{x="cat"} |{result = x * 2}]', None),  # String multiplication
    # Missing field access
    missing_field=('[{x=5} |{result = y + 10}]', 'not found|Field.*not found'),
    # Division by zero in pipeline
    div_zero=('[10 |{result = $in / 0}]', None),
)
def test_pipeline_errors(key, expr, error_match, module, scopes):
    """Test pipeline error cases."""
    ast = comp.parse_expr(expr)
    pipeline = ast.find(comp.ast.Pipeline)
    
    val = comp.run._eval.evaluate(pipeline, module, scopes)
    runtest.assert_fails(val, match=error_match)


@runtest.params(
    "code, input_data, error_match",
    # Function not found
    missing_func=(
        '!func |test ~_ = {result = [{x=5} |notfound]}',
        {},
        'not found'
    ),
    # Type mismatch in function expectation
    wrong_input=(
        '''!func |needs-num ~{x ~num} = {result = x * 2}
           !func |test ~_ = {result = [{x="text"} |needs-num]}''',
        {},
        None  # Will fail during shape matching
    ),
)
def test_pipeline_function_errors(key, code, input_data, error_match):
    """Test pipeline function invocation errors."""
    val = runtest.run_function(code, "test", input_data)
    runtest.assert_fails(val, match=error_match)


@runtest.params(
    "expr, input_val, expected",
    # $in propagation
    in_scope=('[|{result = $in.x + 1}]', {'x': 10}, {'result': 11}),
    # Nested scope access
    nested_in=('[{outer=5} |{inner = [outer |{val = $in * 2}]} |{final = inner.val}]',
               {},
               {'outer': 5, 'inner': {'val': 10}, 'final': 10}),
    # $out scope chaining in pipeline
    chained=('[10 |{a = $in} |{b = a + 5 c = $in}]', {}, {'a': 10, 'b': 15, 'c': 10}),
)
def test_pipeline_scopes(key, expr, input_val, expected, module, scopes):
    """Test scope handling in pipelines."""
    if input_val:
        scopes = scopes.copy()
        scopes['in'] = comp.run.Value(input_val)
    
    ast = comp.parse_expr(expr)
    pipeline = ast.find(comp.ast.Pipeline)
    
    result = comp.run._eval.evaluate(pipeline, module, scopes)
    assert result.to_python() == expected


@runtest.params(
    "expr, expected",
    # Boolean operations in pipeline
    bool_ops=('[#true |{x = $in} |{result = x && #true}]', {'x': True, 'result': True}),
    # String operations
    strings=('[{s="hello"} |{result = s}]', {'s': 'hello', 'result': 'hello'}),
    # Tags
    tags=('[#custom |{result = $in}]', {'result': '#custom'}),
    # Mixed types
    mixed=('[{n=42 s="text" b=#true} |{all = n}]',
           {'n': 42, 's': 'text', 'b': True, 'all': 42}),
)
def test_pipeline_types(key, expr, expected, module, scopes):
    """Test pipelines with various data types."""
    ast = comp.parse_expr(expr)
    pipeline = ast.find(comp.ast.Pipeline)
    
    result = comp.run._eval.evaluate(pipeline, module, scopes)
    
    # Convert to Python for comparison, handling special cases
    python_result = {}
    for k, v in result.struct.items():
        key = k.to_python()
        if v.is_tag:
            # Keep tag representation
            python_result[key] = f"#{'.'.join(v.tag.path)}"
        else:
            python_result[key] = v.to_python()
    
    assert python_result == expected


def test_pipeline_preserves_unnamed_fields():
    """Test that pipelines properly handle unnamed struct fields."""
    code = '''
    !func |test ~_ = {
        result = [{1 2 x=3} |{sum = #0 + #1 + x}]
    }
    '''
    
    result = runtest.run_function(code, "test", {})
    # Pipeline should transform struct, creating new fields
    value = runtest.get_field(result, "result")
    assert value.is_struct
    # Check that sum was computed
    sum_val = runtest.get_field_python(value, "sum")
    assert sum_val == 6


def test_pipeline_empty():
    """Test edge case of pipeline with no operations."""
    expr = '[42]'
    ast = comp.parse_expr(expr)
    pipeline = ast.find(comp.ast.Pipeline)
    
    module = comp.run.Module("test")
    module.process_builtins()
    scopes = comp.run.Value({"in": {}, "out": {}, "ctx": {}, "mod": {}, "arg": {}})
    
    result = comp.run._eval.evaluate(pipeline, module, scopes)
    assert result.to_python() == 42


def test_complex_pipeline_flow():
    """Test a complex pipeline with multiple stages and transformations."""
    code = '''
    !func |scale ~_ = {
        scaled = $in.value * $in.factor
    }
    
    !func |test ~_ = {
        result = [
            {value=10 factor=3}
            |scale
            |{doubled = scaled * 2 original = value}
            |{final = doubled + original}
        ]
    }
    '''
    
    result = runtest.run_function(code, "test", {})
    final_val = runtest.get_field(result, "result")
    
    # {value=10 factor=3} -> scale -> {scaled=30}
    # -> |{...} -> {scaled=30 doubled=60 original=10}
    # -> |{...} -> {scaled=30 doubled=60 original=10 final=70}
    
    assert runtest.get_field_python(final_val, "scaled") == 30
    assert runtest.get_field_python(final_val, "doubled") == 60
    assert runtest.get_field_python(final_val, "original") == 10
    assert runtest.get_field_python(final_val, "final") == 70
