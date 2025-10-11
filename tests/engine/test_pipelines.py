"""Test pipeline execution."""

from comp.engine.ast import FieldOp, Number, PipeFunc, Pipeline, String, Structure
from comp.engine._engine import Engine
from comp.engine._function import PythonFunction
from comp.engine._value import Value


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
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(5),
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result == Value(10)


def test_multi_step_pipeline():
    """Test [3 |double |double] → 12"""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(3),
        operations=[
            PipeFunc("double"),
            PipeFunc("double"),
        ]
    )

    result = engine.run(pipeline)
    assert result == Value(12)


def test_pipeline_with_function_args():
    """Test [5 |add ^{n=3}] → 8"""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("add", args=Structure([
                FieldOp(Number(3), key=String("n"))
            ]))
        ]
    )

    result = engine.run(pipeline)
    assert result == Value(8)


def test_pipeline_with_identity():
    """Test [42 |identity] → 42"""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(42),
        operations=[PipeFunc("identity")]
    )

    result = engine.run(pipeline)
    assert result.as_scalar() == Value(42)


def test_pipeline_chaining():
    """Test [2 |double |add ^{n=1} |double] → 10"""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(2),
        operations=[
            PipeFunc("double"),              # 2 * 2 = 4
            PipeFunc("add", args=Structure([
                FieldOp(Number(1), key=String("n"))
            ])),                              # 4 + 1 = 5
            PipeFunc("double"),              # 5 * 2 = 10
        ]
    )

    result = engine.run(pipeline)
    assert result == Value(10)


def test_unseeded_pipeline():
    """Test unseeded pipeline uses $in scope."""
    engine = Engine()

    # Unseeded pipeline with $in scope
    pipeline = Pipeline(
        seed=None,
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline, in_=Value(7))
    assert result == Value(14)


def test_unseeded_pipeline_without_in_scope():
    """Test unseeded pipeline fails without $in scope."""
    engine = Engine()

    # No $in scope set
    pipeline = Pipeline(
        seed=None,
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result.tag and result.tag.name == "fail"


def test_pipeline_with_failing_function():
    """Test pipeline stops on function failure."""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("double"),              # Works: 10
            PipeFunc("nonexistent"),         # Fails
            PipeFunc("double"),              # Should not execute
        ]
    )

    result = engine.run(pipeline)
    assert result.tag and result.tag.name == "fail"


def test_pipeline_with_wrong_input_type():
    """Test pipeline with type error in function."""
    engine = Engine()

    pipeline = Pipeline(
        seed=String("not a number"),
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result.tag and result.tag.name == "fail"


def test_pipeline_unparse():
    """Test pipeline unparsing."""
    # Seeded pipeline
    pipeline1 = Pipeline(
        seed=Number(5),
        operations=[PipeFunc("double"), PipeFunc("identity")]
    )
    assert "5" in pipeline1.unparse()
    assert "|double" in pipeline1.unparse()
    assert "[" in pipeline1.unparse()

    # Unseeded pipeline
    pipeline2 = Pipeline(
        seed=None,
        operations=[PipeFunc("double")]
    )
    unparsed = pipeline2.unparse()
    assert "[" in unparsed
    assert "|double" in unparsed


def test_pipefallback_handles_fail():
    """Test PipeFallback recovers from a failure."""
    from comp.engine.ast import PipeFallback

    engine = Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Something went wrong")

    engine.register_function(PythonFunction("fail_func", fail_func))

    # Pipeline: [5 |fail_func |? 42]
    # Should recover with 42
    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("fail_func"),
            PipeFallback(Number(42))
        ]
    )

    result = engine.run(pipeline)
    assert not engine.is_fail(result), f"Expected recovery, got fail: {result}"
    assert result.as_scalar() == Value(42)


def test_pipefallback_passes_success():
    """Test PipeFallback passes through success values."""
    from comp.engine.ast import PipeFallback

    engine = Engine()

    # Pipeline: [5 |double |? 999]
    # Should pass through 10, not use fallback
    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("double"),
            PipeFallback(Number(999))
        ]
    )

    result = engine.run(pipeline)
    assert result == Value(10), f"Expected 10, got {result}"


def test_pipefallback_fail_in_recovery():
    """Test that if recovery expression fails, pipeline fails."""
    from comp.engine.ast import PipeFallback

    engine = Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Fail!")

    engine.register_function(PythonFunction("fail_func", fail_func))

    # Pipeline: [5 |fail_func |? [1 |fail_func]]
    # First fails, fallback also fails
    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("fail_func"),
            PipeFallback(
                Pipeline(
                    seed=Number(1),
                    operations=[PipeFunc("fail_func")]
                )
            )
        ]
    )

    result = engine.run(pipeline)
    assert engine.is_fail(result), "Expected fail when recovery fails"


def test_pipefallback_chaining():
    """Test multiple fallbacks in a chain."""
    from comp.engine.ast import PipeFallback

    engine = Engine()

    # Create a function that always fails
    def fail_func(engine, input_value, args):
        return engine.fail("Fail!")

    engine.register_function(PythonFunction("fail_func", fail_func))

    # Pipeline: [5 |fail_func |? 10 |double]
    # Recovers to 10, then doubles to 20
    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeFunc("fail_func"),
            PipeFallback(Number(10)),
            PipeFunc("double")
        ]
    )

    result = engine.run(pipeline)
    assert result == Value(20), f"Expected 20, got {result}"


def test_pipestruct_merge():
    """Test PipeStruct struct literal."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [{x=1} |{y=2}] → {y=2}
    pipeline = Pipeline(
        seed=Structure([
            FieldOp(value=Number(1), key=String("x"))
        ]),
        operations=[
            PipeStruct(
                Structure([
                    FieldOp(value=Number(2), key=String("y"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result.data == {Value("y"): Value(2)}


def test_pipestruct_receives_struct():
    """Test PipeStruct gets struct even on scalar input."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [5 |{x=1}] → {x=1}
    pipeline = Pipeline(
        seed=Number(5),
        operations=[
            PipeStruct(
                Structure([
                    FieldOp(value=Number(1), key=String("x"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result == Value({Value("x"): Value(1)})
