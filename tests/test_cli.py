"""Test the CLI command-line interface."""

import subprocess
import sys
from pathlib import Path


def test_cli_hello_example():
    """Test running the hello.comp example."""
    # Get the path to hello.comp
    example_path = Path(__file__).parent.parent / "examples" / "working" / "hello.comp"
    
    # Run the CLI
    result = subprocess.run(
        [sys.executable, "-m", "comp.cli", str(example_path)],
        capture_output=True,
        text=True
    )
    
    # Should succeed
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    
    # Should output the result structure
    assert "HELLO FROM COMP!" in result.stdout


def test_cli_greet_example():
    """Test running the greet.comp example."""
    example_path = Path(__file__).parent.parent / "examples" / "working" / "greet.comp"
    
    result = subprocess.run(
        [sys.executable, "-m", "comp.cli", str(example_path)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "HELLO, WORLD!" in result.stdout
    assert "HELLO, COMP!" in result.stdout


def test_cli_pipeline_example():
    """Test running the pipeline.comp example."""
    example_path = Path(__file__).parent.parent / "examples" / "working" / "pipeline.comp"
    
    result = subprocess.run(
        [sys.executable, "-m", "comp.cli", str(example_path)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    # Pipeline: 5 -> double (10) -> add-ten (20) -> double (40)
    assert "final" in result.stdout


def test_cli_no_args():
    """Test CLI with no arguments shows usage."""
    result = subprocess.run(
        [sys.executable, "-m", "comp.cli"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 1
    assert "Usage:" in result.stderr


def test_cli_file_not_found():
    """Test CLI with non-existent file."""
    result = subprocess.run(
        [sys.executable, "-m", "comp.cli", "nonexistent.comp"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


def test_cli_no_main_function():
    """Test CLI with file that has no main function."""
    # Create a temporary file without main
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.comp', delete=False) as f:
        f.write("!func |test ~_ = { x = 5 }\n")
        temp_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "comp.cli", temp_path],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "main" in result.stderr.lower()
    finally:
        Path(temp_path).unlink()


def test_cli_parse_error():
    """Test CLI with invalid syntax."""
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.comp', delete=False) as f:
        f.write("this is not valid comp syntax @#$%\n")
        temp_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "comp.cli", temp_path],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "error" in result.stderr.lower()
    finally:
        Path(temp_path).unlink()
