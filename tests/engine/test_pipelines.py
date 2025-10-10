"""Test pipeline execution."""

from comp.engine.ast import FieldOp, Number, PipeFunc, Pipeline, String, Structure
from comp.engine.engine import Engine
from comp.engine.function import PythonFunction
from comp.engine.value import Value


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
    print("✓ Simple seeded pipeline works")


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
    print("✓ Multi-step pipeline works")


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
    print("✓ Pipeline with function args works")


def test_pipeline_with_identity():
    """Test [42 |identity] → 42"""
    engine = Engine()

    pipeline = Pipeline(
        seed=Number(42),
        operations=[PipeFunc("identity")]
    )

    result = engine.run(pipeline)
    assert result == Value(42)
    print("✓ Pipeline with identity works")


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
    print("✓ Complex pipeline chaining works")


def test_unseeded_pipeline():
    """Test unseeded pipeline uses $in scope."""
    engine = Engine()

    # Set up $in scope
    engine.set_scope('in', Value(7))

    # Unseeded pipeline
    pipeline = Pipeline(
        seed=None,
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result == Value(14)
    print("✓ Unseeded pipeline works")


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
    print("✓ Unseeded pipeline without $in fails correctly")


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
    print("✓ Pipeline stops on function failure")


def test_pipeline_with_wrong_input_type():
    """Test pipeline with type error in function."""
    engine = Engine()

    pipeline = Pipeline(
        seed=String("not a number"),
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result.tag and result.tag.name == "fail"
    print("✓ Pipeline handles function type errors")


def test_pipeline_preserves_in_scope():
    """Test pipeline creates new scope frames."""
    engine = Engine()

    # Set initial $in
    engine.set_scope('in', Value(100))

    # Run seeded pipeline (should not affect outer $in)
    pipeline = Pipeline(
        seed=Number(5),
        operations=[PipeFunc("double")]
    )

    result = engine.run(pipeline)
    assert result == Value(10)

    # Original $in should be unchanged
    assert engine.get_scope('in') == Value(100)
    print("✓ Pipeline preserves outer $in scope")


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

    print("✓ Pipeline unparse works")


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
    assert result == Value(42)

    print("✓ PipeFallback handles fail")


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

    print("✓ PipeFallback passes success")


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

    print("✓ PipeFallback fail in recovery")


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

    print("✓ PipeFallback chaining")


def test_pipestruct_merge():
    """Test PipeStruct merges structures."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [{x=1} |{y=2}] → {x=1 y=2}
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
    assert result.data == {Value("x"): Value(1), Value("y"): Value(2)}

    print("✓ PipeStruct merge")


def test_pipestruct_override():
    """Test PipeStruct overrides existing fields."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [{a=1 b=2} |{b=3}] → {a=1 b=3}
    pipeline = Pipeline(
        seed=Structure([
            FieldOp(value=Number(1), key=String("a")),
            FieldOp(value=Number(2), key=String("b"))
        ]),
        operations=[
            PipeStruct(
                Structure([
                    FieldOp(value=Number(3), key=String("b"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result.data == {Value("a"): Value(1), Value("b"): Value(3)}

    print("✓ PipeStruct override")


def test_pipestruct_chain():
    """Test chaining multiple PipeStruct operations."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [{x=1} |{y=2} |{z=3}] → {x=1 y=2 z=3}
    pipeline = Pipeline(
        seed=Structure([
            FieldOp(value=Number(1), key=String("x"))
        ]),
        operations=[
            PipeStruct(
                Structure([
                    FieldOp(value=Number(2), key=String("y"))
                ])
            ),
            PipeStruct(
                Structure([
                    FieldOp(value=Number(3), key=String("z"))
                ])
            )
        ]
    )

    result = engine.run(pipeline)
    assert result.data == {Value("x"): Value(1), Value("y"): Value(2), Value("z"): Value(3)}

    print("✓ PipeStruct chain")


def test_pipestruct_requires_struct():
    """Test PipeStruct fails on non-struct input."""
    from comp.engine.ast import PipeStruct

    engine = Engine()

    # Pipeline: [5 |{x=1}] → fail
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
    assert engine.is_fail(result)
    assert "requires struct input" in result.data

    print("✓ PipeStruct requires struct")


if __name__ == "__main__":
    test_simple_seeded_pipeline()
    test_multi_step_pipeline()
    test_pipeline_with_function_args()
    test_pipeline_with_identity()
    test_pipeline_chaining()
    test_unseeded_pipeline()
    test_unseeded_pipeline_without_in_scope()
    test_pipeline_with_failing_function()
    test_pipeline_with_wrong_input_type()
    test_pipeline_preserves_in_scope()
    test_pipeline_unparse()
    test_pipefallback_handles_fail()
    test_pipefallback_passes_success()
    test_pipefallback_fail_in_recovery()
    test_pipefallback_chaining()
    test_pipestruct_merge()
    test_pipestruct_override()
    test_pipestruct_chain()
    test_pipestruct_requires_struct()
    print("\n✅ All pipeline tests passed!")
