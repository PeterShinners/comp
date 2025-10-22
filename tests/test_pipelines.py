"""Test pipeline execution."""

import comp
import comptest


def test_multi_step_pipeline():
    """Test [3 |double |double] → 12"""
    result = comptest.run_pipe(
        3,
        comp.ast.PipeFunc("double"),
        comp.ast.PipeFunc("double"),
    )
    comptest.assert_value(result, 12)


def test_pipeline_with_function_args():
    """Test [5 |add 3] → 8"""
    result = comptest.run_pipe(
        5,
        comp.ast.PipeFunc("add", args=comp.ast.Structure([
            comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.String("n"))
        ]))
    )
    comptest.assert_value(result, 8)


def test_unseeded_pipeline():
    """Test unseeded pipeline uses $in scope."""
    result = comptest.run_pipe(
        None,
        comp.ast.PipeFunc("double"),
        in_=7
    )
    comptest.assert_value(result, 14)


def test_pipeline_with_failing_function():
    """Test pipeline stops on function failure."""
    result = comptest.run_pipe(
        3,
        comp.ast.PipeFunc("nonexistent"),
        comp.ast.PipeFunc("double"),
    )
    comptest.assert_fail(result, "not found")


def test_pipeline_with_wrong_input_type():
    """Test pipeline with type error in function."""
    result = comptest.run_pipe(
        "not a string",
        comp.ast.PipeFunc("double"),
    )
    comptest.assert_fail(result, "expects num")


def test_pipe_fallback():
    """Test comp.ast.PipeFallback recovers from a failure."""
    def fail_func(engine, input_value, args):
        return comp.fail("Something went wrong")
        yield  # Make it a generator (unreachable)

    result = comptest.run_pipe(
        5,
        comp.ast.PipeFunc("double"),
        comp.ast.PipeFunc("fail_func"),
        comp.ast.PipeFallback(comp.ast.Number(42)),
        comp.ast.PipeFunc("double"),
        func=fail_func,
    )
    comptest.assert_value(result, 84)


def test_pipe_fallback_ignored():
    """Test comp.ast.PipeFallback passes through success values."""
    result = comptest.run_pipe(
        5,
        comp.ast.PipeFunc("double"),
        comp.ast.PipeFallback(comp.ast.Number(999)),
        comp.ast.PipeFunc("double"),
    )
    comptest.assert_value(result, 20)


def test_pipefallback_fail_in_recovery():
    """Test that if recovery expression fails, pipeline fails."""
    def fail_func(engine, input_value, args):
        return comp.fail("Something went wrong")
        yield  # Make it a generator (unreachable)

    # comp.ast.Pipeline: [5 |fail_func |? [1 |fail_func]]
    result = comptest.run_pipe(
        5,
        comp.ast.PipeFunc("fail_func"),
        comp.ast.PipeFallback(
            comp.ast.Pipeline(
                seed=comp.ast.Number(1),
                operations=[comp.ast.PipeFunc("fail_func")],
            ),
        ),
        func=fail_func,
    )
    comptest.assert_fail(result, "Something went wrong")


def test_pipestruct_merge():
    """Test comp.ast.PipeStruct struct literal."""
    result = comptest.run_pipe(
        comp.ast.Structure([
            comp.ast.FieldOp(value=comp.ast.Number(1), key=comp.ast.String("x"))
        ]),
        comp.ast.PipeStruct(
            comp.ast.Structure([
                comp.ast.FieldOp(value=comp.ast.Number(2), key=comp.ast.String("y"))
            ])
        ),
    )
    comptest.assert_value(result, y=2)
    assert len(result.data) == 1


def test_pipestruct_receives_struct():
    """Test comp.ast.PipeStruct gets struct even on scalar input."""
    result = comptest.run_pipe(
        5,
        comp.ast.PipeStruct(
            comp.ast.Structure([
                comp.ast.FieldOp(value=comp.ast.Number(1), key=comp.ast.String("x"))
            ])
        ),
    )
    comptest.assert_value(result, x=1)
    assert len(result.data) == 1

