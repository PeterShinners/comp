"""Test pipeline execution."""

import comp


def run_generator(gen):
    """Helper to run a generator to completion."""
    value = None
    try:
        while True:
            value = gen.send(value)
    except StopIteration as e:
        return e.value


def test_simple_seeded_pipeline():
    """Test [5 |double] → 10"""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[comp.ast.PipeFunc("double")]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 10}
    assert result.to_python()[0] == 10


def test_multi_step_pipeline():
    """Test [3 |double |double] → 12"""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(3),
        operations=[
            comp.ast.PipeFunc("double"),
            comp.ast.PipeFunc("double"),
        ]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 12}
    assert result.to_python()[0] == 12


def test_pipeline_with_function_args():
    """Test [5 |add ^{n=3}] → 8"""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("add", args=comp.ast.Structure([
                comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.String("n"))
            ]))
        ]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 8}
    assert result.to_python()[0] == 8


def test_pipeline_with_identity():
    """Test [42 |identity] → 42"""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(42),
        operations=[comp.ast.PipeFunc("identity")]
    )

    result = engine.run(pipeline)
    assert result.as_scalar().to_python() == 42


def test_pipeline_chaining():
    """Test [2 |double |add ^{n=1} |double] → 10"""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(2),
        operations=[
            comp.ast.PipeFunc("double"),              # 2 * 2 = 4
            comp.ast.PipeFunc("add", args=comp.ast.Structure([
                comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.String("n"))
            ])),                              # 4 + 1 = 5
            comp.ast.PipeFunc("double"),              # 5 * 2 = 10
        ]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 10}
    assert result.to_python()[0] == 10


def test_unseeded_pipeline():
    """Test unseeded pipeline uses $in scope."""
    engine = comp.Engine()

    # Unseeded pipeline with $in scope
    pipeline = comp.ast.Pipeline(
        seed=None,
        operations=[comp.ast.PipeFunc("double")]
    )

    result = engine.run(pipeline, in_=comp.Value(7))
    # Python functions now return structs, so result is {_: 14}
    assert result.to_python()[0] == 14


def test_unseeded_pipeline_without_in_scope():
    """Test unseeded pipeline fails without $in scope."""
    engine = comp.Engine()

    # No $in scope set
    pipeline = comp.ast.Pipeline(
        seed=None,
        operations=[comp.ast.PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert engine.is_fail(result)


def test_pipeline_with_failing_function():
    """Test pipeline stops on function failure."""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("double"),              # Works: 10
            comp.ast.PipeFunc("nonexistent"),         # Fails
            comp.ast.PipeFunc("double"),              # Should not execute
        ]
    )

    result = engine.run(pipeline)
    assert engine.is_fail(result)


def test_pipeline_with_wrong_input_type():
    """Test pipeline with type error in function."""
    engine = comp.Engine()

    pipeline = comp.ast.Pipeline(
        seed=comp.ast.String("not a number"),
        operations=[comp.ast.PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert engine.is_fail(result)


def test_pipeline_unparse():
    """Test pipeline unparsing."""
    # Seeded pipeline
    pipeline1 = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[comp.ast.PipeFunc("double"), comp.ast.PipeFunc("identity")]
    )
    assert "5" in pipeline1.unparse()
    assert "|double" in pipeline1.unparse()
    assert "[" in pipeline1.unparse()

    # Unseeded pipeline
    pipeline2 = comp.ast.Pipeline(
        seed=None,
        operations=[comp.ast.PipeFunc("double")]
    )
    unparsed = pipeline2.unparse()
    assert "[" in unparsed
    assert "|double" in unparsed


def test_pipefallback_handles_fail():
    """Test comp.ast.PipeFallback recovers from a failure."""
    engine = comp.Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Something went wrong")

    # Directly add to builtin function registry for testing
    engine.functions["fail_func"] = comp.PythonFunction("fail_func", fail_func)

    # comp.ast.Pipeline: [5 |fail_func |? 42]
    # Should recover with 42
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("fail_func"),
            comp.ast.PipeFallback(comp.ast.Number(42))
        ]
    )

    result = engine.run(pipeline)
    assert not engine.is_fail(result), f"Expected recovery, got fail: {result}"
    assert result.as_scalar().to_python() == 42


def test_pipefallback_passes_success():
    """Test comp.ast.PipeFallback passes through success values."""
    engine = comp.Engine()

    # comp.ast.Pipeline: [5 |double |? 999]
    # Should pass through 10, not use fallback
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("double"),
            comp.ast.PipeFallback(comp.ast.Number(999))
        ]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 10}
    assert result.to_python()[0] == 10, f"Expected 10, got {result}"


def test_pipefallback_fail_in_recovery():
    """Test that if recovery expression fails, pipeline fails."""
    engine = comp.Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Fail!")

    # Directly add to builtin function registry for testing
    engine.functions["fail_func"] = comp.PythonFunction("fail_func", fail_func)

    # comp.ast.Pipeline: [5 |fail_func |? [1 |fail_func]]
    # First fails, fallback also fails
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("fail_func"),
            comp.ast.PipeFallback(
                comp.ast.Pipeline(
                    seed=comp.ast.Number(1),
                    operations=[comp.ast.PipeFunc("fail_func")]
                )
            )
        ]
    )

    result = engine.run(pipeline)
    assert engine.is_fail(result), "Expected fail when recovery fails"


def test_pipefallback_chaining():
    """Test multiple fallbacks in a chain."""
    engine = comp.Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Fail!")

    # Directly add to builtin function registry for testing
    engine.functions["fail_func"] = comp.PythonFunction("fail_func", fail_func)

    # comp.ast.Pipeline: [5 |fail_func |? 10 |double]
    # Recovers to 10, then doubles to 20
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeFunc("fail_func"),
            comp.ast.PipeFallback(comp.ast.Number(10)),
            comp.ast.PipeFunc("double")
        ]
    )

    result = engine.run(pipeline)
    # Python functions now return structs, so result is {_: 20}
    assert result.to_python()[0] == 20, f"Expected 20, got {result}"


def test_pipestruct_merge():
    """Test comp.ast.PipeStruct struct literal."""
    engine = comp.Engine()

    # comp.ast.Pipeline: [{x=1} |{y=2}] → {y=2}
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Structure([
            comp.ast.FieldOp(value=comp.ast.Number(1), key=comp.ast.String("x"))
        ]),
        operations=[
            comp.ast.PipeStruct(
                comp.ast.Structure([
                    comp.ast.FieldOp(value=comp.ast.Number(2), key=comp.ast.String("y"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result.to_python() == {"y": 2}


def test_pipestruct_receives_struct():
    """Test comp.ast.PipeStruct gets struct even on scalar input."""
    engine = comp.Engine()

    # comp.ast.Pipeline: [5 |{x=1}] → {x=1}
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeStruct(
                comp.ast.Structure([
                    comp.ast.FieldOp(value=comp.ast.Number(1), key=comp.ast.String("x"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result.to_python() == {"x": 1}
