import bytearound
from bytearound import check


def function_with_one_line_genexpr(x):
    # this makes CPython emit a nonempty co_lnotab for the generator's code object, even though
    # the code is all on one line
    return all(g(y) for y in x)


# this, on the other hand, generates an empty co_lnotab
def one_line_function(x): pass


def test_genexpr():
    co = function_with_one_line_genexpr.func_code.co_consts[1]
    check(co)
    check(one_line_function)


def function_with_args(*args):
    pass


def function_with_kwargs(**kwargs):
    pass


def function_with_args_and_kwargs(*args, **kwargs):
    pass


def test_unused_starargs():
    check(function_with_args)
    check(function_with_kwargs)
    check(function_with_args_and_kwargs)


def function_that_uses_ints_and_floats():
    return type(1), type(1.0)


def test_equal_but_different():
    check(function_that_uses_ints_and_floats)


def test_myself():
    bytearound.check_recursive(bytearound)
