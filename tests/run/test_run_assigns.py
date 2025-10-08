"""Test assignment operations"""

import pytest
import runtest
import comp


@pytest.fixture
def mixed_data():
    """Mixed data structure."""
    return comp.run.Value({
        "one": 1,
        comp.run.Unnamed(): 2.5,
        2: "two",
        True: 3,
        "tens": [10, 20],
    })


@runtest.params(
    "expr, result",
    new=('''four=4''', '{one=1 2.5 2="two" #true=3 tens={10 20} four=4}'),
    field=('''one="O"''', '{one="O" 2.5 2="two" #true=3 tens={10 20}}'),
    index=('''#2="ii"''', '{one=1 2.5 2="ii" #true=3 tens={10 20}}'),
    branch=('''one={1 1}''', '{one={1 1} 2.5 2="two" #true=3 tens={10 20}}'),
    deep=('''tens.#0="X"''', '{one=1 2.5 2="two" #true=3 tens={"X" 20}}'),
    flat=('''tens=10''', '{one=1 2.5 2="two" #true=3 tens=10}'),
    expr=(''''2'=2''', '{one=1 2.5 2=2 #true=3 tens={10 20}}'),
    tag=(''''#true'=#false''', '{one=1 2.5 2="two" #true=#false tens={10 20}}'),
    make=('''a.b.c="d"''', '{one=1 2.5 2="two" #true=3 tens={10 20} a={b={c="d"}}}'),
    extend=('''#6=6''', None), # no out of range extending
)
def test_assignments(key, expr, result, mixed_data, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(f"{{x.{expr}}}")
    assign = ast.find(comp.ast.StructAssign)
    ident = assign.key
    value = comp.run._eval.evaluate(assign.value, module, scopes)

    func = comp.run._eval.evaluate
    wrapped = {comp.run.Value("x"): mixed_data}
    if result is None:
        with pytest.raises(Exception):
            comp.run._assign.assign_nested_field(ident, value, wrapped, module, scopes, func)
    else:
        comp.run._assign.assign_nested_field(ident, value, wrapped, module, scopes, func)
        rep = repr(mixed_data)
        assert rep == result
