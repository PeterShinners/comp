"""Test advanced scope behaviors: $out, unnamed, and scope interactions."""

import runtest
import comp.run


def test_out_scope_self_reference():
    """Test that $out allows referencing previously set fields."""
    code = """
    !func |test ~_ = {
        first = 10
        second = $out.first
        third = $out.second
    }
    """
    result = runtest.run_function(code, "test", {})
    
    # All fields should reference the first value
    assert runtest.get_field_python(result, "first") == 10
    assert runtest.get_field_python(result, "second") == 10
    assert runtest.get_field_python(result, "third") == 10


def test_unnamed_scope_from_out():
    """Test that unscoped identifiers read from $out first."""
    code = """
    !func |test ~_ = {
        cat = 100
        dog = cat
        pig = dog
    }
    """
    result = runtest.run_function(code, "test", {})
    
    # dog and pig should reference values from $out (previously set fields)
    assert runtest.get_field_python(result, "cat") == 100
    assert runtest.get_field_python(result, "dog") == 100
    assert runtest.get_field_python(result, "pig") == 100


def test_unnamed_scope_from_in():
    """Test that unscoped identifiers fall back to $in when not in $out."""
    code = """
    !func |test ~_ = {
        dog = cat
        pig = dog
    }
    """
    # Pass cat in the input
    in_val = {"cat": "meow"}
    result = runtest.run_function(code, "test", in_val)
    
    # dog gets cat from $in, pig gets dog from $out
    assert runtest.get_field_python(result, "dog") == "meow"
    assert runtest.get_field_python(result, "pig") == "meow"


def test_all_scopes_together():
    """Test interaction between all scopes: $in, $out, unnamed, $ctx, $mod, $arg, ^, @."""
    code = """
    !func |test ~_ = {
        @temp = 999
        first = $in.input_val
        second = first
        third = $ctx.context_val
        fourth = $mod.module_val
        fifth = $arg.argument_val
        sixth = ^combined
        seventh = @temp
        eighth = second
    }
    """
    in_val = {"input_val": 100}
    ctx_val = {"context_val": 200}
    mod_val = {"module_val": 300}
    arg_val = {"argument_val": 400, "combined": 500}
    
    result = runtest.run_function(code, "test", in_val, ctx_val, mod_val, arg_val)
    
    assert runtest.get_field_python(result, "first") == 100   # From $in
    assert runtest.get_field_python(result, "second") == 100  # From unnamed->$out (first)
    assert runtest.get_field_python(result, "third") == 200   # From $ctx
    assert runtest.get_field_python(result, "fourth") == 300  # From $mod
    assert runtest.get_field_python(result, "fifth") == 400   # From $arg
    assert runtest.get_field_python(result, "sixth") == 500   # From ^ ($arg overrides)
    assert runtest.get_field_python(result, "seventh") == 999 # From @ (local)
    assert runtest.get_field_python(result, "eighth") == 100  # From unnamed->$out (second)


def test_chained_scope_priority():
    """Test that ^ has proper priority and unnamed scope is independent."""
    code = """
    !func |test ~_ = {
        value = 10
        from_unnamed = value
        from_chained = ^value
    }
    """
    # Set value in all scopes to see priority
    in_val = {"value": 1}
    ctx_val = {"value": 2}
    mod_val = {"value": 3}
    arg_val = {"value": 4}
    
    result = runtest.run_function(code, "test", in_val, ctx_val, mod_val, arg_val)
    
    assert runtest.get_field_python(result, "value") == 10        # Set in $out
    assert runtest.get_field_python(result, "from_unnamed") == 10  # Gets from $out (priority)
    assert runtest.get_field_python(result, "from_chained") == 4   # Gets from $arg via ^


def test_out_scope_updates_incrementally():
    """Test that $out updates as fields are assigned."""
    code = """
    !func |test ~_ = {
        a = 1
        b = $out.a + 10
        c = $out.b + 100
    }
    """
    result = runtest.run_function(code, "test", {})
    
    assert runtest.get_field_python(result, "a") == 1
    assert runtest.get_field_python(result, "b") == 11
    assert runtest.get_field_python(result, "c") == 111


def test_local_scope_isolation():
    """Test that @ (local) scope is isolated from other scopes."""
    code = """
    !func |test ~_ = {
        @private = "secret"
        public = "visible"
        result = @private
    }
    """
    result = runtest.run_function(code, "test", {})
    
    # @private should not appear in output (not in $out)
    assert comp.run.Value("private") not in result.struct
    assert runtest.get_field_python(result, "public") == "visible"
    assert runtest.get_field_python(result, "result") == "secret"
